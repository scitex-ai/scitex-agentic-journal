"""Tests for `_submit/_persist.py` — id minting + on-disk record shape.

No mocks. Each test writes a real JSON record to `tmp_path` via the
real `persist_verdict` and inspects the file. Time is injected via
the public `now=` kwarg so the id-format assertion is deterministic
without monkey-patching `datetime`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._gate1 import (
    ClewVerification,
    OrcidRecord,
)
from scitex_agentic_journal._submit import (
    Gate1Verdict,
    PersistedSubmission,
    Submission,
    persist_verdict,
)
from scitex_agentic_journal._submit._persist import GATE1_RECORD_FILENAME

_FIXED_TIME = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)


def _make_verdict(bundle_dir: Path) -> Gate1Verdict:
    submission = Submission(
        bundle_dir=bundle_dir,
        orcid_id="0000-0002-1825-0097",
        code_repo_url="https://github.com/octocat/Hello-World.git",
        clew_project_dir=bundle_dir,
    )
    orcid_record = OrcidRecord(
        orcid_id="0000-0002-1825-0097",
        given_name="Stephen",
        family_name="Hawking",
        credit_name="Stephen W. Hawking",
    )
    clew = ClewVerification(
        project_dir=bundle_dir,
        green_claims=("claim-A",),
        red_claims=(),
        total_claims=1,
        raw_stdout='[{"id":"claim-A","status":"green"}]',
    )
    return Gate1Verdict(
        submission=submission,
        orcid_record=orcid_record,
        code_repo_head_commit="abc123",
        code_repo_head_subject="Initial commit",
        clew_verification=clew,
    )


def test_persist_verdict_returns_persisted_submission_instance(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert isinstance(persisted, PersistedSubmission)


def test_persist_verdict_mints_id_matching_canonical_format(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    pattern = re.compile(r"^sub_2026_06_13_[0-9a-f]{6}$")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert pattern.match(persisted.submission_id)


def test_persist_verdict_writes_record_file_to_expected_path(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert persisted.record_path.is_file()


def test_persist_verdict_record_dir_contains_canonical_filename(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert persisted.record_path.name == GATE1_RECORD_FILENAME


def test_persist_verdict_record_path_is_under_record_dir(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    # Assert
    assert persisted.record_path.parent == persisted.record_dir


def test_persist_verdict_persisted_json_has_pass_verdict(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["verdict"] == "pass"


def test_persist_verdict_persisted_json_carries_submission_id(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["submission_id"] == persisted.submission_id


def test_persist_verdict_persisted_json_carries_orcid_id(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["submission"]["orcid_id"] == "0000-0002-1825-0097"


def test_persist_verdict_persisted_json_carries_green_claims(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["clew_verification"]["green_claims"] == ["claim-A"]


def test_persist_verdict_persisted_json_carries_minted_at_utc(tmp_path: Path) -> None:
    # Arrange
    verdict = _make_verdict(tmp_path / "bundle")
    # Act
    persisted = persist_verdict(verdict, home=tmp_path / "home", now=_FIXED_TIME)
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["minted_at_utc"] == _FIXED_TIME.isoformat()
