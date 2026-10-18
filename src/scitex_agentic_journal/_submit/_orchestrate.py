"""Run the three Gate-1 checks against a :class:`Submission`.

Executes ``verify_orcid`` (M1.1, #2) → ``cloned_code_repo`` (M1.2, #3)
→ ``verify_clew_dag`` (M1.3, #4) in declared order. Short-circuits on
the first failure and re-raises the structured ``GateFailure`` wrapped
in :class:`Gate1Failure` so the CLI orchestrator (and downstream MCP
server) can present a single uniform error shape.

The code-repo step uses the ``cloned_code_repo`` context manager so
the clone is cleaned up automatically after Gate-1 returns — the
gate's job is to *verify* cloneability, not to persist a working
tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scitex_agentic_journal._gate1 import (
    ClewVerification,
    GateFailure,
    OrcidRecord,
    cloned_code_repo,
    verify_clew_dag,
    verify_orcid,
)
from scitex_agentic_journal._submit._types import Submission


class Gate1Failure(Exception):
    """One of the three Gate-1 structural checks rejected the submission.

    Wraps the underlying :class:`GateFailure` so the CLI / MCP layer
    can ``except Gate1Failure`` once instead of three times. The
    ``check`` / ``reason`` / ``detail`` attributes mirror the wrapped
    failure for backwards-compatible message formatting.
    """

    def __init__(self, wrapped: GateFailure) -> None:
        super().__init__(str(wrapped))
        self.wrapped = wrapped
        self.check = wrapped.check
        self.reason = wrapped.reason
        self.detail = wrapped.detail


@dataclass(frozen=True)
class Gate1Verdict:
    """Structured success outcome of :func:`run_gate1`.

    Attributes
    ----------
    submission :
        The :class:`Submission` that was checked.
    orcid_record :
        The :class:`OrcidRecord` returned by ``verify_orcid``.
    code_repo_head_commit :
        The HEAD commit hash of the cloned repo at the time of check.
        The clone itself is not retained — Gate-1 only verifies
        *cloneability*.
    code_repo_head_subject :
        First line of the HEAD commit message at the time of check.
    clew_verification :
        The :class:`ClewVerification` returned by ``verify_clew_dag``.
    """

    submission: Submission
    orcid_record: OrcidRecord
    code_repo_head_commit: str
    code_repo_head_subject: str
    clew_verification: ClewVerification


def _run_orcid(submission: Submission) -> OrcidRecord:
    try:
        return verify_orcid(submission.orcid_id)
    except GateFailure as exc:
        raise Gate1Failure(exc) from exc


def _run_code_repo(submission: Submission) -> tuple[str, str]:
    try:
        with cloned_code_repo(submission.code_repo_url) as repo:
            return repo.head_commit, repo.head_subject
    except GateFailure as exc:
        raise Gate1Failure(exc) from exc


def _run_clew(submission: Submission) -> ClewVerification:
    try:
        return verify_clew_dag(submission.clew_project_dir)
    except GateFailure as exc:
        raise Gate1Failure(exc) from exc


def run_gate1(submission: Submission) -> Gate1Verdict:
    """Run the three Gate-1 checks in declared order, short-circuit on fail.

    Parameters
    ----------
    submission :
        The typed bundle descriptor produced by
        :func:`scitex_agentic_journal._submit.load_submission`.

    Returns
    -------
    Gate1Verdict
        A frozen record of every sub-check's payload.

    Raises
    ------
    Gate1Failure
        On the first sub-check that fails. ``Gate1Failure.check`` /
        ``reason`` / ``detail`` mirror the wrapped ``GateFailure`` so
        the CLI prints a single line without losing detail.
    """
    orcid_record = _run_orcid(submission)
    head_commit, head_subject = _run_code_repo(submission)
    clew_verification = _run_clew(submission)
    return Gate1Verdict(
        submission=submission,
        orcid_record=orcid_record,
        code_repo_head_commit=head_commit,
        code_repo_head_subject=head_subject,
        clew_verification=clew_verification,
    )
