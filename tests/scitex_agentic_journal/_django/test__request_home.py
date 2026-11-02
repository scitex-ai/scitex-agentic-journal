"""Real user-provider, authentication and filesystem-isolation regressions."""

import json

import pytest
from django.test import RequestFactory, override_settings

from tests.scitex_agentic_journal._django.test_views import _configure_django  # noqa: F401

PROVIDER = __name__ + ".user_home"


def user_home(request):
    """A fixture host capability: authenticated identity, actual temp filesystem."""
    return request.fixture_users / request.user.username


def unavailable_home(request):
    return None


def denied_home(request):
    from django.core.exceptions import PermissionDenied

    raise PermissionDenied("Host rejects this identity")


def _request(root, username="alice"):
    from django.contrib.auth.models import AnonymousUser, User

    request = RequestFactory().get("/apps/journal/archive/")
    request.fixture_users = root
    request.user = User(username=username) if username else AnonymousUser()
    return request


def _record(root, username, kind, value):
    directory = root / username / ".scitex/agentic-journal/submissions/sub_owned"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{kind}.json").write_text(json.dumps(value))


def test_provider_resolution_creates_no_files(tmp_path):
    # Arrange
    from scitex_agentic_journal._django._request_home import request_home

    request = _request(tmp_path)
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        result = request_home(request)
    # Assert
    assert result == tmp_path / "alice/.scitex/agentic-journal" and not list(
        tmp_path.iterdir()
    )


@pytest.mark.parametrize(
    "view_name,kind",
    [("review_record_view", "review"), ("decision_record_view", "decision")],
)
def test_each_authenticated_user_reads_only_own_record(tmp_path, view_name, kind):
    # Arrange
    from scitex_agentic_journal._django import views

    _record(tmp_path, "alice", kind, {"record": {"owner": "alice"}})
    _record(tmp_path, "bob", kind, {"record": {"owner": "bob"}})
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        alice = getattr(views, view_name)(_request(tmp_path), "sub_owned")
        bob = getattr(views, view_name)(_request(tmp_path, "bob"), "sub_owned")
    # Assert
    assert (
        json.loads(alice.content)[f"{kind}_record"]
        != json.loads(bob.content)[f"{kind}_record"]
    )


def test_anonymous_cannot_read_mounted_archive(tmp_path):
    # Arrange
    from scitex_agentic_journal._django.views import submissions_index

    request = _request(tmp_path, "")
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        response = submissions_index(request)
    # Assert
    assert response.status_code == 403


@pytest.mark.parametrize(
    "provider",
    [
        __name__ + ".unavailable_home",
        __name__ + ".denied_home",
        "missing.module.provider",
        "",
    ],
)
def test_mounted_provider_failure_never_falls_back(tmp_path, provider):
    # Arrange
    from scitex_agentic_journal._django.views import submissions_index

    request = _request(tmp_path)
    # Act
    with override_settings(
        SCITEX_USER_HOME_PROVIDER=provider, SCITEX_APP_MODE="mounted"
    ):
        response = submissions_index(request)
    # Assert
    assert response.status_code == 503 and not list(tmp_path.iterdir())


def test_archive_alias_escape_is_rejected(tmp_path):
    # Arrange
    from scitex_agentic_journal._django.views import submissions_index

    home = tmp_path / "alice"
    home.mkdir()
    outside = tmp_path / "bob"
    outside.mkdir()
    (home / ".scitex").symlink_to(outside, target_is_directory=True)
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        response = submissions_index(_request(tmp_path))
    # Assert
    assert response.status_code == 503


@pytest.mark.parametrize(
    "identifier", ["../bob", "/etc/passwd", "sub_owned/../../bob", ".", "", "x\\y"]
)
def test_record_id_traversal_is_not_a_path(tmp_path, identifier):
    # Arrange
    from scitex_agentic_journal._django.views import review_record_view

    request = _request(tmp_path)
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        response = review_record_view(request, identifier)
    # Assert
    assert response.status_code == 404


def test_record_file_alias_is_not_followed(tmp_path):
    # Arrange
    from scitex_agentic_journal._django.views import review_record_view

    _record(tmp_path, "alice", "gate1", {"gate": "gate1"})
    _record(tmp_path, "bob", "review", {"record": {"private": "bob"}})
    base = tmp_path / "alice/.scitex/agentic-journal/submissions/sub_owned"
    (base / "review.json").symlink_to(
        tmp_path / "bob/.scitex/agentic-journal/submissions/sub_owned/review.json"
    )
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        response = review_record_view(_request(tmp_path), "sub_owned")
    # Assert
    assert response.status_code == 404


def test_portal_renders_real_review_with_escaped_record_content(tmp_path):
    # Arrange
    from scitex_agentic_journal._django.views import app_page

    _record(
        tmp_path,
        "alice",
        "review",
        {
            "record": {
                "adapter": "<script>not executable</script>",
                "rubric_version": "r7",
            }
        },
    )
    request = _request(tmp_path)
    request.GET = request.GET.copy()
    request.GET.update({"section": "review", "submission": "sub_owned"})
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        response = app_page(request)
    body = response.content.decode()
    # Assert
    assert (
        response.status_code == 200
        and "&lt;script&gt;not executable&lt;/script&gt;" in body
        and "<script>not executable</script>" not in body
        and "r7" in body
    )


def test_review_page_does_not_invent_missing_assessments(tmp_path):
    # Arrange
    from scitex_agentic_journal._django.views import app_page

    _record(tmp_path, "alice", "gate1", {"gate": "gate1"})
    request = _request(tmp_path)
    request.GET = request.GET.copy()
    request.GET.update({"section": "review", "submission": "sub_owned"})
    # Act
    with override_settings(SCITEX_USER_HOME_PROVIDER=PROVIDER):
        response = app_page(request)
    body = response.content.decode()
    # Assert
    assert (
        response.status_code == 200
        and "No review record has been written" in body
        and "No decision record has been written" in body
    )


class UserOnlyProjectProvider:
    """A real filesystem-backed host preference with a user-only app view."""

    def list_projects(self, request):
        from scitex_sdk.ui.project_scope import ProjectEntry

        return [
            ProjectEntry(
                id="alice/paper",
                name="Remembered paper",
                disabled=True,
                disabled_reason="This app works with your personal archive.",
            )
        ]

    def last_visited(self, request):
        return json.loads(request.fixture_profile.read_text())["project"]

    def current_scope(self, request):
        # The remembered project is unsupported by this user-only app. The
        # host truthfully leaves its committed app selection unspecified.
        return None

    def remember(self, request, project_id):
        request.fixture_profile.write_text(json.dumps({"project": project_id}))

    def remember_scope(self, request, selection):
        request.fixture_profile.write_text(
            json.dumps({"scope": selection.scope, "project": selection.id})
        )


def test_explicit_user_view_preserves_host_project_and_unselected_protocol(tmp_path):
    # Arrange
    from scitex_sdk.ui.project_scope import scoped_project_listing_view

    from scitex_agentic_journal._django.views import app_page

    request = _request(tmp_path)
    request.fixture_profile = tmp_path / "host-profile.json"
    original = '{"project":"alice/paper"}'
    request.fixture_profile.write_text(original)
    # Act
    with override_settings(
        SCITEX_USER_HOME_PROVIDER=PROVIDER,
        SCITEX_PROJECT_PROVIDER=__name__ + ".UserOnlyProjectProvider",
        SCITEX_PROJECT_PROVIDER_URL="/fixture/projects/",
    ):
        response = app_page(request)
        provider_response = scoped_project_listing_view(UserOnlyProjectProvider())(
            request
        )
    body = response.content.decode()
    protocol = json.loads(provider_response.content)
    # Assert
    assert (
        response.status_code == 200
        and 'data-view-scope="user"' in body
        and 'data-view-project=""' in body
        and "data-current-scope=" not in body
        and protocol["current"] is None
        and "current_scope" not in protocol
        and protocol["projects"][0]["disabled"] is True
        and request.fixture_profile.read_text() == original
    )
