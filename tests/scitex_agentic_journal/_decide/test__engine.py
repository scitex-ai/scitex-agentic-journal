"""Unit tests for :mod:`scitex_agentic_journal._decide._engine` — pure rules.

No mocks, no HTTP. Each test arranges a typed :class:`ReviewRecord`
directly and asserts one decision-engine outcome at a time so an
audit can pinpoint exactly which rule a regression hits.
"""

from __future__ import annotations

from datetime import datetime, timezone

from scitex_agentic_journal._decide import (
    DecisionEngine,
    DecisionRecord,
    RuleHit,
)
from scitex_agentic_journal._review import (
    ARA_RUBRIC_VERSION,
    ClaimVerifyReport,
    Criticism,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewRecord,
    Severity,
)

_FIXED_TIME = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)  # stx-allow: STX-NL001


def _review(
    *,
    submission_id: str = "sub_2026_06_13_abc123",
    reproducibility: ReproducibilityReport | None = None,
    claim_verify: ClaimVerifyReport | None = None,
    novelty: NoveltyReport | None = None,
    methodology: MethodologyReport | None = None,
) -> ReviewRecord:
    return ReviewRecord(
        submission_id=submission_id,
        adapter="local-deterministic",
        adapter_version="0.1.0",
        prompts_version="v1",
        rubric_version=ARA_RUBRIC_VERSION,
        reproducibility=reproducibility
        or ReproducibilityReport(passed=True, sandbox_image="local"),
        claim_verify=claim_verify or ClaimVerifyReport(green_claim_ids=("c1",)),
        novelty=novelty or NoveltyReport(overlap_score=0.0),
        methodology=methodology or MethodologyReport(criticisms=()),
        started_at=_FIXED_TIME,
        finished_at=_FIXED_TIME,
    )


# ---------------------------------------------------------------------------
# Verdict tier — happy paths
# ---------------------------------------------------------------------------


def test_engine_accepts_happy_path_review() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "accept"


def test_engine_returns_decision_record_instance() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert isinstance(decision, DecisionRecord)


def test_engine_threads_submission_id_into_decision() -> None:
    # Arrange
    record = _review(submission_id="sub_2026_06_13_deadbe")
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.submission_id == "sub_2026_06_13_deadbe"


def test_engine_stamps_rules_version_on_decision() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.rules_version == "v1"


def test_engine_stamps_decided_at_when_overridden() -> None:
    # Arrange
    record = _review()
    fixed = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # stx-allow: STX-NL001
    # Act
    decision = DecisionEngine().decide(record, now=fixed)
    # Assert
    assert decision.decided_at == fixed


def test_engine_carries_review_content_hash_with_sha256_prefix() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.review_content_hash.startswith("sha256:")


# ---------------------------------------------------------------------------
# Reject tier — first-failing-reject-rule wins
# ---------------------------------------------------------------------------


def test_engine_rejects_on_methodology_fatal() -> None:
    # Arrange
    record = _review(
        methodology=MethodologyReport(
            criticisms=(
                Criticism(severity=Severity.FATAL, section="§3", note="bad stats"),
            ),
        ),
    )
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "reject"


def test_engine_rejects_when_reproducibility_fails() -> None:
    # Arrange
    record = _review(
        reproducibility=ReproducibilityReport(passed=False, sandbox_image="local"),
    )
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "reject"


def test_engine_rejects_when_zero_green_claims() -> None:
    # Arrange
    record = _review(claim_verify=ClaimVerifyReport(green_claim_ids=()))
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "reject"


def test_engine_reject_wins_over_revise_when_both_apply() -> None:
    """methodology=FATAL (reject) and overlap=0.9 (revise) → reject wins."""
    # Arrange
    record = _review(
        methodology=MethodologyReport(
            criticisms=(
                Criticism(severity=Severity.FATAL, section="§3", note="."),
            ),
        ),
        novelty=NoveltyReport(overlap_score=0.9),
    )
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "reject"


# ---------------------------------------------------------------------------
# Revise tier
# ---------------------------------------------------------------------------


def test_engine_revises_on_methodology_major() -> None:
    # Arrange
    record = _review(
        methodology=MethodologyReport(
            criticisms=(
                Criticism(severity=Severity.MAJOR, section="§2", note="control"),
            ),
        ),
    )
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "revise"


def test_engine_revises_when_red_claims_present() -> None:
    # Arrange
    record = _review(
        claim_verify=ClaimVerifyReport(
            green_claim_ids=("c1",), red_claim_ids=("c2",)
        ),
    )
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "revise"


def test_engine_revises_when_overlap_meets_threshold() -> None:
    # Arrange
    record = _review(novelty=NoveltyReport(overlap_score=0.7))
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "revise"


def test_engine_revises_when_overlap_above_threshold() -> None:
    # Arrange
    record = _review(novelty=NoveltyReport(overlap_score=0.85))
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "revise"


def test_engine_does_not_revise_when_overlap_below_threshold() -> None:
    # Arrange
    record = _review(novelty=NoveltyReport(overlap_score=0.5))
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "accept"


def test_engine_does_not_revise_on_methodology_minor_alone() -> None:
    # Arrange
    record = _review(
        methodology=MethodologyReport(
            criticisms=(
                Criticism(severity=Severity.MINOR, section="§1", note="typo"),
            ),
        ),
    )
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert decision.verdict == "accept"


# ---------------------------------------------------------------------------
# RuleHit audit trail
# ---------------------------------------------------------------------------


def test_engine_emits_one_rule_hit_per_yaml_rule() -> None:
    # Arrange
    record = _review()
    engine = DecisionEngine()
    expected = len(engine.rules.rules)
    # Act
    decision = engine.decide(record, now=_FIXED_TIME)
    # Assert
    assert len(decision.rule_hits) == expected


def test_engine_rule_hits_are_typed_rule_hit_instances() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert all(isinstance(h, RuleHit) for h in decision.rule_hits)


def test_engine_rule_hit_for_methodology_fatal_fails_on_fatal_record() -> None:
    # Arrange
    record = _review(
        methodology=MethodologyReport(
            criticisms=(
                Criticism(severity=Severity.FATAL, section="§3", note="."),
            ),
        ),
    )
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    hit = next(h for h in decision.rule_hits if h.rule_id == "methodology_fatal")
    # Assert
    assert hit.passed is False


def test_engine_rule_hit_for_methodology_fatal_passes_on_clean_record() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    hit = next(h for h in decision.rule_hits if h.rule_id == "methodology_fatal")
    # Assert
    assert hit.passed is True


def test_engine_rule_hit_messages_surface_numeric_threshold() -> None:
    """No silent thresholds — the overlap rule must print 0.7."""
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    hit = next(
        h for h in decision.rule_hits if h.rule_id == "novelty_overlap_high"
    )
    # Assert
    assert "0.7" in hit.message


def test_engine_rule_hit_default_accept_always_passes() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    hit = next(h for h in decision.rule_hits if h.rule_id == "default_accept")
    # Assert
    assert hit.passed is True


def test_engine_rule_hit_carries_rules_version_stamp() -> None:
    # Arrange
    record = _review()
    # Act
    decision = DecisionEngine().decide(record, now=_FIXED_TIME)
    # Assert
    assert all(h.version == "v1" for h in decision.rule_hits)
