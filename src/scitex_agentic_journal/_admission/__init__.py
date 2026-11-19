"""Admission checks for contract-based submissions (design §13.1)."""

from __future__ import annotations

from scitex_agentic_journal._admission._checks import (
    FAILED,
    NOT_RUN,
    PASSED,
    Executor,
    NoExecutor,
)
from scitex_agentic_journal._admission._run import load_admission, run_admission

__all__ = [
    "FAILED",
    "NOT_RUN",
    "PASSED",
    "Executor",
    "NoExecutor",
    "load_admission",
    "run_admission",
]
