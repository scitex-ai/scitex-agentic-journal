"""URL config for the embedded reviewer dashboard.

URLs are organised so URL reverses match the public-API names used
elsewhere (e.g. ``submission-detail`` matches the MCP tool name
``aj_get_submission``).
"""

from __future__ import annotations

from django.urls import path

from scitex_agentic_journal._django import handlers, views

app_name = "scitex_agentic_journal"


urlpatterns = [
    path("", views.app_page, name="index"),
    path("app/", views.app_page, name="app-page"),
    path("submit/", handlers.submit, name="submit"),
    path("archive/", views.archive_view, name="archive"),
    path("dashboard/", views.decision_dashboard_view, name="decision-dashboard"),
    path(
        "submissions/<str:submission_id>/",
        views.submission_detail,
        name="submission-detail",
    ),
    path(
        "submissions/<str:submission_id>/review/",
        views.review_record_view,
        name="review-record",
    ),
    path(
        "submissions/<str:submission_id>/decision/",
        views.decision_record_view,
        name="decision-record",
    ),
    path(
        "submissions/<str:submission_id>/validator/",
        views.validator_view,
        name="validator",
    ),
    path(
        "submissions/<str:submission_id>/share/",
        views.share_view,
        name="share",
    ),
    path("papers/<str:persistent_id>/html/", views.html_view, name="paper-html"),
    path("admin/", views.admin_panel, name="admin-panel"),
]
