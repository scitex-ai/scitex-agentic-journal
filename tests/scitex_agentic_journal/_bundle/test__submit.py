"""submit_bundle records valid bundles idempotently and refuses invalid ones."""

from __future__ import annotations

import pytest
from scitex_agentic_journal._bundle import (
    BundleInvalidError,
    bundle_path,
    load_intake,
    submit_bundle,
    validate_bundle,
)

from tests.scitex_agentic_journal._contract_helpers import (
    REFERENCE_BUNDLE,
    copy_reference_bundle,
)


def test_submit_creates_an_intake_record(tmp_path):
    # Arrange
    home = tmp_path / "home"
    # Act
    receipt = submit_bundle(REFERENCE_BUNDLE, home=home)
    # Assert
    assert load_intake(receipt.submission_id, home=home)["manifest_sha256"] == (
        validate_bundle(REFERENCE_BUNDLE).manifest_sha256
    )


def test_submit_keeps_a_valid_copy_of_the_bundle(tmp_path):
    # Arrange
    home = tmp_path / "home"
    receipt = submit_bundle(REFERENCE_BUNDLE, home=home)
    # Act
    copy = validate_bundle(bundle_path(receipt.submission_id, home=home))
    # Assert
    assert copy.submission_id == receipt.submission_id


def test_resubmitting_identical_bytes_is_idempotent(tmp_path):
    # Arrange
    home = tmp_path / "home"
    submit_bundle(REFERENCE_BUNDLE, home=home)
    # Act
    again = submit_bundle(REFERENCE_BUNDLE, home=home)
    # Assert
    assert again.created is False


def test_invalid_bundle_is_refused_with_its_findings(tmp_path):
    # Arrange
    bundle = copy_reference_bundle(tmp_path / "bundle")
    (bundle / "extra.txt").write_text("x\n")
    # Act
    call = lambda: submit_bundle(bundle, home=tmp_path / "home")
    # Assert
    with pytest.raises(BundleInvalidError, match="unlisted-file"):
        call()
