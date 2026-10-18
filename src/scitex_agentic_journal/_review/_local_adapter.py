"""Local deterministic reviewer adapter — no LLM, no network.

Implements the :class:`ReviewerAdapter` protocol with a hand-rolled,
fully-deterministic payload per sub-report so the M2 pipeline (Gate-1
record → ReviewRunner → persisted review) runs end-to-end *without*
needing API tokens for Qwen / Spartan / Claude. The output is NOT a
real review — it's a structural placeholder that lets downstream
gates exercise their shapes (decision engine #7, persistent ID #8,
publish hand-off #9).

The acceptance language in #6 names this provider explicitly:
"Spartan / Qwen / local". This module is the "local" branch — useful
for development, CI, and the operator's local-staging bring-up
before any live LLM endpoint exists.

Each sub-report is honest about what it can and cannot say without
real model output:

* reproducibility: ``passed=True``, ``sandbox_image='local-deterministic'``
  with a note that no sandbox actually ran.
* claim_verify: echo the Gate-1 ``clew claim verify`` triage — the
  runner does not re-run ``clew`` from here; the Gate-1 verdict
  already carries that result and we forward it so downstream rules
  (M3 ``claim_verify_zero_green``) have something to evaluate. If
  the gate-1 record cannot be located the report degrades to the
  honest "empty triage" fallback.
* novelty: ``overlap_score=0.0`` (i.e. no signal), no neighbours.
* methodology: empty :class:`Criticism` tuple, ``Severity.NONE``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scitex_agentic_journal._review._rubric import SubReportKind
from scitex_agentic_journal._review._types import (
    AdapterMode,
    ClaimVerifyReport,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewSubReport,
    ReviewerAdapter,
    SubmissionInputs,
)


_NOTE = (
    "local-deterministic adapter — no LLM ran. Use only for "
    "structural pipeline development; replace with a live "
    "Qwen/Spartan adapter for an editorial decision."
)


def _gate1_claim_triage(
    submission_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Best-effort echo of the Gate-1 clew claim triage.

    Returns ``(green_claim_ids, red_claim_ids)``. Resolution mirrors
    :func:`scitex_agentic_journal._submit._persist._submission_home`:
    ``$SCITEX_AGENTIC_JOURNAL_HOME`` then
    ``~/.scitex/agentic-journal``. Any error (no env, no file, bad
    JSON, missing keys) collapses to two empty tuples — the honest
    "I have no signal" fallback that keeps the adapter callable
    even when called outside the canonical submission home.
    """
    home_env = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    home = Path(home_env).expanduser().resolve() if home_env else (
        Path.home() / ".scitex" / "agentic-journal"
    )
    gate1_path = home / "submissions" / submission_id / "gate1.json"
    try:
        payload = json.loads(gate1_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (), ()
    clew = payload.get("clew_verification") if isinstance(payload, dict) else None
    if not isinstance(clew, dict):
        return (), ()
    green = tuple(str(c) for c in clew.get("green_claims", ()) if isinstance(c, str))
    red = tuple(str(c) for c in clew.get("red_claims", ()) if isinstance(c, str))
    return green, red


class LocalDeterministicAdapter:
    """Hand-rolled, no-network adapter — satisfies :class:`ReviewerAdapter`.

    Static analogue of the Qwen / Spartan adapters: same shape, same
    method, deterministic output. The output is honest about its
    placeholder nature via the embedded note strings.
    """

    adapter_name: str = "local-deterministic"
    adapter_version: str = "0.1.0"
    mode: AdapterMode = "stub"

    def run_sub_report(
        self,
        kind: SubReportKind,
        inputs: SubmissionInputs,
        prompts_version: str,
    ) -> ReviewSubReport:
        del prompts_version  # version is captured in ReviewRecord
        if kind is SubReportKind.REPRODUCIBILITY:
            return ReviewSubReport(
                kind=kind,
                payload=ReproducibilityReport(
                    passed=True,
                    sandbox_image="local-deterministic",
                    notes=_NOTE,
                ),
            )
        if kind is SubReportKind.CLAIM_VERIFY:
            green, red = _gate1_claim_triage(inputs.submission_id)
            return ReviewSubReport(
                kind=kind,
                payload=ClaimVerifyReport(
                    green_claim_ids=green,
                    yellow_claim_ids=(),
                    red_claim_ids=red,
                ),
            )
        if kind is SubReportKind.NOVELTY:
            return ReviewSubReport(
                kind=kind,
                payload=NoveltyReport(
                    overlap_score=0.0,
                    nearest_neighbour_dois=(),
                ),
            )
        if kind is SubReportKind.METHODOLOGY:
            return ReviewSubReport(
                kind=kind,
                payload=MethodologyReport(criticisms=()),
            )
        # Defensive — the SubReportKind enum is closed so we should
        # never get here; raise loudly if we do.
        raise ValueError(
            f"LocalDeterministicAdapter does not know how to run sub-report "
            f"kind {kind!r}; this is a bug in scitex-agentic-journal."
        )


# Static structural check at import time — protects against a future
# refactor that breaks the protocol shape.
_check: ReviewerAdapter = LocalDeterministicAdapter()
del _check
