"""Tests for `_decide/_load_review.py` — strict review.json reader."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scitex_agentic_journal._decide import (
    DecisionLoadError,
    load_review_record,
)
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


def _materialise_review(
    home: Path,
    submission_id: str = "sub_2026_06_13_abc123",
    *,
    novelty_overlap: float = 0.1,
    methodology: MethodologyReport | None = None,
    red_claims: tuple[str, ...] = (),
) -> ReviewRecord:
    record = ReviewRecord(
        submission_id=submission_id,
        adapter="local-deterministic",
        adapter_version="0.1.0",
        prompts_version="v1",
        rubric_version=ARA_RUBRIC_VERSION,
        reproducibility=ReproducibilityReport(
            passed=True, sandbox_image="local", notes="ok"
        ),
        claim_verify=ClaimVerifyReport(
            green_claim_ids=("c1",),
            red_claim_ids=red_claims,
        ),
        novelty=NoveltyReport(
            overlap_score=novelty_overlap,
            nearest_neighbour_dois=("10.1/a",),
        ),
        methodology=methodology
        or MethodologyReport(
            criticisms=(
                Criticism(severity=Severity.MINOR, section="§1", note="typo"),
            ),
        ),
        started_at=_FIXED_TIME,
        finished_at=_FIXED_TIME,
    )
    persist_review(record, home=home, now=_FIXED_TIME)
    return record


def test_load_review_record_returns_review_record_instance(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_review(home)
    # Act
    loaded = load_review_record("sub_2026_06_13_abc123", home=home)
    # Assert
    assert isinstance(loaded, ReviewRecord)


def test_load_review_record_threads_submission_id_through(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_review(home, "sub_2026_06_13_deadbe")
    # Act
    loaded = load_review_record("sub_2026_06_13_deadbe", home=home)
    # Assert
    assert loaded.submission_id == "sub_2026_06_13_deadbe"


def test_load_review_record_round_trips_novelty_overlap_score(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_review(home, novelty_overlap=0.42)
    # Act
    loaded = load_review_record("sub_2026_06_13_abc123", home=home)
    # Assert
    assert loaded.novelty.overlap_score == 0.42


def test_load_review_record_round_trips_methodology_criticism(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_review(
        home,
        methodology=MethodologyReport(
            criticisms=(
                Criticism(severity=Severity.MAJOR, section="§3", note="control"),
            ),
        ),
    )
    # Act
    loaded = load_review_record("sub_2026_06_13_abc123", home=home)
    # Assert
    assert loaded.methodology.max_severity is Severity.MAJOR


def test_load_review_record_round_trips_red_claims(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_review(home, red_claims=("c9",))
    # Act
    loaded = load_review_record("sub_2026_06_13_abc123", home=home)
    # Assert
    assert loaded.claim_verify.red_claim_ids == ("c9",)


def test_load_review_record_raises_when_submission_dir_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    # Act
    ctx = pytest.raises(DecisionLoadError, match="no persisted submission")
    # Assert
    with ctx:
        load_review_record("sub_2026_06_13_unknown", home=home)


def test_load_review_record_raises_when_review_json_missing(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    (home / "submissions" / "sub_2026_06_13_abc123").mkdir(parents=True)
    # Act
    ctx = pytest.raises(DecisionLoadError, match="missing its review.json")
    # Assert
    with ctx:
        load_review_record("sub_2026_06_13_abc123", home=home)


def test_load_review_record_raises_on_invalid_json(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    sub = home / "submissions" / "sub_2026_06_13_abc123"
    sub.mkdir(parents=True)
    (sub / "review.json").write_text("{not-json", encoding="utf-8")
    # Act
    ctx = pytest.raises(DecisionLoadError, match="not valid JSON")
    # Assert
    with ctx:
        load_review_record("sub_2026_06_13_abc123", home=home)
