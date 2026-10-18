"""SchedulerPort — enqueue / dequeue reviewer-agent jobs.

The reviewer agent loop is owned by the agent runtime (Spartan / Qwen /
local). Agentic-journal only knows: a submission `S` needs a review
record; it places a `ReviewJob` on a queue; the reviewer agent dequeues
it. The port hides whether the queue is in-memory, Redis, SQLite, or
something else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ReviewJob:
    """One unit of work for a reviewer agent."""

    submission_id: str
    prompts_version: str
    adapter: str


@runtime_checkable
class SchedulerPort(Protocol):
    """Loose coupling to whatever queues reviewer-agent jobs.

    The in-memory default ships with the package; replacement
    implementations (Redis / SQS / Hub-managed) plug in via DI.
    """

    def enqueue(self, job: ReviewJob) -> None:
        """Add ``job`` to the queue. Raises on persistence failure."""
        ...

    def dequeue(self) -> ReviewJob | None:
        """Return the next pending job, or ``None`` if the queue is empty.

        ``None`` here is **not** a silent-fallback "everything is fine"
        signal; it is the documented vacuous return when there is no
        work. Reviewer agents poll on this.
        """
        ...
