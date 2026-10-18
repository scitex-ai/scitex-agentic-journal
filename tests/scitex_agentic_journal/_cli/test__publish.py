"""Tests for the live `publish` command on the top-level CLI.

Drives `scitex-agentic-journal publish` via Click's `CliRunner` against
a real on-disk submission shape materialised under a tmp_path
`SCITEX_AGENTIC_JOURNAL_HOME`. No mocks. The full pipeline runs:
load_submission_records → LivePaperProxy → LocalFilesystemLivePaperPort.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli_main

SUBMISSION_ID = "sub_2026_06_13_abc123"


def _materialise(
    home: Path,
    *,
    verdict: str = "accept",
    persistent_id: str = "scitex-aj-20260613-test-abcdef",
    skip_persistent_id: bool = False,
) -> Path:
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = home / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (submission_dir / "gate1.json").write_text(
        json.dumps(
            {
                "submission_id": SUBMISSION_ID,
                "gate": "gate1",
                "verdict": "pass",
                "submission": {
                    "bundle_dir": str(bundle_dir),
                    "orcid_id": "0000-0002-1825-0097",
                    "code_repo_url": "https://example.com/r.git",
                    "clew_project_dir": str(bundle_dir),
                },
                "clew_verification": {
                    "project_dir": str(bundle_dir),
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
                "code_repo": {
                    "head_commit": "abc123",
                    "head_subject": "init",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (submission_dir / "review.json").write_text(
        json.dumps(
            {
                "submission_id": SUBMISSION_ID,
                "content_hash": "sha256:" + "a" * 64,
                "written_at_utc": "2026-06-13T12:00:00+00:00",
                "record": {"submission_id": SUBMISSION_ID},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (submission_dir / "decision.json").write_text(
        json.dumps(
            {
                "submission_id": SUBMISSION_ID,
                "verdict": verdict,
                "content_hash": "sha256:" + "b" * 64,
                "written_at_utc": "2026-06-13T12:30:00+00:00",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if not skip_persistent_id:
        (submission_dir / "persistent_id.json").write_text(
            json.dumps(
                {
                    "submission_id": SUBMISSION_ID,
                    "persistent_id": persistent_id,
                    "backend": "internal",
                    "minted_at_utc": "2026-06-13T13:00:00+00:00",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return submission_dir


@pytest.fixture
def home_ready_to_publish(tmp_path: Path):
    """Materialise a fully accepted submission and point env at it.

    Yield-teardown fixture (NM002-compliant) — no `monkeypatch`.
    """
    home = tmp_path / "home"
    _materialise(home)
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(home)
    try:
        yield home
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original


# ----- --help -------------------------------------------------------------


def test_publish_help_exits_zero() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", "--help"])
    # Assert
    assert result.exit_code == 0, result.output


def test_publish_help_mentions_dry_run_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", "--help"])
    # Assert
    assert "--dry-run" in result.output


def test_publish_help_mentions_yes_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", "--help"])
    # Assert
    assert "--yes" in result.output


def test_publish_help_mentions_port_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", "--help"])
    # Assert
    assert "--port" in result.output


# ----- --dry-run ----------------------------------------------------------


def test_publish_dry_run_exits_zero(home_ready_to_publish: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main, ["publish", SUBMISSION_ID, "--dry-run"]
    )
    # Assert
    assert result.exit_code == 0, result.output


def test_publish_dry_run_emits_dry_run_marker(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main, ["publish", SUBMISSION_ID, "--dry-run"]
    )
    # Assert
    assert "DRY-RUN publish" in result.output


def test_publish_dry_run_does_not_write_bundle_json(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    bundle_path = (
        home_ready_to_publish / "published" / SUBMISSION_ID / "bundle.json"
    )
    # Act
    runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--dry-run"])
    # Assert
    assert not bundle_path.exists()


# ----- real publish against local-filesystem port -------------------------


def test_publish_real_exits_zero_against_accepted_submission(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--yes"])
    # Assert
    assert result.exit_code == 0, result.output


def test_publish_real_emits_published_marker(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--yes"])
    # Assert
    assert "PUBLISHED" in result.output


def test_publish_real_emits_persistent_id_in_output(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--yes"])
    # Assert
    assert "persistent_id=scitex-aj-20260613-test-abcdef" in result.output


def test_publish_real_writes_bundle_json_under_published(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    bundle_path = (
        home_ready_to_publish / "published" / SUBMISSION_ID / "bundle.json"
    )
    # Act
    runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--yes"])
    # Assert
    assert bundle_path.is_file()


def test_publish_real_emits_viewer_url_file_uri(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--yes"])
    # Assert
    assert "viewer_url=file://" in result.output


# ----- error paths --------------------------------------------------------


def test_publish_exits_nonzero_for_unknown_submission(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path / "empty-home")
    try:
        # Act
        result = runner.invoke(
            cli_main, ["publish", "sub_2026_06_13_unknown", "--yes"]
        )
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert result.exit_code != 0


def test_publish_exits_nonzero_when_decision_verdict_is_not_accept(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    home = tmp_path / "home"
    _materialise(home, verdict="revise")
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(home)
    try:
        # Act
        result = runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--yes"])
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert result.exit_code != 0


def test_publish_exits_nonzero_with_remote_stub_port(
    home_ready_to_publish: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main,
        ["publish", SUBMISSION_ID, "--yes", "--port", "remote-stub"],
    )
    # Assert
    assert result.exit_code != 0


def test_publish_exits_nonzero_when_persistent_id_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    home = tmp_path / "home"
    _materialise(home, skip_persistent_id=True)
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(home)
    try:
        # Act
        result = runner.invoke(cli_main, ["publish", SUBMISSION_ID, "--yes"])
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert result.exit_code != 0
