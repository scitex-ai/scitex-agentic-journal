"""Durable real-file upload snapshots; no network or fabricated API results."""

import hashlib
import json
import shutil

import pytest
from django.core.files import locks

from scitex_agentic_journal._django._uploads import (
    UploadConflict,
    persist_uploaded_verdict,
)
from tests.scitex_agentic_journal._submit.test__persist import _make_verdict


@pytest.fixture
def upload(tmp_path):
    source = tmp_path / "stage"
    source.mkdir()
    (source / "manuscript.txt").write_text("Original evidence\n")
    (source / "bundle.yaml").write_text("title: Example\n")
    return (
        _make_verdict(source),
        tmp_path / "home",
        hashlib.sha256(b"fixture upload").hexdigest(),
    )


def test_persisted_inputs_survive_intake_cleanup(upload):
    # Arrange
    verdict, home, fingerprint = upload
    # Act
    receipt = persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
    shutil.rmtree(verdict.submission.bundle_dir)
    record = json.loads(receipt.record_path.read_text())
    from pathlib import Path

    bundle = Path(record["submission"]["bundle_dir"])
    # Assert
    assert (bundle / "manuscript.txt").read_text() == "Original evidence\n" and record[
        "clew_verification"
    ]["project_dir"] == str(bundle)


def test_identical_retry_preserves_record_and_later_review(upload):
    # Arrange
    verdict, home, fingerprint = upload
    receipt = persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
    original = receipt.record_path.read_bytes()
    review = receipt.record_dir / "review.json"
    review.write_text('{"record":{"reviewer":"actual-run"}}')
    # Act
    retry = persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
    # Assert
    assert (
        retry == receipt
        and retry.record_path.read_bytes() == original
        and review.read_text() == '{"record":{"reviewer":"actual-run"}}'
    )


def test_modified_durable_assets_refuse_retry_without_rewrite(upload):
    # Arrange
    from pathlib import Path

    verdict, home, fingerprint = upload
    receipt = persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
    original = receipt.record_path.read_bytes()
    bundle = Path(json.loads(original)["submission"]["bundle_dir"])
    (bundle / "manuscript.txt").write_text("Changed after persistence")
    # Act
    failure = None
    try:
        persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
    except UploadConflict as exc:
        failure = exc
    # Assert
    assert (
        failure is not None
        and "changed" in str(failure)
        and receipt.record_path.read_bytes() == original
    )


def test_symlink_in_upload_is_rejected_without_record(upload, tmp_path):
    # Arrange
    verdict, home, fingerprint = upload
    private = tmp_path / "private"
    private.write_text("Other user's data")
    (verdict.submission.bundle_dir / "leak").symlink_to(private)
    # Act
    failure = None
    try:
        persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
    except UploadConflict as exc:
        failure = exc
    # Assert
    assert (
        failure is not None
        and "symbolic" in str(failure)
        and not list((home / "submissions").iterdir())
    )


def test_competing_upload_lock_refuses_mutation(upload):
    # Arrange
    verdict, home, fingerprint = upload
    directory = home / "locks"
    directory.mkdir(parents=True)
    path = directory / f"sub_{fingerprint[:32]}.lock"
    # Act
    failure = None
    with path.open("w") as held:
        locked = locks.lock(held, locks.LOCK_EX | locks.LOCK_NB)
        if not locked:
            raise RuntimeError("Fixture could not acquire real file lock")
        try:
            try:
                persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
            except UploadConflict as exc:
                failure = exc
        finally:
            locks.unlock(held)
    # Assert
    assert (
        failure is not None
        and "already being persisted" in str(failure)
        and not list((home / "submissions").iterdir())
    )


def test_nested_clew_input_is_rebased_to_durable_snapshot(upload):
    # Arrange
    from dataclasses import replace
    from pathlib import Path

    verdict, home, fingerprint = upload
    nested = verdict.submission.bundle_dir / "analysis"
    nested.mkdir()
    (nested / "claims.txt").write_text("Evidence fixture")
    verdict = replace(
        verdict,
        submission=replace(verdict.submission, clew_project_dir=nested),
        clew_verification=replace(verdict.clew_verification, project_dir=nested),
    )
    # Act
    receipt = persist_uploaded_verdict(verdict, home=home, fingerprint=fingerprint)
    record = json.loads(receipt.record_path.read_text())
    expected = Path(record["submission"]["bundle_dir"]) / "analysis"
    # Assert
    assert (
        record["submission"]["clew_project_dir"] == str(expected)
        and record["clew_verification"]["project_dir"] == str(expected)
        and (expected / "claims.txt").read_text() == "Evidence fixture"
    )
