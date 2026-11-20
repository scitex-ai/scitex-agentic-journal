"""Portable format/binding checks keep their verdict narrower than reproduction."""

from __future__ import annotations

import json

import pytest

from scitex_agentic_journal._admission._evidence_check import check_evidence_bundle
from scitex_agentic_journal._admission._executor import EVIDENCE_BUNDLE
from tests.scitex_agentic_journal._contract_helpers import REPO_TESTS

FIXTURE = (
    REPO_TESTS / "scitex_agentic_journal/fixtures/clew-0.36.0/evidence-bundle.json"
)


@pytest.fixture
def project(tmp_path):
    path = tmp_path / EVIDENCE_BUNDLE
    path.parent.mkdir(parents=True)
    path.write_bytes(FIXTURE.read_bytes())
    return tmp_path


def _report():
    return {"claims": [{"claim_id": "total", "state": "supported", "stated_value": 6}]}


def test_actual_bundle_binds_the_main_claim_without_certifying_hashes(project):
    # Arrange
    manifest, report = {"main_claims": ["total"]}, _report()
    # Act
    check = check_evidence_bundle(project, manifest, report)
    # Assert
    assert (
        check["status"],
        check["required"],
        check["details"]["signature_verified"],
        check["details"]["file_hashes_verified"],
    ) == ("passed", False, False, False)


@pytest.mark.parametrize("field,value", [("state", "unsupported"), ("stated_value", 7)])
def test_disagreement_with_the_submitted_claim_fails(project, field, value):
    # Arrange
    report = _report()
    report["claims"][0][field] = value
    # Act
    check = check_evidence_bundle(project, {"main_claims": ["total"]}, report)
    # Assert
    assert (check["status"], set(check["details"]["binding_errors"])) == (
        "failed",
        {"total"},
    )


def test_main_claim_absent_from_the_snapshot_fails(project):
    # Arrange
    manifest = {"main_claims": ["missing"]}
    # Act
    check = check_evidence_bundle(project, manifest, _report())
    # Assert
    assert (check["status"], set(check["details"]["binding_errors"])) == (
        "failed",
        {"missing"},
    )


@pytest.mark.parametrize("available", [True, False])
def test_unavailable_bundle_is_not_a_pass(tmp_path, available):
    # Arrange
    project = tmp_path if available else None
    # Act
    check = check_evidence_bundle(project, {"main_claims": ["total"]}, _report())
    # Assert
    assert (check["status"], check["required"]) == ("not-run", False)


def test_malformed_released_document_fails(project):
    # Arrange
    path = project / EVIDENCE_BUNDLE
    doc = json.loads(path.read_text())
    del doc["runs"][0]["inputs"]
    path.write_text(json.dumps(doc))
    # Act
    check = check_evidence_bundle(project, {"main_claims": ["total"]}, _report())
    # Assert
    assert (check["status"], "inputs" in check["reason"]) == ("failed", True)


def test_symlinked_bundle_fails_without_reading_the_target(tmp_path):
    # Arrange
    project = tmp_path / "project"
    path = project / EVIDENCE_BUNDLE
    path.parent.mkdir(parents=True)
    path.symlink_to(FIXTURE)
    # Act
    check = check_evidence_bundle(project, {"main_claims": ["total"]}, _report())
    # Assert
    assert check["status"] == "failed"
