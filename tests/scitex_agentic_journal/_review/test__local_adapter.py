"""Tests for `_review/_local_adapter.py` — LocalDeterministicAdapter.

Each TQ001/TQ002/TQ003/TQ007-compliant: single assertion, AAA markers,
descriptive name. No mocks — the adapter is hermetic by design.
"""

from __future__ import annotations

from pathlib import Path

from scitex_agentic_journal._review import (
    ClaimVerifyReport,
    LocalDeterministicAdapter,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewerAdapter,
    Severity,
    SubReportKind,
    SubmissionInputs,
)


def _inputs() -> SubmissionInputs:
    return SubmissionInputs(
        submission_id="sub_2026_06_13_abc123",
        manuscript_dir=Path("/tmp/bundle"),
        claims_path=Path("/tmp/bundle/claims.json"),
        dag_dir=Path("/tmp/bundle"),
        code_repo_url="https://example.com/r.git",
        corresponding_author_orcid="0000-0002-1825-0097",
    )


def test_local_deterministic_adapter_satisfies_reviewer_adapter_protocol() -> None:
    # Arrange
    adapter = LocalDeterministicAdapter()
    # Act
    is_adapter = isinstance(adapter, ReviewerAdapter)
    # Assert
    assert is_adapter


def test_local_deterministic_adapter_name_is_local_deterministic() -> None:
    # Arrange
    adapter = LocalDeterministicAdapter()
    # Act
    name = adapter.adapter_name
    # Assert
    assert name == "local-deterministic"


def test_local_deterministic_adapter_reproducibility_payload_is_passed_true() -> None:
    # Arrange
    adapter = LocalDeterministicAdapter()
    # Act
    sub = adapter.run_sub_report(
        kind=SubReportKind.REPRODUCIBILITY, inputs=_inputs(), prompts_version="v1"
    )
    # Assert
    assert isinstance(sub.payload, ReproducibilityReport) and sub.payload.passed


def test_local_deterministic_adapter_claim_verify_payload_has_empty_buckets() -> None:
    # Arrange
    adapter = LocalDeterministicAdapter()
    # Act
    sub = adapter.run_sub_report(
        kind=SubReportKind.CLAIM_VERIFY, inputs=_inputs(), prompts_version="v1"
    )
    # Assert
    assert isinstance(sub.payload, ClaimVerifyReport) and sub.payload.green_count == 0


def test_local_deterministic_adapter_novelty_payload_has_zero_overlap_score() -> None:
    # Arrange
    adapter = LocalDeterministicAdapter()
    # Act
    sub = adapter.run_sub_report(
        kind=SubReportKind.NOVELTY, inputs=_inputs(), prompts_version="v1"
    )
    # Assert
    assert isinstance(sub.payload, NoveltyReport) and sub.payload.overlap_score == 0.0


def test_local_deterministic_adapter_methodology_payload_has_no_criticisms() -> None:
    # Arrange
    adapter = LocalDeterministicAdapter()
    # Act
    sub = adapter.run_sub_report(
        kind=SubReportKind.METHODOLOGY, inputs=_inputs(), prompts_version="v1"
    )
    # Assert
    assert isinstance(sub.payload, MethodologyReport) and sub.payload.max_severity is Severity.NONE
