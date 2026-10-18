"""Tests for the live `review` command on the top-level CLI.

Drives `scitex-agentic-journal review` via Click's `CliRunner`
against a real on-disk `gate1.json` materialised under a `tmp_path`
SCITEX_AGENTIC_JOURNAL_HOME. No mocks. The full pipeline runs:
load gate1.json → select_adapter → ReviewRunner → persist review.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli_main


@pytest.fixture
def home_with_gate1(tmp_path: Path):
    """Materialise a real gate1.json and point the env at it.

    Yield-teardown fixture (NM002-compliant) — no `monkeypatch`.
    """
    home = tmp_path / "home"
    sub = home / "submissions" / "sub_2026_06_13_abc123"
    sub.mkdir(parents=True)
    payload = {
        "submission_id": "sub_2026_06_13_abc123",
        "gate": "gate1",
        "verdict": "pass",
        "submission": {
            "bundle_dir": str(home / "bundle"),
            "orcid_id": "0000-0002-1825-0097",
            "code_repo_url": "https://github.com/octocat/Hello-World.git",
            "clew_project_dir": str(home / "bundle"),
        },
        "clew_verification": {
            "project_dir": str(home / "bundle"),
            "green_claims": ["c1"],
            "red_claims": [],
            "total_claims": 1,
        },
        "orcid_record": {
            "orcid_id": "0000-0002-1825-0097",
            "given_name": "Test",
            "family_name": "Author",
            "credit_name": None,
        },
        "code_repo": {"head_commit": "abc123", "head_subject": "init"},
    }
    (sub / "gate1.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(home)
    try:
        yield home
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original


def test_review_exits_zero_against_gate1_record_with_local_adapter(
    home_with_gate1: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main, ["review", "sub_2026_06_13_abc123", "--adapter", "local"]
    )
    # Assert
    assert result.exit_code == 0, result.output


def test_review_emits_review_done_marker_on_success(home_with_gate1: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main, ["review", "sub_2026_06_13_abc123", "--adapter", "local"]
    )
    # Assert
    assert "REVIEW DONE" in result.output


def test_review_emits_canonical_content_hash_in_output(home_with_gate1: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main, ["review", "sub_2026_06_13_abc123", "--adapter", "local"]
    )
    # Assert
    assert "content_hash=sha256:" in result.output


def test_review_writes_review_json_next_to_gate1_json(
    home_with_gate1: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    review_path = (
        home_with_gate1 / "submissions" / "sub_2026_06_13_abc123" / "review.json"
    )
    # Act
    runner.invoke(
        cli_main, ["review", "sub_2026_06_13_abc123", "--adapter", "local"]
    )
    # Assert
    assert review_path.is_file()


def test_review_exits_nonzero_for_unknown_adapter_name(
    home_with_gate1: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main,
        ["review", "sub_2026_06_13_abc123", "--adapter", "no-such-provider"],
    )
    # Assert
    assert result.exit_code != 0


def test_review_exits_nonzero_when_submission_id_has_no_persisted_gate1(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path / "empty-home")
    try:
        # Act
        result = runner.invoke(
            cli_main,
            ["review", "sub_2026_06_13_unknown", "--adapter", "local"],
        )
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert result.exit_code != 0


def test_review_exits_nonzero_for_qwen_stub_until_endpoint_is_wired(
    home_with_gate1: Path,
) -> None:
    """`QwenAdapterStub.run_sub_report` raises NotImplementedError;
    the CLI must surface that as a clean ClickException instead of a
    Python traceback.
    """
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main, ["review", "sub_2026_06_13_abc123", "--adapter", "qwen"]
    )
    # Assert
    assert result.exit_code != 0
