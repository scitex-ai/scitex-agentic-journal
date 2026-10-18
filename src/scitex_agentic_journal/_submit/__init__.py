"""M1 submit orchestrator — wires Gate-1 (#2/#3/#4) into one verdict.

Public surface (consumed by :mod:`scitex_agentic_journal._cli` and by
the future MCP server):

* :class:`Submission` — the typed bundle descriptor loaded from
  ``<bundle>/bundle.yaml``.
* :func:`load_submission` — parse the manifest into a
  :class:`Submission`. Raises :class:`SubmissionLoadError` on
  malformed input.
* :class:`Gate1Verdict` — structured outcome of
  :func:`run_gate1`. Carries the three sub-check results (ORCID,
  code-repo, Clew DAG) plus a single ``passed`` bool.
* :func:`run_gate1` — executes the three Gate-1 checks in declared
  order and short-circuits on the first failure. Raises
  :class:`Gate1Failure` carrying the structured per-check detail.
* :func:`persist_verdict` — mint a deterministic-ish submission id,
  write the persisted gate-1 record to disk, return the id.
"""

from scitex_agentic_journal._submit._loader import (
    SubmissionLoadError,
    load_submission,
)
from scitex_agentic_journal._submit._orchestrate import (
    Gate1Failure,
    Gate1Verdict,
    run_gate1,
)
from scitex_agentic_journal._submit._persist import (
    PersistedSubmission,
    persist_verdict,
)
from scitex_agentic_journal._submit._types import Submission

__all__ = [
    "Gate1Failure",
    "Gate1Verdict",
    "PersistedSubmission",
    "Submission",
    "SubmissionLoadError",
    "load_submission",
    "persist_verdict",
    "run_gate1",
]
