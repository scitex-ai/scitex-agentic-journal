"""HubPort — notifications back to a `scitex-hub` deployment.

When a decision is reached (`accept`, `revise`, `reject`) we want the
corresponding-author to learn about it. The Hub owns the user record +
notification surface (in-app / email / webhook); we just hand it a
typed event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

NotificationKind = Literal[
    "submission_received",
    "gate1_failed",
    "review_started",
    "decision_accept",
    "decision_revise",
    "decision_reject",
    "published",
]


@dataclass(frozen=True, slots=True)
class HubNotification:
    """One outbound event to the hub notification surface."""

    submission_id: str
    kind: NotificationKind
    recipient_orcid: str
    summary: str


@runtime_checkable
class HubPort(Protocol):
    """Loose coupling to a `scitex-hub` notification surface.

    Default implementation is a no-op (useful in headless test runs).
    A live deployment wires this to the hub's HTTP / MCP surface.
    """

    def notify(self, event: HubNotification) -> None:
        """Deliver ``event`` to the hub. Raises on transport failure."""
        ...
