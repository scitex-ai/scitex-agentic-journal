"""Tests for `_review/_load_gate1.py` — strict gate1.json reader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_agentic_journal._review import (
    ReviewLoadError,
    SubmissionInputs,
    load_submission_inputs,
)


def _write_gate1(
    home: Path,
    submission_id: str = "sub_2026_06_13_abc123",
    *,
    orcid_id: str = "0000-0002-1825-0097",
    code_repo_url: str = "https://example.com/r.git",
    bundle_dir: Path | None = None,
    clew_project_dir: Path | None = None,
) -> Path:
    submission_dir = home / "submissions" / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "submission_id": submission_id,
        "gate": "gate1",
        "verdict": "pass",
        "submission": {
            "bundle_dir": str(bundle_dir or (home / "bundle")),
            "orcid_id": orcid_id,
            "code_repo_url": code_repo_url,
            "clew_project_dir": str(
                clew_project_dir or bundle_dir or (home / "bundle")
            ),
        },
        "clew_verification": {
            "project_dir": str(clew_project_dir or bundle_dir or (home / "bundle")),
            "green_claims": ["c1"],
            "red_claims": [],
            "total_claims": 1,
        },
        "orcid_record": {
            "orcid_id": orcid_id,
            "given_name": "Test",
            "family_name": "Author",
            "credit_name": None,
        },
        "code_repo": {"head_commit": "abc123", "head_subject": "init"},
    }
    (submission_dir / "gate1.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return submission_dir


def test_load_submission_inputs_returns_submission_inputs_instance(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _write_gate1(home)
    # Act
    inputs = load_submission_inputs("sub_2026_06_13_abc123", home=home)
    # Assert
    assert isinstance(inputs, SubmissionInputs)


def test_load_submission_inputs_threads_submission_id_through(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _write_gate1(home)
    # Act
    inputs = load_submission_inputs("sub_2026_06_13_abc123", home=home)
    # Assert
    assert inputs.submission_id == "sub_2026_06_13_abc123"


def test_load_submission_inputs_threads_orcid_id_into_inputs(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _write_gate1(home, orcid_id="0000-0002-1825-0097")
    # Act
    inputs = load_submission_inputs("sub_2026_06_13_abc123", home=home)
    # Assert
    assert inputs.corresponding_author_orcid == "0000-0002-1825-0097"


def test_load_submission_inputs_threads_code_repo_url_into_inputs(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _write_gate1(home, code_repo_url="https://example.com/repo.git")
    # Act
    inputs = load_submission_inputs("sub_2026_06_13_abc123", home=home)
    # Assert
    assert inputs.code_repo_url == "https://example.com/repo.git"


def test_load_submission_inputs_raises_when_submission_dir_missing(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    # Act
    ctx = pytest.raises(ReviewLoadError, match="no persisted submission")
    # Assert
    with ctx:
        load_submission_inputs("sub_2026_06_13_unknown", home=home)


def test_load_submission_inputs_raises_when_gate1_json_missing(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    (home / "submissions" / "sub_2026_06_13_abc123").mkdir(parents=True)
    # Act
    ctx = pytest.raises(ReviewLoadError, match="missing its gate1.json")
    # Assert
    with ctx:
        load_submission_inputs("sub_2026_06_13_abc123", home=home)


def test_load_submission_inputs_raises_when_gate1_json_is_invalid_json(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    sub = home / "submissions" / "sub_2026_06_13_abc123"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text("{not-json", encoding="utf-8")
    # Act
    ctx = pytest.raises(ReviewLoadError, match="not valid JSON")
    # Assert
    with ctx:
        load_submission_inputs("sub_2026_06_13_abc123", home=home)


def test_load_submission_inputs_raises_when_submission_block_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    sub = home / "submissions" / "sub_2026_06_13_abc123"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(
        json.dumps({"submission_id": "sub_2026_06_13_abc123"}), encoding="utf-8"
    )
    # Act
    ctx = pytest.raises(ReviewLoadError, match="missing 'submission'")
    # Assert
    with ctx:
        load_submission_inputs("sub_2026_06_13_abc123", home=home)
