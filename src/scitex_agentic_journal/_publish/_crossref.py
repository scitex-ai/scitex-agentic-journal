"""Crossref id-minter stub.

Crossref membership is currently out of scope (the journal is
positioning JaLC + Zenodo first). The stub exists so the backend
catalogue is complete and operator dashboards can list it as
"not enabled" rather than "unknown".
"""

from __future__ import annotations

from scitex_agentic_journal._publish._types import (
    Backend,
    IdMinter,
    MintInput,
    PersistentId,
)


class CrossrefStub:
    """Crossref backend — not enabled; raises on use."""

    backend: Backend = "crossref"

    def mint(self, mint_input: MintInput) -> PersistentId:
        raise NotImplementedError(
            "CrossrefStub.mint() is a deliberate placeholder. "
            "Crossref membership is currently out of scope for the journal; "
            "if you enable this backend, wire https://api.crossref.org/ "
            "and supply SCITEX_AJ_CROSSREF_TOKEN. No silent fallback."
        )


_check_crossref: IdMinter = CrossrefStub()
del _check_crossref
