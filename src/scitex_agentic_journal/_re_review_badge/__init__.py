"""M4 paper-level re-review badge — agentic-journal → live-paper contract.

This package is the producer side of the ReReviewBadge contract that
``scitex-live-paper`` lands in PR #38: live-paper exposes a typed
``BundleContext.re_review_badge`` slot the host populates per-request
via ``mount(resolver=...)``. Once we expose a "latest review/decision
for a paper id" query, the hub's resolver hands the badge in.

This module is that query.

Public surface
--------------

* :class:`ReReviewBadge` — the exact dataclass shape live-paper's
  :mod:`scitex_live_paper._types.ReReviewBadge` expects. We re-emit
  the shape here so the hub does not need to import live-paper just
  to type-check the resolver return.
* :data:`ReReviewStatus` — the four-state ``Literal`` mirroring the
  live-paper status palette: ``verified``, ``concerns``,
  ``contradicted``, ``stale``.
* :func:`resolve_badge_for_paper` — scans
  ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/*/persistent_id.json``
  for the matching ``persistent_id`` and emits the badge from that
  submission's ``decision.json`` + ``review.json``. Returns ``None``
  if no matching submission exists — the SPA then hides the badge
  per the live-paper contract.

The boundary is deliberately tight:

* This module **owns** the verdict-to-status mapping and the
  agentic-journal-side audit trail (``log_url`` points at the
  resolver-produced URL, not at clew).
* This module does **not** import :mod:`scitex_live_paper`. The shape
  is a separate copy; the consumer adapts at the boundary.
* Per-claim chips stay owned by ``scitex-clew``. This badge is only
  the paper-level rolled-up verdict.
"""

from __future__ import annotations

from scitex_agentic_journal._re_review_badge._resolver import (
    BADGE_REVIEWER_PREFIX,
    resolve_badge_for_paper,
)
from scitex_agentic_journal._re_review_badge._types import (
    ReReviewBadge,
    ReReviewStatus,
    verdict_to_status,
)

__all__ = [
    "BADGE_REVIEWER_PREFIX",
    "ReReviewBadge",
    "ReReviewStatus",
    "resolve_badge_for_paper",
    "verdict_to_status",
]
