"""Tests for `_submit/_loader.py` — the strict bundle.yaml parser.

No mocks. Each test writes a real `bundle.yaml` to `tmp_path` and
calls `load_submission` against it; the manifest reader hits real
disk and the real `yaml.safe_load`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scitex_agentic_journal._submit import (
    Submission,
    SubmissionLoadError,
    load_submission,
)
from scitex_agentic_journal._submit._loader import MANIFEST_FILENAME


def _write_manifest(bundle: Path, body: str) -> Path:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / MANIFEST_FILENAME).write_text(body, encoding="utf-8")
    return bundle


def test_load_submission_raises_when_bundle_directory_does_not_exist(
    tmp_path: Path,
) -> None:
    # Arrange
    missing = tmp_path / "no-such-bundle"
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="does not exist")
    # Assert
    with ctx:
        load_submission(missing)


def test_load_submission_raises_when_bundle_path_is_a_file(tmp_path: Path) -> None:
    # Arrange
    not_a_dir = tmp_path / "bundle.txt"
    not_a_dir.write_text("oops", encoding="utf-8")
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="not a directory")
    # Assert
    with ctx:
        load_submission(not_a_dir)


def test_load_submission_raises_when_manifest_file_is_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="missing the bundle.yaml")
    # Assert
    with ctx:
        load_submission(bundle)


def test_load_submission_raises_when_manifest_is_empty(tmp_path: Path) -> None:
    # Arrange
    bundle = _write_manifest(tmp_path / "bundle", "")
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="is empty")
    # Assert
    with ctx:
        load_submission(bundle)


def test_load_submission_raises_when_manifest_is_invalid_yaml(
    tmp_path: Path,
) -> None:
    # Arrange — malformed flow-mapping
    bundle = _write_manifest(tmp_path / "bundle", "orcid_id: [bad: yaml")
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="not valid YAML")
    # Assert
    with ctx:
        load_submission(bundle)


def test_load_submission_raises_when_manifest_root_is_not_mapping(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _write_manifest(tmp_path / "bundle", "- 1\n- 2\n")
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="must be a YAML mapping")
    # Assert
    with ctx:
        load_submission(bundle)


def test_load_submission_raises_when_orcid_id_key_is_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    body = "code_repo_url: https://example.com/r.git\n"
    bundle = _write_manifest(tmp_path / "bundle", body)
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="orcid_id")
    # Assert
    with ctx:
        load_submission(bundle)


def test_load_submission_raises_when_code_repo_url_key_is_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    body = "orcid_id: 0000-0002-1825-0097\n"
    bundle = _write_manifest(tmp_path / "bundle", body)
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="code_repo_url")
    # Assert
    with ctx:
        load_submission(bundle)


def test_load_submission_raises_when_required_value_is_empty_string(
    tmp_path: Path,
) -> None:
    # Arrange
    body = "orcid_id: ''\ncode_repo_url: https://example.com/r.git\n"
    bundle = _write_manifest(tmp_path / "bundle", body)
    # Act
    ctx = pytest.raises(SubmissionLoadError, match="must be a non-empty")
    # Assert
    with ctx:
        load_submission(bundle)


def test_load_submission_returns_submission_for_minimal_valid_manifest(
    tmp_path: Path,
) -> None:
    # Arrange
    body = (
        "orcid_id: 0000-0002-1825-0097\n"
        "code_repo_url: https://github.com/octocat/Hello-World.git\n"
    )
    bundle = _write_manifest(tmp_path / "bundle", body)
    # Act
    submission = load_submission(bundle)
    # Assert
    assert isinstance(submission, Submission)


def test_load_submission_resolves_bundle_dir_to_absolute_path(
    tmp_path: Path,
) -> None:
    # Arrange
    body = (
        "orcid_id: 0000-0002-1825-0097\n"
        "code_repo_url: https://github.com/octocat/Hello-World.git\n"
    )
    bundle = _write_manifest(tmp_path / "bundle", body)
    # Act
    submission = load_submission(bundle)
    # Assert
    assert submission.bundle_dir.is_absolute()


def test_load_submission_defaults_clew_project_dir_to_bundle_root(
    tmp_path: Path,
) -> None:
    # Arrange
    body = (
        "orcid_id: 0000-0002-1825-0097\n"
        "code_repo_url: https://github.com/octocat/Hello-World.git\n"
    )
    bundle = _write_manifest(tmp_path / "bundle", body)
    # Act
    submission = load_submission(bundle)
    # Assert
    assert submission.clew_project_dir == submission.bundle_dir


def test_load_submission_resolves_relative_clew_project_path_against_bundle(
    tmp_path: Path,
) -> None:
    # Arrange
    body = (
        "orcid_id: 0000-0002-1825-0097\n"
        "code_repo_url: https://github.com/octocat/Hello-World.git\n"
        "clew_project_path: ./clew\n"
    )
    bundle = _write_manifest(tmp_path / "bundle", body)
    (bundle / "clew").mkdir()
    # Act
    submission = load_submission(bundle)
    # Assert
    assert submission.clew_project_dir == (bundle / "clew").resolve()


def test_load_submission_passes_through_absolute_clew_project_path(
    tmp_path: Path,
) -> None:
    # Arrange
    elsewhere = (tmp_path / "elsewhere-clew").resolve()
    elsewhere.mkdir()
    body = (
        "orcid_id: 0000-0002-1825-0097\n"
        "code_repo_url: https://github.com/octocat/Hello-World.git\n"
        f"clew_project_path: {elsewhere}\n"
    )
    bundle = _write_manifest(tmp_path / "bundle", body)
    # Act
    submission = load_submission(bundle)
    # Assert
    assert submission.clew_project_dir == elsewhere
