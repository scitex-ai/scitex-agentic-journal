"""Tests for the SDK-shell plugin page — real render, no stubs.

``app_page`` must render inside the genuine
``scitex_sdk/app/app_shell.html`` chain (extends + block), not a
test double: the SDK is installed in this container, so the full
template inheritance resolves for real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="module")
def _configure_django() -> None:
    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            DEBUG=False,
            ALLOWED_HOSTS=["testserver", "localhost"],
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django.contrib.staticfiles",
                "scitex_sdk.app",
                "scitex_sdk.ui",
                "scitex_agentic_journal._django",
            ],
            SCITEX_UI_AUTOWIRE_INSPECTOR=False,
        STATIC_URL="/static/",
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                },
            },
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": [],
                    "APP_DIRS": True,
                    "OPTIONS": {},
                }
            ],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            ROOT_URLCONF="tests._django_test_urls",
            USE_TZ=True,
        )
        django.setup()
    elif "testserver" not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "testserver"]


@pytest.fixture
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("SCITEX_AGENTIC_JOURNAL_HOME", str(home))
    return home


def _client():
    from django.test import Client

    return Client()


def test_app_page_renders_empty_journal(_home: Path) -> None:
    response = _client().get("/aj/app/")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Agentic Journal" in body
    assert "No submissions yet" in body


def test_app_page_renders_sdk_shell_chain(_home: Path) -> None:
    # The SDK chain leaves brand evidence: the shared favicon from
    # `_branding_head.html` and the `scitex_app_content` block
    # nesting. Both prove the real `app_shell.html` resolved — not a
    # stub.
    body = _client().get("/aj/app/").content.decode("utf-8")
    assert "scitex-favicon.svg" in body
    assert "<main" in body


def test_app_page_lists_persisted_submission(_home: Path) -> None:
    sub = _home / "submissions" / "sub_2026_10_19_aaaaaa"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(
        json.dumps({"submission_id": "sub_2026_10_19_aaaaaa", "gate": "gate1"}),
        encoding="utf-8",
    )
    (sub / "decision.json").write_text(
        json.dumps({"record": {"verdict": "accept"}}), encoding="utf-8"
    )
    body = _client().get("/aj/app/").content.decode("utf-8")
    assert "sub_2026_10_19_aaaaaa" in body
    assert "accept" in body


def test_app_page_mounts_shared_app_header_without_leaf_h1(_home: Path) -> None:
    # Identical-row contract + Django comment discipline: the app row is the
    # shared mount (title from the manifest label), never a leaf <h1>; and
    # template comments must use {% comment %} blocks — Django only strips
    # single-line {# #}, so a multi-line {# #} would leak raw into the page
    # (measured 2026-10-22: it did).
    body = _client().get("/aj/app/").content.decode("utf-8")
    assert '<div data-stx-app-header data-app-title="Agentic Journal">' in body
    assert "<h1" not in body
    assert "{#" not in body


def test_app_page_template_extends_sdk_shell() -> None:
    # Contract anchor independent of rendering: the template extends
    # exactly the SDK shell and fills exactly `scitex_app_content`.
    from scitex_agentic_journal._django import _leaf  # noqa: F401
    from django.template import engines

    template = engines["django"].get_template("scitex_agentic_journal/app.html")
    assert template.template.nodelist  # parsed, not empty
    source = Path(template.template.origin.name).read_text(encoding="utf-8")
    assert '{% extends "scitex_sdk/app/app_shell.html" %}' in source
    assert "{% block scitex_app_content %}" in source
    # Prefix/namespace-agnostic: no real `{% url %}` tags (the word
    # only appears inside comments).
    import re as _re

    code = _re.sub(r"\{#.*?#\}", "", source, flags=_re.S)
    code = _re.sub(
        r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}", "", code, flags=_re.S
    )
    assert "{% url " not in code


def test_app_page_route_reverses() -> None:
    from django.urls import reverse

    assert reverse("scitex_agentic_journal:app-page").endswith("/app/")
