"""Review runner — orchestrates the four sub-reports for one submission.

The runner is **pure orchestration**: it asks the adapter for each
sub-report in the rubric-fixed order and assembles the
:class:`ReviewRecord`. It does not call LLMs, it does not score
severities, and it does not decide accept / revise / reject. Gate-3
(decision engine) consumes the record this runner produces.
"""

from __future__ import annotations

from datetime import datetime, timezone

from scitex_agentic_journal._review._rubric import (
    ARA_RUBRIC_VERSION,
    SubReportKind,
)
from scitex_agentic_journal._review._types import (
    ClaimVerifyReport,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewerAdapter,
    ReviewRecord,
    ReviewSubReport,
    SubmissionInputs,
)


def _utcnow() -> datetime:
    """Wall-clock helper. Pulled out so tests can monkey-patch.

    We use timezone-aware UTC because the record gets persisted; a
    naive `datetime.now()` would lose the timezone on round-trip.
    """
    return datetime.now(tz=timezone.utc)


class ReviewRunner:
    """Run all four ARA sub-reports against one submission.

    Parameters
    ----------
    adapter :
        Reviewer-agent adapter. Any object satisfying
        :class:`ReviewerAdapter` works; the in-memory test adapter
        plugs in the same way as Qwen / Spartan / Claude adapters.
    prompts_version :
        Which prompt set to feed the adapter. The runner does not
        manage prompts itself; it just threads the version string
        through so the adapter can pick up the right files and so
        the record can be re-derived later.
    """

    def __init__(
        self,
        adapter: ReviewerAdapter,
        *,
        prompts_version: str = "v1",
    ) -> None:
        self._adapter = adapter
        self._prompts_version = prompts_version

    @property
    def adapter(self) -> ReviewerAdapter:
        return self._adapter

    @property
    def prompts_version(self) -> str:
        return self._prompts_version

    def run(self, inputs: SubmissionInputs) -> ReviewRecord:
        """Run the four sub-reports and assemble a :class:`ReviewRecord`.

        The sub-reports are requested **in rubric order**. If the
        adapter raises on any kind, the runner does not swallow it —
        the exception bubbles to the caller (gate-3 must not run on
        a partial record).
        """
        started_at = _utcnow()
        sub_reports: dict[SubReportKind, ReviewSubReport] = {}
        for kind in SubReportKind:
            sub_reports[kind] = self._adapter.run_sub_report(
                kind=kind,
                inputs=inputs,
                prompts_version=self._prompts_version,
            )
        finished_at = _utcnow()
        return ReviewRecord(
            submission_id=inputs.submission_id,
            adapter=self._adapter.adapter_name,
            adapter_version=self._adapter.adapter_version,
            prompts_version=self._prompts_version,
            rubric_version=ARA_RUBRIC_VERSION,
            reproducibility=_payload(
                sub_reports[SubReportKind.REPRODUCIBILITY],
                ReproducibilityReport,
            ),
            claim_verify=_payload(
                sub_reports[SubReportKind.CLAIM_VERIFY],
                ClaimVerifyReport,
            ),
            novelty=_payload(
                sub_reports[SubReportKind.NOVELTY],
                NoveltyReport,
            ),
            methodology=_payload(
                sub_reports[SubReportKind.METHODOLOGY],
                MethodologyReport,
            ),
            started_at=started_at,
            finished_at=finished_at,
        )


def _payload(sub_report: ReviewSubReport, expected_type: type) -> object:
    """Unwrap the typed payload from a :class:`ReviewSubReport`.

    Loudly type-checks at the boundary so a misbehaving adapter that
    returns the wrong payload class for a kind fails immediately —
    not silently later inside the decision engine.
    """
    if not isinstance(sub_report.payload, expected_type):
        raise TypeError(
            f"adapter returned {type(sub_report.payload).__name__} for kind "
            f"{sub_report.kind.value}; expected {expected_type.__name__}"
        )
    return sub_report.payload
