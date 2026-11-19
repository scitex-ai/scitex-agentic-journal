"""validate_bundle on the real reference bundle and on targeted breakages."""

from __future__ import annotations

import json

import pytest
from scitex_agentic_journal._bundle import seal_bundle, validate_bundle

from tests.scitex_agentic_journal._contract_helpers import (
    REFERENCE_BUNDLE,
    copy_reference_bundle,
    read_manifest,
    write_manifest,
)


@pytest.fixture
def bundle(tmp_path):
    return copy_reference_bundle(tmp_path / "bundle")


def _codes(path):
    return {f.code for f in validate_bundle(path).findings}


def test_reference_bundle_is_valid():
    # Arrange
    path = REFERENCE_BUNDLE
    # Act
    result = validate_bundle(path)
    # Assert
    assert result.findings == []


def test_submission_id_is_derived_from_the_manifest_hash():
    # Arrange
    result = validate_bundle(REFERENCE_BUNDLE)
    # Act
    sid = result.submission_id
    # Assert
    assert sid == f"aj-{result.manifest_sha256[:16]}"


def test_unlisted_file_is_refused(bundle):
    # Arrange
    (bundle / "manuscript" / "notes.txt").write_text("smuggled input\n")
    # Act
    codes = _codes(bundle)
    # Assert
    assert "unlisted-file" in codes


def test_edited_file_fails_its_hash(bundle):
    # Arrange
    (bundle / "references.bib").write_text("@misc{x, title={changed}}\n")
    # Act
    codes = _codes(bundle)
    # Assert
    assert "hash-mismatch" in codes


def test_symlink_is_refused(bundle):
    # Arrange
    (bundle / "manuscript" / "link.tex").symlink_to(bundle / "manuscript" / "paper.tex")
    # Act
    codes = _codes(bundle)
    # Assert
    assert "symlink" in codes


def test_missing_manifest_field_is_a_schema_finding(bundle):
    # Arrange
    manifest = read_manifest(bundle)
    del manifest["main_claims"]
    write_manifest(bundle, manifest)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "manifest-schema" in codes


def test_non_public_data_is_refused_in_v1(bundle):
    # Arrange
    manifest = read_manifest(bundle)
    manifest["data"] = [
        dict(
            name="ward-eeg",
            url="https://example.org/eeg",
            licence="proprietary",
            access="restricted",
        )
    ]
    write_manifest(bundle, manifest)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "data-not-public" in codes


def test_unconfirmed_agent_conversion_is_refused(bundle):
    # Arrange
    manifest = read_manifest(bundle)
    manifest["conversion"] = {
        "agent": "converter",
        "model": None,
        "source_commit": "a" * 40,
        "result_commit": "b" * 40,
        "diff_sha256": "c" * 64,
        "author_confirmed": False,
    }
    write_manifest(bundle, manifest)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "conversion-unconfirmed" in codes


def test_unknown_main_claim_is_refused(bundle):
    # Arrange
    manifest = read_manifest(bundle)
    manifest["main_claims"] = ["auc", "does-not-exist"]
    write_manifest(bundle, manifest)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "main-claim-unknown" in codes


def _rewrite_listed(bundle, rel, mutate):
    path = bundle / rel
    doc = json.loads(path.read_text())
    mutate(doc)
    path.write_text(json.dumps(doc, indent=1) + "\n")
    import hashlib

    manifest = read_manifest(bundle)
    manifest["files"][rel] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    write_manifest(bundle, manifest)


def test_packet_state_disagreeing_with_the_report_is_refused(bundle):
    # Arrange
    def flip(packet):
        packet["needs_inspection"][0]["state"] = "not_checkable"

    _rewrite_listed(bundle, "review-packet/review.json", flip)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "packet-report-state" in codes


def test_packet_missing_a_claim_is_refused(bundle):
    # Arrange
    def drop(packet):
        packet["needs_inspection"].pop()

    _rewrite_listed(bundle, "review-packet/review.json", drop)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "packet-report-claims" in codes


def test_report_with_unknown_major_version_is_refused(bundle):
    # Arrange
    def bump(report):
        report["schema_version"] = "2.0.0"

    _rewrite_listed(bundle, "evidence-report.json", bump)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "evidence-report-schema" in codes


def test_missing_directory_is_reported(tmp_path):
    # Arrange
    path = tmp_path / "absent"
    # Act
    codes = _codes(path)
    # Assert
    assert codes == {"not-a-directory"}


def test_seal_makes_an_edited_bundle_valid_again(bundle):
    # Arrange
    (bundle / "references.bib").write_text("@misc{y, title={revised}}\n")
    (bundle / "manuscript" / "supplement.pdf").write_bytes(b"%PDF-1.4\n")
    seal_bundle(bundle)
    # Act
    result = validate_bundle(bundle)
    # Assert
    assert result.findings == []


def test_seal_refuses_symlinks(bundle):
    # Arrange
    (bundle / "manuscript" / "link.tex").symlink_to(bundle / "manuscript" / "paper.tex")
    # Act
    call = lambda: seal_bundle(bundle)  # noqa: E731
    # Assert
    with pytest.raises(ValueError, match="symlink"):
        call()

def test_packet_entry_without_claim_id_is_a_finding_not_a_crash(bundle):
    # Arrange
    def strip(packet):
        del packet["needs_inspection"][0]["claim_id"]
    _rewrite_listed(bundle, "review-packet/review.json", strip)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "review-packet-schema" in codes


def test_packet_showing_a_different_value_than_the_report_is_refused(bundle):
    # Arrange
    def alter(packet):
        packet["supported"][0]["stated_value"] = 0.99
    _rewrite_listed(bundle, "review-packet/review.json", alter)
    # Act
    codes = _codes(bundle)
    # Assert
    assert "packet-report-field" in codes


def test_fifo_in_a_bundle_is_refused(bundle):
    # Arrange
    import os

    os.mkfifo(bundle / "manuscript" / "pipe")
    # Act
    codes = _codes(bundle)
    # Assert
    assert "special-file" in codes
