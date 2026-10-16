"""Read-only views for the reviewer dashboard.

The views in M1 are intentionally minimal: they return a structured
JSON payload describing what the page **would** show once the gate
engines persist real records. Once gate-2 / gate-3 / gate-4 ship, the
views switch from "placeholder" to "read the real model row" with no
template change.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from scitex_agentic_journal._django import _leaf


def submissions_index(request: HttpRequest) -> JsonResponse:
    """List endpoint (placeholder).

    Returns 200 with an empty list so deployments can wire the
    endpoint into their nav before the journal has any data. The
    placeholder is explicit (``"placeholder": true``) so dashboards
    don't render it as a real empty journal.
    """
    return JsonResponse(
        {
            "submissions": [],
            "placeholder": True,
            "next_milestone": "M1 submission gate",
        }
    )


def submission_detail(request: HttpRequest, submission_id: str) -> JsonResponse:
    """Detail endpoint for one submission (placeholder)."""
    return JsonResponse(
        {
            "submission_id": submission_id,
            "status": "gate1-pending",
            "placeholder": True,
        }
    )


def review_record_view(request: HttpRequest, submission_id: str) -> JsonResponse:
    """Read the gate-2 review record (placeholder until M2)."""
    return JsonResponse(
        {
            "submission_id": submission_id,
            "review_record": None,
            "placeholder": True,
            "expected_milestone": "M2",
        }
    )


def decision_record_view(request: HttpRequest, submission_id: str) -> JsonResponse:
    """Read the gate-3 decision record (placeholder until M3)."""
    return JsonResponse(
        {
            "submission_id": submission_id,
            "decision_record": None,
            "placeholder": True,
            "expected_milestone": "M3",
        }
    )


def admin_panel(request: HttpRequest) -> JsonResponse:
    """Operator-decision panel (placeholder)."""
    return JsonResponse(
        {
            "panels": [],
            "placeholder": True,
            "note": (
                "Manual override is only allowed on `agent-wait` blockers — "
                "never on accept / revise / reject."
            ),
        }
    )


def archive_view(request: HttpRequest) -> JsonResponse:
    """Leaf archive list — real FS read, placeholder when empty."""
    return JsonResponse(_leaf.list_archive())


def decision_dashboard_view(request: HttpRequest) -> JsonResponse:
    """Leaf decision dashboard — verdict + badge rows for the Monday demo."""
    return JsonResponse(_leaf.decision_dashboard())


def validator_view(request: HttpRequest, submission_id: str) -> JsonResponse:
    """Leaf validator panel — deterministic mock until M2 runs."""
    return JsonResponse(_leaf.validator_mock_report(submission_id))


def share_view(request: HttpRequest, submission_id: str) -> JsonResponse:
    """Leaf browse+share — persistent id when minted, else submission id."""
    payload = _leaf.share_record(submission_id)
    if payload is None:
        return JsonResponse({"submission_id": submission_id, "found": False}, status=404)
    return JsonResponse(payload)


def html_view(request: HttpRequest, persistent_id: str) -> JsonResponse:
    """Leaf HTML-view payload — badge + ids for the live-paper renderer."""
    return JsonResponse(_leaf.html_payload(persistent_id))
