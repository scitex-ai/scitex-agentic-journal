"""Session-holding ORCID client.

A trivial wrapper around :func:`scitex_agentic_journal._gate1._orcid.verify_orcid`
that lets callers reuse a configured :class:`requests.Session` (timeout,
retries, auth) across many ORCID iD resolves.

Why a class
-----------
The gate-1 function is enough on its own, but downstream surfaces (Live
Paper authorship card, reviewer dashboard author list, Hub user-link
panel) typically resolve **N** iDs at once. Constructing a Session once
and reusing it is materially faster than letting :mod:`requests` allocate
a per-call connection pool.
"""

from __future__ import annotations

from typing import Final, Literal

import requests

from scitex_agentic_journal._gate1._orcid import (
    OrcidRecord,
    verify_orcid,
)
from scitex_agentic_journal._orcid._link import OrcidLink

Env = Literal["prod", "sandbox"]

_PROD_API: Final[str] = "https://pub.orcid.org/v3.0"
_SANDBOX_API: Final[str] = "https://pub.sandbox.orcid.org/v3.0"


def _base_url_for(env: Env) -> str:
    return _SANDBOX_API if env == "sandbox" else _PROD_API


class OrcidClient:
    """Reusable ORCID public-API client.

    Parameters
    ----------
    env :
        ``"prod"`` (default) → ``pub.orcid.org``; ``"sandbox"`` →
        ``pub.sandbox.orcid.org``.
    session :
        Optional pre-configured :class:`requests.Session`. The client
        does **not** mutate the session (no header overrides, no
        adapter swaps); per-request headers are set on the request
        itself by :func:`verify_orcid`. Pass a session if you have
        retry / proxy / auth wired up; otherwise a fresh one is created
        and reused for this client's lifetime.

    Examples
    --------
    >>> client = OrcidClient()                                   # doctest: +SKIP
    >>> rec = client.fetch("0000-0002-1825-0097")                # doctest: +SKIP
    >>> rec.display_name                                          # doctest: +SKIP
    'Josiah Carberry'
    """

    def __init__(
        self,
        *,
        env: Env = "prod",
        session: requests.Session | None = None,
    ) -> None:
        self.env: Env = env
        self._base_url: str = _base_url_for(env)
        self._session: requests.Session = session or requests.Session()

    @property
    def base_url(self) -> str:
        """The ORCID public-API base URL this client is bound to."""
        return self._base_url

    @property
    def session(self) -> requests.Session:
        """The underlying :class:`requests.Session`. Exposed for tests."""
        return self._session

    def fetch(self, orcid_id: str) -> OrcidRecord:
        """Resolve an ORCID iD and return its slim :class:`OrcidRecord`.

        Accepts any input shape :func:`verify_orcid` accepts (bare,
        ``https://orcid.org/...``, sandbox URL with explicit ``env``).
        Raises :class:`scitex_agentic_journal._gate1._errors.GateFailure`
        on malformed iDs, checksum failure, HTTP non-200, JSON shape
        we don't recognise, or network error. No silent fallback.
        """
        return verify_orcid(
            orcid_id,
            session=self._session,
            base_url=self._base_url,
        )

    def link(self, orcid_id: str) -> OrcidLink:
        """Return an :class:`OrcidLink` (URL helpers) without hitting the network.

        Convenience for callers that already have a client lying around
        and want the canonical URL form, e.g. when rendering an author
        list before the full record is needed.
        """
        return OrcidLink.parse(orcid_id, env=self.env)
