"""Internal-id minter — default backend, no external deps.

Mints ``scitex-aj-{YYYYMMDD}-{slug}-{hash6}`` deterministically from
the inputs so the same submission re-minted on the same day produces
the same id. That property matters for replays / disaster recovery.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Final

from scitex_agentic_journal._publish._types import (
    Backend,
    IdMinter,
    MintInput,
    PersistentId,
)

_SLUG_MAX_LEN: Final[int] = 40
"""Cap slug length so ids stay readable in URLs / citations."""

_BACKEND: Backend = "internal"


def _slugify(text: str) -> str:
    """ASCII-only kebab-case slug, capped at :data:`_SLUG_MAX_LEN` chars.

    Empty / non-alphanumeric inputs collapse to ``"untitled"`` rather
    than emitting an empty segment that would break the id format.
    """
    # Normalise unicode -> nearest ASCII.
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_bytes = decomposed.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_bytes.lower()
    kebab = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not kebab:
        return "untitled"
    return kebab[:_SLUG_MAX_LEN].rstrip("-") or "untitled"


def _short_hash(payload: str) -> str:
    """First 6 hex chars of sha256(payload) — collision space is
    16^6 ≈ 16M, plenty for an alpha-stage internal id namespace.
    """
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:6]


class InternalIdMinter:
    """Deterministic local id-minter — no network, no external auth."""

    backend: Backend = _BACKEND

    def mint(self, mint_input: MintInput) -> PersistentId:
        """Return ``scitex-aj-YYYYMMDD-<slug>-<hash6>`` for the input.

        Determinism is guaranteed because the inputs are fully
        captured: same MintInput → same id. Re-minting on a different
        ``decided_at`` day yields a different YYYYMMDD prefix, which
        is the intended behaviour (the id encodes the decision day).
        """
        date_prefix = mint_input.decided_at.strftime("%Y%m%d")
        slug = _slugify(mint_input.title)
        payload = (
            f"{mint_input.submission_id}|"
            f"{mint_input.corresponding_author_orcid}|"
            f"{mint_input.title}|"
            f"{date_prefix}"
        )
        hash6 = _short_hash(payload)
        return PersistentId(
            persistent_id=f"scitex-aj-{date_prefix}-{slug}-{hash6}",
            backend=_BACKEND,
        )


# Verify at import time that the class actually satisfies the protocol.
# (Catches a missing method or a type drift before any caller does.)
_minter_check: IdMinter = InternalIdMinter()
del _minter_check
