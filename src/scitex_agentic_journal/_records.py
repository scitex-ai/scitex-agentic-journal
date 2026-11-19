"""Shared helpers for the journal's on-disk JSON records.

Every record lives under ``<home>/submissions/<submission_id>/``, where
``<home>`` is ``$SCITEX_AGENTIC_JOURNAL_HOME`` or ``~/.scitex/agentic-journal``
(the layout the legacy intake already uses). Records are written atomically
(temp file + rename) and hashed over canonical JSON so a record can be cited
by its hash.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SUBMISSION_ID_RE = re.compile(r"^aj-[0-9a-f]{16}$")


class RecordError(RuntimeError):
    """A record is missing, malformed, or an id is not a valid record id."""


def journal_home(home: Path | None = None) -> Path:
    """Resolve the journal home directory (explicit > env > default)."""
    if home is not None:
        return Path(home)
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit)
    return Path.home() / ".scitex" / "agentic-journal"


def submission_dir(submission_id: str, home: Path | None = None) -> Path:
    """Directory of one contract-based submission; validates the id shape."""
    if not _SUBMISSION_ID_RE.fullmatch(submission_id):
        raise RecordError(
            f"invalid submission id {submission_id!r}; expected 'aj-' + 16 hex digits"
        )
    return journal_home(home) / "submissions" / submission_id


@contextmanager
def record_lock(record_dir: Path) -> Iterator[None]:
    """Exclusive lock on one submission's records (read-modify-write safety)."""
    record_dir.mkdir(parents=True, exist_ok=True)
    with (record_dir / ".lock").open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes used for hashing (sorted keys, no spaces)."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utcnow_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def write_record(path: Path, payload: dict[str, Any]) -> str:
    """Atomically write ``payload`` as pretty JSON; return its canonical sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return sha256_hex(canonical_json(payload))


def read_record(path: Path) -> dict[str, Any]:
    """Read a JSON record, raising :class:`RecordError` with the path on failure."""
    if not path.is_file():
        raise RecordError(f"record not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RecordError(f"record {path} is not valid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise RecordError(f"record {path} must be a JSON object")
    return payload
