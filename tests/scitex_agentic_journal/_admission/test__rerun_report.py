"""Parsing of clew's rerun report and its mapping to the two check records.

The fixture ``fixtures/clew-rerun-report.json`` follows the published
``scitex-clew.rerun-report`` 1.0.0 contract field for field.
"""

from __future__ import annotations

import json

import pytest
from scitex_agentic_journal._admission._rerun_report import (
    RerunReportError,
    executability_record,
    parse_rerun_report,
    reproduction_record,
)

from tests.scitex_agentic_journal._contract_helpers import REPO_TESTS

FIXTURE = REPO_TESTS / "scitex_agentic_journal" / "fixtures" / "clew-rerun-report.json"
TOOL = {"name": "scitex-clew bundle rerun (sealed apptainer sandbox)", "version": "x"}
DETAILS = {"outcome_sha256": "0" * 64}


@pytest.fixture(scope="module")
def text():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def report(text):
    return parse_rerun_report(text)


def _reproduction(report, main_claims, bundle_sha256=None):
    return reproduction_record(
        report,
        main_claims,
        bundle_sha256=bundle_sha256 or report["bundle_sha256"],
        tool=TOOL,
        details=DETAILS,
    )


def test_fixture_parses_as_a_rerun_report(report):
    # Arrange
    expected = "scitex-clew.rerun-report"
    # Act
    schema = report["schema"]
    # Assert
    assert schema == expected


def test_non_json_output_is_refused():
    # Arrange
    text = "Traceback (most recent call last):\n"
    # Act
    call = lambda: parse_rerun_report(text)  # noqa: E731
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_other_schema_is_refused(text):
    # Arrange
    other = json.loads(text) | {"schema": "scitex-clew.evidence-report"}
    # Act
    call = lambda: parse_rerun_report(json.dumps(other))  # noqa: E731
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_next_major_version_is_refused(text):
    # Arrange
    other = json.loads(text) | {"schema_version": "2.0.0"}
    # Act
    call = lambda: parse_rerun_report(json.dumps(other))  # noqa: E731
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_unknown_claim_status_is_refused(text):
    # Arrange
    other = json.loads(text)
    other["claims"][0]["status"] = "probably"
    # Act
    call = lambda: parse_rerun_report(json.dumps(other))  # noqa: E731
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_executable_report_passes_executability(report):
    # Arrange
    tool = TOOL
    # Act
    rec = executability_record(report, tool=tool, details=DETAILS)
    # Assert
    assert rec["status"] == "passed"


def test_not_executable_report_fails_executability(report):
    # Arrange
    other = {**report, "executable": False}
    # Act
    rec = executability_record(other, tool=TOOL, details=DETAILS)
    # Assert
    assert rec["status"] == "failed"


def test_executability_is_never_required(report):
    # Arrange
    tool = TOOL
    # Act
    rec = executability_record(report, tool=tool, details=DETAILS)
    # Assert
    assert rec["required"] is False


def test_reproduced_main_claim_passes_reproduction(report):
    # Arrange
    main_claims = ["auc"]
    # Act
    rec = _reproduction(report, main_claims)
    # Assert
    assert rec["status"] == "passed"


def test_differing_main_claim_fails_reproduction(report):
    # Arrange
    main_claims = ["auc", "n_rows"]
    # Act
    rec = _reproduction(report, main_claims)
    # Assert
    assert rec["details"]["not_reproduced"] == {"n_rows": "differs"}


def test_main_claim_absent_from_the_report_fails_reproduction(report):
    # Arrange
    main_claims = ["auc", "accuracy"]
    # Act
    rec = _reproduction(report, main_claims)
    # Assert
    assert rec["details"]["not_reproduced"] == {"accuracy": "not in rerun report"}


def test_report_for_another_bundle_fails_reproduction(report):
    # Arrange
    main_claims = ["auc"]
    # Act
    rec = _reproduction(report, main_claims, bundle_sha256="f" * 64)
    # Assert
    assert "not the submitted bundle" in rec["reason"]


def test_reproduction_details_carry_the_declared_tolerance(report):
    # Arrange
    main_claims = ["auc"]
    # Act
    rec = _reproduction(report, main_claims)
    # Assert
    assert rec["details"]["claims"][0]["tolerance"] == 0.005


def test_reproduction_details_carry_per_run_output_matches(report):
    # Arrange
    main_claims = ["auc"]
    # Act
    rec = _reproduction(report, main_claims)
    # Assert
    assert [o["match"] for r in rec["details"]["runs"] for o in r["outputs"]] == [
        True,
        False,
    ]


def test_reproduction_details_cite_the_outcome_record(report):
    # Arrange
    main_claims = ["auc"]
    # Act
    rec = _reproduction(report, main_claims)
    # Assert
    assert rec["details"]["outcome_sha256"] == DETAILS["outcome_sha256"]
