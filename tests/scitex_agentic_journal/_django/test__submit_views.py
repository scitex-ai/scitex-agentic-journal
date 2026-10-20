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
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("SCITEX_AGENTIC_JOURNAL_HOME", str(home))
    return home


def _client():
    from django.test import Client

    return Client()


# ----- read surface -------------------------------------------------------


def test_index_empty_home_is_placeholder(_home: Path) -> None:
    body = json.loads(_client().get("/aj/archive/").content)
    assert body["submissions"] == []
    assert body["placeholder"] is True


def test_index_lists_persisted_submission(_home: Path) -> None:
    sub = _home / "submissions" / "sub_2026_10_19_aaaaaa"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(
        json.dumps({"submission_id": "sub_2026_10_19_aaaaaa", "gate": "gate1"}),
        encoding="utf-8",
    )
    body = json.loads(_client().get("/aj/archive/").content)
    assert body["placeholder"] is False
    assert [r["submission_id"] for r in body["submissions"]] == [
        "sub_2026_10_19_aaaaaa"
    ]


def test_detail_unknown_is_404(_home: Path) -> None:
    response = _client().get("/aj/submissions/nope/")
    assert response.status_code == 404
    assert json.loads(response.content)["found"] is False


def test_detail_known_returns_summary(_home: Path) -> None:
    sub = _home / "submissions" / "sub_1"
    sub.mkdir(parents=True)
    (sub / "gate1.json").write_text(json.dumps({"gate": "gate1"}), encoding="utf-8")
    (sub / "decision.json").write_text(
        json.dumps({"record": {"verdict": "accept"}}), encoding="utf-8"
    )
    response = _client().get("/aj/submissions/sub_1/")
    assert response.status_code == 200
    body = json.loads(response.content)
    assert body["found"] is True
    assert body["verdict"] == "accept"


# ----- submit handler -----------------------------------------------------


def test_submit_rejects_get_with_405(_home: Path) -> None:
    response = _client().get("/aj/submit/")
    assert response.status_code == 405
    assert json.loads(response.content)["ok"] is False


def test_submit_rejects_invalid_json_with_400(_home: Path) -> None:
    response = _client().post(
        "/aj/submit/", data="{not json", content_type="application/json"
    )
    assert response.status_code == 400


def test_submit_rejects_bundle_dir_path_with_400(_home: Path) -> None:
    # Caller-supplied filesystem paths are never read (hub SITE-1 rule).
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_dir": "/tmp/elsewhere"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "bundle_yaml" in json.loads(response.content)["reason"]


def test_submit_rejects_missing_bundle_yaml_with_400(_home: Path) -> None:
    response = _client().post(
        "/aj/submit/", data=json.dumps({}), content_type="application/json"
    )
    assert response.status_code == 400
    assert "bundle_yaml" in json.loads(response.content)["reason"]


def test_submit_rejects_absolute_files_key_with_400(_home: Path) -> None:
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": "orcid_id: x\n", "files": {"/etc/passwd": "x"}}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_submit_rejects_dotdot_files_key_with_400(_home: Path) -> None:
    response = _client().post(
        "/aj/submit/",
        data=json.dumps(
            {"bundle_yaml": "orcid_id: x\n", "files": {"../escape": "x"}}
        ),
        content_type="application/json",
    )
    assert response.status_code == 400


def _bad_orcid_yaml() -> str:
    return 'orcid_id: "not-an-orcid"\ncode_repo_url: "https://example.com/x.git"\n'


def test_submit_rejects_malformed_orcid_with_422(_home: Path) -> None:
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": _bad_orcid_yaml()}),
        content_type="application/json",
    )
    assert response.status_code == 422
    body = json.loads(response.content)
    assert body["ok"] is False
    assert body.get("check") == "orcid"


def test_submit_rejects_non_mapping_bundle_with_422(_home: Path) -> None:
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": "- just\n- a\n- list\n"}),
        content_type="application/json",
    )
    assert response.status_code == 422
    assert json.loads(response.content)["ok"] is False


def test_submit_rejects_absolute_clew_path_with_422(_home: Path) -> None:
    yaml_text = (
        'orcid_id: "0000-0002-1825-0097"\n'
        'code_repo_url: "https://example.com/x.git"\n'
        'clew_project_path: "/etc"\n'
    )
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": yaml_text}),
        content_type="application/json",
    )
    assert response.status_code == 422
    assert "clew_project_path" in json.loads(response.content)["reason"]


def _fake_verdict(submission):
    from scitex_agentic_journal._gate1 import ClewVerification, OrcidRecord
    from scitex_agentic_journal._submit._orchestrate import Gate1Verdict

    return Gate1Verdict(
        submission=submission,
        orcid_record=OrcidRecord(
            orcid_id=submission.orcid_id,
            given_name="Ada",
            family_name="Lovelace",
            credit_name=None,
        ),
        code_repo_head_commit="0" * 40,
        code_repo_head_subject="fake",
        clew_verification=ClewVerification(
            project_dir=submission.clew_project_dir,
            green_claims=("c1",),
            red_claims=(),
            total_claims=1,
            raw_stdout="fake",
        ),
    )


def _good_yaml() -> str:
    return (
        'orcid_id: "0000-0002-1825-0097"\n'
        'code_repo_url: "https://example.com/x.git"\n'
    )


def test_submit_persists_and_returns_201(
    _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scitex_agentic_journal._submit as _submit_mod

    monkeypatch.setattr(
        _submit_mod, "run_gate1", lambda submission: _fake_verdict(submission)
    )
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": _good_yaml()}),
        content_type="application/json",
    )
    assert response.status_code == 201
    body = json.loads(response.content)
    assert body["ok"] is True
    record = _home / "submissions" / body["submission_id"] / "gate1.json"
    assert record.is_file()
    assert json.loads(record.read_text())["bundle_sha256"]


def test_submit_double_submit_is_idempotent(
    _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scitex_agentic_journal._submit as _submit_mod

    monkeypatch.setattr(
        _submit_mod, "run_gate1", lambda submission: _fake_verdict(submission)
    )
    client = _client()
    payload = json.dumps({"bundle_yaml": _good_yaml()})
    first = json.loads(
        client.post("/aj/submit/", data=payload, content_type="application/json").content
    )
    second = json.loads(
        client.post("/aj/submit/", data=payload, content_type="application/json").content
    )
    assert first["submission_id"] == second["submission_id"]
    assert sorted(p.name for p in (_home / "submissions").iterdir()) == [
        first["submission_id"]
    ]


def test_submit_cleans_up_staging(
    _home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scitex_agentic_journal._submit as _submit_mod

    monkeypatch.setattr(
        _submit_mod, "run_gate1", lambda submission: _fake_verdict(submission)
    )
    _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": _good_yaml()}),
        content_type="application/json",
    )
    staging = _home / "staging"
    assert not staging.exists() or list(staging.iterdir()) == []


# ----- hub mounting contract ----------------------------------------------


def test_urlconf_stays_flat_for_hub_login_required_gating() -> None:
    """Hub wraps every URLPattern; a nested include() would slip the gate."""
    from django.urls import URLPattern

    from scitex_agentic_journal._django import urls as leaf_urls

    assert leaf_urls.urlpatterns, "leaf urlconf must not be empty"
    for entry in leaf_urls.urlpatterns:
        assert isinstance(entry, URLPattern), (
            f"hub cannot gate {entry!r}: keep the leaf urlconf flat "
            "(no include()/URLResolver)."
        )


def test_submit_route_reverses() -> None:
    from django.urls import reverse

    url = reverse("scitex_agentic_journal:submit")
    assert url.endswith("/submit/")
