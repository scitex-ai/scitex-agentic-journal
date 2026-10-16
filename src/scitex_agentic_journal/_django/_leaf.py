"""Leaf helpers for the Monday demo — Django-free.

Archive / browse / share / HTML payloads read the real on-disk
submission home (``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/*/``)
without importing Django, so unit tests exercise them with ``tmp_path``.

Placeholder contracts stay in ``views`` / ``handlers``: empty home
still returns explicit ``placeholder: True`` rather than a silent
empty list. Rendering stays behind ports — this module never imports
``scitex_live_paper``; the HTML payload carries the badge + IDs the
live-paper renderer consumes via its ports contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


def _submission_home(home: Path | None = None) -> Path:
    if home is not None:
        return home
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _safe_read_json(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _record_block(payload: dict) -> dict:
    record = payload.get("record")
    if isinstance(record, dict):
        return record
    return payload


def submission_ids(home: Path | None = None) -> list[str]:
    """Sorted submission ids present on disk (empty when home missing)."""
    root = _submission_home(home) / "submissions"
    if not root.is_dir():
        return []
    ids: list[str] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            ids.append(child.name)
    return ids


def list_archive(home: Path | None = None) -> dict[str, Any]:
    """Archive payload for the demo dashboard.

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
        return {"submissions": [], "placeholder": True, "next_milestone": "M1 submission gate"}
    return {"submissions": items, "placeholder": False}


def get_submission_summary(submission_id: str, home: Path | None = None) -> Optional[dict[str, Any]]:
    """Browse payload for one submission; ``None`` when unknown."""
    root = _submission_home(home)
    subdir = root / "submissions" / submission_id
    if not subdir.is_dir():
        return None
    gate1 = _safe_read_json(subdir / "gate1.json")
    review = _safe_read_json(subdir / "review.json")
    decision = _safe_read_json(subdir / "decision.json")
    pid_doc = _safe_read_json(subdir / "persistent_id.json")
    persistent_id: Optional[str] = None
    if pid_doc is not None:
        block = _record_block(pid_doc)
        cand = block.get("persistent_id", pid_doc.get("persistent_id"))
        if isinstance(cand, str) and cand:
            persistent_id = cand
    verdict: Optional[str] = None
    if decision is not None:
        block = _record_block(decision)
        v = block.get("verdict")
        if isinstance(v, str):
            verdict = v
    return {
        "submission_id": submission_id,
        "has_gate1": gate1 is not None,
        "has_review": review is not None,
        "has_decision": decision is not None,
        "verdict": verdict,
        "persistent_id": persistent_id,
    }


def validator_mock_report(submission_id: str) -> dict[str, Any]:
    """Deterministic mock agent repro report for the validator panel.

    No I/O: the demo shows this shape until a real reviewer adapter
    runs. Explicit ``mock: True`` so nobody mistakes it for a real run.
    """
    return {
        "submission_id": submission_id,
        "mock": True,
        "adapter": "mock-agent-repro",
        "checks": [
            {"name": "orcid-resolvable", "passed": True, "detail": "mock: ORCID resolves"},
            {"name": "code-repo-cloneable", "passed": True, "detail": "mock: repo clones"},
            {"name": "clew-dag-verifies-claim", "passed": True, "detail": "mock: >=1 claim green"},
        ],
        "repro": {"status": "not-run", "log": "mock: reviewer agent not yet executed"},
    }


def share_record(submission_id: str, home: Path | None = None) -> Optional[dict[str, Any]]:
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
    try:
        from scitex_agentic_journal._re_review_badge._types import verdict_to_status
    except Exception:
        verdict_to_status = None  # type: ignore[assignment]

    root = _submission_home(home)
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {"verified": 0, "concerns": 0, "contradicted": 0, "stale": 0}
    for sid in submission_ids(root):
        summary = get_submission_summary(sid, home=root)
        if summary is None:
            continue
        verdict = summary.get("verdict")
        if verdict_to_status is not None:
            try:
                status = verdict_to_status(verdict)
            except Exception:
                status = "stale"
        else:
            status = {"accept": "verified", "revise": "concerns", "reject": "contradicted"}.get(
                verdict if isinstance(verdict, str) else "", "stale"
            )
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
    matched: Optional[str] = None
    badge: Optional[dict[str, Any]] = None
    if sub_root.is_dir():
        for child in sorted(sub_root.iterdir()):
            if not child.is_dir():
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
    try:
        from scitex_agentic_journal._re_review_badge._resolver import resolve_badge_for_paper
    except Exception:
        resolve_badge_for_paper = None  # type: ignore[assignment]
    if resolve_badge_for_paper is not None:
        try:
            resolved = resolve_badge_for_paper(persistent_id, home=root)
        except Exception:
            resolved = None
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
