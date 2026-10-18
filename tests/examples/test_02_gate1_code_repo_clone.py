"""PS-303 example test — Gate-1 code-repo cloneability shell example.

Mirrors ``examples/02_gate1_code_repo_clone.sh``. Executes the script
as the user would, performing a real shallow ``git clone`` of a small
public repo. Skips gracefully when ``git`` is missing or the network
is unreachable. No mocks.

The script run lives in a module-scope fixture so the four
single-assertion sibling tests share one ``git clone`` instead of
hammering GitHub four times.
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
    / "02_gate1_code_repo_clone.sh"
)
# GitHub's canonical tutorial repo. Tiny (a single README), public, and
# stable since 2011 — chosen so the clone runs in <2 s even on slow
# links and we don't pay the bandwidth of a real research repo.
SAMPLE_REPO = "https://github.com/octocat/Hello-World.git"
_GITHUB_HOST = "github.com"


def _online(host: str = _GITHUB_HOST, port: int = 443, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def clone_script_result() -> subprocess.CompletedProcess[str]:
    """Run the example script once and share the result across siblings.

    Skips the whole module when bash / git is missing or github.com is
    not reachable — both shapes the audit explicitly allows for an
    end-to-end script test.
    """
    if not EXAMPLE.exists():
        pytest.skip(f"example script missing: {EXAMPLE}")
    if not os.access(EXAMPLE, os.X_OK):
        pytest.skip(f"example script not executable: {EXAMPLE}")
    if shutil.which("bash") is None:
        pytest.skip("bash not on PATH")
    if shutil.which("git") is None:
        pytest.skip("git not on PATH")
    if not _online():
        pytest.skip(f"network egress to {_GITHUB_HOST} unavailable")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.run(
        ["bash", str(EXAMPLE), SAMPLE_REPO],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


@pytest.mark.integration
def test_example_clone_script_exits_zero_for_public_repo(
    clone_script_result: subprocess.CompletedProcess[str],
) -> None:
    """A real, public git repo must drive the script to exit 0."""
    # Arrange
    result = clone_script_result
    # Act
    rc = result.returncode
    # Assert
    assert rc == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


@pytest.mark.integration
def test_example_clone_script_prints_gate1_pass_marker(
    clone_script_result: subprocess.CompletedProcess[str],
) -> None:
    """Stdout must include the canonical ``GATE-1 PASS`` line that the
    M1 CLI orchestrator (#5) will key off.
    """
    # Arrange
    stdout = clone_script_result.stdout
    # Act
    has_marker = "GATE-1 PASS" in stdout
    # Assert
    assert has_marker, f"expected 'GATE-1 PASS' in stdout; got:\n{stdout}"


@pytest.mark.integration
def test_example_clone_script_reports_head_commit(
    clone_script_result: subprocess.CompletedProcess[str],
) -> None:
    """Stdout must report a HEAD commit — verifies the clone actually
    materialised a working tree, not just touched an empty dir.
    """
    # Arrange
    stdout = clone_script_result.stdout
    # Act
    has_head = "HEAD commit" in stdout
    # Assert
    assert has_head, f"expected 'HEAD commit' in stdout; got:\n{stdout}"


@pytest.mark.integration
def test_example_clone_script_echoes_supplied_repo_url(
    clone_script_result: subprocess.CompletedProcess[str],
) -> None:
    """Stdout must echo the repo URL we passed — guards against a
    refactor silently substituting a hard-coded URL.
    """
    # Arrange
    stdout = clone_script_result.stdout
    # Act
    echoes = SAMPLE_REPO in stdout
    # Assert
    assert echoes, f"expected repo URL in stdout; got:\n{stdout}"
