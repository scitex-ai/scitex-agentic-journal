"""Unit tests for :mod:`scitex_agentic_journal._review` — no network."""

from __future__ import annotations

from pathlib import Path

import pytest
from scitex_agentic_journal._review import (
    ARA_RUBRIC_VERSION,
    AraRubric,
    ClaimVerifyReport,
    Criticism,
    MethodologyReport,
    NoveltyReport,
    QwenAdapterStub,
    ReproducibilityReport,
    ReviewerAdapter,
    ReviewRecord,
    ReviewRunner,
    ReviewSubReport,
    Severity,
    SubmissionInputs,
    SubReportKind,
)


def _inputs() -> SubmissionInputs:
    return SubmissionInputs(
        submission_id="s-001",
        manuscript_dir=Path("/tmp/m"),
        claims_path=Path("/tmp/claims.yaml"),
        dag_dir=Path("/tmp/dag"),
        code_repo_url="https://github.com/owner/repo",
        corresponding_author_orcid="0000-0002-1825-0097",
    )


# ----- Rubric --------------------------------------------------------------


def test_rubric_version_is_v1() -> None:
    # Arrange
    expected = "v1"
    # Act
    version = ARA_RUBRIC_VERSION
    # Assert
    assert version == expected


def test_rubric_kinds_count_is_four() -> None:
    # Arrange
    rubric = AraRubric()
    # Act
    count = len(rubric.kinds)
    # Assert
    assert count == 4


def test_rubric_kinds_first_is_reproducibility() -> None:
    # Arrange
    rubric = AraRubric()
    # Act
    first = rubric.kinds[0]
    # Assert
    assert first is SubReportKind.REPRODUCIBILITY


def test_rubric_describe_known_kind_returns_text() -> None:
    # Arrange
    rubric = AraRubric()
    # Act
    text = rubric.describe(SubReportKind.METHODOLOGY)
    # Assert
    assert "methodolog" in text.lower()


# ----- MethodologyReport severity --------------------------------------------


def test_empty_methodology_has_severity_none() -> None:
    # Arrange
    report = MethodologyReport()
    # Act
    severity = report.max_severity
    # Assert
    assert severity is Severity.NONE


def test_methodology_max_severity_picks_highest() -> None:
    # Arrange
    report = MethodologyReport(
        criticisms=(
            Criticism(severity=Severity.MINOR, section="§1", note="."),
            Criticism(severity=Severity.MAJOR, section="§2", note="."),
            Criticism(severity=Severity.MINOR, section="§3", note="."),
        ),
    )
    # Act
    severity = report.max_severity
    # Assert
    assert severity is Severity.MAJOR


def test_methodology_fatal_wins_over_major() -> None:
    # Arrange
    report = MethodologyReport(
        criticisms=(
            Criticism(severity=Severity.MAJOR, section="§1", note="."),
            Criticism(severity=Severity.FATAL, section="§2", note="."),
        ),
    )
    # Act
    severity = report.max_severity
    # Assert
    assert severity is Severity.FATAL


# ----- ClaimVerifyReport ----------------------------------------------------


def test_claim_verify_report_green_count_matches_tuple() -> None:
    # Arrange
    report = ClaimVerifyReport(green_claim_ids=("c1", "c2", "c3"))
    # Act
    count = report.green_count
    # Assert
    assert count == 3


# ----- Qwen stub ------------------------------------------------------------


def test_qwen_stub_satisfies_reviewer_adapter_protocol() -> None:
    # Arrange
    adapter = QwenAdapterStub()
    # Act
    is_protocol = isinstance(adapter, ReviewerAdapter)
    # Assert
    assert is_protocol is True


def test_qwen_stub_run_sub_report_raises_not_implemented() -> None:
    # Arrange
    adapter = QwenAdapterStub()
    # Act
    # Assert
    with pytest.raises(NotImplementedError):
        adapter.run_sub_report(
            kind=SubReportKind.REPRODUCIBILITY,
            inputs=_inputs(),
            prompts_version="v1",
        )


# ----- ReviewRunner with in-memory adapter ----------------------------------


class _DummyAdapter:
    adapter_name: str = "dummy"
    adapter_version: str = "0.0.1"
    mode = "stub"

    def __init__(self) -> None:
        self.calls: list[SubReportKind] = []

    def run_sub_report(
        self,
        kind: SubReportKind,
        inputs: SubmissionInputs,
        prompts_version: str,
    ) -> ReviewSubReport:
        self.calls.append(kind)
        payload_for_kind = {
            SubReportKind.REPRODUCIBILITY: ReproducibilityReport(
                passed=True, sandbox_image="alpine:3.20"
            ),
            SubReportKind.CLAIM_VERIFY: ClaimVerifyReport(green_claim_ids=("c1",)),
            SubReportKind.NOVELTY: NoveltyReport(overlap_score=0.1),
            SubReportKind.METHODOLOGY: MethodologyReport(),
        }
        return ReviewSubReport(kind=kind, payload=payload_for_kind[kind])


def test_runner_calls_adapter_for_all_four_kinds() -> None:
    # Arrange
    adapter = _DummyAdapter()
    runner = ReviewRunner(adapter, prompts_version="v1")
    # Act
    runner.run(_inputs())
    # Assert
    assert adapter.calls == [
        SubReportKind.REPRODUCIBILITY,
        SubReportKind.CLAIM_VERIFY,
        SubReportKind.NOVELTY,
        SubReportKind.METHODOLOGY,
    ]


def test_runner_record_stamps_rubric_version() -> None:
    # Arrange
    runner = ReviewRunner(_DummyAdapter(), prompts_version="v1")
    # Act
    record = runner.run(_inputs())
    # Assert
    assert record.rubric_version == "v1"


def test_runner_record_stamps_adapter_name() -> None:
    # Arrange
    runner = ReviewRunner(_DummyAdapter(), prompts_version="v1")
    # Act
    record = runner.run(_inputs())
    # Assert
    assert record.adapter == "dummy"


def test_runner_record_stamps_prompts_version() -> None:
    # Arrange
    runner = ReviewRunner(_DummyAdapter(), prompts_version="v2")
    # Act
    record = runner.run(_inputs())
    # Assert
    assert record.prompts_version == "v2"


def test_runner_record_carries_typed_reproducibility_payload() -> None:
    # Arrange
    runner = ReviewRunner(_DummyAdapter(), prompts_version="v1")
    # Act
    record = runner.run(_inputs())
    # Assert
    assert isinstance(record.reproducibility, ReproducibilityReport)


def test_runner_record_carries_typed_claim_verify_payload() -> None:
    # Arrange
    runner = ReviewRunner(_DummyAdapter(), prompts_version="v1")
    # Act
    record = runner.run(_inputs())
    # Assert
    assert isinstance(record.claim_verify, ClaimVerifyReport)


def test_runner_record_finish_at_is_after_start_at() -> None:
    # Arrange
    runner = ReviewRunner(_DummyAdapter(), prompts_version="v1")
    # Act
    record = runner.run(_inputs())
    # Assert
    assert record.finished_at >= record.started_at


# ----- ReviewRunner type-safety against a misbehaving adapter ---------------


class _BadAdapter:
    adapter_name: str = "bad"
    adapter_version: str = "0.0.1"
    mode = "stub"

    def run_sub_report(
        self,
        kind: SubReportKind,
        inputs: SubmissionInputs,
        prompts_version: str,
    ) -> ReviewSubReport:
        # Wrong payload type for the reproducibility kind.
        return ReviewSubReport(
            kind=kind,
            payload="not-a-report",
        )


def test_runner_raises_type_error_on_wrong_payload_type() -> None:
    # Arrange
    runner = ReviewRunner(_BadAdapter(), prompts_version="v1")
    # Act
    # Assert
    with pytest.raises(TypeError):
        runner.run(_inputs())


# ----- ReviewRecord immutability --------------------------------------------


def test_review_record_is_frozen() -> None:
    # Arrange
    runner = ReviewRunner(_DummyAdapter(), prompts_version="v1")
    record = runner.run(_inputs())
    # Act
    # Assert
    with pytest.raises(Exception):
        # FrozenInstanceError is in dataclasses; we just confirm "raises".
        record.submission_id = "tampered"  # type: ignore[misc]
