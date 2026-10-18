"""Live Paper hand-off proxy.

A thin shim over :class:`LivePaperPort` so callers can publish without
constructing the bundle by hand or importing the port directly.
"""

from __future__ import annotations

from pathlib import Path

from scitex_agentic_journal._ports import (
    LivePaperBundle,
    LivePaperPort,
    PublishReceipt,
)
from scitex_agentic_journal._publish._types import PersistentId


class LivePaperProxy:
    """Hand an accepted submission to a :class:`LivePaperPort`.

    The proxy stays intentionally thin: package up the bundle, call
    the port, return the receipt. Any extra logic (retries, audit
    log entries, hub notification fan-out) belongs upstream so this
    module remains testable with a stubbed port.
    """

    def __init__(self, port: LivePaperPort) -> None:
        self._port = port

    def publish(
        self,
        *,
        submission_id: str,
        persistent_id: PersistentId,
        manuscript_dir: Path,
        review_record_id: str,
        decision_record_id: str,
    ) -> PublishReceipt:
        """Package + hand off; return the live-paper receipt unchanged.

        Raises whatever :meth:`LivePaperPort.publish` raises — no
        suppression, no fallback to "publish later".
        """
        bundle = LivePaperBundle(
            submission_id=submission_id,
            persistent_id=persistent_id.persistent_id,
            manuscript_dir=manuscript_dir,
            review_record_id=review_record_id,
            decision_record_id=decision_record_id,
        )
        return self._port.publish(bundle)
