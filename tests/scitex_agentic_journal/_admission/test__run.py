"""run_admission end to end: real git repo, real scitex-dev lint, local ORCID HTTP.

Nothing is mocked. The repository is a real git repo on disk, the lint is
scitex-dev's own CLI run as a subprocess, and ORCID answers over a real
local HTTP server from the Gate-1 fixture records.
"""

from __future__ import annotations

import pytest
from scitex_agentic_journal._admission import load_admission, run_admission
from scitex_agentic_journal._bundle import submit_bundle

from tests.scitex_agentic_journal._contract_helpers import (
    OrcidServer,
    copy_reference_bundle,
    make_research_repo,
    point_bundle_at,
)


def _admit(tmp_path, *, research=True, **manifest_changes):
    url, commit = make_research_repo(tmp_path / "repo", research=research)
    bundle = copy_reference_bundle(tmp_path / "bundle")
    point_bundle_at(bundle, url, commit, **manifest_changes)
    home = tmp_path / "home"
    sid = submit_bundle(bundle, home=home).submission_id
    with OrcidServer() as orcid:
        record = run_admission(sid, home=home, orcid_base_url=orcid, allow_local_repositories=True)
    return record, sid, home


def _check(record, name):
    return next(c for c in record["checks"] if c["check"] == name)


@pytest.fixture(scope="module")
def admitted(tmp_path_factory):
    return _admit(tmp_path_factory.mktemp("admitted"))


def test_conforming_submission_is_admitted(admitted):
    # Arrange
    record, _, _ = admitted
    # Act
    verdict = record["admitted"]
    # Assert
    assert verdict is True, record["blocking"]


def test_orcid_check_resolves_the_submitter(admitted):
    # Arrange
    record, _, _ = admitted
    # Act
    check = _check(record, "orcid")
    # Assert
    assert check["status"] == "passed"


def test_scitex_form_check_runs_the_real_lint(admitted):
    # Arrange
    record, _, _ = admitted
    # Act
    check = _check(record, "scitex-form")
    # Assert
    assert check["details"]["all_rules_ran"] is True


def test_clew_reverify_is_recorded_as_not_run_with_a_reason(admitted):
    # Arrange
    record, _, _ = admitted
    # Act
    check = _check(record, "clew-reverify")
    # Assert
    assert check["status"] == "not-run" and "host store" in check["reason"]


def test_reproduction_is_not_run_without_an_isolated_executor(admitted):
    # Arrange
    record, _, _ = admitted
    # Act
    check = _check(record, "reproduction")
    # Assert
    assert check["status"] == "not-run"


def test_admission_record_is_persisted(admitted):
    # Arrange
    record, sid, home = admitted
    # Act
    stored = load_admission(sid, home=home)
    # Assert
    assert stored == record


def test_project_not_declared_research_is_not_admitted(tmp_path):
    # Arrange
    record, _, _ = _admit(tmp_path, research=False)
    # Act
    blocking = record["blocking"]
    # Assert
    assert blocking == ["scitex-form"]


def test_unsupported_main_claim_blocks_admission(tmp_path):
    # Arrange
    record, _, _ = _admit(tmp_path, main_claims=["auc", "n_rows"])
    # Act
    check = _check(record, "main-claims-evidence")
    # Assert
    assert check["details"]["not_supported"].keys() == {"n_rows"}


def test_unreachable_repository_blocks_admission(tmp_path):
    # Arrange
    bundle = copy_reference_bundle(tmp_path / "bundle")
    point_bundle_at(bundle, str(tmp_path / "no-such-repo"), "0" * 40)
    home = tmp_path / "home"
    sid = submit_bundle(bundle, home=home).submission_id
    # Act
    with OrcidServer() as orcid:
        record = run_admission(sid, home=home, orcid_base_url=orcid, allow_local_repositories=True)
    # Assert
    assert set(record["blocking"]) == {"repository", "scitex-form"}


def test_unknown_submitter_orcid_blocks_admission(tmp_path):
    # Arrange
    record, _, _ = _admit(tmp_path, submitter_orcid="0000-0001-5109-3700")
    # Act
    check = _check(record, "orcid")
    # Assert
    assert check["status"] == "failed"


def test_non_https_repository_is_refused_by_default(tmp_path):
    # Arrange
    url, commit = make_research_repo(tmp_path / "repo")
    bundle = copy_reference_bundle(tmp_path / "bundle")
    point_bundle_at(bundle, url, commit)
    home = tmp_path / "home"
    sid = submit_bundle(bundle, home=home).submission_id
    # Act
    with OrcidServer() as orcid:
        record = run_admission(sid, home=home, orcid_base_url=orcid)
    # Assert
    assert "not https://" in _check(record, "repository")["reason"]


def test_option_like_repository_url_is_never_passed_as_a_git_option(tmp_path):
    # Arrange
    bundle = copy_reference_bundle(tmp_path / "bundle")
    point_bundle_at(bundle, "--upload-pack=touch " + str(tmp_path / "pwned"), "0" * 40)
    home = tmp_path / "home"
    sid = submit_bundle(bundle, home=home).submission_id
    # Act
    with OrcidServer() as orcid:
        run_admission(sid, home=home, orcid_base_url=orcid, allow_local_repositories=True)
    # Assert
    assert not (tmp_path / "pwned").exists()

