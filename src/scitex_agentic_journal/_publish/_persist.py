"""Persist a :class:`PersistentId` next to ``gate1.json`` / ``review.json``.

Mirrors :mod:`scitex_agentic_journal._review._persist` shape so the
M5 decision engine and the M6 audit tools can locate the persistent
id with the same submission-home convention:

::

    $SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/persistent_id.json

The on-disk payload includes a canonical ``content_hash`` so
downstream tools can detect post-write tampering, mirroring the
review record's ``sha256:<hex>`` convention.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._publish._types import PersistentId

PERSISTENT_ID_FILENAME = "persistent_id.json"
"""On-disk filename for the persisted persistent-ID record."""


@dataclass(frozen=True)
class PersistedPersistentId:
    """Receipt returned by :func:`persist_persistent_id`.

    Attributes
    ----------
    submission_id :
        The submission whose persistent id just persisted.
    record_path :
        Absolute path to the written ``persistent_id.json``.
    persistent_id :
        The :class:`PersistentId` that was persisted (so callers can
        chain without re-loading from disk).
    backend :
        Backend tag from :class:`PersistentId.backend`. Mirrored at
        the top level for convenience in dashboard / log output.
    """

    submission_id: str
    record_path: Path
    persistent_id: PersistentId
    backend: str


def _submission_home() -> Path:
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _record_to_jsonable(submission_id: str, persistent_id: PersistentId) -> dict:
    return {
        "submission_id": submission_id,
        "persistent_id": persistent_id.persistent_id,
        "backend": persistent_id.backend,
    }


def _serialise_for_hash(payload: dict) -> str:
    """Canonical JSON for hashing — sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def persist_persistent_id(
    submission_id: str,
    persistent_id: PersistentId,
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> PersistedPersistentId:
    """Write ``persistent_id.json`` for ``submission_id``.

    Parameters
    ----------
    submission_id :
        The ``sub_YYYY_MM_DD_<hex>`` token from M1.
    persistent_id :
        The :class:`PersistentId` produced by :func:`mint_for_submission`.
    home :
        Override the submission-home root. ``None`` honours
        ``$SCITEX_AGENTIC_JOURNAL_HOME`` then falls back to
        ``~/.scitex/agentic-journal/``. Tests inject ``tmp_path``.
    now :
        Override the ``written_at_utc`` timestamp. Tests inject a
        deterministic value; production passes ``None``.

    Returns
    -------
    PersistedPersistentId
        Receipt with the submission id, on-disk record path, and
        the persisted :class:`PersistentId`.
    """
    root = home if home is not None else _submission_home()
    submission_dir = root / "submissions" / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    record_path = submission_dir / PERSISTENT_ID_FILENAME

    record = _record_to_jsonable(submission_id, persistent_id)
    canonical = _serialise_for_hash(record)
    content_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    written_at = (now or datetime.now(timezone.utc)).isoformat()

    payload = {
        "submission_id": submission_id,
        "content_hash": content_hash,
        "written_at_utc": written_at,
        "record": record,
    }
    record_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PersistedPersistentId(
        submission_id=submission_id,
        record_path=record_path,
        persistent_id=persistent_id,
        backend=persistent_id.backend,
    )
