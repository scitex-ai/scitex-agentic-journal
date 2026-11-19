"""Journal consumes the actual released Clew documents without importing Clew."""

from __future__ import annotations

import hashlib
import json

import pytest

from scitex_agentic_journal._contracts import vendored_entry, vendored_schema
from scitex_agentic_journal._contracts._clew import contract_errors
from tests.scitex_agentic_journal._contract_helpers import REPO_TESTS

FIXTURE = REPO_TESTS / "scitex_agentic_journal/fixtures/clew-0.36.0"


@pytest.fixture
def bundle():
    return json.loads((FIXTURE / "evidence-bundle.json").read_text())


@pytest.mark.parametrize(
    "name",
    [
        "evidence-bundle.schema.1.0.0.json",
        "rerun-report.schema.1.0.0.json",
        "rerun-report.schema.1.1.0.json",
    ],
)
def test_released_schema_ids_and_source_commits_match_the_pins(name):
    # Arrange
    entry = vendored_entry("scitex-clew", name)
    # Act: loading also verifies the packaged bytes against the pin.
    schema = vendored_schema("scitex-clew", name)
    # Assert
    assert (schema["$id"], entry["ref"], entry["commit"]) == (
        entry["schema_id"],
        "v0.36.0",
        "6ebb780f7a5c1813c8445f8829ea8ba740cdaf62",
    )


def test_fixture_is_an_unedited_export_from_the_published_wheel(bundle):
    # Arrange
    provenance = json.loads((FIXTURE / "PROVENANCE.json").read_text())
    # Act
    digest = hashlib.sha256((FIXTURE / "evidence-bundle.json").read_bytes()).hexdigest()
    # Assert
    assert digest == provenance["sha256"]["evidence-bundle.json"]


def test_actual_published_wheel_bundle_validates(bundle):
    # Arrange
    document = bundle
    # Act
    errors = contract_errors(document, "evidence-bundle")
    # Assert
    assert errors == []


@pytest.mark.parametrize(
    "field,value",
    [("script", "../outside.py"), ("outputs", {"results/total.json": "not-a-hash"})],
)
def test_released_contract_rejects_unsafe_paths_and_malformed_hashes(
    bundle, field, value
):
    # Arrange
    bundle["runs"][0][field] = value
    # Act
    errors = contract_errors(bundle, "evidence-bundle")
    # Assert
    assert errors


@pytest.mark.parametrize("collection", ["runs", "claims"])
def test_ambiguous_repeated_ids_are_rejected(bundle, collection):
    # Arrange
    bundle[collection].append(bundle[collection][0].copy())
    # Act
    errors = contract_errors(bundle, "evidence-bundle")
    # Assert
    assert any("duplicate" in error for error in errors)


def test_unknown_extension_keys_are_preserved(bundle):
    # Arrange
    bundle["future_extension"] = {"opaque": True}
    bundle["runs"][0]["future_extension"] = 42
    # Act
    errors = contract_errors(bundle, "evidence-bundle")
    # Assert
    assert errors == []


def test_unreleased_contract_version_is_refused(bundle):
    # Arrange
    bundle["schema_version"] = "1.99.0"
    # Act
    errors = contract_errors(bundle, "evidence-bundle")
    # Assert
    assert errors == ["unsupported evidence-bundle schema_version '1.99.0'"]


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0"])
def test_genuine_rerun_fields_validate_in_both_supported_contracts(version):
    # Arrange: 1.1.0 is the real output; the 1.0.0 case checks legacy compatibility.
    report = json.loads((FIXTURE / "rerun-report.json").read_text())
    report["schema_version"] = version
    # Act
    errors = contract_errors(report, "rerun-report")
    # Assert
    assert errors == []
