"""Gate-3 editorial decision engine: accept | revise | reject.

The decision engine consumes the immutable :class:`ReviewRecord`
produced by M2 and applies a versioned YAML rules-set to derive one
of three verdicts plus a structured rationale (every evaluated rule
emits a :class:`RuleHit`).

The engine is **rule-based** — no LLM, no thresholds in code. Every
numeric threshold lives in
``_decide/rules/<version>.yaml`` and is surfaced in the rule hit
message so an auditor can verify what the engine compared without
re-reading the YAML.

Out of scope here: appeals / human override (post-MVP).
"""

from __future__ import annotations

from scitex_agentic_journal._decide._engine import (
    DecisionEngine,
    RuleEvaluatorMissing,
)
from scitex_agentic_journal._decide._load_review import (
    DecisionLoadError,
    load_review_record,
)
from scitex_agentic_journal._decide._persist import (
    PersistedDecision,
    persist_decision,
)
from scitex_agentic_journal._decide._rules import (
    RULES_VERSION,
    RulesLoadError,
    RulesSet,
    RuleSpec,
    RulesThresholds,
    load_rules,
)
from scitex_agentic_journal._decide._types import (
    DecisionRecord,
    DecisionVerdict,
    RuleHit,
)

__all__ = [
    "DecisionEngine",
    "DecisionLoadError",
    "DecisionRecord",
    "DecisionVerdict",
    "PersistedDecision",
    "RULES_VERSION",
    "RuleEvaluatorMissing",
    "RuleHit",
    "RuleSpec",
    "RulesLoadError",
    "RulesSet",
    "RulesThresholds",
    "load_review_record",
    "load_rules",
    "persist_decision",
]
