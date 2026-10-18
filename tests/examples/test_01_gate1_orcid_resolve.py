"""PS-303 example test — Gate-1 ORCID resolvability shell example.

Mirrors ``examples/01_gate1_orcid_resolve.sh``. Executes the script as
the user would, against a real ORCID record over the network. Skips
gracefully when bash is missing or the network is unreachable so an
offline / firewalled CI leg does not red the suite. No mocks.

The script run lives in a module-scope fixture so the four
single-assertion sibling tests share one network round-trip instead of
hammering pub.orcid.org four times.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "01_gate1_orcid_resolve.sh"
)
# Stephen Hawking — a stable, real ORCID record. The 0097 checksum is
# canonical and won't move.
SAMPLE_ORCID = "0000-0002-1825-0097"
_ORCID_HOST = "pub.orcid.org"


def _online(host: str = _ORCID_HOST, port: int = 443, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def orcid_script_result() -> subprocess.CompletedProcess[str]:
    """Run the example script once and share the result across siblings.

    Skips the whole module when bash is missing or pub.orcid.org is not
    reachable — both shapes the audit explicitly allows for an
    end-to-end script test.
    """
    if not EXAMPLE.exists():
        pytest.skip(f"example script missing: {EXAMPLE}")
    if not os.access(EXAMPLE, os.X_OK):
        pytest.skip(f"example script not executable: {EXAMPLE}")
    if shutil.which("bash") is None:
        pytest.skip("bash not on PATH")
    if not _online():
        pytest.skip(f"network egress to {_ORCID_HOST} unavailable")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.run(
        ["bash", str(EXAMPLE), SAMPLE_ORCID],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


@pytest.mark.integration
def test_example_orcid_resolve_script_exits_zero_for_resolvable_orcid(
    orcid_script_result: subprocess.CompletedProcess[str],
) -> None:
    """A real, resolvable ORCID id must drive the script to exit 0."""
    # Arrange
    result = orcid_script_result
    # Act
    rc = result.returncode
    # Assert
    assert rc == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


@pytest.mark.integration
def test_example_orcid_resolve_script_prints_gate1_pass_marker(
    orcid_script_result: subprocess.CompletedProcess[str],
) -> None:
    """Stdout must include the canonical ``GATE-1 PASS`` line that the
    M1 CLI orchestrator (#5) will key off.
    """
    # Arrange
    stdout = orcid_script_result.stdout
    # Act
    has_marker = "GATE-1 PASS" in stdout
    # Assert
    assert has_marker, f"expected 'GATE-1 PASS' in stdout; got:\n{stdout}"


@pytest.mark.integration
def test_example_orcid_resolve_script_echoes_supplied_orcid_id(
    orcid_script_result: subprocess.CompletedProcess[str],
) -> None:
    """Stdout must echo the ORCID id we passed — this protects against
    a future refactor accidentally resolving against a hard-coded id.
    """
    # Arrange
    stdout = orcid_script_result.stdout
    # Act
    echoes = SAMPLE_ORCID in stdout
    # Assert
    assert echoes, f"expected ORCID id in stdout; got:\n{stdout}"
