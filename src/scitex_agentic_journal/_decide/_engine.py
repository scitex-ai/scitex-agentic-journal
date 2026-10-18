"""Rule-based editorial decision engine — gate-3 over a ReviewRecord.

The engine consumes the immutable :class:`ReviewRecord` produced by
M2 and applies the bundled YAML rules-set
(:func:`scitex_agentic_journal._decide._rules.load_rules`) to derive
one of three verdicts: ``accept``, ``revise``, ``reject``.

The engine emits a :class:`RuleHit` for **every** rule in the set, not
just the ones that fired, so the resulting :class:`DecisionRecord`
proves which rules passed alongside which failed. Verdict precedence
is fixed: the first failing rule in the reject tier wins reject;
otherwise the first failing revise rule wins revise; otherwise
accept.

No LLM, no network — purely deterministic over the typed record.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from scitex_agentic_journal._decide._rules import (
    RuleSpec,
    RulesSet,
    load_rules,
)
from scitex_agentic_journal._decide._types import (
    DecisionRecord,
    DecisionVerdict,
    RuleHit,
)
from scitex_agentic_journal._review._persist import _serialise_for_hash
from scitex_agentic_journal._review._rubric import Severity
from scitex_agentic_journal._review._types import ReviewRecord


def _utcnow() -> datetime:
    """Wall-clock helper; tests inject a fixed ``now=`` instead."""
    return datetime.now(tz=timezone.utc)


def _review_content_hash(record: ReviewRecord) -> str:
    """Re-derive the ``sha256:<hex>`` content hash of the review.

    Re-uses the canonicalisation from
    :mod:`scitex_agentic_journal._review._persist` so a decision
    record's ``review_content_hash`` is byte-identical to the
    receipt printed by ``scitex-agentic-journal review``.
    """
    canonical = _serialise_for_hash(record)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DecisionEngine:
    """Apply the YAML rules-set to a :class:`ReviewRecord`.

    Parameters
    ----------
    rules :
        Pre-loaded rules-set. ``None`` triggers a lazy
        :func:`load_rules` call so the common case is "just construct".
    """

    def __init__(self, rules: RulesSet | None = None) -> None:
        self._rules = rules if rules is not None else load_rules()

    @property
    def rules(self) -> RulesSet:
        return self._rules

    def decide(
        self,
        record: ReviewRecord,
        *,
        now: datetime | None = None,
    ) -> DecisionRecord:
        """Return a :class:`DecisionRecord` for the given review.

        The rules-set is evaluated in declared order. Every rule
        emits a :class:`RuleHit`; the verdict is determined by the
        first failing rule by tier precedence (reject > revise >
        accept).

        Parameters
        ----------
        record :
            The immutable review record from M2.
        now :
            Override ``decided_at`` for deterministic tests; in
            production pass ``None``.

        Returns
        -------
        DecisionRecord
            Frozen record carrying the verdict, rules-set version,
            every rule hit, and the upstream review content_hash.
        """
        hits: list[RuleHit] = []
        first_reject: RuleHit | None = None
        first_revise: RuleHit | None = None
        for spec in self._rules.rules:
            hit = self._evaluate(spec, record)
            hits.append(hit)
            if hit.passed:
                continue
            if spec.verdict == "reject" and first_reject is None:
                first_reject = hit
            elif spec.verdict == "revise" and first_revise is None:
                first_revise = hit
        verdict: DecisionVerdict
        if first_reject is not None:
            verdict = "reject"
        elif first_revise is not None:
            verdict = "revise"
        else:
            verdict = "accept"
        decided_at = now if now is not None else _utcnow()
        return DecisionRecord(
            submission_id=record.submission_id,
            verdict=verdict,
            rules_version=self._rules.version,
            rule_hits=tuple(hits),
            decided_at=decided_at,
            review_content_hash=_review_content_hash(record),
        )

    # ------------------------------------------------------------------
    # Per-rule predicates. Each returns the :class:`RuleHit` with
    # ``passed=False`` when the rule's failure condition is met.
    # ------------------------------------------------------------------

    def _evaluate(self, spec: RuleSpec, record: ReviewRecord) -> RuleHit:
        evaluator = _RULE_EVALUATORS.get(spec.rule_id)
        if evaluator is None:
            # Unknown rule id in the YAML — surface loudly rather than
            # silently passing it. This keeps the YAML and the engine
            # in lock-step: adding a rule to the YAML without wiring it
            # here is a build-time error, not a silent no-op.
            raise RuleEvaluatorMissing(
                f"no Python evaluator for rule id {spec.rule_id!r} "
                f"(rules version {self._rules.version!r}); update "
                "scitex_agentic_journal._decide._engine._RULE_EVALUATORS."
            )
        return evaluator(spec, record, self._rules)


class RuleEvaluatorMissing(RuntimeError):
    """YAML declares a rule id with no Python evaluator wired."""


# ---------------------------------------------------------------------------
# Rule evaluators. Kept as free functions (not methods) so the registry
# stays a plain dict — easier to audit at a glance than method dispatch.
# Each evaluator returns a RuleHit with passed=False when the rule fires.
# ---------------------------------------------------------------------------


def _rule_methodology_fatal(
    spec: RuleSpec, record: ReviewRecord, rules: RulesSet
) -> RuleHit:
    max_sev = record.methodology.max_severity
    fired = max_sev is Severity.FATAL
    message = (
        f"methodology.max_severity={max_sev.value!r}; "
        f"rule fires when severity == {Severity.FATAL.value!r}."
    )
    return RuleHit(
        rule_id=spec.rule_id,
        version=rules.version,
        passed=not fired,
        message=message,
    )


def _rule_reproducibility_failed(
    spec: RuleSpec, record: ReviewRecord, rules: RulesSet
) -> RuleHit:
    passed_flag = bool(record.reproducibility.passed)
    fired = not passed_flag
    message = (
        f"reproducibility.passed={passed_flag!r}; "
        "rule fires when reproducibility.passed is False."
    )
    return RuleHit(
        rule_id=spec.rule_id,
        version=rules.version,
        passed=not fired,
        message=message,
    )


def _rule_claim_verify_zero_green(
    spec: RuleSpec, record: ReviewRecord, rules: RulesSet
) -> RuleHit:
    green = record.claim_verify.green_count
    fired = green == 0
    message = (
        f"claim_verify.green_count={green}; "
        "rule fires when green_count == 0."
    )
    return RuleHit(
        rule_id=spec.rule_id,
        version=rules.version,
        passed=not fired,
        message=message,
    )


def _rule_methodology_major(
    spec: RuleSpec, record: ReviewRecord, rules: RulesSet
) -> RuleHit:
    max_sev = record.methodology.max_severity
    fired = max_sev is Severity.MAJOR
    message = (
        f"methodology.max_severity={max_sev.value!r}; "
        f"rule fires when severity == {Severity.MAJOR.value!r}."
    )
    return RuleHit(
        rule_id=spec.rule_id,
        version=rules.version,
        passed=not fired,
        message=message,
    )


def _rule_claim_verify_red_present(
    spec: RuleSpec, record: ReviewRecord, rules: RulesSet
) -> RuleHit:
    red = record.claim_verify.red_claim_ids
    fired = len(red) > 0
    message = (
        f"claim_verify.red_claim_ids={list(red)!r}; "
        "rule fires when at least one red claim is present."
    )
    return RuleHit(
        rule_id=spec.rule_id,
        version=rules.version,
        passed=not fired,
        message=message,
    )


def _rule_novelty_overlap_high(
    spec: RuleSpec, record: ReviewRecord, rules: RulesSet
) -> RuleHit:
    threshold = rules.thresholds.novelty_revise_threshold
    score = float(record.novelty.overlap_score)
    fired = score >= threshold
    message = (
        f"novelty.overlap_score={score!r}; "
        f"rule fires when overlap_score >= {threshold!r} "
        "(thresholds.novelty_revise_threshold)."
    )
    return RuleHit(
        rule_id=spec.rule_id,
        version=rules.version,
        passed=not fired,
        message=message,
    )


def _rule_default_accept(
    spec: RuleSpec, record: ReviewRecord, rules: RulesSet
) -> RuleHit:
    del record
    return RuleHit(
        rule_id=spec.rule_id,
        version=rules.version,
        passed=True,
        message=(
            "default-accept anchor; passes unconditionally so every "
            "decision record cites at least one rule hit."
        ),
    )


_RULE_EVALUATORS = {
    "methodology_fatal": _rule_methodology_fatal,
    "reproducibility_failed": _rule_reproducibility_failed,
    "claim_verify_zero_green": _rule_claim_verify_zero_green,
    "methodology_major": _rule_methodology_major,
    "claim_verify_red_present": _rule_claim_verify_red_present,
    "novelty_overlap_high": _rule_novelty_overlap_high,
    "default_accept": _rule_default_accept,
}
