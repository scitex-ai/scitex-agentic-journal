"""Typed surface of the M4 paper-level re-review badge.

Mirrors :class:`scitex_live_paper._types.ReReviewBadge` byte-for-byte
so the hub can hand the value we return straight to
``mount(resolver=...)`` without an adapter step. We intentionally do
not import :mod:`scitex_live_paper` here; that would couple every
agentic-journal install to a live-paper install. Boundary check at
the hub's resolver: it asserts the shapes match.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, Optional


#: Verdict-to-status mapping ownership lives here (not in
#: :mod:`_decide`) so a decision-engine bump cannot silently change
#: the badge palette. Any new verdict MUST also update this mapping.
ReReviewStatus = Literal[
    "verified",       # green — agentic re-review found no issues
    "concerns",       # amber — re-review flagged caveats / weaknesses
    "contradicted",   # red — re-review contradicted at least one claim
    "stale",          # grey — no recent re-review (default until first run)
]


_VERDICT_TO_STATUS: Final[dict[str, ReReviewStatus]] = {
    "accept": "verified",
    "revise": "concerns",
    "reject": "contradicted",
}


def verdict_to_status(verdict: str | None) -> ReReviewStatus:
    """Map a M3 decision verdict to a live-paper :data:`ReReviewStatus`.

    ``None`` / unknown verdicts collapse to ``"stale"``: live-paper
    treats that as "no recent re-review" and renders the muted grey
    chip. We never raise — a future M3 verdict the hub does not know
    about must still produce a valid badge.
    """
    if verdict is None:
        return "stale"
    return _VERDICT_TO_STATUS.get(verdict, "stale")


@dataclass(frozen=True, slots=True)
class ReReviewBadge:
    """Paper-level re-review verdict the hub hands to live-paper.

    Shape matches :class:`scitex_live_paper._types.ReReviewBadge`:

    * ``status`` — one of :data:`ReReviewStatus`.
    * ``last_reviewed_at`` — ISO-8601 UTC string from the M3 decision
      record's ``decided_at`` (or the envelope ``written_at_utc`` if
      the inner record is missing for any reason).
    * ``reviewer`` — adapter id pulled from the M2 review record,
      prefixed with :data:`BADGE_REVIEWER_PREFIX` (e.g.
      ``"agentic-journal:local-deterministic"``) so the hub UI shows
      where the verdict came from rather than just the model name.
    * ``log_url`` — optional deep link into the agentic-journal log /
      record viewer. Hubs that don't yet have a record viewer pass
      ``None`` (the SPA hides the link).
    * ``notes`` — optional short operator-facing line. We synthesise
      it from the first failing rule hit so the badge has a
      one-glance summary.

    Frozen + slots — the badge is a value object passed across a
    network boundary; mutation would be a footgun.
    """

    status: ReReviewStatus
    last_reviewed_at: Optional[str] = None
    reviewer: Optional[str] = None
    log_url: Optional[str] = None
    notes: Optional[str] = None
