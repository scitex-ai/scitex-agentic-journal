"""Qwen reviewer-agent adapter — stub.

Real adapter wiring lives behind an API token + endpoint URL we don't
ship in this repo. The stub exists to:

* Pin the adapter shape so :class:`ReviewRunner` can type-check it
  immediately.
* Fail loudly with guidance until the real adapter ships — no silent
  fallback to a "mock review" payload.
"""

from __future__ import annotations

from scitex_agentic_journal._review._rubric import SubReportKind
from scitex_agentic_journal._review._types import (
    AdapterMode,
    ReviewerAdapter,
    ReviewSubReport,
    SubmissionInputs,
)


class QwenAdapterStub:
    """Self-hosted Qwen endpoint — not yet wired."""

    adapter_name: str = "qwen-self-hosted"
    adapter_version: str = "0.0.0-stub"
    mode: AdapterMode = "stub"

    def run_sub_report(
        self,
        kind: SubReportKind,
        inputs: SubmissionInputs,
        prompts_version: str,
    ) -> ReviewSubReport:
        raise NotImplementedError(
            f"QwenAdapterStub.run_sub_report({kind.value!r}) is a deliberate "
            "placeholder. Wire it to the self-hosted Qwen endpoint (HTTP) and "
            "supply the auth token via SCITEX_AJ_QWEN_TOKEN before use. "
            "No silent fallback to a fabricated review payload."
        )


# Static structural check.
_check_qwen: ReviewerAdapter = QwenAdapterStub()
del _check_qwen
