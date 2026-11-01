"""Per-user persisted journal record reads — Django-free.

Archive / browse / share / HTML payloads read the real on-disk
submission home (``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/*/``)
without importing Django, so unit tests exercise them with ``tmp_path``.

An empty archive retains ``placeholder: True`` for compatibility; review
and decision reads never fabricate records. Rendering stays behind ports — this module never imports
``scitex_live_paper``; the HTML payload carries the badge + IDs the
live-paper renderer consumes via its ports contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from scitex_agentic_journal._submit._ids import validate_submission_id


def _submission_home(home: Path | None = None) -> Path:
    if home is not None:
        return home
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _safe_read_json(path: Path) -> dict | None:
    if path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _record_block(payload: dict) -> dict:
    record = payload.get("record")
    if isinstance(record, dict):
        return record
    return payload


def submission_dir(submission_id: str, home: Path | None = None):
    """Resolve only a single safe identifier; never follow archive aliases."""
    try:
        validate_submission_id(submission_id)
    except ValueError:
        return None
    root = _submission_home(home).resolve()
    collection = root / "submissions"
    candidate = collection / submission_id
    if collection.is_symlink() or candidate.is_symlink():
        return None
    if candidate.resolve().parent != collection.resolve():
        return None
    return candidate if candidate.is_dir() else None


def read_record(submission_id, kind, home=None):
    """Read an existing persisted record; unsupported names never become paths."""
    if kind not in {"gate1", "review", "decision", "persistent_id"}:
        raise ValueError("Unknown journal record kind")
    directory = submission_dir(submission_id, home)
    return (
        _safe_read_json(directory / f"{kind}.json") if directory is not None else None
    )


def submission_ids(home: Path | None = None) -> list[str]:
    """Sorted submission ids present on disk (empty when home missing)."""
    root = _submission_home(home) / "submissions"
    if root.is_symlink() or not root.is_dir():
        return []
    ids: list[str] = []
    for child in sorted(root.iterdir()):
        if submission_dir(child.name, home) is not None:
            ids.append(child.name)
    return ids


def list_archive(home: Path | None = None) -> dict[str, Any]:
    """Archive payload from persisted records.

    Returns ``placeholder: True`` when no submissions exist so the UI
    renders the wired-but-empty state instead of a misleading table.
    """
    root = _submission_home(home)
    ids = submission_ids(root)
    items: list[dict[str, Any]] = []
    for sid in ids:
        summary = get_submission_summary(sid, home=root)
        if summary is not None:
            items.append(summary)
    if not items:
        return {
            "submissions": [],
            "placeholder": True,
            "next_milestone": "M1 submission gate",
        }
    return {"submissions": items, "placeholder": False}


def get_submission_summary(
    submission_id: str, home: Path | None = None
) -> dict[str, Any] | None:
    """Browse payload for one submission; ``None`` when unknown."""
    root = _submission_home(home)
    subdir = submission_dir(submission_id, root)
    if subdir is None:
        return None
    gate1 = _safe_read_json(subdir / "gate1.json")
    review = _safe_read_json(subdir / "review.json")
    decision = _safe_read_json(subdir / "decision.json")
    pid_doc = _safe_read_json(subdir / "persistent_id.json")
    persistent_id: str | None = None
    if pid_doc is not None:
        block = _record_block(pid_doc)
        cand = block.get("persistent_id", pid_doc.get("persistent_id"))
        if isinstance(cand, str) and cand:
            persistent_id = cand
    verdict: str | None = None
    if decision is not None:
        block = _record_block(decision)
        v = block.get("verdict")
        if isinstance(v, str):
            verdict = v
    return {
        "submission_id": submission_id,
        "example": bool(
            (gate1 or {}).get("example") or _record_block(decision or {}).get("example")
        ),
        "has_gate1": gate1 is not None,
        "has_review": review is not None,
        "has_decision": decision is not None,
        "verdict": verdict,
        "persistent_id": persistent_id,
    }


def validator_report(submission_id, home=None):
    """Expose recorded evidence, never synthetic passing validation checks."""
    gate = read_record(submission_id, "gate1", home)
    review = read_record(submission_id, "review", home)
    return {
        "submission_id": submission_id,
        "mock": False,
        "checks": [],
        "gate1_record": gate,
        "review_record": review,
        "recorded": review is not None,
        "repro": {"status": "recorded" if review is not None else "not-run"},
    }


def validator_mock_report(submission_id, home=None):
    """Compatibility name; synthetic checks have been retired."""
    return validator_report(submission_id, home)


def share_record(submission_id: str, home: Path | None = None) -> dict[str, Any] | None:
    """Share payload: persistent id + badge inputs, ``None`` when unknown."""
    summary = get_submission_summary(submission_id, home=home)
    if summary is None:
        return None
    return {
        "submission_id": submission_id,
        "persistent_id": summary.get("persistent_id"),
        "verdict": summary.get("verdict"),
        "share": (
            {"persistent_id": summary["persistent_id"]}
            if summary.get("persistent_id")
            else {"submission_id": submission_id}
        ),
    }


def decision_dashboard(home: Path | None = None) -> dict[str, Any]:
    """Decision-dashboard payload for the Monday demo.

    One row per submission carrying verdict + badge status, plus
    counts by status. Badge resolution never raises: a submission
    without mint/review/decision records shows ``stale`` (the
    live-paper palette for "no recent re-review").
    """
    from scitex_agentic_journal._re_review_badge._types import verdict_to_status

    root = _submission_home(home)
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {
        "verified": 0,
        "concerns": 0,
        "contradicted": 0,
        "stale": 0,
    }
    for sid in submission_ids(root):
        summary = get_submission_summary(sid, home=root)
        if summary is None:
            continue
        verdict = summary.get("verdict")
        status = verdict_to_status(verdict)
        counts[status] = counts.get(status, 0) + 1
        rows.append(
            {
                "submission_id": sid,
                "verdict": verdict,
                "status": status,
                "has_review": summary.get("has_review"),
                "has_decision": summary.get("has_decision"),
                "persistent_id": summary.get("persistent_id"),
            }
        )
    if not rows:
        return {"rows": [], "counts": counts, "placeholder": True, "total": 0}
    return {"rows": rows, "counts": counts, "placeholder": False, "total": len(rows)}


def html_payload(persistent_id: str, home: Path | None = None) -> dict[str, Any]:
    """HTML-view payload consumed via the live-paper ports contract.

    This repo never renders: it returns the ids + badge the renderer
    needs (``renderer: "live-paper-ports"``). ``found: False`` when no
    local submission mints that id — the SPA then hides the badge per
    the ReReviewBadge contract.
    """
    root = _submission_home(home)
    sub_root = root / "submissions"
    matched: str | None = None
    badge: dict[str, Any] | None = None
    if sub_root.is_dir():
        for sid in submission_ids(root):
            child = submission_dir(sid, root)
            if child is None:
                continue
            pid_doc = _safe_read_json(child / "persistent_id.json")
            if pid_doc is None:
                continue
            block = _record_block(pid_doc)
            cand = block.get("persistent_id", pid_doc.get("persistent_id"))
            if cand == persistent_id:
                matched = child.name
                break
    if matched is None:
        return {
            "persistent_id": persistent_id,
            "found": False,
            "renderer": "live-paper-ports",
            "badge": None,
        }
    from scitex_agentic_journal._re_review_badge._resolver import (
        resolve_badge_for_paper,
    )

    resolved = resolve_badge_for_paper(persistent_id, home=root)
    if resolved is not None:
        badge = {
            "status": resolved.status,
            "last_reviewed_at": resolved.last_reviewed_at,
            "reviewer": resolved.reviewer,
            "log_url": resolved.log_url,
            "notes": resolved.notes,
        }
    return {
        "persistent_id": persistent_id,
        "found": True,
        "submission_id": matched,
        "renderer": "live-paper-ports",
        "badge": badge,
    }
