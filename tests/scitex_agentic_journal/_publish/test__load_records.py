"""Tests for `_publish/_load_records.py` — strict on-disk record reader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_agentic_journal._publish import (
    PublishLoadError,
    PublishRecords,
    load_submission_records,
)

SUBMISSION_ID = "sub_2026_06_13_abc123"


def _write_gate1(submission_dir: Path, bundle_dir: Path) -> Path:
    payload = {
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
        "code_repo": {"head_commit": "abc123", "head_subject": "init"},
    }
    out = submission_dir / "gate1.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _write_review(
    submission_dir: Path,
    *,
    content_hash: str = "sha256:" + "a" * 64,
) -> Path:
    payload = {
        "submission_id": SUBMISSION_ID,
        "content_hash": content_hash,
        "written_at_utc": "2026-06-13T12:00:00+00:00",
        "record": {"submission_id": SUBMISSION_ID},
    }
    out = submission_dir / "review.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _write_decision(
    submission_dir: Path,
    *,
    verdict: str = "accept",
    content_hash: str = "sha256:" + "b" * 64,
) -> Path:
    payload = {
        "submission_id": SUBMISSION_ID,
        "verdict": verdict,
        "content_hash": content_hash,
        "written_at_utc": "2026-06-13T12:30:00+00:00",
    }
    out = submission_dir / "decision.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _write_persistent_id(
    submission_dir: Path,
    *,
    persistent_id: str = "scitex-aj-20260613-test-abcdef",
) -> Path:
    payload = {
        "submission_id": SUBMISSION_ID,
        "persistent_id": persistent_id,
        "backend": "internal",
        "minted_at_utc": "2026-06-13T13:00:00+00:00",
    }
    out = submission_dir / "persistent_id.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _materialise_happy_path(
    home: Path,
    *,
    verdict: str = "accept",
    persistent_id: str = "scitex-aj-20260613-test-abcdef",
    review_hash: str = "sha256:" + "a" * 64,
    decision_hash: str = "sha256:" + "b" * 64,
) -> Path:
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = home / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    _write_gate1(submission_dir, bundle_dir)
    _write_review(submission_dir, content_hash=review_hash)
    _write_decision(submission_dir, verdict=verdict, content_hash=decision_hash)
    _write_persistent_id(submission_dir, persistent_id=persistent_id)
    return submission_dir


# ---------- happy path ------------------------------------------------------


def test_load_submission_records_returns_publish_records_instance(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home)
    # Act
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Assert
    assert isinstance(records, PublishRecords)


def test_load_submission_records_threads_submission_id_through(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home)
    # Act
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Assert
    assert records.submission_id == SUBMISSION_ID


def test_load_submission_records_threads_manuscript_dir_from_gate1(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home)
    # Act
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Assert
    assert records.manuscript_dir == home / "bundle"


def test_load_submission_records_threads_review_record_id_from_review(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home, review_hash="sha256:" + "1" * 64)
    # Act
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Assert
    assert records.review_record_id == "sha256:" + "1" * 64


def test_load_submission_records_threads_decision_record_id_from_decision(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home, decision_hash="sha256:" + "2" * 64)
    # Act
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Assert
    assert records.decision_record_id == "sha256:" + "2" * 64


def test_load_submission_records_threads_persistent_id_through(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home, persistent_id="scitex-aj-20260613-xyz-fedcba")
    # Act
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Assert
    assert records.persistent_id == "scitex-aj-20260613-xyz-fedcba"


# ---------- error branches --------------------------------------------------


def test_load_submission_records_raises_when_submission_dir_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    # Act
    ctx = pytest.raises(PublishLoadError, match="no persisted submission")
    # Assert
    with ctx:
        load_submission_records("sub_2026_06_13_unknown", home=home)


def test_load_submission_records_raises_when_gate1_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True)
    # Act
    ctx = pytest.raises(PublishLoadError, match="missing its gate1.json")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)


def test_load_submission_records_raises_when_review_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True)
    bundle_dir = home / "bundle"
    bundle_dir.mkdir(parents=True)
    _write_gate1(submission_dir, bundle_dir)
    # Act
    ctx = pytest.raises(PublishLoadError, match="missing its review.json")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)


def test_load_submission_records_raises_when_decision_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True)
    bundle_dir = home / "bundle"
    bundle_dir.mkdir(parents=True)
    _write_gate1(submission_dir, bundle_dir)
    _write_review(submission_dir)
    # Act
    ctx = pytest.raises(PublishLoadError, match="missing its decision.json")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)


def test_load_submission_records_raises_when_persistent_id_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True)
    bundle_dir = home / "bundle"
    bundle_dir.mkdir(parents=True)
    _write_gate1(submission_dir, bundle_dir)
    _write_review(submission_dir)
    _write_decision(submission_dir)
    # Act
    ctx = pytest.raises(PublishLoadError, match="persistent_id.json")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)


def test_load_submission_records_raises_when_decision_verdict_is_not_accept(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home, verdict="reject")
    # Act
    ctx = pytest.raises(PublishLoadError, match="cannot be published")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)


def test_load_submission_records_raises_when_decision_verdict_is_revise(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise_happy_path(home, verdict="revise")
    # Act
    ctx = pytest.raises(PublishLoadError, match="not 'accept'")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)


def test_load_submission_records_raises_when_gate1_is_invalid_json(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True)
    (submission_dir / "gate1.json").write_text("{not-json", encoding="utf-8")
    # Act
    ctx = pytest.raises(PublishLoadError, match="not valid JSON")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)


def test_load_submission_records_raises_when_review_content_hash_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True)
    bundle_dir = home / "bundle"
    bundle_dir.mkdir(parents=True)
    _write_gate1(submission_dir, bundle_dir)
    (submission_dir / "review.json").write_text(
        json.dumps({"submission_id": SUBMISSION_ID}), encoding="utf-8"
    )
    # Act
    ctx = pytest.raises(PublishLoadError, match="content_hash")
    # Assert
    with ctx:
        load_submission_records(SUBMISSION_ID, home=home)
