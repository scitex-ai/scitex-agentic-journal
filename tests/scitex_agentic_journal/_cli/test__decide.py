"""Tests for the live `decide` command on the top-level CLI.

Drives `scitex-agentic-journal decide` via Click's `CliRunner`
against a real on-disk `review.json` materialised under a `tmp_path`
SCITEX_AGENTIC_JOURNAL_HOME. No mocks. The full pipeline runs:
load review.json → DecisionEngine → persist decision.json.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli_main
from scitex_agentic_journal._review import (
    ARA_RUBRIC_VERSION,
    ClaimVerifyReport,
    Criticism,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewRecord,
    Severity,
    persist_review,
)

_FIXED_TIME = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)  # stx-allow: STX-NL001


def _make_review(
    *,
    methodology: MethodologyReport | None = None,
    reproducibility: ReproducibilityReport | None = None,
) -> ReviewRecord:
    return ReviewRecord(
        submission_id="sub_2026_06_13_abc123",
        adapter="local-deterministic",
        adapter_version="0.1.0",
        prompts_version="v1",
        rubric_version=ARA_RUBRIC_VERSION,
        reproducibility=reproducibility
        or ReproducibilityReport(passed=True, sandbox_image="local"),
        claim_verify=ClaimVerifyReport(green_claim_ids=("c1",)),
        novelty=NoveltyReport(overlap_score=0.0),
        methodology=methodology or MethodologyReport(criticisms=()),
        started_at=_FIXED_TIME,
        finished_at=_FIXED_TIME,
    )


@pytest.fixture
def home_with_review(tmp_path: Path):
    """Materialise a real review.json and point the env at it."""
    home = tmp_path / "home"
    persist_review(_make_review(), home=home, now=_FIXED_TIME)
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(home)
    try:
        yield home
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original


def test_decide_exits_zero_against_review_record(home_with_review: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["decide", "sub_2026_06_13_abc123"])
    # Assert
    assert result.exit_code == 0, result.output


def test_decide_emits_decision_marker_on_success(home_with_review: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["decide", "sub_2026_06_13_abc123"])
    # Assert
    assert "DECISION" in result.output


def test_decide_emits_verdict_in_output(home_with_review: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["decide", "sub_2026_06_13_abc123"])
    # Assert
    assert "verdict=accept" in result.output


def test_decide_emits_rules_version_in_output(home_with_review: Path) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["decide", "sub_2026_06_13_abc123"])
    # Assert
    assert "rules_version=v1" in result.output


def test_decide_emits_canonical_content_hash_in_output(
    home_with_review: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["decide", "sub_2026_06_13_abc123"])
    # Assert
    assert "content_hash=sha256:" in result.output


def test_decide_writes_decision_json_next_to_review_json(
    home_with_review: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    decision_path = (
        home_with_review
        / "submissions"
        / "sub_2026_06_13_abc123"
        / "decision.json"
    )
    # Act
    runner.invoke(cli_main, ["decide", "sub_2026_06_13_abc123"])
    # Assert
    assert decision_path.is_file()


def test_decide_exits_nonzero_when_submission_id_has_no_persisted_review(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path / "empty-home")
    try:
        # Act
        result = runner.invoke(
            cli_main, ["decide", "sub_2026_06_13_unknown"]
        )
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert result.exit_code != 0


def test_decide_does_not_dump_python_traceback_on_load_error(
    tmp_path: Path,
) -> None:
    """ClickException → single structured line, no traceback."""
    # Arrange
    runner = CliRunner()
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path / "empty-home")
    try:
        # Act
        result = runner.invoke(
            cli_main, ["decide", "sub_2026_06_13_unknown"]
        )
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert "Traceback" not in result.output


def test_decide_reject_verdict_on_fatal_methodology(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    persist_review(
        _make_review(
            methodology=MethodologyReport(
                criticisms=(
                    Criticism(
                        severity=Severity.FATAL, section="§3", note="bad"
                    ),
                ),
            ),
        ),
        home=home,
        now=_FIXED_TIME,
    )
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(home)
    runner = CliRunner()
    try:
        # Act
        result = runner.invoke(cli_main, ["decide", "sub_2026_06_13_abc123"])
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert "verdict=reject" in result.output


def test_decide_help_renders_cleanly() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["decide", "--help"])
    # Assert
    assert result.exit_code == 0
