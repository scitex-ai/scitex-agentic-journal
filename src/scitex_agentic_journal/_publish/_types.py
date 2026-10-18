"""Shared types for the publish stage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, Protocol, runtime_checkable

Backend = Literal[
    "internal",
    "zenodo-sandbox",
    "zenodo",
    "jalc",
    "crossref",
]
"""All recognised id-minter backends. Adding a new one MUST update
:func:`scitex_agentic_journal._publish._select.select_minter`."""


CITATION_TEMPLATE: Final[str] = (
    "SciTeX Agentic Journal ({persistent_id}). https://scitex.ai/aj/{persistent_id}"
)
"""Plain-text citation suffix used while the journal is pre-DOI.
Once the project moves to Zenodo / JaLC the DOI becomes the canonical
URL, but the internal id survives as the short handle."""


@dataclass(frozen=True, slots=True)
class MintInput:
    """Inputs the id-minter sees.

    Kept small and explicit so it survives schema drift in
    Submission / DecisionRecord without coupling here.
    """

    submission_id: str
    title: str
    corresponding_author_orcid: str
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class PersistentId:
    """A minted identifier + the backend that produced it."""

    persistent_id: str
    backend: Backend

    def citation_suffix(self) -> str:
        """Plain-text citation suffix using :data:`CITATION_TEMPLATE`."""
        return CITATION_TEMPLATE.format(persistent_id=self.persistent_id)


@runtime_checkable
class IdMinter(Protocol):
    """Common shape every id-minter exposes.

    ``backend`` is a stable string used in :class:`PersistentId`
    records and in operator dashboards. ``mint`` raises on failure;
    a half-minted id is never returned (no silent fallback).
    """

    backend: Backend

    def mint(self, mint_input: MintInput) -> PersistentId: ...
