"""UiPort — reviewer dashboard hooks.

The reviewer dashboard (`_django` sub-app, mounted into scitex-hub via
`apps/workspace/agentic_journal_app`) renders submission status. The
port lets non-Django consumers (CLI, MCP server, in-memory tests)
emit the same status updates without dragging Django in.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


class SubmissionStatus(str, Enum):
    """Status values rendered on the reviewer dashboard."""

    GATE1_PENDING = "gate1-pending"
    GATE1_FAILED = "gate1-failed"
    UNDER_REVIEW = "under-review"
    DECIDED_ACCEPT = "decided-accept"
    DECIDED_REVISE = "decided-revise"
    DECIDED_REJECT = "decided-reject"
    PUBLISHED = "published"


@runtime_checkable
class UiPort(Protocol):
    """Loose coupling to the reviewer-dashboard UI.

    Default implementation is a no-op (CLI / headless). Production
    wires it to the Django app's status-update channel so the
    dashboard refreshes without polling.
    """

    def update_status(self, submission_id: str, status: SubmissionStatus) -> None:
        """Push a status update for ``submission_id``.

        Raises on transport failure. Never silently drops updates —
        the dashboard would lie about state otherwise.
        """
        ...
