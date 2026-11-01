"""Author guidance and per-user reads of actual journal records."""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from scitex_sdk.ui.branding import shell_context
from scitex_sdk.ui.project_scope import (
    LocalProjectProvider,
    host_project_provider,
    project_listing_view,
)

from . import _leaf
from ._manifest import load_manifest
from ._request_home import journal_request, request_home

SECTIONS = (
    ("authors", _("For authors")),
    ("prepare", _("Prepare")),
    ("submit", _("Submit")),
    ("archive", _("Your submissions")),
    ("review", _("Review & revision")),
    ("publication", _("Publication")),
)


def _projects_root():
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_PROJECTS_DIR")
    if explicit:
        return Path(explicit).expanduser()
    return (
        Path(os.environ.get("SCITEX_DIR", "~/.scitex")).expanduser()
        / "agentic-journal/projects"
    )


def _project_provider(request):
    provider = host_project_provider()
    if provider is not None:
        return provider
    mounted = (
        bool(getattr(settings, "SCITEX_USER_HOME_PROVIDER", ""))
        or getattr(settings, "SCITEX_APP_MODE", "standalone") != "standalone"
    )
    local = request_home(request) / "projects" if mounted else _projects_root()
    return LocalProjectProvider(local)


project_scope = journal_request(project_listing_view(_project_provider))


def _app_scope():
    return load_manifest().get("scope") or "user"


def _page_base(request):
    path = request.path
    path = path.removesuffix("app/")
    return path if path.endswith("/") else path + "/"


@journal_request
def app_page(request: HttpRequest):
    """Render original author guidance alongside the user's recorded workflow."""
    from scitex_agentic_journal import __version__

    home = request_home(request)
    from ._examples import default_example_bundle_dir

    section = request.GET.get("section", "authors")
    if section not in {key for key, _ in SECTIONS}:
        section = "authors"
    selected = request.GET.get("submission", "")
    summary = _leaf.get_submission_summary(selected, home) if selected else None
    if selected and summary is None:
        return JsonResponse({"error": "submission-not-found"}, status=404)
    review = _leaf.read_record(selected, "review", home) if summary else None
    decision = _leaf.read_record(selected, "decision", home) if summary else None
    context = {
        **shell_context(
            "Agentic Journal",
            panes={"ai": "unused", "files": "unused", "viewer": "unused"},
        ),
        **_leaf.list_archive(home),
        "app_scope": _app_scope(),
        "app_version": __version__,
        "current_project": None,  # A view never changes the host's global project profile.
        "sections": [
            {"key": key, "label": label, "active": key == section}
            for key, label in SECTIONS
        ],
        "section": section,
        "page_base": _page_base(request),
        "submit_url": _page_base(request) + "submit/",
        "example_available": default_example_bundle_dir().is_dir(),
        "example_load_url": _page_base(request)
        + "examples/example-project-mnist/load/",
        "selected_submission": summary,
        "review": _leaf._record_block(review) if review else None,
        "decision": _leaf._record_block(decision) if decision else None,
    }
    return render(request, "scitex_agentic_journal/app.html", context)


@journal_request
def submissions_index(request):
    return JsonResponse(_leaf.list_archive(request_home(request)))


@journal_request
def submission_detail(request, submission_id):
    summary = _leaf.get_submission_summary(submission_id, request_home(request))
    return (
        JsonResponse({**summary, "found": True, "placeholder": False})
        if summary
        else JsonResponse({"submission_id": submission_id, "found": False}, status=404)
    )


def _record_response(request, submission_id, kind):
    record = _leaf.read_record(submission_id, kind, request_home(request))
    return JsonResponse(
        {
            "submission_id": submission_id,
            f"{kind}_record": record,
            "recorded": record is not None,
            "placeholder": False,
        },
        status=200 if record is not None else 404,
    )


@journal_request
def review_record_view(request, submission_id):
    return _record_response(request, submission_id, "review")


@journal_request
def decision_record_view(request, submission_id):
    return _record_response(request, submission_id, "decision")


@journal_request
def admin_panel(request):
    return JsonResponse(
        {
            "panels": [],
            "placeholder": True,
            "note": "No web operator actions are enabled.",
        }
    )


@journal_request
def archive_view(request):
    return JsonResponse(_leaf.list_archive(request_home(request)))


@journal_request
def decision_dashboard_view(request):
    return JsonResponse(_leaf.decision_dashboard(request_home(request)))


@journal_request
def validator_view(request, submission_id):
    home = request_home(request)
    if _leaf.get_submission_summary(submission_id, home) is None:
        return JsonResponse({"error": "submission-not-found"}, status=404)
    return JsonResponse(_leaf.validator_report(submission_id, home))


@journal_request
def share_view(request, submission_id):
    payload = _leaf.share_record(submission_id, request_home(request))
    return (
        JsonResponse(payload)
        if payload
        else JsonResponse({"submission_id": submission_id, "found": False}, status=404)
    )


@journal_request
def html_view(request, persistent_id):
    return JsonResponse(_leaf.html_payload(persistent_id, request_home(request)))
