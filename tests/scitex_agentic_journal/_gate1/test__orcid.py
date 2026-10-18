"""Tests for ``_gate1._orcid.verify_orcid``.

Discipline (STX-NM001-003 / PA-306, "no mocks"):

- The production path stays real HTTP via ``requests``. We never patch
  ``requests``, never use a respx/responses-style replay library, and
  never inject a fake session object.
- For hermetic CI we spin up a **real local HTTP server** (stdlib
  ``http.server`` on an ephemeral port) that serves real JSON files
  out of ``tests/scitex_agentic_journal/_gate1/_fixtures/``. The
  resolver hits it over real TCP via the legitimate ``base_url``
  config seam that the CLI will also use (e.g. to point at
  ``sandbox.orcid.org``).
- One test (``test_real_orcid_org_record_resolves_for_carberry``) talks
  to the real ``pub.orcid.org``; it is marked ``@pytest.mark.network``
  and skipped unless ``SCITEX_RUN_NETWORK_TESTS=1``.

Structure (STX-TQ rules):

- Every test carries the three ``# Arrange`` / ``# Act`` / ``# Assert``
  marker comments on separate lines in that order (TQ002).
- Each test asserts exactly one fact; multi-assertion tests are split
  by behaviour (TQ007). ``with pytest.raises(...)`` counts as one
  assertion and is never paired with a trailing ``assert``.
- Test names spell out the subject, condition, and expected behaviour
  (TQ003: ≥3 word-tokens after ``test_``).
"""

from __future__ import annotations

import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator

import pytest

from scitex_agentic_journal._gate1 import GateFailure, OrcidRecord, verify_orcid
from scitex_agentic_journal._gate1._orcid import normalize_orcid

FIXTURE_DIR = Path(__file__).parent / "_fixtures"


# ---------------------------------------------------------------------------
# Local fixture HTTP server — real TCP, real HTTP, real ``requests`` client.
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Serve ORCID-like ``/v3.0/{iD}/record`` responses from fixture JSON."""

    def do_GET(self) -> None:  # noqa: N802 (stdlib API)
        server: _FixtureServer = self.server  # type: ignore[assignment]
        spec = server.fixture_map.get(self.path)
        if spec is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "fixture not registered"}')
            return
        status, payload = spec
        if isinstance(payload, Path):
            body = payload.read_bytes()
            content_type = "application/json"
        elif isinstance(payload, (bytes, bytearray)):
            body = bytes(payload)
            content_type = "application/octet-stream"
        else:
            body = payload.encode("utf-8")
            content_type = "text/plain"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


class _FixtureServer(ThreadingHTTPServer):
    fixture_map: dict[str, tuple[int, object]]


@pytest.fixture
def orcid_fixture_server() -> (
    Iterator[Callable[[dict[str, tuple[int, object]]], str]]
):
    """Spin up a local HTTP server on an ephemeral port; yield base_url builder."""
    server = _FixtureServer(("127.0.0.1", 0), _FixtureHandler)
    server.fixture_map = {}
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def configure(fixture_map: dict[str, tuple[int, object]]) -> str:
        server.fixture_map = fixture_map
        return f"http://127.0.0.1:{port}/v3.0"

    try:
        yield configure
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# normalize_orcid — pure unit, no HTTP at all.
# ---------------------------------------------------------------------------


def test_normalize_orcid_accepts_bare_form_unchanged() -> None:
    # Arrange
    bare = "0000-0002-1825-0097"
    # Act
    out = normalize_orcid(bare)
    # Assert
    assert out == bare


def test_normalize_orcid_strips_orcid_org_url_prefix() -> None:
    # Arrange
    url = "https://orcid.org/0000-0002-1825-0097"
    # Act
    out = normalize_orcid(url)
    # Assert
    assert out == "0000-0002-1825-0097"


def test_normalize_orcid_strips_sandbox_orcid_org_url_prefix() -> None:
    # Arrange
    url = "https://sandbox.orcid.org/0000-0002-1825-0097"
    # Act
    out = normalize_orcid(url)
    # Assert
    assert out == "0000-0002-1825-0097"


def test_normalize_orcid_strips_trailing_slash_from_url() -> None:
    # Arrange
    url = "https://orcid.org/0000-0002-1825-0097/"
    # Act
    out = normalize_orcid(url)
    # Assert
    assert out == "0000-0002-1825-0097"


def test_normalize_orcid_accepts_x_check_digit_unchanged() -> None:
    # Arrange
    x_tail = "0000-0002-1694-233X"
    # Act
    out = normalize_orcid(x_tail)
    # Assert
    assert out == x_tail


def test_normalize_orcid_rejects_unparseable_garbage_string() -> None:
    # Arrange
    garbage = "not-an-orcid"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        normalize_orcid(garbage)


def test_normalize_orcid_rejects_bad_checksum_digit() -> None:
    # Arrange
    bad_checksum = "0000-0002-1825-0098"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        normalize_orcid(bad_checksum)


# ---------------------------------------------------------------------------
# verify_orcid — happy paths against the real local fixture server.
# ---------------------------------------------------------------------------


def test_verify_orcid_returns_orcid_record_instance(orcid_fixture_server) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0002-1825-0097/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0002-1825-0097_record.json",
            ),
        }
    )
    # Act
    rec = verify_orcid("0000-0002-1825-0097", base_url=base)
    # Assert
    assert isinstance(rec, OrcidRecord)


def test_verify_orcid_record_carries_given_name(orcid_fixture_server) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0002-1825-0097/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0002-1825-0097_record.json",
            ),
        }
    )
    # Act
    rec = verify_orcid("0000-0002-1825-0097", base_url=base)
    # Assert
    assert rec.given_name == "Josiah"


def test_verify_orcid_record_carries_family_name(orcid_fixture_server) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0002-1825-0097/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0002-1825-0097_record.json",
            ),
        }
    )
    # Act
    rec = verify_orcid("0000-0002-1825-0097", base_url=base)
    # Assert
    assert rec.family_name == "Carberry"


def test_verify_orcid_record_carries_credit_name(orcid_fixture_server) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0002-1825-0097/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0002-1825-0097_record.json",
            ),
        }
    )
    # Act
    rec = verify_orcid("0000-0002-1825-0097", base_url=base)
    # Assert
    assert rec.credit_name == "Josiah S. Carberry"


def test_verify_orcid_display_name_prefers_credit_name_when_set(
    orcid_fixture_server,
) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0002-1825-0097/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0002-1825-0097_record.json",
            ),
        }
    )
    # Act
    rec = verify_orcid("0000-0002-1825-0097", base_url=base)
    # Assert
    assert rec.display_name == "Josiah S. Carberry"


def test_verify_orcid_handles_missing_given_name_field(
    orcid_fixture_server,
) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0001-2345-6789/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0001-2345-6789_record_minimal.json",
            ),
        }
    )
    # Act
    rec = verify_orcid("0000-0001-2345-6789", base_url=base)
    # Assert
    assert rec.given_name is None


def test_verify_orcid_falls_back_to_family_name_for_display(
    orcid_fixture_server,
) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0001-2345-6789/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0001-2345-6789_record_minimal.json",
            ),
        }
    )
    # Act
    rec = verify_orcid("0000-0001-2345-6789", base_url=base)
    # Assert
    assert rec.display_name == "Solo"


# ---------------------------------------------------------------------------
# verify_orcid — failure paths against real (mis-)configured fixture server.
# ---------------------------------------------------------------------------


def test_verify_orcid_raises_when_record_endpoint_returns_404(
    orcid_fixture_server,
) -> None:
    # Arrange
    base = orcid_fixture_server({})
    # Act
    # Assert
    with pytest.raises(GateFailure):
        verify_orcid("0000-0002-1825-0097", base_url=base)


def test_verify_orcid_raises_when_record_endpoint_returns_500(
    orcid_fixture_server,
) -> None:
    # Arrange
    base = orcid_fixture_server(
        {"/v3.0/0000-0002-1825-0097/record": (500, "boom")}
    )
    # Act
    # Assert
    with pytest.raises(GateFailure):
        verify_orcid("0000-0002-1825-0097", base_url=base)


def test_verify_orcid_raises_when_record_body_is_not_json(
    orcid_fixture_server,
) -> None:
    # Arrange
    base = orcid_fixture_server(
        {"/v3.0/0000-0002-1825-0097/record": (200, b"<html>nope</html>")}
    )
    # Act
    # Assert
    with pytest.raises(GateFailure):
        verify_orcid("0000-0002-1825-0097", base_url=base)


def test_verify_orcid_raises_when_record_shape_lacks_person_object(
    orcid_fixture_server,
) -> None:
    # Arrange
    base = orcid_fixture_server(
        {
            "/v3.0/0000-0002-1825-0097/record": (
                200,
                FIXTURE_DIR / "orcid_0000-0002-1825-0097_record_garbled.json",
            ),
        }
    )
    # Act
    # Assert
    with pytest.raises(GateFailure):
        verify_orcid("0000-0002-1825-0097", base_url=base)


def test_verify_orcid_raises_when_orcid_api_host_is_unreachable() -> None:
    # Arrange
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        closed_port = s.getsockname()[1]
    closed_base = f"http://127.0.0.1:{closed_port}/v3.0"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        verify_orcid("0000-0002-1825-0097", base_url=closed_base)


# ---------------------------------------------------------------------------
# Optional real-network test against pub.orcid.org.
# ---------------------------------------------------------------------------


@pytest.mark.network
@pytest.mark.skipif(
    os.environ.get("SCITEX_RUN_NETWORK_TESTS") != "1",
    reason="opt in by setting SCITEX_RUN_NETWORK_TESTS=1",
)
def test_real_orcid_org_record_resolves_for_carberry() -> None:
    # Arrange
    iD = "0000-0002-1825-0097"
    # Act
    rec = verify_orcid(iD)
    # Assert
    assert rec.display_name
