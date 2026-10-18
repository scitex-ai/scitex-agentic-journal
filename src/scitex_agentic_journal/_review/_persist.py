"""Persist a :class:`ReviewRecord` next to the Gate-1 submission record.

The acceptance language in #6 specifies "Persist the review record
next to the submission with hash-stamped provenance". We:

* drop ``review.json`` into the same submission directory the M1
  persister (gate-1) writes to, so M3 (decision engine, #7) can
  load both records from one place.
* derive ``content_hash`` from the canonicalised record JSON so any
  downstream mutation is detectable.
* record ``written_at_utc`` for chronology.

The on-disk filename is intentionally ``review.json`` (not
``review-<adapter>.json``) — M2 ships a *single* reviewer per
submission. Multi-reviewer panels are post-MVP.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._review._types import ReviewRecord

REVIEW_RECORD_FILENAME = "review.json"
"""On-disk filename for the persisted review record."""


@dataclass(frozen=True)
class PersistedReview:
    """Receipt returned by :func:`persist_review`.

    Attributes
    ----------
    submission_id :
        The submission whose review just persisted.
    record_path :
        Absolute path to the written ``review.json``.
    content_hash :
        ``sha256:<hex>`` of the canonicalised record JSON. Stable
        across reruns of the same adapter on the same inputs —
        downstream tools can use it to detect tampering.
    """

    submission_id: str
    record_path: Path
    content_hash: str


def _submission_home() -> Path:
    """Mirror `_submit._persist._submission_home` so the layout matches."""
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _serialise_for_hash(record: ReviewRecord) -> str:
    """Canonical JSON for hashing — sorted keys, no whitespace.

    `default=str` accepts the `datetime` fields without a custom
    encoder; the canonical form is the ISO-8601 string so two
    records that share the same wall-clock instant hash the same.
    """
    payload = _record_to_jsonable(record)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _record_to_jsonable(record: ReviewRecord) -> dict:
    """Recursively convert a frozen dataclass tree to JSON-able primitives."""

    def _conv(value: object) -> object:
        if is_dataclass(value):
            return {k: _conv(v) for k, v in asdict(value).items()}
        if isinstance(value, tuple):
            return [_conv(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    return {
        "submission_id": record.submission_id,
        "adapter": record.adapter,
        "adapter_version": record.adapter_version,
        "prompts_version": record.prompts_version,
        "rubric_version": record.rubric_version,
        "reproducibility": _conv(record.reproducibility),
        "claim_verify": _conv(record.claim_verify),
        "novelty": _conv(record.novelty),
        "methodology": _conv(record.methodology),
        "started_at": record.started_at.isoformat(),
        "finished_at": record.finished_at.isoformat(),
    }


def persist_review(
    record: ReviewRecord,
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> PersistedReview:
    """Write ``review.json`` next to the M1 ``gate1.json`` for this submission.

    Parameters
    ----------
    record :
        The review record produced by :class:`ReviewRunner.run`.
    home :
        Override the submission-home root. ``None`` honours
        ``$SCITEX_AGENTIC_JOURNAL_HOME`` then falls back to
        ``~/.scitex/agentic-journal/``. Tests inject ``tmp_path``.
    now :
        Override the timestamp written to ``written_at_utc``. Tests
        inject a deterministic value; production passes ``None``.

    Returns
    -------
    PersistedReview
        Receipt with the submission id, on-disk record path, and
        the canonical content hash.
    """
    root = home if home is not None else _submission_home()
    submission_dir = root / "submissions" / record.submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    record_path = submission_dir / REVIEW_RECORD_FILENAME

    canonical = _serialise_for_hash(record)
    content_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    written_at = (now or datetime.now(timezone.utc)).isoformat()

    payload = {
        "submission_id": record.submission_id,
        "content_hash": content_hash,
        "written_at_utc": written_at,
        "record": _record_to_jsonable(record),
    }
    record_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PersistedReview(
        submission_id=record.submission_id,
        record_path=record_path,
        content_hash=content_hash,
    )
