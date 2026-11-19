"""Review ingestion from any source, validated against the submission's evidence."""

from __future__ import annotations

import copy

import pytest
from scitex_agentic_journal._admission import run_admission
from scitex_agentic_journal._bundle import submit_bundle
from scitex_agentic_journal._ingest import (
    ReviewRejectedError,
    file_review,
    list_reviews,
    load_findings,
)
from scitex_agentic_journal._preprint import create_preprint

from tests.scitex_agentic_journal._contract_helpers import (
    TEST_ORCID,
    OrcidServer,
    copy_reference_bundle,
    make_research_repo,
    point_bundle_at,
)

HUMAN = {
    "kind": "human",
    "identity": {"orcid": "0000-0001-2345-6789", "name": "A. Reviewer"},
    "declared_independence": {"not_an_author": True, "saw_author_materials": False},
    "disclosure": "blind",
}
SERVICE = {
    "kind": "external-service",
    "identity": {
        "service": "example-review-service",
        "service_version": "2.1",
        "model": {"provider": "example", "name": "reviewer-large"},
    },
    "declared_independence": {"not_an_author": True, "saw_author_materials": False},
    "disclosure": "model-family",
}


def _report(sid, **extra):
    report = {
        "schema": "scitex-agentic-journal.review-report",
        "schema_version": "1.0",
        "submission_id": sid,
        "claim_findings": [
            {
                "claim_id": "n_rows",
                "verdict": "not-supported",
                "graph_nodes": ["o"],
                "severity": "major",
                "dimension": "scientific-validity",
                "comment": "The stated n differs from the results file.",
            },
            {
                "claim_id": "auc",
                "verdict": "supported",
                "severity": "none",
                "comment": "Matches the recorded run.",
            },
        ],
        "general_findings": [
            {
                "location": "Results, line 7",
                "severity": "minor",
                "dimension": "clarity",
                "comment": "The room temperature sentence is not tied to any data.",
            },
        ],
        "recommendation": "major-revision",
        "confidence": "medium",
        "summary": "One main number is inconsistent with its source.",
    }
    report.update(extra)
    return report


@pytest.fixture(scope="module")
def preprint(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ingest")
    url, commit = make_research_repo(tmp / "repo")
    bundle = copy_reference_bundle(tmp / "bundle")
    point_bundle_at(bundle, url, commit)
    home = tmp / "home"
    sid = submit_bundle(bundle, home=home).submission_id
    with OrcidServer() as orcid:
        run_admission(sid, home=home, orcid_base_url=orcid)
    create_preprint(sid, "v1.1.0", home=home)
    return sid, home


@pytest.fixture(scope="module")
def filed(preprint):
    sid, home = preprint
    return file_review(sid, _report(sid), HUMAN, channel="orcid-login", home=home)


def _finding(record, claim_id):
    return next(f for f in record["claim_findings"] if f["claim_id"] == claim_id)


def test_journal_writes_the_packet_state_onto_each_finding(filed):
    # Arrange
    record = filed
    # Act
    finding = _finding(record, "n_rows")
    # Assert
    assert finding["packet_state"] == "not_supported"


def test_unmentioned_claims_are_recorded_as_not_assessed(filed):
    # Arrange
    record = filed
    # Act
    finding = _finding(record, "calib")
    # Assert
    assert (finding["verdict"], finding["journal_filled"]) == ("not-assessed", True)


def test_reviewer_gets_a_pseudonym(filed):
    # Arrange
    record = filed
    # Act
    pseudonym = record["reviewer_pseudonym"]
    # Assert
    assert pseudonym == "r1"


def test_orcid_login_channel_counts_as_verified(filed):
    # Arrange
    record = filed
    # Act
    attestation = record["attestation"]
    # Assert
    assert attestation == {"channel": "orcid-login", "verified_by_journal": True}


def test_refiling_the_same_review_is_idempotent(preprint, filed):
    # Arrange
    sid, home = preprint
    # Act
    again = file_review(sid, _report(sid), HUMAN, channel="orcid-login", home=home)
    # Assert
    assert again["review_id"] == filed["review_id"]


def test_findings_ledger_does_not_duplicate_on_refile(preprint, filed):
    # Arrange
    sid, home = preprint
    file_review(sid, _report(sid), HUMAN, channel="orcid-login", home=home)
    # Act
    ledger = load_findings(sid, home=home)
    # Assert
    assert len(ledger["findings"]) == 3


def test_a_second_source_gets_its_own_pseudonym(preprint, filed):
    # Arrange
    sid, home = preprint
    # Act
    record = file_review(sid, _report(sid), SERVICE, channel="service-key", home=home)
    # Assert
    assert record["reviewer_pseudonym"] == "r2"


def test_reviews_are_listed(preprint, filed):
    # Arrange
    sid, home = preprint
    # Act
    reviews = list_reviews(sid, home=home)
    # Assert
    assert filed["review_id"] in {r["review_id"] for r in reviews}


def test_author_cannot_review_their_own_submission(preprint):
    # Arrange
    sid, home = preprint
    author = copy.deepcopy(HUMAN)
    author["identity"]["orcid"] = TEST_ORCID
    # Act
    call = lambda: file_review(
        sid, _report(sid), author, channel="orcid-login", home=home
    )
    # Assert
    with pytest.raises(ReviewRejectedError, match="is an author"):
        call()


def test_producer_agent_cannot_review(preprint):
    # Arrange
    sid, home = preprint
    producer = copy.deepcopy(SERVICE)
    producer["identity"]["service"] = "scitex-live-paper-reference-provider"
    # Act
    call = lambda: file_review(
        sid, _report(sid), producer, channel="service-key", home=home
    )
    # Assert
    with pytest.raises(ReviewRejectedError, match="producer"):
        call()


def test_unknown_claim_is_rejected(preprint):
    # Arrange
    sid, home = preprint
    report = _report(sid)
    report["claim_findings"][0]["claim_id"] = "made-up"
    # Act
    call = lambda: file_review(sid, report, HUMAN, channel="orcid-login", home=home)
    # Assert
    with pytest.raises(ReviewRejectedError, match="not a registered claim"):
        call()


def test_graph_node_outside_the_claim_graph_is_rejected(preprint):
    # Arrange
    sid, home = preprint
    report = _report(sid)
    report["claim_findings"][0]["graph_nodes"] = ["zz"]
    # Act
    call = lambda: file_review(sid, report, HUMAN, channel="orcid-login", home=home)
    # Assert
    with pytest.raises(ReviewRejectedError, match="not in claim n_rows"):
        call()


def test_reviewer_cannot_supply_the_packet_state(preprint):
    # Arrange
    sid, home = preprint
    report = _report(sid)
    report["claim_findings"][0]["packet_state"] = "supported"
    # Act
    call = lambda: file_review(sid, report, HUMAN, channel="orcid-login", home=home)
    # Assert
    with pytest.raises(ReviewRejectedError, match="packet_state"):
        call()


def test_human_source_without_orcid_is_rejected(preprint):
    # Arrange
    sid, home = preprint
    anonymous = copy.deepcopy(HUMAN)
    anonymous["identity"] = {"name": "someone"}
    # Act
    call = lambda: file_review(
        sid, _report(sid), anonymous, channel="self-declared", home=home
    )
    # Assert
    with pytest.raises(ReviewRejectedError, match="orcid"):
        call()


def test_review_before_preprint_is_rejected(tmp_path):
    # Arrange
    url, commit = make_research_repo(tmp_path / "repo")
    bundle = copy_reference_bundle(tmp_path / "bundle")
    point_bundle_at(bundle, url, commit)
    home = tmp_path / "home"
    sid = submit_bundle(bundle, home=home).submission_id
    # Act
    call = lambda: file_review(
        sid, _report(sid), HUMAN, channel="orcid-login", home=home
    )
    # Assert
    with pytest.raises(ReviewRejectedError, match="not a preprint"):
        call()
