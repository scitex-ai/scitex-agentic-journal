"""Parsing of clew's rerun report, which the journal keeps only as a hint.

The fixture ``fixtures/clew-rerun-report.json`` follows the
``scitex-clew.rerun-report`` 1.1.0 contract (scitex-clew PR #231) field for field.
"""

from __future__ import annotations

import json

import pytest
from scitex_agentic_journal._admission._rerun_report import (
    RerunReportError,
    parse_rerun_report,
    sandbox_reported,
)

from tests.scitex_agentic_journal._contract_helpers import REPO_TESTS

FIXTURE = REPO_TESTS / "scitex_agentic_journal" / "fixtures" / "clew-rerun-report.json"


@pytest.fixture(scope="module")
def text():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def report(text):
    return parse_rerun_report(text)


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
    call = lambda: parse_rerun_report(text)
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_other_schema_is_refused(text):
    # Arrange
    other = json.loads(text) | {"schema": "scitex-clew.evidence-report"}
    # Act
    call = lambda: parse_rerun_report(json.dumps(other))
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_next_major_version_is_refused(text):
    # Arrange
    other = json.loads(text) | {"schema_version": "2.0.0"}
    # Act
    call = lambda: parse_rerun_report(json.dumps(other))
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_unknown_claim_status_is_refused(text):
    # Arrange
    other = json.loads(text)
    other["claims"][0]["status"] = "probably"
    # Act
    call = lambda: parse_rerun_report(json.dumps(other))
    # Assert
    with pytest.raises(RerunReportError):
        call()


def test_sandbox_reported_is_marked_untrusted(report):
    # Arrange
    hint = report
    # Act
    summary = sandbox_reported(hint, None)
    # Assert
    assert summary["trusted"] is False


def test_sandbox_reported_lists_the_claim_statuses_clew_claimed(report):
    # Arrange
    hint = report
    # Act
    summary = sandbox_reported(hint, None)
    # Assert
    assert summary["claims"] == {"auc": "reproduced", "n_rows": "differs"}


def test_unparsable_output_is_recorded_with_its_error():
    # Arrange
    error = "rerun output is not JSON"
    # Act
    summary = sandbox_reported(None, error)
    # Assert
    assert summary == {"parsed": False, "error": error}
