"""Tests for :mod:`scitex_agentic_journal._publish._zenodo` — TQ, no mocks.

Two layers:

* **Hermetic** — calling :meth:`ZenodoSandboxStub.mint` without the
  ``SCITEX_AJ_ZENODO_SANDBOX_TOKEN`` env var must raise
  :class:`RuntimeError` with a clear "set ..." message. No HTTP.
* **Opt-in real network** — when both ``SCITEX_RUN_NETWORK_TESTS=1``
  and ``SCITEX_AJ_ZENODO_SANDBOX_TOKEN`` are present we hit the real
  ``sandbox.zenodo.org`` and assert the returned DOI is shaped like
  Zenodo's canonical ``10.5281/zenodo.<id>``. Mirrors the opt-in
  gating pattern from ``tests/.../_submit/test__orchestrate.py``.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from scitex_agentic_journal._publish import (
    MintInput,
    PersistentId,
    ZenodoSandboxStub,
)


def _mint_input() -> MintInput:
    return MintInput(
        submission_id="sub_2026_06_13_test",
        title="Real-HTTP sandbox-Zenodo M4 acceptance probe",
        corresponding_author_orcid="0000-0002-1825-0097",
        decided_at=datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Hermetic — no token → clear RuntimeError.
#
# The "no token" tests assume ``SCITEX_AJ_ZENODO_SANDBOX_TOKEN`` is absent
# from the test environment (it is in CI; developers running locally with
# it exported get an env-gated skip via the ``no_sandbox_token_env``
# fixture). The audit (PA-306 §3) forbids the ``monkeypatch`` fixture, so
# we use env-presence checks via a fixture rather than env mutation — the
# same pattern the M1 ``_submit`` tests use to gate network opt-in. The
# skip lives in the fixture (not in the test body) so PA-307 §3 STX-TQ007
# counts only the one assertion in each test.
# ---------------------------------------------------------------------------


@pytest.fixture
def no_sandbox_token_env() -> None:
    """Skip when ``SCITEX_AJ_ZENODO_SANDBOX_TOKEN`` is set.

    These tests probe the failure path that fires when the env var is
    absent; if the developer has it exported locally we have to skip
    rather than mutate their environment (PA-306 §3 forbids
    ``monkeypatch``).
    """
    if os.environ.get("SCITEX_AJ_ZENODO_SANDBOX_TOKEN"):
        pytest.skip(
            "SCITEX_AJ_ZENODO_SANDBOX_TOKEN is set; this test asserts the "
            "no-token failure path"
        )


def test_zenodo_sandbox_mint_without_token_raises_runtime_error(
    no_sandbox_token_env: None,
) -> None:
    # Arrange
    stub = ZenodoSandboxStub()
    # Act
    ctx = pytest.raises(RuntimeError)
    # Assert
    with ctx:
        stub.mint(_mint_input())


def test_zenodo_sandbox_mint_without_token_message_names_env_var(
    no_sandbox_token_env: None,
) -> None:
    """The error text must guide the operator to the missing env var.

    M4 acceptance: "If token missing, raise a clear RuntimeError
    ('set SCITEX_AJ_ZENODO_SANDBOX_TOKEN to enable sandbox minting')".
    """
    # Arrange
    stub = ZenodoSandboxStub()
    captured: RuntimeError | None = None
    # Act
    try:
        stub.mint(_mint_input())
    except RuntimeError as e:
        captured = e
    # Assert
    assert (
        captured is not None
        and "SCITEX_AJ_ZENODO_SANDBOX_TOKEN" in str(captured)
    )


# ---------------------------------------------------------------------------
# Opt-in real-network — only runs when both env vars are present.
# ---------------------------------------------------------------------------


@pytest.fixture
def sandbox_token() -> str:
    """Skip the real-HTTP test unless explicitly opted in."""
    if os.environ.get("SCITEX_RUN_NETWORK_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_NETWORK_TESTS=1")
    token = os.environ.get("SCITEX_AJ_ZENODO_SANDBOX_TOKEN")
    if not token:
        pytest.skip("SCITEX_AJ_ZENODO_SANDBOX_TOKEN not set")
    return token


@pytest.mark.network
def test_zenodo_sandbox_mint_returns_zenodo_doi_against_real_sandbox(
    sandbox_token: str,
) -> None:
    """Real HTTP against ``sandbox.zenodo.org`` — the M4 dev-backend probe."""
    # Arrange
    stub = ZenodoSandboxStub()
    # Act
    pid = stub.mint(_mint_input())
    # Assert
    assert isinstance(pid, PersistentId)


@pytest.mark.network
def test_zenodo_sandbox_mint_doi_uses_zenodo_prefix(
    sandbox_token: str,
) -> None:
    # Arrange
    stub = ZenodoSandboxStub()
    # Act
    pid = stub.mint(_mint_input())
    # Assert
    assert pid.persistent_id.startswith("10.5281/zenodo.")


@pytest.mark.network
def test_zenodo_sandbox_mint_persistent_id_backend_is_zenodo_sandbox(
    sandbox_token: str,
) -> None:
    # Arrange
    stub = ZenodoSandboxStub()
    # Act
    pid = stub.mint(_mint_input())
    # Assert
    assert pid.backend == "zenodo-sandbox"
