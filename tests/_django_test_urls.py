"""Minimal top-level urlconf for the aj-django tests.

Mounts the embedded app at ``/aj/`` with its declared ``app_name`` so
``reverse('scitex_agentic_journal:submission-detail', ...)`` resolves
during the test run. Not part of the shipped package.
"""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("aj/", include("scitex_agentic_journal._django.urls")),
]
