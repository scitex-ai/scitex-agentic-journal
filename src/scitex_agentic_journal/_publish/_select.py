"""Backend selection for the publish stage.

The selected backend is configured per deployment via the
``SCITEX_AJ_ID_BACKEND`` env var. Looking up an unknown backend
raises :class:`UnknownBackendError` — no silent fallback to
``InternalIdMinter``.
"""

from __future__ import annotations

from scitex_agentic_journal._publish._crossref import CrossrefStub
from scitex_agentic_journal._publish._internal import InternalIdMinter
from scitex_agentic_journal._publish._jalc import JalcStub
from scitex_agentic_journal._publish._types import Backend, IdMinter
from scitex_agentic_journal._publish._zenodo import (
    ZenodoSandboxStub,
    ZenodoStub,
)


class UnknownBackendError(ValueError):
    """Raised when :func:`select_minter` is given an unknown backend name."""


def select_minter(backend: str) -> IdMinter:
    """Return a fresh minter for ``backend``.

    Raises :class:`UnknownBackendError` for unknown / misspelled
    backends. The deployment operator gets a clear error rather than
    a silent fallback to a different id namespace.
    """
    table: dict[Backend, type[IdMinter]] = {
        "internal": InternalIdMinter,
        "zenodo-sandbox": ZenodoSandboxStub,
        "zenodo": ZenodoStub,
        "jalc": JalcStub,
        "crossref": CrossrefStub,
    }
    if backend not in table:
        raise UnknownBackendError(
            f"unknown id-backend {backend!r}; known backends: {sorted(table)}"
        )
    return table[backend]()  # type: ignore[abstract]
