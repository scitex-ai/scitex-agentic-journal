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
    expected_keys = {
        "app",
        "label",
        "title",
        "icon",
        "mount",
        "permissions",
        "version",
    }
    # Act
    body = load_manifest()
    # Assert
    assert expected_keys.issubset(body.keys())


def test_manifest_app_matches_dotted_app_name() -> None:
    # Arrange
    body = load_manifest()
    # Act
    name_in_manifest = body["app"]
    # Assert
    assert name_in_manifest == APP_NAME


def test_manifest_label_matches_app_label() -> None:
    # Arrange
    body = load_manifest()
    # Act
    label = body["label"]
    # Assert
    assert label == APP_LABEL


def test_manifest_mount_is_prefix() -> None:
    # Arrange
    body = load_manifest()
    # Act
    mount = body["mount"]
    # Assert
    assert mount.startswith("/")


def test_manifest_permissions_contains_admin() -> None:
    # Arrange
    body = load_manifest()
    # Act
    has_admin = "admin" in body["permissions"]
    # Assert
    assert has_admin is True


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
            "scitex_agentic_journal._django",
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


def test_handler_submit_returns_503_until_implemented() -> None:
    # Arrange
    from django.test import RequestFactory
    from scitex_agentic_journal._django.handlers import submit

    request = RequestFactory().post("/aj/submit")
    # Act
    response = submit(request)
    # Assert
    assert response.status_code == 503


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
