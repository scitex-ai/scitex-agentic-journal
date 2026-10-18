"""Gate-2 review engine: ARA rubric + runner + versioned prompts + adapter.

The review engine produces a :class:`ReviewRecord` per submission. The
record carries four typed sub-reports (reproducibility, claim verify,
novelty, methodology) plus the prompt and adapter versions used. The
record is **immutable** once written: rules-version + decision live
in `_decision` (M3), not here.

This module only orchestrates. Actual LLM calls live behind a
:class:`ReviewerAdapter` and are not invoked here in unit tests.
"""

from __future__ import annotations

from scitex_agentic_journal._review._adapters import (
    ADAPTER_REGISTRY,
    UnknownAdapterError,
    list_adapter_names,
    select_adapter,
)
from scitex_agentic_journal._review._load_gate1 import (
    ReviewLoadError,
    load_submission_inputs,
)
from scitex_agentic_journal._review._local_adapter import LocalDeterministicAdapter
from scitex_agentic_journal._review._persist import (
    PersistedReview,
    persist_review,
)
from scitex_agentic_journal._review._qwen_adapter import QwenAdapterStub
from scitex_agentic_journal._review._rubric import (
    ARA_RUBRIC_VERSION,
    AraRubric,
    Severity,
    SubReportKind,
)
from scitex_agentic_journal._review._runner import ReviewRunner
from scitex_agentic_journal._review._types import (
    ClaimVerifyReport,
    Criticism,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewerAdapter,
    ReviewRecord,
    ReviewSubReport,
    SubmissionInputs,
)

__all__ = [
    "ADAPTER_REGISTRY",
    "ARA_RUBRIC_VERSION",
    "AraRubric",
    "ClaimVerifyReport",
    "Criticism",
    "LocalDeterministicAdapter",
    "MethodologyReport",
    "NoveltyReport",
    "PersistedReview",
    "QwenAdapterStub",
    "ReproducibilityReport",
    "ReviewLoadError",
    "ReviewRecord",
    "ReviewRunner",
    "ReviewSubReport",
    "ReviewerAdapter",
    "Severity",
    "SubReportKind",
    "SubmissionInputs",
    "UnknownAdapterError",
    "list_adapter_names",
    "load_submission_inputs",
    "persist_review",
    "select_adapter",
]
