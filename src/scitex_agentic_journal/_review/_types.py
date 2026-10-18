"""Typed surfaces of the review engine.

A :class:`ReviewRecord` is the immutable output of one reviewer-agent
run. It captures the four ARA sub-reports plus the prompt / rubric /
adapter versions so a decision can be re-derived deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from scitex_agentic_journal._review._rubric import Severity, SubReportKind

# ---------------------------------------------------------------------------
# Inputs given to a reviewer adapter run.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SubmissionInputs:
    """The slice of a submission a reviewer adapter actually needs.

    We pass IDs / paths, not the full `Submission` object, so adapter
    implementations can serialise the input over an HTTP wire without
    pulling agentic-journal types onto the reviewer host.
    """

    submission_id: str
    manuscript_dir: Path
    claims_path: Path
    dag_dir: Path
    code_repo_url: str
    corresponding_author_orcid: str


# ---------------------------------------------------------------------------
# Per-sub-report payloads.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReproducibilityReport:
    """Result of re-running the bundled code in a sandbox."""

    passed: bool
    sandbox_image: str
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ClaimVerifyReport:
    """Per-claim re-verification result."""

    green_claim_ids: tuple[str, ...]
    yellow_claim_ids: tuple[str, ...] = field(default_factory=tuple)
    red_claim_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def green_count(self) -> int:
        return len(self.green_claim_ids)


@dataclass(frozen=True, slots=True)
class NoveltyReport:
    """Literature triangulation outcome."""

    overlap_score: float  # 0.0 fully novel — 1.0 fully redundant
    nearest_neighbour_dois: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Criticism:
    """One methodology critique."""

    severity: Severity
    section: str
    note: str


@dataclass(frozen=True, slots=True)
class MethodologyReport:
    """Methodology critique sub-report."""

    criticisms: tuple[Criticism, ...] = field(default_factory=tuple)

    @property
    def max_severity(self) -> Severity:
        """Highest severity in the list, or :attr:`Severity.NONE`."""
        if not self.criticisms:
            return Severity.NONE
        order = (
            Severity.NONE,
            Severity.MINOR,
            Severity.MAJOR,
            Severity.FATAL,
        )
        return max(
            (c.severity for c in self.criticisms),
            key=order.index,
        )


# ---------------------------------------------------------------------------
# Aggregate review record.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewSubReport:
    """Wraps one sub-report payload with its kind discriminator."""

    kind: SubReportKind
    payload: object


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    """Immutable record of one reviewer-agent run.

    ``status`` is not stored — the decision engine reads the four
    sub-reports and runs gate-3 rules separately. The record is
    purely evidence; it does not pre-commit to an outcome.
    """

    submission_id: str
    adapter: str
    adapter_version: str
    prompts_version: str
    rubric_version: str
    reproducibility: ReproducibilityReport
    claim_verify: ClaimVerifyReport
    novelty: NoveltyReport
    methodology: MethodologyReport
    started_at: datetime
    finished_at: datetime


# ---------------------------------------------------------------------------
# Adapter protocol.
# ---------------------------------------------------------------------------


AdapterMode = Literal["stub", "live"]


@runtime_checkable
class ReviewerAdapter(Protocol):
    """Plug-point for reviewer-agent runtimes (Qwen, Spartan, Claude, ...).

    Implementations:

    * Run the prompt against an LLM endpoint.
    * Return a fully-populated `ReviewSubReport` per call.
    * Raise on transport / quota / parse error — never return a partial
      report. (No silent fallback.)
    """

    adapter_name: str
    adapter_version: str
    mode: AdapterMode

    def run_sub_report(
        self,
        kind: SubReportKind,
        inputs: SubmissionInputs,
        prompts_version: str,
    ) -> ReviewSubReport: ...
