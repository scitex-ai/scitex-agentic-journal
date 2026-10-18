"""LivePaperPort — hand off accepted bundles to `scitex-live-paper`.

After gate-4 mints a persistent ID, the publish stage packages the
manuscript + claims + DAG + review record + decision record into a
`LivePaperBundle` and hands it to Live Paper. Live Paper does
rendering, hosting, and the interactive viewer; we do not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LivePaperBundle:
    """The packaged hand-off envelope.

    The strings carry record IDs (review, decision) instead of inlined
    JSON so the receiving Live Paper deployment can fetch the
    canonical records from agentic-journal on its own schedule.
    """

    submission_id: str
    persistent_id: str
    manuscript_dir: Path
    review_record_id: str
    decision_record_id: str


@dataclass(frozen=True, slots=True)
class PublishReceipt:
    """Return value from a successful hand-off.

    ``viewer_url`` is the persistent Live Paper page where the
    rendered manuscript will appear. ``rendered_at`` is left to the
    receiver (live-paper) so the rendering schedule is decoupled.
    """

    persistent_id: str
    viewer_url: str


@runtime_checkable
class LivePaperPort(Protocol):
    """Loose coupling to a `scitex-live-paper` deployment.

    A production implementation POSTs to live-paper's HTTP / MCP
    surface. A test implementation just records the bundles for
    assertion.
    """

    def publish(self, bundle: LivePaperBundle) -> PublishReceipt:
        """Hand off ``bundle`` to Live Paper and return the receipt.

        Raises on transport failure; never returns a partial /
        placeholder receipt.
        """
        ...
