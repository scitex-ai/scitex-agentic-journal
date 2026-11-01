"""Read-only views for the reviewer dashboard.

``submissions_index`` / ``submission_detail`` read the real on-disk
submission home (``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/*/``)
via :mod:`scitex_agentic_journal._django._leaf`, so the Hub-mounted
dashboard lists what the ``submit`` CLI / POST handler actually
persisted. An empty home still returns explicit
``"placeholder": true`` so dashboards render the wired-but-empty
state instead of a misleading table.

Gate-2 / gate-3 views (review / decision) stay placeholders until
M2 / M3 persist real records.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render

from scitex_agentic_journal._django import _leaf
from scitex_agentic_journal._django._manifest import load_manifest

try:
    from scitex_sdk.ui.branding import shell_context
except ImportError as exc:  # scitex-sdk absent or below the GUI capability floor
    raise ImportError(
        "scitex_agentic_journal._django.views needs scitex-sdk>=0.3.9. "
        "Install the journal package with its declared dependencies."
    ) from exc

try:
    from scitex_ui.project_scope import (
        LocalProjectProvider,
        host_project_provider,
        project_listing_view,
        resolve_project,
    )
except ImportError as exc:  # scitex-ui absent — the header picker primitive
    raise ImportError(
        "scitex_agentic_journal._django.views needs scitex-ui, which is "
        "installed alongside scitex-sdk. Reinstall scitex-agentic-journal "
        "with its declared dependencies."
    ) from exc


def _projects_root() -> Path:
    """Folder the standalone project picker lists.

    ``SCITEX_AGENTIC_JOURNAL_PROJECTS_DIR`` wins (isolated CI runs,
    operator demos); otherwise the journal's own user-space projects
    dir. Every non-hidden folder is one project (SDK ``LocalProjectProvider``
    contract, same as scholar's standalone fallback).
    """
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_PROJECTS_DIR")
    if explicit:
        return Path(explicit).expanduser()
    scitex_root = Path(os.environ.get("SCITEX_DIR", "~/.scitex")).expanduser()
    return scitex_root / "agentic-journal" / "projects"


def _project_provider(request):
    """Use the mounted host provider, or a local folder provider standalone."""
    return host_project_provider() or LocalProjectProvider(_projects_root())


# Shared scitex-ui GET-list / POST-remember endpoint (scholar pattern):
# the picker JS talks here; request-time factory keeps mounted hosts
# authoritative for permissions and project identity.
project_scope = project_listing_view(_project_provider)


def _app_scope() -> str:
    """Manifest-declared scope — the template picker's single source of truth."""
    return load_manifest().get("scope") or "user"


def app_page(request: HttpRequest):
    """Plugin page — the archive rendered inside the SDK app shell.

    Server-rendered mirror of :func:`archive_view` for human readers;
    machine clients use the JSON endpoints. Extends
    ``scitex_sdk/app/app_shell.html`` (block ``scitex_app_content``)
    per the SDK leaf contract; carries no ``{% url %}`` tags so the
    page stays correct under hub's mount prefix + namespace.

    The header row is the shared SDK ``stx-app-header`` (no leaf h1)
    with the SDK project picker; scope comes from the manifest.
    """
    from scitex_agentic_journal import __version__ as app_version

    provider = _project_provider(request)
    current_project = resolve_project(
        request,
        provider,
        explicit=request.GET.get("project"),
    )
    # Form action for the empty-state example button: derived from the
    # request's own path (prefix-agnostic under hub mounts, no {% url %}),
    # valid from both the index ("") and the "app/" page routes.
    page_path = request.path
    if page_path.endswith("app/"):
        page_path = page_path[: -len("app/")]
    if not page_path.endswith("/"):
        page_path += "/"
    return render(
        request,
        "scitex_agentic_journal/app.html",
        {
            **_leaf.list_archive(),
            **shell_context(
                "Agentic Journal",
                panes={"ai": "unused", "files": "unused", "viewer": "unused"},
            ),
            "app_scope": _app_scope(),
            "app_version": app_version,
            "current_project": current_project,
            "example_load_url": page_path + "examples/example-project-mnist/load/",
        },
    )

from scitex_agentic_journal._django import _leaf


def submissions_index(request: HttpRequest) -> JsonResponse:
    """List endpoint — real on-disk archive, placeholder when empty.

    Returns 200 with one summary row per persisted submission (the
    same rows the CLI ``submit`` command creates). Deployments can
    wire the endpoint into their nav before the journal has any data:
    the empty home is explicit (``"placeholder": true``) so dashboards
    don't render it as a real empty journal.
    """
    return JsonResponse(_leaf.list_archive())


def submission_detail(request: HttpRequest, submission_id: str) -> JsonResponse:
    """Detail endpoint for one submission — real record, 404 when unknown."""
    summary = _leaf.get_submission_summary(submission_id)
    if summary is None:
        return JsonResponse(
            {"submission_id": submission_id, "found": False},
            status=404,
        )
    return JsonResponse({**summary, "found": True, "placeholder": False})


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
