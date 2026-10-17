"""Tests for the live `submit` command on the top-level CLI.

Mostly hermetic — exercises the loader + Gate1Failure-wrapping paths
that fail before any network IO. One opt-in test drives the real
end-to-end against pub.orcid.org + GitHub + a real clew-registered
bundle (needs a provisioned clew store).
"""

from __future__ import annotations

import os
import secrets
import shutil
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli_main
from scitex_agentic_journal._submit._loader import MANIFEST_FILENAME


def _write_bundle(
    bundle: Path,
    *,
    orcid_id: str = "0000-0002-1825-0097",
    code_repo_url: str = "https://github.com/octocat/Hello-World.git",
) -> Path:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / MANIFEST_FILENAME).write_text(
        f"orcid_id: {orcid_id}\ncode_repo_url: {code_repo_url}\n",
        encoding="utf-8",
    )
    return bundle


def test_submit_exits_nonzero_when_bundle_dir_does_not_exist(tmp_path: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["submit", str(tmp_path / "no-such-bundle")])
    # Assert
    assert result.exit_code != 0


def test_submit_exits_nonzero_when_bundle_manifest_is_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    # Act
    result = runner.invoke(cli_main, ["submit", str(bundle)])
    # Assert
    assert result.exit_code != 0


def test_submit_exits_nonzero_when_orcid_id_is_malformed(tmp_path: Path) -> None:
    # Arrange
    runner = CliRunner()
    bundle = _write_bundle(tmp_path / "bundle", orcid_id="not-an-orcid-id")
    # Act
    result = runner.invoke(cli_main, ["submit", str(bundle)])
    # Assert
    assert result.exit_code != 0


def test_submit_emits_gate_1_fail_line_when_orcid_id_is_malformed(
    tmp_path: Path,
) -> None:
    """The CLI must surface `GATE-1 FAIL [<check>]: <reason>` without
    a Python traceback so operators see one structured line.
    """
    # Arrange
    runner = CliRunner()
    bundle = _write_bundle(tmp_path / "bundle", orcid_id="not-an-orcid-id")
    # Act
    result = runner.invoke(cli_main, ["submit", str(bundle)])
    # Assert
    assert "GATE-1 FAIL [orcid]" in result.output


@pytest.fixture
def real_passing_bundle(tmp_path: Path, monkeypatch_home) -> Path:
    """Real ORCID + GitHub clone + real clew DAG — gated on opt-in env.

    Needs ``SCITEX_RUN_NETWORK_TESTS=1`` (ORCID + code-repo HTTP),
    ``SCITEX_RUN_CLEW_TESTS=1`` (real clew subprocess) AND
    ``SCITEX_RUN_CLEW_STORE_TESTS=1`` (a provisioned PostgreSQL clew
    store — claim registration needs it).
    """
    if os.environ.get("SCITEX_RUN_NETWORK_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_NETWORK_TESTS=1")
    if os.environ.get("SCITEX_RUN_CLEW_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_CLEW_TESTS=1")
    if os.environ.get("SCITEX_RUN_CLEW_STORE_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_CLEW_STORE_TESTS=1")
    if shutil.which("clew") is None:
        pytest.skip("`clew` binary not on PATH")
    if shutil.which("git") is None:
        pytest.skip("`git` not on PATH")
    try:
        import scitex_clew  # noqa: F401
    except ImportError:
        pytest.skip("scitex_clew python package not importable")
    bundle = _write_bundle(tmp_path / "bundle")
    run_id = f"ajfx-{secrets.token_hex(4)}"
    claim_id = f"ajfx-green-{secrets.token_hex(4)}"
    (bundle / "paper.tex").write_text("The answer is 42\n", encoding="utf-8")
    (bundle / "make_result.py").write_text(
        "import scitex_clew as clew\n"
        f'with clew.session(script_path="make_result.py", session_id={run_id!r}) as run:\n'
        '    run.record_input("paper.tex")\n'
        '    with open("result.txt", "w") as fh:\n'
        '        fh.write("value = 42\\n")\n'
        '    run.record_output("result.txt")\n',
        encoding="utf-8",
    )
    import subprocess as _sp

    _sp.run(
        [sys.executable, "make_result.py"],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    _sp.run(
        ["clew", "register-source", "result.txt"],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    _sp.run(
        [
            "clew",
            "claim",
            "add",
            "--file-path",
            "paper.tex",
            "--type",
            "value",
            "--value",
            "42",
            "--source-file",
            "result.txt",
            "--source-session",
            run_id,
            "--claim-id",
            claim_id,
            "--line-number",
            "1",
        ],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    # Seed validation (not the gate): per-claim verify must already be
    # green here — see provisioned_clew_bundle for why this is
    # validation, not answer injection.
    _sp.run(
        ["clew", "claim", "verify", claim_id],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    return bundle


@pytest.fixture
def monkeypatch_home(tmp_path: Path):
    """Real env-var swap (NM002-compliant) — point persist at tmp."""
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path / "home")
    try:
        yield tmp_path / "home"
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original


def test_submit_emits_gate_1_pass_line_for_real_passing_bundle(
    real_passing_bundle: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["submit", str(real_passing_bundle)])
    # Assert
    assert "GATE-1 PASS submission_id=sub_" in result.output
