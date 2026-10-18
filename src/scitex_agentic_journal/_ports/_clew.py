"""ClewPort — read claims + DAG from a `scitex-clew` project.

Clew owns the claim model; agentic-journal **consumes** it. The port
mirrors the slice we actually need (claim list, verification status,
DAG snapshot hash) without importing Clew at module-load time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable


class ClewVerificationStatus(str, Enum):
    """Mirror of Clew's claim verification state for read-only consumers."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class ClewClaim:
    """One claim from `claims.yaml`, slimmed to fields we render / decide on."""

    claim_id: str
    summary: str
    status: ClewVerificationStatus


@dataclass(frozen=True, slots=True)
class ClewDagSnapshot:
    """A pointer to a Clew DAG state at submission time.

    ``content_hash`` is the hash agentic-journal records in the
    submission so a reviewer agent can verify it didn't drift between
    submission and re-run.
    """

    project_root: Path
    content_hash: str
    claim_count: int


@runtime_checkable
class ClewPort(Protocol):
    """Loose coupling to a `scitex-clew` project on disk.

    A production implementation shells out to `clew claim list` /
    `clew dag snapshot`. An in-memory implementation (tests) returns
    a hand-built snapshot.
    """

    def load_claims(self, project_root: Path) -> tuple[ClewClaim, ...]:
        """All claims in ``claims.yaml``. Empty tuple is allowed.

        Caller filters by status; the port does not skip RED claims.
        """
        ...

    def snapshot_dag(self, project_root: Path) -> ClewDagSnapshot:
        """Take a content-hashed DAG snapshot.

        Raises if `dag/` is missing — gate-1 needs to fail loud on
        this, not silently degrade.
        """
        ...
