"""Vendored and journal-owned contract schemas load, are pinned, and validate."""

from __future__ import annotations

import hashlib
import json
from importlib import resources

import pytest
from scitex_agentic_journal._contracts import (
    ContractError,
    journal_schema,
    validate,
    vendored_entry,
    vendored_schema,
)

from tests.scitex_agentic_journal._contract_helpers import REFERENCE_BUNDLE

LP = "scitex-live-paper"
VENDORED = ["evidence-report.schema.json", "review-packet.schema.json"]


@pytest.mark.parametrize("name", VENDORED)
def test_vendored_file_bytes_match_the_pinned_sha256(name):
    # Arrange
    entry = vendored_entry(LP, name)
    node = resources.files("scitex_agentic_journal._contracts").joinpath(
        "vendor", LP, name
    )
    # Act
    digest = hashlib.sha256(node.read_bytes()).hexdigest()
    # Assert
    assert digest == entry["sha256"]


@pytest.mark.parametrize("name", VENDORED)
def test_vendored_schema_id_matches_the_pin_record(name):
    # Arrange
    entry = vendored_entry(LP, name)
    # Act
    schema = vendored_schema(LP, name)
    # Assert
    assert schema["$id"] == entry["schema_id"]


def test_unknown_vendored_file_is_refused():
    # Arrange
    name = "nope.schema.json"
    # Act
    call = lambda: vendored_entry(LP, name)
    # Assert
    with pytest.raises(ContractError, match="not vendored"):
        call()


@pytest.mark.parametrize("name", ["submission", "review-report", "review-source"])
def test_journal_schema_declares_draft_2020_12(name):
    # Arrange
    expected = "https://json-schema.org/draft/2020-12/schema"
    # Act
    schema = journal_schema(name)
    # Assert
    assert schema["$schema"] == expected


def test_reference_evidence_report_validates_against_the_vendored_schema():
    # Arrange
    report = json.loads((REFERENCE_BUNDLE / "evidence-report.json").read_text())
    # Act
    errors = validate(report, vendored_schema(LP, "evidence-report.schema.json"))
    # Assert
    assert errors == []


def test_unknown_evidence_state_is_reported_with_its_value():
    # Arrange
    report = json.loads((REFERENCE_BUNDLE / "evidence-report.json").read_text())
    report["claims"][0]["state"] = "probably-fine"
    # Act
    errors = validate(report, vendored_schema(LP, "evidence-report.schema.json"))
    # Assert
    assert any("probably-fine" in e for e in errors)
