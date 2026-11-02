"""Unit tests for :mod:`scitex_agentic_journal._django` — Django-free where possible."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_agentic_journal._django import (
    APP_LABEL,
    APP_MANIFEST_PATH,
    APP_NAME,
    load_manifest,
)

# ----- Manifest (no Django) -------------------------------------------------


def test_app_name_is_dotted_import_path() -> None:
    # Arrange
    expected = "scitex_agentic_journal._django"
    # Act
    name = APP_NAME
    # Assert
    assert name == expected


def test_app_label_is_python_identifier() -> None:
    # Arrange
    label = APP_LABEL
    # Act
    is_id = label.isidentifier()
    # Assert
    assert is_id is True


def test_manifest_path_points_to_manifest_json() -> None:
    # Arrange
    path = APP_MANIFEST_PATH
    # Act
    name = path.name
    # Assert
    assert name == "manifest.json"


def test_manifest_loads_with_required_keys() -> None:
    # Arrange
    # the SDK's required six (MANIFEST_REQUIRED_KEYS).
    expected_keys = {
        "name",
        "slug",
        "label",
        "pip_package",
        "icon",
        "license",
    }
    # Act
    body = load_manifest()
    # Assert
    assert expected_keys.issubset(body.keys())


def test_manifest_declares_no_version() -> None:
    # Arrange
    # hand-written `version` is FORBIDDEN (drifts from the
    # installed dist; the version derives from `pip_package`).
    # Act
    body = load_manifest()
    # Assert
    assert "version" not in body


def test_manifest_scope_is_closed_enum() -> None:
    # Arrange
    # Act
    body = load_manifest()
    # Assert
    assert body.get("scope", "user") in {"user", "project"}


def test_manifest_pip_package_is_this_dist() -> None:
    # Arrange
    # Act
    body = load_manifest()
    # Assert
    assert body["pip_package"] == "scitex-agentic-journal"


def test_manifest_name_uses_app_suffix() -> None:
    # Arrange
    # SDK advisory: `name` ends with `_app` / `-app`.
    # Act
    body = load_manifest()
    # Assert
    assert body["name"].endswith(("_app", "-app"))


def test_manifest_rejects_version_key(tmp_path: Path) -> None:
    # Arrange
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "name": "x_app",
                "slug": "x",
                "label": "X",
                "pip_package": "x",
                "icon": "x",
                "license": "x",
                "version": "0.0.0",
            }
        )
    )
    # Act
    # Assert
    with pytest.raises(ValueError, match="version"):
        load_manifest(bad)


def test_manifest_rejects_unknown_scope(tmp_path: Path) -> None:
    # Arrange
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "name": "x_app",
                "slug": "x",
                "label": "X",
                "pip_package": "x",
                "icon": "x",
                "license": "x",
                "scope": "galaxy",
            }
        )
    )
    # Act
    # Assert
    with pytest.raises(ValueError, match="scope"):
        load_manifest(bad)


def test_manifest_matches_sdk_validator_when_sdk_present() -> None:
    # Arrange
    # the SDK's own validator is authoritative; our mirror
    # must agree with it wherever the SDK is installed.
    scitex_sdk = pytest.importorskip("scitex_sdk.app.appmaker._validate._manifest")
    # Act
    errors = scitex_sdk.validate_manifest(APP_MANIFEST_PATH.parent)
    # Assert
    assert errors == []


def test_manifest_missing_file_raises(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "nope.json"
    # Act
    # Assert
    with pytest.raises(FileNotFoundError):
        load_manifest(missing)


def test_manifest_missing_required_key_raises(tmp_path: Path) -> None:
    # Arrange
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"app": "x"}))
    # Act
    # Assert
    with pytest.raises(KeyError):
        load_manifest(bad)


# ----- Django app config + URLs (requires Django, but no DB) ---------------


@pytest.fixture(autouse=True, scope="module")
def _configure_django() -> None:
    """Minimal Django settings so ``apps`` / ``urls`` / ``views`` import.

    No database, no auth backends; just enough to let
    ``django.urls.reverse`` work and ``AppConfig.ready`` run the
    manifest validation.
    """
    import django
    from django.conf import settings

    if settings.configured:
        return
    settings.configure(
        DEBUG=False,
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


def test_app_config_label_matches_app_label() -> None:
    # Arrange
    from scitex_agentic_journal._django.apps import (
        SciTeXAgenticJournalConfig,
    )

    # Act
    label = SciTeXAgenticJournalConfig.label
    # Assert
    assert label == APP_LABEL


def test_app_config_name_matches_app_name() -> None:
    # Arrange
    from scitex_agentic_journal._django.apps import (
        SciTeXAgenticJournalConfig,
    )

    # Act
    name = SciTeXAgenticJournalConfig.name
    # Assert
    assert name == APP_NAME


def test_app_config_uses_required_sdk_base() -> None:
    # Arrange: the SDK is a required package dependency.
    from scitex_sdk.app.embed import ScitexAppConfig

    from scitex_agentic_journal._django.apps import SciTeXAgenticJournalConfig

    # Act
    uses_sdk = issubclass(SciTeXAgenticJournalConfig, ScitexAppConfig)
    # Assert: a plain Django fallback loses the shared app contract.
    assert uses_sdk


def test_urls_reverse_submission_detail() -> None:
    # Arrange
    from django.urls import reverse

    # Act
    url = reverse(
        "scitex_agentic_journal:submission-detail",
        kwargs={"submission_id": "s-001"},
    )
    # Assert
    assert "s-001" in url


def test_urls_reverse_review_record() -> None:
    # Arrange
    from django.urls import reverse

    # Act
    url = reverse(
        "scitex_agentic_journal:review-record",
        kwargs={"submission_id": "s-001"},
    )
    # Assert
    assert url.endswith("/review/")


def test_urls_reverse_decision_record() -> None:
    # Arrange
    from django.urls import reverse

    # Act
    url = reverse(
        "scitex_agentic_journal:decision-record",
        kwargs={"submission_id": "s-001"},
    )
    # Assert
    assert url.endswith("/decision/")


def test_handler_submit_rejects_empty_post_without_traceback() -> None:
    # Arrange
    # POST with no JSON body must 400, never 503, never raise.
    from django.test import RequestFactory

    from scitex_agentic_journal._django.handlers import submit

    request = RequestFactory().post("/aj/submit/")
    # Act
    response = submit(request)
    # Assert
    assert response.status_code == 400


def test_view_submissions_index_returns_placeholder_flag() -> None:
    # Arrange
    from django.test import RequestFactory

    from scitex_agentic_journal._django.views import submissions_index

    request = RequestFactory().get("/")
    # Act
    response = submissions_index(request)
    body = json.loads(response.content)
    # Assert
    assert body["placeholder"] is True


def _root_response():
    # Arrange + Act — the app URL must render the human GUI; raw JSON at
    # the root is what the operator flagged (screenshot 20261020).
    from django.test import Client
    from django.urls import reverse

    url = reverse("scitex_agentic_journal:index")
    return url, Client().get(url)


def test_root_url_resolves_to_app() -> None:
    # Arrange
    url, _ = _root_response()
    # Act
    path = url
    # Assert
    assert path == "/aj/"


def test_root_url_status_ok() -> None:
    # Arrange
    _, response = _root_response()
    # Act
    code = response.status_code
    # Assert
    assert code == 200


def test_root_url_serves_html() -> None:
    # Arrange
    _, response = _root_response()
    # Act
    content_type = response["Content-Type"]
    # Assert
    assert content_type.startswith("text/html")


def test_root_url_brands_journal() -> None:
    # Arrange
    _, response = _root_response()
    # Act
    content = response.content
    # Assert
    assert b"Agentic Journal" in content
