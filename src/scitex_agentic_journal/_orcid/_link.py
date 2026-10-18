"""Pure-Python ORCID iD link helpers — no network.

Useful in templates / serialisers / CLI output where we need a stable
URL form for an iD without paying for a network resolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from scitex_agentic_journal._gate1._orcid import normalize_orcid

Env = Literal["prod", "sandbox"]

_PROD_HOST: Final[str] = "orcid.org"
_SANDBOX_HOST: Final[str] = "sandbox.orcid.org"


def orcid_url(orcid_id: str, *, env: Env = "prod") -> str:
    """Return ``https://orcid.org/<bare-id>`` (or sandbox).

    Normalises the input first, so any URL / bare / sandbox form is
    accepted. The output is the **canonical https URL** ORCID expects
    in citations and bio links.

    Examples
    --------
    >>> orcid_url("0000-0002-1825-0097")
    'https://orcid.org/0000-0002-1825-0097'
    >>> orcid_url("https://orcid.org/0000-0002-1825-0097/")
    'https://orcid.org/0000-0002-1825-0097'
    >>> orcid_url("0000-0002-1825-0097", env="sandbox")
    'https://sandbox.orcid.org/0000-0002-1825-0097'
    """
    bare = normalize_orcid(orcid_id)
    host = _SANDBOX_HOST if env == "sandbox" else _PROD_HOST
    return f"https://{host}/{bare}"


@dataclass(frozen=True, slots=True)
class OrcidLink:
    """Hashable, comparable ORCID handle with canonical URL forms.

    Use :meth:`OrcidLink.parse` for input from authors / CLI / API; it
    accepts any URL or bare form and raises
    :class:`scitex_agentic_journal._gate1._errors.GateFailure` if the
    iD is malformed or fails checksum.

    Attributes
    ----------
    canonical : str
        Bare 16-digit form, e.g. ``"0000-0002-1825-0097"``.
    env : Env
        ``"prod"`` for ``orcid.org``, ``"sandbox"`` for ``sandbox.orcid.org``.
    """

    canonical: str
    env: Env = "prod"

    @classmethod
    def parse(cls, value: str, *, env: Env | None = None) -> OrcidLink:
        """Accept any input form; return a normalised :class:`OrcidLink`.

        Sandbox/prod inference order:

        1. Explicit ``env`` argument wins.
        2. Otherwise the input host (if any) is inspected — a
           ``sandbox.orcid.org`` URL produces ``env="sandbox"``.
        3. Otherwise default to ``env="prod"``.
        """
        bare = normalize_orcid(value)
        if env is not None:
            resolved_env: Env = env
        elif "sandbox.orcid.org" in (value or "").lower():
            resolved_env = "sandbox"
        else:
            resolved_env = "prod"
        return cls(canonical=bare, env=resolved_env)

    @property
    def url(self) -> str:
        """The canonical https URL for the iD on the resolved environment."""
        return orcid_url(self.canonical, env=self.env)

    @property
    def is_sandbox(self) -> bool:
        """True if this iD refers to the ORCID Sandbox environment."""
        return self.env == "sandbox"

    def __str__(self) -> str:  # pragma: no cover - trivial passthrough
        return self.canonical
