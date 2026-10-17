"""Tests for `_submit/_orchestrate.py` — sequential Gate-1 driver.

Mostly hermetic. The ORCID sub-check rejects malformed ids
*before* any HTTP, so we can verify the failure-wrapping shape
without network. One opt-in real end-to-end test exercises the
full M1.1 + M1.2 + M1.3 happy path against `pub.orcid.org`,
`github.com/octocat/Hello-World`, and a real clew-registered project —
gated on `SCITEX_RUN_NETWORK_TESTS=1`, `SCITEX_RUN_CLEW_TESTS=1`, and
`SCITEX_RUN_CLEW_STORE_TESTS=1` (a provisioned clew store).
No mocks anywhere.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from scitex_agentic_journal._submit import (
    Gate1Failure,
    Gate1Verdict,
    Submission,
    run_gate1,
)


def _submission(
    bundle: Path,
    *,
    orcid_id: str = "0000-0002-1825-0097",
    code_repo_url: str = "https://github.com/octocat/Hello-World.git",
    clew_project_dir: Path | None = None,
) -> Submission:
    return Submission(
        bundle_dir=bundle,
        orcid_id=orcid_id,
        code_repo_url=code_repo_url,
        clew_project_dir=clew_project_dir if clew_project_dir is not None else bundle,
    )


# ---------------------------------------------------------------------------
# Hermetic — ORCID malformed-id rejection happens pre-network.
# ---------------------------------------------------------------------------


def test_run_gate1_raises_gate1_failure_when_orcid_is_malformed(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    submission = _submission(bundle, orcid_id="not-an-orcid-id")
    # Act
    ctx = pytest.raises(Gate1Failure)
    # Assert
    with ctx:
        run_gate1(submission)


def test_run_gate1_failure_check_is_orcid_when_orcid_is_malformed(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    submission = _submission(bundle, orcid_id="not-an-orcid-id")
    # Act
    captured: Gate1Failure | None = None
    try:
        run_gate1(submission)
    except Gate1Failure as f:
        captured = f
    # Assert
    assert captured is not None and captured.check == "orcid"


def test_run_gate1_failure_message_renders_canonical_gate_1_fail_line(
    tmp_path: Path,
) -> None:
    """`GateFailure.__str__` produces `GATE-1 FAIL [<check>]: <reason>`;
    the wrapping `Gate1Failure` must surface the same shape so the CLI
    can print one structured line without re-formatting.
    """
    # Arrange
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    submission = _submission(bundle, orcid_id="not-an-orcid-id")
    # Act
    captured: Gate1Failure | None = None
    try:
        run_gate1(submission)
    except Gate1Failure as f:
        captured = f
    # Assert
    assert captured is not None and str(captured.wrapped).startswith(
        "GATE-1 FAIL [orcid]"
    )


# ---------------------------------------------------------------------------
# Opt-in real end-to-end — exercises every layer against the real world.
# ---------------------------------------------------------------------------


@pytest.fixture
def real_clew_bundle(tmp_path: Path) -> Path:
    """Register a real bundle so the M1.3 step has work to do.

    Skips the dependent test when network + clew + git are not all
    present. We need ALL of: `SCITEX_RUN_NETWORK_TESTS=1` (for the
    ORCID and code-repo HTTP), `SCITEX_RUN_CLEW_TESTS=1` (for the
    real clew subprocess), `SCITEX_RUN_CLEW_STORE_TESTS=1` (a
    provisioned PostgreSQL clew store — verification needs it),
    `clew` on PATH, and `git` on PATH.
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
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "paper.tex").write_text("The answer is 42\n", encoding="utf-8")
    (bundle / "make_result.py").write_text(
        "import scitex_clew as clew\n"
        'with clew.session(script_path="make_result.py") as run:\n'
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
            "--line-number",
            "1",
        ],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    return bundle


def test_run_gate1_returns_gate1_verdict_for_real_passing_bundle(
    real_clew_bundle: Path,
) -> None:
    """Real ORCID + real GitHub clone + real `clew dag --claims`."""
    # Arrange
    submission = _submission(real_clew_bundle)
    # Act
    verdict = run_gate1(submission)
    # Assert
    assert isinstance(verdict, Gate1Verdict)
