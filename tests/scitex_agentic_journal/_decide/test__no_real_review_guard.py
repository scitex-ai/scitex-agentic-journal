"""Design 01, defect 1: no decision without a real review on record.

The local-deterministic adapter reports reproducibility as passed without
running anything. Before 0.2.0 such a placeholder review could reach
``default_accept``. The engine now refuses every review whose adapter mode
is not ``live``, including legacy records that carry no mode at all.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from scitex_agentic_journal._decide import (
    DecisionEngine,
    NoRealReviewError,
    load_review_record,
)
from scitex_agentic_journal._review import (
    ARA_RUBRIC_VERSION,
    ClaimVerifyReport,
    LocalDeterministicAdapter,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewRecord,
    ReviewRunner,
    SubmissionInputs,
    persist_review,
)

_T = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)  # stx-allow: STX-NL001


def _record(mode: str) -> ReviewRecord:
    return ReviewRecord(
        submission_id="sub_2026_11_19_guard",
        adapter="local-deterministic",
        adapter_version="0.1.0",
        prompts_version="v1",
        rubric_version=ARA_RUBRIC_VERSION,
        reproducibility=ReproducibilityReport(passed=True, sandbox_image="local"),
        claim_verify=ClaimVerifyReport(green_claim_ids=("c1",)),
        novelty=NoveltyReport(overlap_score=0.0),
        methodology=MethodologyReport(criticisms=()),
        started_at=_T,
        finished_at=_T,
        adapter_mode=mode,
    )


@pytest.mark.parametrize("mode", ["stub", "unknown"])
def test_engine_refuses_a_placeholder_review(mode):
    # Arrange
    record = _record(mode)
    # Act
    call = lambda: DecisionEngine().decide(record, now=_T)
    # Assert
    with pytest.raises(NoRealReviewError, match="real review"):
        call()


def test_local_deterministic_runner_output_is_marked_stub(tmp_path: Path):
    # Arrange
    inputs = SubmissionInputs(
        submission_id="sub_2026_11_19_guard",
        manuscript_dir=tmp_path,
        claims_path=tmp_path / "claims.yaml",
        dag_dir=tmp_path,
        code_repo_url="https://example.invalid/repo.git",
        corresponding_author_orcid="0000-0002-1825-0097",
    )
    # Act
    record = ReviewRunner(LocalDeterministicAdapter()).run(inputs)
    # Assert
    assert record.adapter_mode == "stub"


def test_legacy_review_without_a_mode_loads_as_unknown(tmp_path: Path):
    # Arrange
    home = tmp_path / "home"
    persisted = persist_review(_record("live"), home=home, now=_T)
    payload = json.loads(persisted.record_path.read_text())
    del payload["record"]["adapter_mode"]
    persisted.record_path.write_text(json.dumps(payload))
    # Act
    record = load_review_record("sub_2026_11_19_guard", home=home)
    # Assert
    assert record.adapter_mode == "unknown"


def test_live_review_is_decided():
    # Arrange
    record = replace(_record("live"), adapter="fixture-live-reviewer")
    # Act
    decision = DecisionEngine().decide(record, now=_T)
    # Assert
    assert decision.verdict == "accept"
