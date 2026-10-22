"""Tests for the submit handler — POST → Gate-1 → persist.

Covers :func:`handlers.submit` (POST → Gate-1 → persist) and the
real-record :func:`views.submissions_index` /
:func:`views.submission_detail`. Network-free: the failure path uses
a locally-rejected bundle (malformed ORCID, same shape as the CLI
test), and the success path monkeypatches the two ``_submit``
seams the handler calls.
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


# ----- submit handler -----------------------------------------------------


def test_submit_rejects_get_status(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().get("/aj/submit/")
    # Assert
    assert response.status_code == 405


def test_submit_rejects_get_ok_false(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().get("/aj/submit/")
    # Assert
    assert json.loads(response.content)["ok"] is False


def test_submit_rejects_invalid_json_with_400(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/", data="{not json", content_type="application/json"
    )
    # Assert
    assert response.status_code == 400


def test_submit_rejects_bundle_dir_path_status(_home: Path) -> None:
    # Arrange
    # caller-supplied filesystem paths are never read.
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_dir": "/tmp/elsewhere"}),
        content_type="application/json",
    )
    # Assert
    assert response.status_code == 400


def test_submit_rejects_bundle_dir_path_reason(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_dir": "/tmp/elsewhere"}),
        content_type="application/json",
    )
    # Assert
    assert "bundle_yaml" in json.loads(response.content)["reason"]


def test_submit_rejects_missing_bundle_yaml_status(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/", data=json.dumps({}), content_type="application/json"
    )
    # Assert
    assert response.status_code == 400


def test_submit_rejects_missing_bundle_yaml_reason(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/", data=json.dumps({}), content_type="application/json"
    )
    # Assert
    assert "bundle_yaml" in json.loads(response.content)["reason"]


def test_submit_rejects_absolute_files_key_with_400(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": "orcid_id: x\n", "files": {"/etc/passwd": "x"}}),
        content_type="application/json",
    )
    # Assert
    assert response.status_code == 400


def test_submit_rejects_dotdot_files_key_with_400(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps(
            {"bundle_yaml": "orcid_id: x\n", "files": {"../escape": "x"}}
        ),
        content_type="application/json",
    )
    # Assert
    assert response.status_code == 400


def _bad_orcid_yaml() -> str:
    return 'orcid_id: "not-an-orcid"\ncode_repo_url: "https://example.com/x.git"\n'


def test_submit_rejects_malformed_orcid_status(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": _bad_orcid_yaml()}),
        content_type="application/json",
    )
    # Assert
    assert response.status_code == 422


def test_submit_rejects_malformed_orcid_ok_false(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": _bad_orcid_yaml()}),
        content_type="application/json",
    )
    # Assert
    assert json.loads(response.content)["ok"] is False


def test_submit_rejects_malformed_orcid_check(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": _bad_orcid_yaml()}),
        content_type="application/json",
    )
    # Assert
    assert json.loads(response.content).get("check") == "orcid"


def test_submit_rejects_non_mapping_bundle_status(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": "- just\n- a\n- list\n"}),
        content_type="application/json",
    )
    # Assert
    assert response.status_code == 422


def test_submit_rejects_non_mapping_bundle_ok_false(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": "- just\n- a\n- list\n"}),
        content_type="application/json",
    )
    # Assert
    assert json.loads(response.content)["ok"] is False


def test_submit_rejects_absolute_clew_path_status(_home: Path) -> None:
    # Arrange
    _home
    yaml_text = (
        'orcid_id: "0000-0002-1825-0097"\n'
        'code_repo_url: "https://example.com/x.git"\n'
        'clew_project_path: "/etc"\n'
    )
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": yaml_text}),
        content_type="application/json",
    )
    # Assert
    assert response.status_code == 422


def test_submit_rejects_absolute_clew_path_reason(_home: Path) -> None:
    # Arrange
    _home
    yaml_text = (
        'orcid_id: "0000-0002-1825-0097"\n'
        'code_repo_url: "https://example.com/x.git"\n'
        'clew_project_path: "/etc"\n'
    )
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": yaml_text}),
        content_type="application/json",
    )
    # Assert
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


@pytest.fixture
def _gate1_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    # stub the network-bound gate with a fixed verdict.
    import scitex_agentic_journal._submit as _submit_mod

    monkeypatch.setattr(
        _submit_mod, "run_gate1", lambda submission: _fake_verdict(submission)
    )


def _post_good() -> dict:
    # Act
    # submit the known-good bundle.
    import json as _json

    response = _client().post(
        "/aj/submit/",
        data=_json.dumps({"bundle_yaml": _good_yaml()}),
        content_type="application/json",
    )
    return response


def test_submit_persists_status(
    _home: Path, _gate1_ok: None
) -> None:
    # Arrange
    _home
    _gate1_ok
    # Act
    response = _post_good()
    # Assert
    assert response.status_code == 201


def test_submit_persists_ok_true(
    _home: Path, _gate1_ok: None
) -> None:
    # Arrange
    _home
    _gate1_ok
    # Act
    response = _post_good()
    # Assert
    assert json.loads(response.content)["ok"] is True


def test_submit_persists_gate1_record(
    _home: Path, _gate1_ok: None
) -> None:
    # Arrange
    _home
    _gate1_ok
    # Act
    body = json.loads(_post_good().content)
    # Assert
    assert (_home / "submissions" / body["submission_id"] / "gate1.json").is_file()


def test_submit_persists_bundle_sha(
    _home: Path, _gate1_ok: None
) -> None:
    # Arrange
    _home
    _gate1_ok
    # Act
    body = json.loads(_post_good().content)
    # Assert
    assert json.loads(
        (_home / "submissions" / body["submission_id"] / "gate1.json").read_text()
    )["bundle_sha256"]


def test_submit_double_submit_same_id(
    _home: Path, _gate1_ok: None
) -> None:
    # Arrange
    _home
    _gate1_ok
    client = _client()
    payload = json.dumps({"bundle_yaml": _good_yaml()})
    # Act
    first = json.loads(
        client.post("/aj/submit/", data=payload, content_type="application/json").content
    )
    second = json.loads(
        client.post("/aj/submit/", data=payload, content_type="application/json").content
    )
    # Assert
    assert first["submission_id"] == second["submission_id"]


def test_submit_double_submit_single_record(
    _home: Path, _gate1_ok: None
) -> None:
    # Arrange
    _home
    _gate1_ok
    client = _client()
    payload = json.dumps({"bundle_yaml": _good_yaml()})
    # Act
    first = json.loads(
        client.post("/aj/submit/", data=payload, content_type="application/json").content
    )
    client.post("/aj/submit/", data=payload, content_type="application/json")
    # Assert
    assert sorted(p.name for p in (_home / "submissions").iterdir()) == [
        first["submission_id"]
    ]


def test_submit_cleans_up_staging(
    _home: Path, _gate1_ok: None
) -> None:
    # Arrange
    _home
    _gate1_ok
    # Act
    _post_good()
    staging = _home / "staging"
    # Assert
    assert not staging.exists() or list(staging.iterdir()) == []


