"""Tests for `_publish/_mint.py` — `mint_for_submission` end-to-end.

Uses the on-disk gate1.json shape produced by
:mod:`scitex_agentic_journal._submit._persist`. No mocks, no HTTP —
the InternalIdMinter backend is fully deterministic so the test
can assert exact id structure.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scitex_agentic_journal._publish import (
    MintLoadError,
    PersistentId,
    mint_for_submission,
)

_FIXED_TIME = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)


def _write_gate1(
    home: Path,
    submission_id: str = "sub_2026_06_13_abc123",
    *,
    orcid: str = "0000-0002-1825-0097",
    bundle_dir: Path | None = None,
) -> Path:
    """Drop a minimal valid gate1.json under ``home`` for ``submission_id``."""
    submission_dir = home / "submissions" / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "submission_id": submission_id,
        "gate": "gate1",
        "verdict": "pass",
        "minted_at_utc": _FIXED_TIME.isoformat(),
        "submission": {
            "bundle_dir": str(bundle_dir or submission_dir),
            "orcid_id": orcid,
            "code_repo_url": "https://github.com/octocat/Hello-World.git",
            "clew_project_dir": str(bundle_dir or submission_dir),
        },
        "orcid_record": {},
        "code_repo": {"head_commit": "x", "head_subject": "y"},
        "clew_verification": {
            "project_dir": str(bundle_dir or submission_dir),
            "green_claims": [],
            "red_claims": [],
            "total_claims": 0,
        },
    }
    gate1_path = submission_dir / "gate1.json"
    gate1_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return gate1_path


def _write_bundle_yaml(bundle_dir: Path, title: str) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "bundle.yaml").write_text(
        f"title: {title!r}\norcid_id: '0000-0002-1825-0097'\n"
        "code_repo_url: 'https://github.com/octocat/Hello-World.git'\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Happy path — internal backend, deterministic id.
# ---------------------------------------------------------------------------


def test_mint_for_submission_returns_persistent_id_for_internal_backend(
    tmp_path: Path,
) -> None:
    # Arrange
    _write_gate1(tmp_path)
    # Act
    pid = mint_for_submission(
        "sub_2026_06_13_abc123",
        backend="internal",
        home=tmp_path,
        now=_FIXED_TIME,
    )
    # Assert
    assert isinstance(pid, PersistentId)


def test_mint_for_submission_internal_backend_returns_internal_tag(
    tmp_path: Path,
) -> None:
    # Arrange
    _write_gate1(tmp_path)
    # Act
    pid = mint_for_submission(
        "sub_2026_06_13_abc123",
        backend="internal",
        home=tmp_path,
        now=_FIXED_TIME,
    )
    # Assert
    assert pid.backend == "internal"


def test_mint_for_submission_internal_id_embeds_decision_date(
    tmp_path: Path,
) -> None:
    # Arrange
    _write_gate1(tmp_path)
    # Act
    pid = mint_for_submission(
        "sub_2026_06_13_abc123",
        backend="internal",
        home=tmp_path,
        now=_FIXED_TIME,
    )
    # Assert
    assert "20260613" in pid.persistent_id


def test_mint_for_submission_uses_bundle_title_when_present(
    tmp_path: Path,
) -> None:
    """When ``bundle.yaml`` carries ``title:``, the slug must reflect it."""
    # Arrange
    bundle = tmp_path / "bundle_xyz"
    _write_bundle_yaml(bundle, title="Quantised Toad Holography")
    _write_gate1(tmp_path, bundle_dir=bundle)
    # Act
    pid = mint_for_submission(
        "sub_2026_06_13_abc123",
        backend="internal",
        home=tmp_path,
        now=_FIXED_TIME,
    )
    # Assert
    assert "quantised-toad-holography" in pid.persistent_id


def test_mint_for_submission_falls_back_to_submission_id_title_when_no_bundle_yaml(
    tmp_path: Path,
) -> None:
    """No bundle.yaml → fallback title derived from submission id."""
    # Arrange
    _write_gate1(tmp_path, bundle_dir=tmp_path / "nonexistent_bundle")
    # Act
    pid = mint_for_submission(
        "sub_2026_06_13_abc123",
        backend="internal",
        home=tmp_path,
        now=_FIXED_TIME,
    )
    # Assert: slug for "Submission sub_2026_06_13_abc123" lower-kebab.
    assert "submission" in pid.persistent_id


def test_mint_for_submission_passes_decision_record_decided_at_through(
    tmp_path: Path,
) -> None:
    """A decision_record with an ISO ``decided_at`` overrides ``now``."""
    # Arrange
    _write_gate1(tmp_path)
    decision = {"decided_at": "2026-09-01T00:00:00+00:00"}
    # Act
    pid = mint_for_submission(
        "sub_2026_06_13_abc123",
        backend="internal",
        home=tmp_path,
        now=_FIXED_TIME,
        decision_record=decision,
    )
    # Assert
    assert "20260901" in pid.persistent_id


# ---------------------------------------------------------------------------
# Error path — missing submission → MintLoadError.
# ---------------------------------------------------------------------------


def test_mint_for_submission_raises_mint_load_error_when_submission_dir_missing(
    tmp_path: Path,
) -> None:
    # Arrange — no gate1.json on disk.
    home = tmp_path
    # Act
    ctx = pytest.raises(MintLoadError)
    # Assert
    with ctx:
        mint_for_submission(
            "sub_2026_06_13_missing",
            backend="internal",
            home=home,
            now=_FIXED_TIME,
        )


def test_mint_for_submission_raises_mint_load_error_when_gate1_json_missing(
    tmp_path: Path,
) -> None:
    """Submission dir exists but no gate1.json → MintLoadError."""
    # Arrange
    (tmp_path / "submissions" / "sub_2026_06_13_emptydir").mkdir(parents=True)
    # Act
    ctx = pytest.raises(MintLoadError)
    # Assert
    with ctx:
        mint_for_submission(
            "sub_2026_06_13_emptydir",
            backend="internal",
            home=tmp_path,
            now=_FIXED_TIME,
        )


def test_mint_for_submission_raises_mint_load_error_when_gate1_json_is_garbage(
    tmp_path: Path,
) -> None:
    # Arrange
    submission_dir = tmp_path / "submissions" / "sub_2026_06_13_garbage"
    submission_dir.mkdir(parents=True)
    (submission_dir / "gate1.json").write_text("not json", encoding="utf-8")
    # Act
    ctx = pytest.raises(MintLoadError)
    # Assert
    with ctx:
        mint_for_submission(
            "sub_2026_06_13_garbage",
            backend="internal",
            home=tmp_path,
            now=_FIXED_TIME,
        )
