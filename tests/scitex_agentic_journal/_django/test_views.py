"""Tests for the live Django submission surface — handlers + real reads.

Covers :func:`handlers.submit` (POST → Gate-1 → persist) and the
real-record :func:`views.submissions_index` /
:func:`views.submission_detail`. Network-free: the failure path uses
a locally-rejected bundle (malformed ORCID, same shape as the CLI
test), and the success path monkeypatches the two ``_submit``
seams the handler calls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import re as _re

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
            # The SDK UI config autowires dev middleware/processors in
            # ready() — explicitly off under test.
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
def _home(tmp_path: Path):
    # Arrange — real env-var swap (NM002-compliant): point persist at tmp.
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path / "home")
    try:
        yield tmp_path / "home"
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original


def _client():
    from django.test import Client

    return Client()


def _seed_gate1(home: Path) -> str:
    sid = "sub_2026_10_19_aaaaaa"
    sub = home / "submissions" / sid
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(
        json.dumps({"submission_id": sid, "gate": "gate1"}),
        encoding="utf-8",
    )
    return sid


def _seed_decision(home: Path, sid: str, verdict: str = "accept") -> None:
    (home / "submissions" / sid / "decision.json").write_text(
        json.dumps({"record": {"verdict": verdict}}), encoding="utf-8"
    )


# ----- read surface -------------------------------------------------------


def test_index_empty_home_submissions(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = json.loads(_client().get("/aj/archive/").content)
    # Assert
    assert body["submissions"] == []


def test_index_empty_home_placeholder(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = json.loads(_client().get("/aj/archive/").content)
    # Assert
    assert body["placeholder"] is True


def test_index_lists_persisted_submission_not_placeholder(_home: Path) -> None:
    # Arrange
    _seed_gate1(_home)
    # Act
    body = json.loads(_client().get("/aj/archive/").content)
    # Assert
    assert body["placeholder"] is False


def test_index_lists_persisted_submission_id(_home: Path) -> None:
    # Arrange
    sid = _seed_gate1(_home)
    # Act
    body = json.loads(_client().get("/aj/archive/").content)
    # Assert
    assert [r["submission_id"] for r in body["submissions"]] == [sid]


def test_detail_unknown_status_404(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().get("/aj/submissions/nope/")
    # Assert
    assert response.status_code == 404


def test_detail_unknown_found_false(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().get("/aj/submissions/nope/")
    # Assert
    assert json.loads(response.content)["found"] is False


def test_detail_known_status_200(_home: Path) -> None:
    # Arrange
    sub = _home / "submissions" / "sub_1"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(json.dumps({"gate": "gate1"}), encoding="utf-8")
    _seed_decision(_home, "sub_1")
    # Act
    response = _client().get("/aj/submissions/sub_1/")
    # Assert
    assert response.status_code == 200


def test_detail_known_found_true(_home: Path) -> None:
    # Arrange
    sub = _home / "submissions" / "sub_1"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(json.dumps({"gate": "gate1"}), encoding="utf-8")
    _seed_decision(_home, "sub_1")
    # Act
    response = _client().get("/aj/submissions/sub_1/")
    # Assert
    assert json.loads(response.content)["found"] is True


def test_detail_known_verdict(_home: Path) -> None:
    # Arrange
    sub = _home / "submissions" / "sub_1"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(json.dumps({"gate": "gate1"}), encoding="utf-8")
    _seed_decision(_home, "sub_1")
    # Act
    response = _client().get("/aj/submissions/sub_1/")
    # Assert
    assert json.loads(response.content)["verdict"] == "accept"


# ----- hub mounting contract ----------------------------------------------


def test_urlconf_flat_for_hub_gating() -> None:
    # Arrange
    # hub wraps every URLPattern; a nested include() would slip
    # the gate, and the leaf urlconf must not be empty.
    from django.urls import URLPattern

    from scitex_agentic_journal._django import urls as leaf_urls

    # Act
    flat = bool(leaf_urls.urlpatterns) and all(
        isinstance(entry, URLPattern) for entry in leaf_urls.urlpatterns
    )
    # Assert
    assert flat


def test_submit_route_reverses() -> None:
    # Arrange
    from django.urls import reverse

    # Act
    url = reverse("scitex_agentic_journal:submit")
    # Assert
    assert url.endswith("/submit/")


# ----- plugin app page (views.index) ----









@pytest.fixture
def _persisted(_home: Path) -> Path:
    # Arrange
    # one persisted accept submission.
    sub = _home / "submissions" / "sub_2026_10_19_aaaaaa"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(
        json.dumps({"submission_id": "sub_2026_10_19_aaaaaa", "gate": "gate1"}),
        encoding="utf-8",
    )
    (sub / "decision.json").write_text(
        json.dumps({"record": {"verdict": "accept"}}), encoding="utf-8"
    )
    return _home




def _body() -> str:
    # Act
    # GET the plugin page and decode.
    return _client().get("/aj/app/").content.decode("utf-8")


def test_app_page_status_ok(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().get("/aj/app/")
    # Assert
    assert response.status_code == 200


def test_app_page_shows_label(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert "Agentic Journal" in body


def test_app_page_shows_empty_state(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert "No submissions yet" in body


def test_app_page_empty_state_names_example_project(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert "example-project-mnist" in body


def test_app_page_empty_state_form_posts_to_loader(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert 'action="/aj/examples/example-project-mnist/load/"' in body


def test_app_page_renders_sdk_favicon(_home: Path) -> None:
    # Arrange
    # the shared favicon from `_branding_head.html` proves the
    # real `app_shell.html` resolved, not a stub.
    _home
    # Act
    body = _body()
    # Assert
    assert "scitex-favicon.svg" in body


def test_app_page_renders_main_landmark(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert "<main" in body


def test_app_page_lists_persisted_submission(_persisted: Path) -> None:
    # Arrange
    _persisted
    # Act
    body = _body()
    # Assert
    assert "sub_2026_10_19_aaaaaa" in body


def test_app_page_lists_persisted_verdict(_persisted: Path) -> None:
    # Arrange
    _persisted
    # Act
    body = _body()
    # Assert
    assert "accept" in body


def test_app_page_mounts_shared_app_header(_home: Path) -> None:
    # Arrange
    # shared SDK header row (server-rendered, scholar pattern) —
    # one row with the title span plus the picker slot.
    _home
    # Act
    body = _body()
    # Assert
    assert '<header class="stx-app-header">' in body


def test_app_page_header_shows_title(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert "SciTeX Agentic Journal" in body


def test_app_page_header_has_picker_slot(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert "stx-app-header__slot--project-selector" in body


def test_app_page_has_no_js_header_mount(_home: Path) -> None:
    # Arrange
    # the JS-mount div was the duplicated header — server markup only.
    _home
    # Act
    body = _body()
    # Assert
    assert "data-stx-app-header" not in body


def test_app_page_template_wires_picker_tag() -> None:
    # Arrange
    source = _template_source()
    # Act
    wired = "scitex_project_picker" in source
    # Assert
    assert wired


@pytest.fixture
def _projects(tmp_path: Path):
    # Arrange — real env-var swap (NM002-compliant): point the
    # standalone picker at a tmp projects folder with one project.
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_PROJECTS_DIR")
    root = tmp_path / "projects"
    (root / "example-project-mnist").mkdir(parents=True)
    os.environ["SCITEX_AGENTIC_JOURNAL_PROJECTS_DIR"] = str(root)
    try:
        yield root
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_PROJECTS_DIR", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_PROJECTS_DIR"] = original


def test_project_scope_lists_local_projects(_projects: Path) -> None:
    # Arrange
    _projects
    # Act
    body = json.loads(_client().get("/aj/api/projects").content)
    # Assert
    assert [p["id"] for p in body["projects"]] == ["example-project-mnist"]


def test_project_scope_post_remembers_project(_projects: Path) -> None:
    # Arrange
    _projects
    # Act
    body = json.loads(
        _client()
        .post(
            "/aj/api/projects",
            data=json.dumps({"id": "example-project-mnist"}),
            content_type="application/json",
        )
        .content
    )
    # Assert
    assert body["current"] == "example-project-mnist"


def test_app_page_accepts_project_param(_projects: Path) -> None:
    # Arrange
    _projects
    # Act
    response = _client().get("/aj/app/?project=example-project-mnist")
    # Assert
    assert response.status_code == 200


def test_app_page_has_no_leaf_h1(_home: Path) -> None:
    # Arrange
    _home
    # Act
    body = _body()
    # Assert
    assert "<h1" not in body


def test_app_page_has_no_template_comment_leak(_home: Path) -> None:
    # Arrange
    # Django only strips single-line {# #}; a multi-line block
    # would leak raw into the page (measured 2026-10-22: it did).
    _home
    # Act
    body = _body()
    # Assert
    assert "{#" not in body


def _template_source() -> str:
    # Arrange
    # contract anchor independent of rendering.
    from django.template import engines

    template = engines["django"].get_template("scitex_agentic_journal/app.html")
    return Path(template.template.origin.name).read_text(encoding="utf-8")


def test_app_page_template_extends_sdk_shell() -> None:
    # Arrange
    source = _template_source()
    # Act
    extends = '{% extends "scitex_sdk/app/app_shell.html" %}' in source
    # Assert
    assert extends


def test_app_page_template_fills_content_block() -> None:
    # Arrange
    source = _template_source()
    # Act
    fills = "{% block scitex_app_content %}" in source
    # Assert
    assert fills


def test_app_page_template_has_no_real_url_tags() -> None:
    # Arrange
    # prefix/namespace-agnostic: no real `{% url %}` tags (the
    # word only appears inside comments).
    source = _template_source()
    # Act
    code = _re.sub(r"\{#.*?#\}", "", source, flags=_re.S)
    code = _re.sub(
        r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}", "", code, flags=_re.S
    )
    # Assert
    assert "{% url " not in code


def test_app_page_route_reverses() -> None:
    # Arrange
    from django.urls import reverse

    # Act
    url = reverse("scitex_agentic_journal:app-page")
    # Assert
    assert url.endswith("/app/")
