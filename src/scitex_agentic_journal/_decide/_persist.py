"""Persist a :class:`DecisionRecord` next to the M2 ``review.json``.

The decision engine is gate-3 in the MVP loop; its on-disk artefact
sits next to the M1 ``gate1.json`` and the M2 ``review.json`` so a
single submission directory carries the full audit trail from
submission → review → decision. The next gate (#8 / persistent-ID
minting) can load all three from one place.

* drops ``decision.json`` into ``submissions/<id>/``.
* derives ``content_hash`` from the canonicalised record JSON so any
  downstream mutation is detectable.
* records ``written_at_utc`` for chronology.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._decide._types import DecisionRecord

DECISION_RECORD_FILENAME = "decision.json"
"""On-disk filename for the persisted decision record."""


@dataclass(frozen=True)
class PersistedDecision:
    """Receipt returned by :func:`persist_decision`.

    Attributes
    ----------
    submission_id :
        The submission whose decision just persisted.
    record_path :
        Absolute path to the written ``decision.json``.
    content_hash :
        ``sha256:<hex>`` of the canonicalised record JSON. Stable
        across reruns of the engine on the same review record.
    """

    submission_id: str
    record_path: Path
    content_hash: str


def _submission_home() -> Path:
    """Mirror `_review._persist._submission_home`."""
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _record_to_jsonable(record: DecisionRecord) -> dict:
    """Recursively convert the frozen dataclass tree to JSON primitives."""

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
        "verdict": record.verdict,
        "rules_version": record.rules_version,
        "rule_hits": [_conv(h) for h in record.rule_hits],
        "decided_at": record.decided_at.isoformat(),
        "review_content_hash": record.review_content_hash,
    }


def _serialise_for_hash(record: DecisionRecord) -> str:
    """Canonical JSON for hashing — sorted keys, no whitespace."""
    payload = _record_to_jsonable(record)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def persist_decision(
    record: DecisionRecord,
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> PersistedDecision:
    """Write ``decision.json`` next to ``review.json`` for this submission.

    Parameters
    ----------
    record :
        The decision record produced by :class:`DecisionEngine.decide`.
    home :
        Override the submission-home root. ``None`` honours
        ``$SCITEX_AGENTIC_JOURNAL_HOME`` then falls back to
        ``~/.scitex/agentic-journal/``. Tests inject ``tmp_path``.
    now :
        Override the timestamp written to ``written_at_utc``. Tests
        inject a deterministic value; production passes ``None``.

    Returns
    -------
    PersistedDecision
        Receipt with the submission id, on-disk record path, and
        the canonical content hash.
    """
    root = home if home is not None else _submission_home()
    submission_dir = root / "submissions" / record.submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    record_path = submission_dir / DECISION_RECORD_FILENAME

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
    return PersistedDecision(
        submission_id=record.submission_id,
        record_path=record_path,
        content_hash=content_hash,
    )
