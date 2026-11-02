"""No-mocks tests for the example-project loader (:mod:`_examples`).

Covers :func:`load_example_project` (example bundle → labeled demo
records): fixed id, three records, example flags, idempotent rewrite,
and the unavailable/malformed-bundle failures. Django-free: pure
``tmp_path`` I/O, hermetic (no env, no network).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_agentic_journal._django import _examples
from scitex_agentic_journal._django._leaf import submission_ids
from scitex_agentic_journal._submit import SubmissionLoadError


def _bundle(tmp_path: Path) -> Path:
    # Arrange helper — minimal valid bundle (loader validates the
    # real manifest schema; Gate-1 itself never runs).
    bundle = tmp_path / "example-project-mnist"
    bundle.mkdir(parents=True)
    (bundle / "bundle.yaml").write_text(
        "orcid_id: '0000-0000-0000-0000'\n"
        "code_repo_url: 'https://example.invalid/mnist.git'\n",
        encoding="utf-8",
    )
    return bundle


def test_load_example_returns_fixed_id(tmp_path: Path) -> None:
    # Arrange
    bundle = _bundle(tmp_path)
    # Act
    receipt = _examples.load_example_project(bundle, home=tmp_path / "home")
    # Assert
    assert receipt["submission_id"] == "example-project-mnist"


def test_load_example_writes_three_records(tmp_path: Path) -> None:
    # Arrange
    bundle = _bundle(tmp_path)
    # Act
    _examples.load_example_project(bundle, home=tmp_path / "home")
    # Assert
    names = sorted(
        p.name
        for p in (tmp_path / "home" / "submissions" / "example-project-mnist").iterdir()
    )
    assert names == ["decision.json", "gate1.json", "persistent_id.json"]


def test_load_example_gate1_carries_example_flag(tmp_path: Path) -> None:
    # Arrange
    bundle = _bundle(tmp_path)
    # Act
    _examples.load_example_project(bundle, home=tmp_path / "home")
    # Assert
    payload = json.loads(
        (
            tmp_path / "home" / "submissions" / "example-project-mnist" / "gate1.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["example"] is True


def test_load_example_decision_is_labeled_accept(tmp_path: Path) -> None:
    # Arrange
    bundle = _bundle(tmp_path)
    # Act
    _examples.load_example_project(bundle, home=tmp_path / "home")
    # Assert
    payload = json.loads(
        (
            tmp_path
            / "home"
            / "submissions"
            / "example-project-mnist"
            / "decision.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["record"]["verdict"] == "accept"


def test_load_example_is_idempotent(tmp_path: Path) -> None:
    # Arrange
    bundle = _bundle(tmp_path)
    home = tmp_path / "home"
    # Act
    _examples.load_example_project(bundle, home=home)
    _examples.load_example_project(bundle, home=home)
    # Assert
    assert submission_ids(home) == ["example-project-mnist"]


def test_load_example_missing_bundle_raises(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "no-such-bundle"
    # Act
    # Assert
    with pytest.raises(_examples.ExampleUnavailable):
        _examples.load_example_project(missing, home=tmp_path / "home")


def test_default_bundle_dir_falls_back_to_home_proj(tmp_path: Path) -> None:
    # Arrange — real env-var swap (NM002-compliant): HOME carries the
    # example project, no explicit bundle override wins over nothing.
    import os as _os

    bundle = tmp_path / "proj" / "example-project-mnist"
    bundle.mkdir(parents=True)
    (bundle / "bundle.yaml").write_text(
        "orcid_id: '0000-0000-0000-0000'\n"
        "code_repo_url: 'https://example.invalid/mnist.git'\n",
        encoding="utf-8",
    )
    saved = dict(_os.environ)
    _os.environ.pop("SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE", None)
    _os.environ["HOME"] = str(tmp_path)
    try:
        # Act
        found = _examples.default_example_bundle_dir()
    finally:
        _os.environ.clear()
        _os.environ.update(saved)
    # Assert
    assert found == bundle


def test_candidate_dirs_include_container_mount_point() -> None:
    # Arrange
    # Act
    candidates = _examples._candidate_bundle_dirs()
    # Assert
    assert Path("/example-project-mnist") in candidates


def test_load_example_malformed_bundle_raises(tmp_path: Path) -> None:
    # Arrange
    bundle = tmp_path / "bad-bundle"
    bundle.mkdir(parents=True)
    (bundle / "bundle.yaml").write_text("orcid_id: ''\n", encoding="utf-8")
    # Act
    # Assert
    with pytest.raises(SubmissionLoadError):
        _examples.load_example_project(bundle, home=tmp_path / "home")


def test_example_loader_preserves_unexpected_existing_content(tmp_path: Path) -> None:
    # Arrange
    bundle = _bundle(tmp_path)
    home = tmp_path / "home"
    target = home / "submissions" / _examples.EXAMPLE_SUBMISSION_ID
    target.mkdir(parents=True)
    evidence = target / "important-research.txt"
    evidence.write_text("Preserve this user file")
    # Act
    failure = None
    try:
        _examples.load_example_project(bundle, home=home)
    except _examples.ExampleConflict as exc:
        failure = exc
    # Assert
    assert (
        failure is not None
        and evidence.read_text() == "Preserve this user file"
        and list(target.iterdir()) == [evidence]
    )


def test_example_loader_never_follows_existing_target_alias(tmp_path: Path) -> None:
    # Arrange
    bundle = _bundle(tmp_path)
    home = tmp_path / "home"
    collection = home / "submissions"
    collection.mkdir(parents=True)
    other = tmp_path / "other-user"
    other.mkdir()
    target = collection / _examples.EXAMPLE_SUBMISSION_ID
    target.symlink_to(other, target_is_directory=True)
    # Act
    # Assert
    with pytest.raises(_examples.ExampleConflict):
        _examples.load_example_project(bundle, home=home)
