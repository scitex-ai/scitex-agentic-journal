"""Typed surfaces of the editorial decision engine (Gate-3 / M3).

A :class:`DecisionRecord` is the immutable output of one decision-engine
run over a :class:`scitex_agentic_journal._review.ReviewRecord`. It
carries the verdict, the rules-set version, and every evaluated rule
hit (passed and failed) so an auditor can reconstruct *why* the engine
reached its verdict without re-running the engine.

The decision engine is rule-based — there is no LLM here. The record
is purely structured rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# The three possible editorial verdicts. ``Literal`` rather than an
# ``Enum`` so the JSON form is a plain string and the type checker
# narrows correctly on equality.
DecisionVerdict = Literal["accept", "revise", "reject"]


@dataclass(frozen=True, slots=True)
class RuleHit:
    """One evaluated rule from the decision rules-set.

    Both passing and failing rules emit a :class:`RuleHit` so the
    record carries the full audit trail. ``message`` MUST surface
    every threshold the rule compared against — no silent numbers.

    Attributes
    ----------
    rule_id :
        Stable identifier from the YAML rules-set (e.g.
        ``methodology_fatal``). Auditors cite this id.
    version :
        Rules-set version the rule belongs to (e.g. ``v1``). Pinned
        per-hit so multi-version audits stay unambiguous.
    passed :
        ``True`` if the rule's predicate evaluated false (i.e. the
        submission did NOT trigger the rule). ``False`` if the rule
        triggered. The terminology mirrors check-style audit tools:
        "passed" == "no issue", "failed" == "issue detected".
    message :
        Human-readable rationale. Includes every numeric threshold
        the rule compared so the auditor can verify by hand.
    """

    rule_id: str
    version: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """Immutable record of one decision-engine run.

    The record is content-addressed via the upstream review's
    ``content_hash`` so any later edit to the review is detectable
    on re-decide. ``rule_hits`` is a tuple — not a list — to keep
    the dataclass frozen and round-trip stable.

    Attributes
    ----------
    submission_id :
        The submission the decision applies to.
    verdict :
        One of ``accept``, ``revise``, ``reject``. The verdict is
        derived from the first failing rule by tier (reject wins
        over revise; revise wins over accept).
    rules_version :
        The YAML rules-set version that produced this decision.
        Bump-by-bump auditable.
    rule_hits :
        Every evaluated rule from the rules-set in declaration
        order. Passing rules are included so the record proves
        which rules did NOT fire, not just which did.
    decided_at :
        UTC instant the engine ran. Tests inject a fixed value;
        production uses ``datetime.now(timezone.utc)``.
    review_content_hash :
        ``sha256:<hex>`` of the canonicalised review record this
        decision was derived from. Pins the decision to the exact
        review so a tampered review is detectable.
    """

    submission_id: str
    verdict: DecisionVerdict
    rules_version: str
    rule_hits: tuple[RuleHit, ...]
    decided_at: datetime
    review_content_hash: str
