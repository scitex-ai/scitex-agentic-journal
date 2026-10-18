"""ARA rubric — the four sub-reports the reviewer agent emits.

The rubric is the **versioned contract** between the journal and any
reviewer-agent runtime. A change to the rubric (adding a sub-report,
splitting one) bumps :data:`ARA_RUBRIC_VERSION`. Once a record is
written against version `v1`, the decision engine rolls forward by
re-running review under the newer rubric — never by silently
re-interpreting old `v1` records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

ARA_RUBRIC_VERSION: Final[str] = "v1"
"""Version stamp embedded in every :class:`ReviewRecord`."""


class SubReportKind(str, Enum):
    """The four ARA sub-reports.

    Order is fixed — review engines emit and dashboards render in
    this order so reviewers stay consistent across deployments.
    """

    REPRODUCIBILITY = "reproducibility"
    CLAIM_VERIFY = "claim_verify"
    NOVELTY = "novelty"
    METHODOLOGY = "methodology"


class Severity(str, Enum):
    """Methodology-criticism severity bands.

    ``NONE`` exists so :meth:`MethodologyReport.max_severity` returns
    a typed value even when there are zero criticisms, instead of
    forcing callers to handle an empty list specially.
    """

    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"
    FATAL = "fatal"


@dataclass(frozen=True, slots=True)
class AraRubric:
    """The full rubric — kinds + version + brief descriptions.

    Used by the dashboard / docs renderer; not by the runner directly
    (the runner just iterates over :class:`SubReportKind`).
    """

    version: str = ARA_RUBRIC_VERSION
    kinds: tuple[SubReportKind, ...] = (
        SubReportKind.REPRODUCIBILITY,
        SubReportKind.CLAIM_VERIFY,
        SubReportKind.NOVELTY,
        SubReportKind.METHODOLOGY,
    )

    descriptions: tuple[tuple[SubReportKind, str], ...] = (
        (
            SubReportKind.REPRODUCIBILITY,
            "Clone the repo, re-execute the entry-point, verify each claim "
            "re-derives green in a sandbox.",
        ),
        (
            SubReportKind.CLAIM_VERIFY,
            "For each claim in claims.yaml, run `clew claim verify` and "
            "record observed evidence vs the manifest.",
        ),
        (
            SubReportKind.NOVELTY,
            "Search scholar for nearest-neighbour papers; flag overlap and "
            "missed prior art.",
        ),
        (
            SubReportKind.METHODOLOGY,
            "Read the manuscript; list methodological weaknesses (stats, "
            "controls, sample size, confound handling).",
        ),
    )

    def describe(self, kind: SubReportKind) -> str:
        """Return the brief description for ``kind``."""
        for k, text in self.descriptions:
            if k == kind:
                return text
        raise KeyError(kind)
