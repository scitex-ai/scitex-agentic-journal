"""Admission checks for contract-based submissions (design §13.1)."""

from __future__ import annotations

from scitex_agentic_journal._admission._checks import (
    FAILED,
    NOT_RUN,
    PASSED,
    Executor,
    NoExecutor,
)
from scitex_agentic_journal._admission._executor import ClewRerunExecutor
from scitex_agentic_journal._admission._run import load_admission, run_admission
from scitex_agentic_journal._admission._sandbox import (
    NO_EGRESS,
    PACKAGE_INDEX_EGRESS,
    ApptainerSandbox,
    SandboxError,
    SandboxResult,
)

__all__ = [
    "FAILED",
    "NOT_RUN",
    "NO_EGRESS",
    "PACKAGE_INDEX_EGRESS",
    "PASSED",
    "ApptainerSandbox",
    "ClewRerunExecutor",
    "Executor",
    "NoExecutor",
    "SandboxError",
    "SandboxResult",
    "load_admission",
    "run_admission",
]
