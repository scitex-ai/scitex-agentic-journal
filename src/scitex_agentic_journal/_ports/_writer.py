"""WriterPort — read a manuscript bundle produced by `scitex-writer`.

The Writer owns the LaTeX manuscript directory layout. Agentic-journal
needs to ingest it and copy the relevant pieces into the submission
record. We stop short of importing `scitex-writer` so this package can
be used in deployments where Writer isn't installed (e.g. an MCP-only
reviewer agent host).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ManuscriptBundle:
    """In-memory handle to a writer-produced manuscript directory.

    Paths are :class:`pathlib.Path` so callers don't need to thread
    string handling. ``figures`` and ``bibliography`` may be empty
    sequences but never ``None`` (no silent fallback).
    """

    root: Path
    main_tex: Path
    figures: tuple[Path, ...] = field(default_factory=tuple)
    bibliography: tuple[Path, ...] = field(default_factory=tuple)


@runtime_checkable
class WriterPort(Protocol):
    """Loose coupling to `scitex-writer` manuscript bundles.

    Implementations:

    * **production**: walks a writer project dir, validates `main.tex`,
      `figures/`, `*.bib` and returns a :class:`ManuscriptBundle`.
    * **in-memory** (tests): builds a bundle from a temporary dir.

    A missing or malformed manuscript MUST raise — the gate-1 contract
    says no silent fallback for structural failures.
    """

    def load_bundle(self, manuscript_dir: Path) -> ManuscriptBundle:
        """Return a :class:`ManuscriptBundle` for ``manuscript_dir``.

        Raises a `WriterPortError` subclass on missing main.tex / bad
        bib / unreadable figure paths. Production implementations
        attach the offending path to the error message.
        """
        ...
