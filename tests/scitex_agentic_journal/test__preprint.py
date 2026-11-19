"""create_preprint only snapshots admitted submissions; internal ID now, DOI later."""

from __future__ import annotations

import pytest
from scitex_agentic_journal._admission import run_admission
from scitex_agentic_journal._bundle import submit_bundle
from scitex_agentic_journal._preprint import (
    PreprintRefusedError,
    create_preprint,
    load_preprint,
)
from scitex_agentic_journal._records import RecordError
from tests.scitex_agentic_journal._contract_helpers import (
    OrcidServer,
    copy_reference_bundle,
    make_research_repo,
    point_bundle_at,
)


def _submitted(tmp_path, *, research=True):
    url, commit = make_research_repo(tmp_path / "repo", research=research)
    bundle = copy_reference_bundle(tmp_path / "bundle")
    point_bundle_at(bundle, url, commit)
    home = tmp_path / "home"
    sid = submit_bundle(bundle, home=home).submission_id
    with OrcidServer() as orcid:
        run_admission(sid, home=home, orcid_base_url=orcid)
    return sid, home


@pytest.fixture(scope="module")
def preprint(tmp_path_factory):
    sid, home = _submitted(tmp_path_factory.mktemp("preprint"))
    return create_preprint(sid, "v1.1.0", home=home), sid, home


def test_preprint_gets_an_internal_id(preprint):
    # Arrange
    record, _, _ = preprint
    # Act
    internal_id = record["internal_id"]
    # Assert
    assert internal_id.startswith("scitex-aj-")


def test_preprint_doi_is_unregistered_until_a_minter_runs(preprint):
    # Arrange
    record, _, _ = preprint
    # Act
    state = (record["doi"], record["doi_status"])
    # Assert
    assert state == (None, "unregistered")


def test_preprint_states_it_is_not_peer_reviewed(preprint):
    # Arrange
    record, _, _ = preprint
    # Act
    flag = record["peer_reviewed"]
    # Assert
    assert flag is False


def test_preprint_creation_is_idempotent_for_the_same_version(preprint):
    # Arrange
    record, sid, home = preprint
    # Act
    again = create_preprint(sid, "v1.1.0", home=home)
    # Assert
    assert again == load_preprint(sid, home=home) == record


def test_a_second_version_of_the_same_submission_is_refused(preprint):
    # Arrange
    _, sid, home = preprint
    # Act
    call = lambda: create_preprint(sid, "v1.2.0", home=home)
    # Assert
    with pytest.raises(PreprintRefusedError, match="new submission"):
        call()


def test_unadmitted_submission_cannot_become_a_preprint(tmp_path):
    # Arrange
    sid, home = _submitted(tmp_path, research=False)
    # Act
    call = lambda: create_preprint(sid, "v1.0.0", home=home)
    # Assert
    with pytest.raises(PreprintRefusedError, match="not admitted"):
        call()


def test_malformed_version_is_refused(preprint):
    # Arrange
    _, sid, home = preprint
    # Act
    call = lambda: create_preprint(sid, "latest", home=home)
    # Assert
    with pytest.raises(PreprintRefusedError, match="MAJOR.MINOR.PATCH"):
        call()


def test_dry_run_builds_the_record_without_writing_it(tmp_path):
    # Arrange
    sid, home = _submitted(tmp_path)
    create_preprint(sid, "v2.0.0", home=home, dry_run=True)
    # Act
    call = lambda: load_preprint(sid, home=home)  # noqa: E731
    # Assert
    with pytest.raises(RecordError, match="record not found"):
        call()
