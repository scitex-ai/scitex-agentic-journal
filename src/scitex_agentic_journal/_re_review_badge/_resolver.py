"""Resolve a paper's persistent id to a :class:`ReReviewBadge`.

The hub's :func:`scitex_live_paper.mount` accepts a ``resolver``
callback: when a paper renders, the resolver is asked to populate
``BundleContext.re_review_badge``. We expose
:func:`resolve_badge_for_paper` as the canonical implementation of
that resolver — the hub passes it through verbatim.

The lookup is filesystem-driven for now (alpha):

1. Scan ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/*/persistent_id.json``
   for an entry whose record's ``persistent_id`` matches the paper id.
2. Load that submission's ``decision.json`` + ``review.json``.
3. Build the :class:`ReReviewBadge` via :func:`verdict_to_status`.

A future iteration will swap step 1 for an index (SQLite or the
``_django`` Django app) so the scan stays O(1). Until then the
filesystem walk is correct + obvious; one paper-load = one badge =
one tiny directory scan.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from scitex_agentic_journal._re_review_badge._types import (
    ReReviewBadge,
    verdict_to_status,
)


#: Prefix prepended to the M2 adapter id when populating
#: :attr:`ReReviewBadge.reviewer`. Lets the live-paper UI distinguish
#: agentic-journal-authored badges from any future human-reviewer or
#: per-claim reviewer line that might share the field.
BADGE_REVIEWER_PREFIX = "agentic-journal"


def _submission_home() -> Path:
    """Mirror the resolution in ``_submit._persist`` / ``_review._persist``."""
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _safe_read_json(path: Path) -> Optional[dict]:
    """Read JSON, returning ``None`` on any failure shape.

    The resolver is called from the hub's request path; a malformed
    record on disk must never crash the page render. Empty / missing /
    invalid → no badge.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _find_submission_for_paper(
    paper_persistent_id: str, home: Path
) -> Optional[Path]:
    """Return the ``submissions/<id>/`` dir whose
    ``persistent_id.json.record.persistent_id`` matches.

    ``None`` if no submission matches, the home is missing, or any
    persistent_id.json is unreadable. Scan is non-recursive past the
    ``submissions/`` parent.
    """
    submissions_root = home / "submissions"
    if not submissions_root.is_dir():
        return None
    for submission_dir in sorted(submissions_root.iterdir()):
        if not submission_dir.is_dir():
            continue
        pid_path = submission_dir / "persistent_id.json"
        if not pid_path.is_file():
            continue
        payload = _safe_read_json(pid_path)
        if payload is None:
            continue
        # The M4 persister wraps the record under ``record``; also
        # accept top-level for back-compat with hand-written records.
        record = payload.get("record") if isinstance(payload.get("record"), dict) else None
        candidate = None
        if record is not None:
            candidate = record.get("persistent_id")
        if not isinstance(candidate, str) or not candidate:
            candidate = payload.get("persistent_id")
        if isinstance(candidate, str) and candidate == paper_persistent_id:
            return submission_dir
    return None


def _decision_block(decision_payload: dict) -> dict:
    """Return the typed decision record block.

    Same convention as the publish loader: the persister wraps the
    typed record under ``record``; older synthetic records hand the
    fields at the top level.
    """
    record = decision_payload.get("record")
    if isinstance(record, dict):
        return record
    return decision_payload


def _review_block(review_payload: dict) -> dict:
    """Return the typed review record block (same wrap convention)."""
    record = review_payload.get("record")
    if isinstance(record, dict):
        return record
    return review_payload


def _notes_from_rule_hits(decision_record: dict) -> Optional[str]:
    """Build a one-line notes string from the first failing rule hit.

    The M3 engine emits a ``RuleHit`` per evaluated rule (passed and
    failed alike) so the decision record carries enough evidence to
    explain the verdict at a glance. We pull the first failed hit's
    ``message`` — the engine already formats those as
    operator-readable strings (e.g. ``methodology.max_severity='major'
    ...``).
    """
    hits = decision_record.get("rule_hits") or ()
    if not isinstance(hits, (list, tuple)):
        return None
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        if hit.get("passed") is False:
            msg = hit.get("message")
            if isinstance(msg, str) and msg:
                return msg
    return None


def resolve_badge_for_paper(
    paper_persistent_id: str,
    *,
    home: Optional[Path] = None,
    log_url: Optional[str] = None,
) -> Optional[ReReviewBadge]:
    """Return a :class:`ReReviewBadge` for ``paper_persistent_id``.

    Parameters
    ----------
    paper_persistent_id :
        The minted id the live-paper viewer is loading. Same string
        agentic-journal stamps in the M5 publish bundle's
        ``persistent_id`` field.
    home :
        Override the submission-home root. ``None`` falls back to
        ``$SCITEX_AGENTIC_JOURNAL_HOME`` then
        ``~/.scitex/agentic-journal``.
    log_url :
        Optional deep link into the agentic-journal log / record
        viewer. The resolver does not synthesise one — the hub knows
        its own URL space.

    Returns
    -------
    ReReviewBadge | None
        ``None`` when no submission matches the id (the SPA hides the
        badge). Otherwise the verdict mapped via
        :func:`verdict_to_status` plus the optional reviewer / notes /
        timestamp fields.

    No exceptions: a malformed record on disk degrades to ``None``
    rather than crashing the render.
    """
    root = home if home is not None else _submission_home()
    submission_dir = _find_submission_for_paper(paper_persistent_id, root)
    if submission_dir is None:
        return None

    decision_payload = _safe_read_json(submission_dir / "decision.json")
    if decision_payload is None:
        return None

    decision_record = _decision_block(decision_payload)
    status = verdict_to_status(decision_record.get("verdict"))

    last_reviewed_at = (
        decision_record.get("decided_at")
        or decision_payload.get("written_at_utc")
    )
    if not isinstance(last_reviewed_at, str):
        last_reviewed_at = None

    review_payload = _safe_read_json(submission_dir / "review.json")
    reviewer: Optional[str] = None
    if review_payload is not None:
        review_record = _review_block(review_payload)
        adapter = review_record.get("adapter")
        if isinstance(adapter, str) and adapter:
            reviewer = f"{BADGE_REVIEWER_PREFIX}:{adapter}"

    return ReReviewBadge(
        status=status,
        last_reviewed_at=last_reviewed_at,
        reviewer=reviewer,
        log_url=log_url,
        notes=_notes_from_rule_hits(decision_record),
    )
