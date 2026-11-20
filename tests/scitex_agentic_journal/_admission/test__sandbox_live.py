"""Real sealed apptainer runs (opt-in).

Set ``SCITEX_RUN_SANDBOX_TESTS=1`` and ``SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE``
to an apptainer image with ``python3`` (e.g. SAC's ``sac-base.sif``). Each test
starts real containers; nothing runs on the host.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scitex_agentic_journal._admission import (
    PACKAGE_INDEX_EGRESS,
    ApptainerSandbox,
    ClewRerunExecutor,
    ResourceLimits,
    SandboxError,
)
from scitex_agentic_journal._admission._executor import EVIDENCE_BUNDLE
from scitex_agentic_journal._admission._sandbox_proc import cgroup_delegation

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
    return ApptainerSandbox(
        Path(IMAGE),
        run_root=tmp_path_factory.mktemp("runs"),
        expected_sha256=os.environ.get("SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE_SHA256"),
    )


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


BUNDLE = {
    "schema": "scitex-clew.evidence-bundle",
    "schema_version": "1.0.0",
    "exported_at": "2026-11-20T00:00:00Z",
    "clew_version": "0.36.0",
    "project": {"project_id": "fixture", "root_name": "fixture"},
    "runs": [
        {"run_id": "r1", "argv": ["make_output.py"], "cwd": ".", "status": "success",
         "script": "make_output.py", "interpreter": {"name": "python", "version": None},
         "external_inputs": [], "started_at": None, "finished_at": None,
         "outputs": {"out.txt": "0" * 64}, "inputs": {}, "run_dir": None}
    ],
    "edges": [],
    "claims": [],
}  # fmt: skip


def test_executor_runs_every_phase_and_verifies_on_the_host(sandbox, tmp_path):
    # Arrange: a deliberately mismatched output still exercises every phase.
    project = _project(tmp_path / "p")
    (project / "requirements.txt").write_text("six==1.16.0\n")
    (project / EVIDENCE_BUNDLE).parent.mkdir(parents=True)
    (project / EVIDENCE_BUNDLE).write_text(json.dumps(BUNDLE))
    clew = os.environ.get(
        "SCITEX_AGENTIC_JOURNAL_CLEW_REQUIREMENT", "scitex-clew==0.36.0"
    )
    executor = ClewRerunExecutor(
        sandbox, clew_requirement=clew, run_root=tmp_path / "r"
    )
    # Act
    records = executor.run(project, {"main_claims": ["c1"]})
    # Assert
    assert [p["phase"] for p in records[0]["details"]["sandbox"]["phases"]] == [
        "create-fetch-venv",
        "fetch-dependencies",
        "fetch-clew",
        "create-venv",
        "install-venv",
        "create-clew-venv",
        "install-clew-venv",
        "rerun",
    ]


@pytest.fixture
def released_replay(sandbox, tmp_path):
    """A real sealed replay in this test's own writable directory."""
    import shutil

    fixture = Path(__file__).resolve().parents[1] / "fixtures/clew-0.36.0"
    project = tmp_path / "genuine"
    shutil.copytree(fixture / "project", project)
    target = project / EVIDENCE_BUNDLE
    target.parent.mkdir(parents=True)
    target.write_bytes((fixture / "evidence-bundle.json").read_bytes())
    bundle = json.loads(target.read_text())
    executor = ClewRerunExecutor(
        sandbox,
        clew_requirement="scitex-clew==0.36.0",
        sandbox_python=os.environ.get(
            "SCITEX_AGENTIC_JOURNAL_SANDBOX_PYTHON", "python3"
        ),
        run_root=tmp_path / "runs",
    )
    return executor.run(
        project, {"main_claims": ["total"]}, report={"claims": bundle["claims"]}
    )


def test_released_clew_fixture_reproduces_by_independent_host_hash(released_replay):
    # Arrange
    records = released_replay
    # Act
    details = records[1].get("details", {})
    claims = details.get("claims", [])
    summary = {
        "checks": [(r["check"], r["status"]) for r in records],
        "claim_by": claims[0].get("by") if claims else None,
        "sandbox_trusted": details.get("sandbox_reported", {}).get("trusted"),
    }
    # Assert
    assert summary == {
        "checks": [("executability", "passed"), ("reproduction", "passed")],
        "claim_by": "output-hash",
        "sandbox_trusted": False,
    }


def test_staging_drops_git_history_and_recorded_outputs(sandbox, tmp_path):
    # Arrange
    project = _project(tmp_path / "p")
    (project / ".git").mkdir()
    (project / "out.txt").write_text("stale\n")
    run = sandbox.open_run(tmp_path / "runs")
    run.stage_project(project, remove=["out.txt"])
    # Act
    res = run.run_command(["ls", "-a", "/work/project"], timeout=120, phase="ls")
    run.finalize()
    # Assert
    assert {".git", "out.txt"} & set(res.stdout.split()) == set()


def test_output_flood_is_capped(tmp_path):
    # Arrange
    capped = ApptainerSandbox(
        Path(IMAGE),
        run_root=tmp_path / "runs",
        limits=ResourceLimits(output_cap_bytes=1_000),
    )
    # Act
    res = capped.run_command(
        None, ["python3", "-c", "print('x' * 5_000_000)"], timeout=120
    )
    # Assert
    assert (len(res.stdout), res.outcome_record["phases"][0]["output_truncated"]) == (
        1_000,
        True,
    )


def test_mismatching_pinned_image_is_refused(tmp_path):
    # Arrange
    pin = "0" * 64
    # Act
    call = lambda: ApptainerSandbox(Path(IMAGE), expected_sha256=pin)
    # Assert
    with pytest.raises(SandboxError, match="not the pinned"):
        call()


FORK = (
    "import subprocess\n"
    "ps = []\n"
    "try:\n"
    "    for _ in range(60):\n"
    "        ps.append(subprocess.Popen(['sleep', '3']))\n"
    "    print('spawned')\n"
    "except OSError:\n"
    "    print('blocked')\n"
)


@pytest.mark.skipif(
    not cgroup_delegation()[0], reason="cgroup limits are not enforced on this host"
)
def test_pids_limit_bites_where_cgroups_are_delegated(tmp_path):
    # Arrange
    limited = ApptainerSandbox(
        Path(IMAGE), run_root=tmp_path / "runs", limits=ResourceLimits(pids=20)
    )
    # Act
    res = limited.run_command(None, ["python3", "-c", FORK], timeout=120)
    # Assert
    assert res.stdout.strip() == "blocked"
