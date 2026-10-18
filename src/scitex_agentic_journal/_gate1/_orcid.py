"""ORCID resolvability — gate-1 structural check.

This module implements :func:`verify_orcid`, which takes an ORCID iD,
calls the public ORCID API, and returns a small structured record
when the iD resolves. The production path uses **real** HTTP via
:mod:`requests`: no mocks, no silent fallbacks. Tests inject a custom
HTTP transport via the ``session`` parameter so CI is hermetic without
needing to monkey-patch ``requests``.

References
----------
- ORCID Public API v3.0 record endpoint
  https://info.orcid.org/documentation/api-tutorials/api-tutorial-read-data-on-a-record/
- ORCID iD checksum (ISO 7064 MOD 11-2)
  https://info.orcid.org/ufaqs/what-is-an-orcid-id/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

import requests

from scitex_agentic_journal._gate1._errors import GateFailure

ORCID_PUB_API_BASE: Final[str] = "https://pub.orcid.org/v3.0"
"""Base URL of the public read-only ORCID API."""

ORCID_REQUEST_TIMEOUT_S: Final[float] = 10.0
"""Per-request timeout. Real network — fail loudly on slowness."""

ORCID_USER_AGENT: Final[str] = "scitex-agentic-journal/0.1 (+gate-1 orcid check)"
"""Identify ourselves so ORCID can attribute traffic if they ask."""

_ORCID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(\d{4})-(\d{4})-(\d{4})-(\d{3})(\d|X)$"
)
"""Bare iD form: ``0000-0002-1825-0097`` (16 digits + optional X check)."""


@dataclass(frozen=True)
class OrcidRecord:
    """Slimmed-down ORCID record sufficient for gate-1.

    We deliberately surface only the few fields that downstream gates
    (and the editorial decision engine) need. Authors' full ORCID
    record is large and noisy; we do not persist it here.
    """

    orcid_id: str
    given_name: str | None
    family_name: str | None
    credit_name: str | None

    @property
    def display_name(self) -> str:
        """Best human label for the author: credit name, else given + family."""
        if self.credit_name:
            return self.credit_name
        parts = [p for p in (self.given_name, self.family_name) if p]
        return " ".join(parts) if parts else self.orcid_id


def normalize_orcid(value: str) -> str:
    """Reduce a user-supplied ORCID string to the canonical bare form.

    Accepts ``0000-0002-1825-0097``, ``orcid.org/0000-...``,
    ``https://orcid.org/0000-...`` (with or without trailing slash),
    ``https://sandbox.orcid.org/0000-...``. Raises :class:`GateFailure`
    on anything else.
    """
    stripped = (value or "").strip()
    # Strip scheme.
    no_scheme = re.sub(r"^https?://", "", stripped, flags=re.IGNORECASE)
    # Strip host.
    no_host = re.sub(
        r"^(sandbox\.)?orcid\.org/", "", no_scheme, flags=re.IGNORECASE
    )
    bare = no_host.rstrip("/")
    if not _ORCID_PATTERN.match(bare):
        raise GateFailure(
            check="orcid",
            reason="orcid id is not in the canonical 16-digit form",
            detail=f"got {value!r}; expected e.g. 0000-0002-1825-0097",
        )
    if not _checksum_ok(bare):
        raise GateFailure(
            check="orcid",
            reason="orcid id checksum is invalid",
            detail=(
                f"{bare} fails ISO 7064 MOD 11-2 check; this is a typo, "
                "not an ORCID account that simply does not exist"
            ),
        )
    return bare


def _checksum_ok(bare: str) -> bool:
    """ISO 7064 MOD 11-2 check digit verification.

    ORCID-spec algorithm copied verbatim from the ORCID FAQ.
    """
    digits = bare.replace("-", "")
    body, check = digits[:-1], digits[-1]
    total = 0
    for ch in body:
        total = (total + int(ch)) * 2
    remainder = total % 11
    expected_n = (12 - remainder) % 11
    expected = "X" if expected_n == 10 else str(expected_n)
    return expected == check


def verify_orcid(
    orcid_id: str,
    *,
    session: requests.Session | None = None,
    base_url: str = ORCID_PUB_API_BASE,
) -> OrcidRecord:
    """Resolve an ORCID iD against the public ORCID API.

    Parameters
    ----------
    orcid_id :
        Bare iD (``0000-0002-1825-0097``) or any URL form ORCID emits.
    session :
        Optional pre-configured ``requests.Session``. The production
        CLI passes ``None``; the test suite passes a session whose
        transport is wired to fixture responses (no mocks, no
        monkey-patching of stdlib).
    base_url :
        Override the API host (used to point at sandbox.orcid.org for
        sandbox iDs or at a fixture host in tests).

    Returns
    -------
    OrcidRecord
        On HTTP 200. The record carries ``given_name``, ``family_name``
        and ``credit_name`` so the editorial pipeline can render the
        author without re-resolving.

    Raises
    ------
    GateFailure
        On any non-200 response, on malformed iDs, on network errors,
        and on JSON shapes we do not understand. Failure is loud.
    """
    bare = normalize_orcid(orcid_id)
    sess = session if session is not None else requests.Session()
    url = f"{base_url.rstrip('/')}/{bare}/record"
    headers = {
        "Accept": "application/json",
        "User-Agent": ORCID_USER_AGENT,
    }
    try:
        resp = sess.get(url, headers=headers, timeout=ORCID_REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:
        raise GateFailure(
            check="orcid",
            reason="orcid api unreachable",
            detail=f"{type(exc).__name__}: {exc} (url={url})",
        ) from exc

    if resp.status_code == 404:
        raise GateFailure(
            check="orcid",
            reason="orcid id does not resolve",
            detail=f"HTTP 404 from {url}; iD is well-formed but unknown to ORCID",
        )
    if resp.status_code != 200:
        raise GateFailure(
            check="orcid",
            reason="orcid api returned non-success status",
            detail=f"HTTP {resp.status_code} from {url}: {resp.text[:200]!r}",
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise GateFailure(
            check="orcid",
            reason="orcid api returned non-json",
            detail=f"{exc} (url={url}); first 200 chars: {resp.text[:200]!r}",
        ) from exc

    return _record_from_payload(bare, payload, url=url)


def _record_from_payload(
    bare: str, payload: dict, *, url: str
) -> OrcidRecord:
    """Pull the handful of name fields we care about out of /record JSON.

    The ORCID JSON is deeply nested. We stay defensive: missing
    sub-fields are OK (return ``None``), but a missing top-level
    ``person`` block means the API returned something we do not know,
    and we fail loud rather than guess.
    """
    person = payload.get("person")
    if not isinstance(person, dict):
        raise GateFailure(
            check="orcid",
            reason="orcid api returned an unfamiliar record shape",
            detail=f"no 'person' object in payload from {url}",
        )
    name = person.get("name") or {}
    given = _value_or_none(name.get("given-names"))
    family = _value_or_none(name.get("family-name"))
    credit = _value_or_none(name.get("credit-name"))
    return OrcidRecord(
        orcid_id=bare,
        given_name=given,
        family_name=family,
        credit_name=credit,
    )


def _value_or_none(node: object) -> str | None:
    """ORCID wraps strings as ``{'value': 'X'}``; return ``'X'`` or ``None``."""
    if isinstance(node, dict):
        v = node.get("value")
        if isinstance(v, str) and v:
            return v
    return None
