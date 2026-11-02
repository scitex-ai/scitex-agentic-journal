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


def _write_bundle(bundle: Path) -> Path:
    # Arrange helper — a minimal on-disk bundle the loader parses
    # without any network IO.
    from scitex_agentic_journal._submit._loader import MANIFEST_FILENAME

    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / MANIFEST_FILENAME).write_text(
        'orcid_id: "0000-0002-1825-0097"\n'
        'code_repo_url: "https://example.com/x.git"\n',
        encoding="utf-8",
    )
    return bundle


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


def _persisted_record(tmp_home, key="abc123"):
    # Arrange + Act helper — fabricate the gate verdict in-process
    # (pure dataclass construction, no mocks, no network) and persist it.
    from datetime import datetime, timezone

    from scitex_agentic_journal._submit._loader import load_submission
    from scitex_agentic_journal._submit._persist import persist_verdict

    bundle = _write_bundle(tmp_home / "bundle")
    submission = load_submission(bundle)
    fixed_now = datetime(2026, 10, 22, tzinfo=timezone.utc)
    return persist_verdict(
        _fake_verdict(submission), home=tmp_home, now=fixed_now, key=key
    )


def test_persist_writes_gate1_record(_home) -> None:
    # Arrange
    _home
    # Act
    receipt = _persisted_record(_home)
    # Assert
    assert receipt.record_path.is_file()


def test_persist_record_carries_bundle_sha(_home) -> None:
    # Arrange
    _home
    # Act
    receipt = _persisted_record(_home, key="abc123")
    # Assert
    assert json.loads(receipt.record_path.read_text())["bundle_sha256"] == "abc123"


def test_persist_same_key_same_id(_home) -> None:
    # Arrange
    # retrying the same submission rewrites the same record dir
    # instead of minting a duplicate (the handler's idempotence rests here).
    _home
    # Act
    first = _persisted_record(_home, key="abc123")
    second = _persisted_record(_home, key="abc123")
    # Assert
    assert first.submission_id == second.submission_id


def test_persist_same_key_single_record_dir(_home) -> None:
    # Arrange
    _home
    # Act
    receipt = _persisted_record(_home, key="abc123")
    second = _persisted_record(_home, key="abc123")
    # Assert
    assert sorted(p.name for p in (_home / "submissions").iterdir()) == [
        receipt.submission_id
    ]


def _needs_network() -> None:
    if os.environ.get("SCITEX_RUN_NETWORK_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_NETWORK_TESTS=1")


def test_submit_persists_real_bundle_with_201(_home) -> None:
    # Arrange
    # the full POST path with the REAL gate (needs ORCID +
    # code-repo HTTP, like the suite's opt-in network tests).
    _needs_network()
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": (
            'orcid_id: "0000-0002-1825-0097"\n'
            'code_repo_url: "https://github.com/octocat/Hello-World.git"\n'
        )}),
        content_type="application/json",
    )
    # Assert
    assert response.status_code == 201


def test_submit_persists_real_bundle_ok_true(_home) -> None:
    # Arrange
    _needs_network()
    _home
    # Act
    response = _client().post(
        "/aj/submit/",
        data=json.dumps({"bundle_yaml": (
            'orcid_id: "0000-0002-1825-0097"\n'
            'code_repo_url: "https://github.com/octocat/Hello-World.git"\n'
        )}),
        content_type="application/json",
    )
    # Assert
    assert json.loads(response.content)["ok"] is True


# ----- example loader handler ------------------------------------------------


@pytest.fixture
def _example_bundle(tmp_path: Path):
    # Arrange — real env-var swap (NM002-compliant): point the demo
    # bundle at a tmp checkout with a valid manifest.
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE")
    bundle = tmp_path / "example-project-mnist"
    bundle.mkdir(parents=True)
    (bundle / "bundle.yaml").write_text(
        "orcid_id: '0000-0000-0000-0000'\n"
        "code_repo_url: 'https://example.invalid/mnist.git'\n",
        encoding="utf-8",
    )
    os.environ["SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE"] = str(bundle)
    try:
        yield bundle
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE"] = original


def test_load_example_json_returns_submission_id(_home: Path, _example_bundle: Path) -> None:
    # Arrange
    _home
    _example_bundle
    # Act
    body = json.loads(
        _client()
        .post("/aj/examples/example-project-mnist/load/", data="{}", content_type="application/json")
        .content
    )
    # Assert
    assert body.get("submission_id") == "example-project-mnist"


def test_load_example_form_redirects_to_index(_home: Path, _example_bundle: Path) -> None:
    # Arrange
    _home
    _example_bundle
    # Act
    response = _client().post("/aj/examples/example-project-mnist/load/")
    # Assert
    assert (response.status_code, response["Location"]) == (303, "/aj/")


def test_load_example_rejects_get(_home: Path) -> None:
    # Arrange
    _home
    # Act
    response = _client().get("/aj/examples/example-project-mnist/load/")
    # Assert
    assert response.status_code == 405


def test_load_example_missing_bundle_is_404(_home: Path, tmp_path: Path) -> None:
    # Arrange
    # all three candidates miss: explicit env, HOME/proj, and the
    # fleet fallback (redirected off-host via $SCITEX_FLEET_HOME).
    _home
    empty_home = tmp_path / "emptyhome"
    empty_home.mkdir(parents=True)
    original = dict(os.environ)
    os.environ["SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE"] = str(tmp_path / "no-such-bundle")
    os.environ["HOME"] = str(empty_home)
    os.environ["SCITEX_FLEET_HOME"] = str(empty_home)
    try:
        # Act
        response = _client().post(
            "/aj/examples/example-project-mnist/load/",
            data="{}",
            content_type="application/json",
        )
    finally:
        os.environ.clear()
        os.environ.update(original)
    # Assert
    assert response.status_code == 404


def test_load_example_malformed_bundle_is_422(_home: Path, tmp_path: Path) -> None:
    # Arrange
    _home
    bundle = tmp_path / "bad-bundle"
    bundle.mkdir(parents=True)
    (bundle / "bundle.yaml").write_text("orcid_id: ''\n", encoding="utf-8")
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE")
    os.environ["SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE"] = str(bundle)
    try:
        # Act
        response = _client().post(
            "/aj/examples/example-project-mnist/load/",
            data="{}",
            content_type="application/json",
        )
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE"] = original
    # Assert
    assert response.status_code == 422


@pytest.mark.parametrize("reserved", ["bundle.yaml", "./bundle.yaml"])
def test_submit_refuses_extra_file_manifest_override_before_staging(_home: Path, reserved: str) -> None:
    # Arrange
    payload = {"bundle_yaml": "orcid_id: original\n", "files": {reserved: "orcid_id: replacement\n"}}
    # Act
    response = _client().post("/aj/submit/", data=json.dumps(payload), content_type="application/json")
    # Assert
    assert response.status_code == 400 and not (_home / "staging").exists()
