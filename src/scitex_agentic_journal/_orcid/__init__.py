"""ORCID client and iD link helpers (validation + URL forms + record fetch).

This package is a thin layer on top of :mod:`scitex_agentic_journal._gate1._orcid`.
The gate-1 module owns the network-touching logic; this package re-exports
that logic under a friendlier name for downstream consumers (review records,
Live Paper authorship cards, Hub user-link rendering) and adds:

* :class:`OrcidLink` — a hashable, comparable iD with ``url`` / ``canonical``
  / ``is_sandbox`` properties.
* :class:`OrcidClient` — a tiny session-holding wrapper around
  :func:`verify_orcid` so consumers do not re-thread session + base_url
  through every call.
* :func:`orcid_url` — pure URL builder, no network.

Design notes
------------
* No silent fallback. All failures bubble :class:`GateFailure` (the same
  typed error gate-1 raises). Consumers handle one error type, not two.
* The umbrella ``scitex.agentic_journal._orcid`` import path is not wired
  during alpha. Use the standalone ``scitex_agentic_journal._orcid``.
"""

from __future__ import annotations

from scitex_agentic_journal._gate1._errors import GateFailure
from scitex_agentic_journal._gate1._orcid import (
    OrcidRecord,
    normalize_orcid,
    verify_orcid,
)
from scitex_agentic_journal._orcid._client import OrcidClient
from scitex_agentic_journal._orcid._link import OrcidLink, orcid_url

__all__ = [
    "GateFailure",
    "OrcidClient",
    "OrcidLink",
    "OrcidRecord",
    "normalize_orcid",
    "orcid_url",
    "verify_orcid",
]
