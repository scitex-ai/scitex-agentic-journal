"""Zenodo + Zenodo-Sandbox id-minter — real HTTP, no mocks.

Both classes are thin wrappers over the shared :func:`_zenodo_mint`
helper, which speaks the Zenodo REST API directly:

* :class:`ZenodoSandboxStub` targets ``https://sandbox.zenodo.org/api/``
  and is the M4 acceptance "dev backend" — mintable in CI / staging
  without burning real DOIs.
* :class:`ZenodoStub` targets ``https://zenodo.org/api/`` and mints a
  real DOI under the SciTeX namespace. Same wire shape; different
  base URL + token.

Env-var contract
----------------
* ``SCITEX_AJ_ZENODO_SANDBOX_TOKEN`` — personal access token for
  :class:`ZenodoSandboxStub`. Required; absent → :class:`RuntimeError`.
* ``SCITEX_AJ_ZENODO_TOKEN`` — personal access token for production
  :class:`ZenodoStub`. Required; absent → :class:`RuntimeError`.

Failure mode
------------
Any non-2xx HTTP response from Zenodo raises :class:`RuntimeError`
with the status code + a truncated response body. There is no
silent fallback to :class:`InternalIdMinter`.
"""

from __future__ import annotations

import os
from typing import Final

import requests

from scitex_agentic_journal._publish._types import (
    Backend,
    IdMinter,
    MintInput,
    PersistentId,
)

_SANDBOX_BASE_URL: Final[str] = "https://sandbox.zenodo.org/api/"
_PROD_BASE_URL: Final[str] = "https://zenodo.org/api/"

_SANDBOX_ENV: Final[str] = "SCITEX_AJ_ZENODO_SANDBOX_TOKEN"
_PROD_ENV: Final[str] = "SCITEX_AJ_ZENODO_TOKEN"

_HTTP_TIMEOUT_S: Final[float] = 30.0
"""Per-request timeout; Zenodo's API is normally fast but we cap it
so a hung connection cannot stall the publish pipeline indefinitely."""

_BODY_TRUNCATE_AT: Final[int] = 500
"""How much of the error response body to surface in :class:`RuntimeError`."""


def _autogen_description(mint_input: MintInput) -> str:
    """Short Zenodo description derived from the submission inputs.

    Zenodo requires ``description`` on a publication-type deposition.
    We mint a one-line description so the deposition is valid; the
    canonical metadata will be replaced by the Live Paper hand-off
    (#9) once the manuscript is rendered.
    """
    return (
        f"SciTeX Agentic Journal submission {mint_input.submission_id}: "
        f"{mint_input.title} (corresponding author ORCID "
        f"{mint_input.corresponding_author_orcid})."
    )


def _build_metadata(mint_input: MintInput) -> dict:
    """Map a :class:`MintInput` onto the Zenodo metadata schema."""
    return {
        "metadata": {
            "upload_type": "publication",
            "publication_type": "article",
            "title": mint_input.title,
            "description": _autogen_description(mint_input),
            "creators": [
                {
                    "name": "SciTeX Agentic Journal author",
                    "orcid": mint_input.corresponding_author_orcid,
                }
            ],
            "publication_date": mint_input.decided_at.date().isoformat(),
        }
    }


def _raise_for_status(resp: "requests.Response", *, when: str) -> None:
    """Treat any non-2xx as a hard failure with truncated body in the message."""
    if 200 <= resp.status_code < 300:
        return
    body = (resp.text or "")[:_BODY_TRUNCATE_AT]
    raise RuntimeError(
        f"Zenodo {when} returned HTTP {resp.status_code}: {body!r}"
    )


def _zenodo_mint(
    *,
    base_url: str,
    token: str,
    backend: Backend,
    mint_input: MintInput,
) -> PersistentId:
    """Mint a DOI against a Zenodo-compatible REST endpoint.

    Three-step Zenodo deposition lifecycle:

    1. ``POST /deposit/depositions`` — create an empty deposition;
       Zenodo allocates a ``record_id`` and a DOI placeholder
       ``10.5281/zenodo.<record_id>``.
    2. ``PUT /deposit/depositions/<id>`` — attach metadata.
    3. ``POST /deposit/depositions/<id>/actions/publish`` — publish.

    We do not upload a file here; the manuscript artefact is attached
    later by the Live Paper hand-off (#9). The DOI is reserved at
    step 1 and finalised at step 3.
    """
    base = base_url.rstrip("/")
    auth_params = {"access_token": token}

    create = requests.post(
        f"{base}/deposit/depositions",
        params=auth_params,
        json={},
        timeout=_HTTP_TIMEOUT_S,
    )
    _raise_for_status(create, when="create deposition")
    created = create.json()
    deposition_id = created.get("id")
    if not isinstance(deposition_id, int):
        raise RuntimeError(
            f"Zenodo create deposition response missing integer 'id': "
            f"{str(created)[:_BODY_TRUNCATE_AT]!r}"
        )

    metadata = _build_metadata(mint_input)
    update = requests.put(
        f"{base}/deposit/depositions/{deposition_id}",
        params=auth_params,
        json=metadata,
        timeout=_HTTP_TIMEOUT_S,
    )
    _raise_for_status(update, when="update deposition metadata")

    publish = requests.post(
        f"{base}/deposit/depositions/{deposition_id}/actions/publish",
        params=auth_params,
        timeout=_HTTP_TIMEOUT_S,
    )
    _raise_for_status(publish, when="publish deposition")
    published = publish.json()

    doi = published.get("doi") or published.get("metadata", {}).get("doi")
    if not isinstance(doi, str) or not doi.strip():
        raise RuntimeError(
            f"Zenodo publish response missing 'doi' string: "
            f"{str(published)[:_BODY_TRUNCATE_AT]!r}"
        )

    return PersistentId(persistent_id=doi, backend=backend)


def _require_token(env_var: str) -> str:
    token = os.environ.get(env_var)
    if not token:
        raise RuntimeError(
            f"set {env_var} to enable sandbox minting"
            if env_var == _SANDBOX_ENV
            else f"set {env_var} to enable production Zenodo minting"
        )
    return token


class ZenodoStub:
    """Production Zenodo backend — real DOI minting under SciTeX namespace.

    Targets ``https://zenodo.org/api/``. Pulls the token from
    :data:`SCITEX_AJ_ZENODO_TOKEN`; absent → :class:`RuntimeError`.

    The sandbox path is the M4 acceptance line; this production path
    shares the same wire shape via :func:`_zenodo_mint` so that
    swapping ``SCITEX_AJ_ID_BACKEND=zenodo`` works in production once
    the SciTeX-owned token is provisioned.
    """

    backend: Backend = "zenodo"

    def mint(self, mint_input: MintInput) -> PersistentId:
        token = _require_token(_PROD_ENV)
        return _zenodo_mint(
            base_url=_PROD_BASE_URL,
            token=token,
            backend=self.backend,
            mint_input=mint_input,
        )


class ZenodoSandboxStub:
    """Zenodo-Sandbox backend — real HTTP against ``sandbox.zenodo.org``.

    The M4 acceptance "dev backend": exercises the full Zenodo wire
    shape without burning real DOIs. Returned DOIs are of the form
    ``10.5281/zenodo.<id>`` exactly like production.
    """

    backend: Backend = "zenodo-sandbox"

    def mint(self, mint_input: MintInput) -> PersistentId:
        token = _require_token(_SANDBOX_ENV)
        return _zenodo_mint(
            base_url=_SANDBOX_BASE_URL,
            token=token,
            backend=self.backend,
            mint_input=mint_input,
        )


# Confirm the classes satisfy the IdMinter Protocol shape at import time.
_check_zenodo: IdMinter = ZenodoStub()
_check_zenodo_sandbox: IdMinter = ZenodoSandboxStub()
del _check_zenodo, _check_zenodo_sandbox
