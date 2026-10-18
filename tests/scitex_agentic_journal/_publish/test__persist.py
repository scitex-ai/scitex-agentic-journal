"""Tests for `_publish/_persist.py` — persistent_id.json round-trip."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._publish import (
    PersistedPersistentId,
    PersistentId,
    persist_persistent_id,
)
from scitex_agentic_journal._publish._persist import PERSISTENT_ID_FILENAME

_FIXED_TIME = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)


def _pid() -> PersistentId:
    return PersistentId(
        persistent_id="scitex-aj-20260613-example-abcdef",
        backend="internal",
    )


def test_persist_persistent_id_returns_persisted_instance(tmp_path: Path) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    # Assert
    assert isinstance(persisted, PersistedPersistentId)


def test_persist_persistent_id_writes_record_file(tmp_path: Path) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    # Assert
    assert persisted.record_path.is_file()


def test_persist_persistent_id_uses_canonical_filename(tmp_path: Path) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    # Assert
    assert persisted.record_path.name == PERSISTENT_ID_FILENAME


def test_persist_persistent_id_record_path_under_submission_dir(
    tmp_path: Path,
) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    expected_dir = tmp_path / "submissions" / submission_id
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    # Assert
    assert persisted.record_path.parent == expected_dir


def test_persist_persistent_id_payload_carries_persistent_id_value(
    tmp_path: Path,
) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert (
        payload["record"]["persistent_id"]
        == "scitex-aj-20260613-example-abcdef"
    )


def test_persist_persistent_id_payload_carries_backend(tmp_path: Path) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["record"]["backend"] == "internal"


def test_persist_persistent_id_content_hash_uses_sha256_prefix(
    tmp_path: Path,
) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert pattern.match(payload["content_hash"])


def test_persist_persistent_id_content_hash_is_deterministic(
    tmp_path: Path,
) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    pid = _pid()
    # Act
    a = persist_persistent_id(
        submission_id, pid, home=tmp_path / "a", now=_FIXED_TIME
    )
    b = persist_persistent_id(
        submission_id, pid, home=tmp_path / "b", now=_FIXED_TIME
    )
    payload_a = json.loads(a.record_path.read_text(encoding="utf-8"))
    payload_b = json.loads(b.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload_a["content_hash"] == payload_b["content_hash"]


def test_persist_persistent_id_returns_backend_at_top_level(
    tmp_path: Path,
) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    # Assert
    assert persisted.backend == "internal"


def test_persist_persistent_id_returns_persistent_id_unchanged(
    tmp_path: Path,
) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    pid = _pid()
    # Act
    persisted = persist_persistent_id(
        submission_id, pid, home=tmp_path, now=_FIXED_TIME
    )
    # Assert
    assert persisted.persistent_id == pid


def test_persist_persistent_id_writes_written_at_utc(tmp_path: Path) -> None:
    # Arrange
    submission_id = "sub_2026_06_13_abc123"
    # Act
    persisted = persist_persistent_id(
        submission_id, _pid(), home=tmp_path, now=_FIXED_TIME
    )
    payload = json.loads(persisted.record_path.read_text(encoding="utf-8"))
    # Assert
    assert payload["written_at_utc"] == _FIXED_TIME.isoformat()
