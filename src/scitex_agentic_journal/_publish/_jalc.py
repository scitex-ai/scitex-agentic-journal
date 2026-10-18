"""JaLC id-minter stub.

Post-incorporation, agentic-journal will be a JaLC member and mint
DOIs under a JaLC-assigned prefix. Until then, calling :meth:`mint`
raises :class:`NotImplementedError` — explicitly, with guidance.
"""

from __future__ import annotations

from scitex_agentic_journal._publish._types import (
    Backend,
    IdMinter,
    MintInput,
    PersistentId,
)


class JalcStub:
    """JaLC backend — pending journal incorporation + JaLC membership."""

    backend: Backend = "jalc"

    def mint(self, mint_input: MintInput) -> PersistentId:
        raise NotImplementedError(
            "JalcStub.mint() is a deliberate placeholder. "
            "Wire it after JaLC membership is confirmed — see https://japanlinkcenter.org/. "
            "No silent fallback to ZenodoStub or the internal minter."
        )


_check_jalc: IdMinter = JalcStub()
del _check_jalc
