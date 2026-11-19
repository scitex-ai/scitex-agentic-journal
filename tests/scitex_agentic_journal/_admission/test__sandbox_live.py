"""Real sealed apptainer runs (opt-in).

Set ``SCITEX_RUN_SANDBOX_TESTS=1`` and ``SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE``
to an apptainer image with ``python3`` (e.g. SAC's ``sac-base.sif``). Each test
starts real containers; nothing runs on the host.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from scitex_agentic_journal._admission import (
    PACKAGE_INDEX_EGRESS,
    ApptainerSandbox,
    ClewRerunExecutor,
    SandboxError,
)
from scitex_agentic_journal._admission._executor import EVIDENCE_BUNDLE

IMAGE = os.environ.get("SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE", "")
pytestmark = pytest.mark.skipif(
    os.environ.get("SCITEX_RUN_SANDBOX_TESTS") != "1" or not IMAGE,
    reason="opt in with SCITEX_RUN_SANDBOX_TESTS=1 and SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE",
)
WRITER = "from pathlib import Path\nPath('out.txt').write_text('42\\n')\nprint('ok')\n"


def _project(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "make_output.py").write_text(WRITER)
    return root


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory):
    return ApptainerSandbox(Path(IMAGE), run_root=tmp_path_factory.mktemp("runs"))


@pytest.fixture(scope="module")
def writer_run(sandbox, tmp_path_factory):
    project = _project(tmp_path_factory.mktemp("writer") / "p")
    return sandbox.run_command(
        project, ["sh", "-c", "python3 make_output.py && cat out.txt"], timeout=300
    )


@pytest.fixture(scope="module")
def network_probe(sandbox, tmp_path_factory):
    project = _project(tmp_path_factory.mktemp("net") / "p")
    code = "import socket; socket.create_connection(('151.101.0.223', 443), timeout=5)"
    return sandbox.run_command(project, ["python3", "-c", code], timeout=120)


@pytest.fixture(scope="module")
def host_probe(sandbox, tmp_path_factory):
    project = _project(tmp_path_factory.mktemp("host") / "p")
    return sandbox.run_command(
        project,
        ["sh", "-c", f"test -e {Path.home()} && echo VISIBLE || echo HIDDEN"],
        timeout=120,
    )


def test_trivial_project_writes_its_output_in_the_sandbox(writer_run):
    # Arrange
    result = writer_run
    # Act
    produced = (result.exit_code, result.stdout.split())
    # Assert
    assert produced == (0, ["ok", "42"])


def test_outcome_record_is_finalized(writer_run):
    # Arrange
    outcome = writer_run.outcome_record
    # Act
    status = outcome["status"]
    # Assert
    assert status == "finalized"


def test_outcome_record_names_the_image_hash(writer_run):
    # Arrange
    outcome = writer_run.outcome_record
    # Act
    digest = outcome["sandbox"]["image_sha256"]
    # Assert
    assert len(digest) == 64


def test_command_phase_has_no_egress(writer_run):
    # Arrange
    phase = writer_run.outcome_record["phases"][0]
    # Act
    egress = phase["egress"]["mode"]
    # Assert
    assert egress == "none"


def test_offline_phase_cannot_open_a_tcp_connection(network_probe):
    # Arrange
    result = network_probe
    # Act
    code = result.exit_code
    # Assert
    assert code != 0


def test_host_home_is_not_visible(host_probe):
    # Arrange
    result = host_probe
    # Act
    seen = result.stdout.strip()
    # Assert
    assert seen == "HIDDEN"


def test_egress_is_refused_once_author_files_are_staged(sandbox, tmp_path):
    # Arrange
    run = sandbox.open_run(tmp_path / "runs")
    run.stage_project(_project(tmp_path / "p"))
    # Act
    call = lambda: run.run_command(
        ["true"], timeout=30, egress=PACKAGE_INDEX_EGRESS, phase="x"
    )
    # Assert
    with pytest.raises(SandboxError, match="egress is closed"):
        call()


def test_executor_installs_dependencies_and_reaches_the_rerun(sandbox, tmp_path):
    # Arrange: clew without `bundle rerun` (<= 0.34) yields no report; the
    # phases before it (fetch, offline install) must still all succeed.
    project = _project(tmp_path / "p")
    (project / "requirements.txt").write_text("six==1.16.0\n")
    (project / EVIDENCE_BUNDLE).parent.mkdir(parents=True)
    (project / EVIDENCE_BUNDLE).write_text("{}\n")
    clew = os.environ.get(
        "SCITEX_AGENTIC_JOURNAL_CLEW_REQUIREMENT", "scitex-clew==0.34.0"
    )
    executor = ClewRerunExecutor(
        sandbox, clew_requirement=clew, run_root=tmp_path / "r"
    )
    # Act
    records = executor.run(project, {"main_claims": ["c1"]})
    # Assert
    assert [p["phase"] for p in records[0]["details"]["sandbox"]["phases"]] == [
        "fetch-dependencies",
        "create-venv",
        "install",
        "rerun",
    ]
