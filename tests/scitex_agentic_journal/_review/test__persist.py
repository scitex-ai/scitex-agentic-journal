"""Tests for `_review/_persist.py` — review.json writer + content_hash."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._review import (
    ARA_RUBRIC_VERSION,
    ClaimVerifyReport,
    LocalDeterministicAdapter,
    MethodologyReport,
    NoveltyReport,
    PersistedReview,
    ReproducibilityReport,
    ReviewRecord,
    persist_review,
)
from scitex_agentic_journal._review._persist import REVIEW_RECORD_FILENAME

_FIXED_TIME = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)  # stx-allow: STX-NL001


def _record(submission_id: str = "sub_2026_06_13_abc123") -> ReviewRecord:
    return ReviewRecord(
        submission_id=submission_id,
        adapter=LocalDeterministicAdapter.adapter_name,
        adapter_version=LocalDeterministicAdapter.adapter_version,
        prompts_version="v1",
        rubric_version=ARA_RUBRIC_VERSION,
        reproducibility=ReproducibilityReport(passed=True, sandbox_image="local"),
        claim_verify=ClaimVerifyReport(green_claim_ids=("c1",)),
        novelty=NoveltyReport(overlap_score=0.0),
        methodology=MethodologyReport(criticisms=()),
        started_at=_FIXED_TIME,
        finished_at=_FIXED_TIME,
    )


def test_persist_review_returns_persisted_review_instance(tmp_path: Path) -> None:
    # Arrange
    record = _record()
    # Act
    persisted = persist_review(record, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert isinstance(persisted, PersistedReview)


def test_persist_review_writes_record_file_under_submission_dir(tmp_path: Path) -> None:
    # Arrange
    record = _record()
    # Act
    persisted = persist_review(record, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert persisted.record_path.is_file()


def test_persist_review_record_path_uses_canonical_filename(tmp_path: Path) -> None:
    # Arrange
    record = _record()
    # Act
    persisted = persist_review(record, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert persisted.record_path.name == REVIEW_RECORD_FILENAME


def test_persist_review_content_hash_uses_sha256_prefix(tmp_path: Path) -> None:
    # Arrange
    record = _record()
    pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
    # Act
    persisted = persist_review(record, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert pattern.match(persisted.content_hash)


def test_persist_review_content_hash_is_deterministic_for_identical_inputs(
    tmp_path: Path,
) -> None:
    """Two persistences of the same record must produce the same
    content_hash so a downstream tool can detect post-write tampering.
    """
    # Arrange
    record = _record()
    # Act
    a = persist_review(record, home=tmp_path / "home_a", now=_FIXED_TIME)
    b = persist_review(record, home=tmp_path / "home_b", now=_FIXED_TIME)
    # Assert
    assert a.content_hash == b.content_hash


def test_persist_review_payload_carries_record_block(tmp_path: Path) -> None:
    # Arrange
    record = _record()
    # Act
    persisted = persist_review(record, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert "record" in payload


def test_persist_review_payload_carries_content_hash_field(tmp_path: Path) -> None:
    # Arrange
    record = _record()
    # Act
    persisted = persist_review(record, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["content_hash"] == persisted.content_hash


def test_persist_review_payload_carries_submission_id(tmp_path: Path) -> None:
    # Arrange
    record = _record(submission_id="sub_2026_06_13_deadbe")
    # Act
    persisted = persist_review(record, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["submission_id"] == "sub_2026_06_13_deadbe"
