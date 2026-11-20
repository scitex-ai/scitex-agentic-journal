"""SAC backend validation and opt-in public-CLI/container qualification."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from scitex_agentic_journal._admission import (
    PACKAGE_INDEX_EGRESS,
    ClewRerunExecutor,
    ResourceLimits,
    SacSandbox,
    SandboxError,
)
from scitex_agentic_journal._admission._executor import EVIDENCE_BUNDLE
from tests.scitex_agentic_journal._contract_helpers import REPO_TESTS

LIVE = pytest.mark.skipif(
    os.environ.get("SCITEX_RUN_SAC_TESTS") != "1",
    reason="opt in with SCITEX_RUN_SAC_TESTS and a pinned SAC image/binary",
)


def test_missing_runtime_is_refused_before_author_code_can_run(tmp_path):
    # Arrange: this file is never executed; runtime validation must fail first.
    image = tmp_path / "image.sif"
    image.touch()
    # Act
    call = lambda: SacSandbox(image, sac_bin=tmp_path / "missing-sac")
    # Assert
    with pytest.raises(SandboxError):
        call()


@pytest.fixture
def live_sandbox(tmp_path):
    return SacSandbox(
        Path(os.environ["SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE"]),
        sac_bin=Path(os.environ["SCITEX_AGENTIC_JOURNAL_SAC_BIN"]),
        expected_sha256=os.environ["SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE_SHA256"],
        run_root=tmp_path / "runs",
    )


@LIVE
def test_genuine_claim_replays_through_sac_with_filtered_fetches(
    live_sandbox, tmp_path
):
    # Arrange
    fixture = REPO_TESTS / "scitex_agentic_journal/fixtures/clew-0.36.0"
    project = tmp_path / "project"
    shutil.copytree(fixture / "project", project)
    bundle_path = project / EVIDENCE_BUNDLE
    bundle_path.parent.mkdir(parents=True)
    bundle_path.write_bytes((fixture / "evidence-bundle.json").read_bytes())
    document = json.loads(bundle_path.read_text())
    executor = ClewRerunExecutor(live_sandbox, clew_requirement="scitex-clew==0.36.0")
    # Act
    records = executor.run(
        project, {"main_claims": ["total"]}, report={"claims": document["claims"]}
    )
    details = records[1].get("details", {})
    outcome = json.loads(Path(details["outcome_path"]).read_text())
    summary = {
        "checks": [(r["check"], r["status"]) for r in records],
        "runtime": outcome["sandbox"]["kind"],
        "filtered": all(p["egress"]["enforced"] for p in outcome["phases"]),
        "outcomes_kept": all(
            p.get("sac", {}).get("outcome_available") for p in outcome["phases"]
        ),
    }
    # Assert
    assert summary == {
        "checks": [("executability", "passed"), ("reproduction", "passed")],
        "runtime": "sac",
        "filtered": True,
        "outcomes_kept": True,
    }


@LIVE
def test_package_index_is_reachable_and_an_unlisted_host_is_recorded_denied(
    live_sandbox,
):
    # Arrange: this trusted network probe runs before any author files are staged.
    code = """import json, urllib.request, urllib.error
allowed = urllib.request.urlopen("https://pypi.org/simple/pip/", timeout=10).status == 200
denied = False
try: urllib.request.urlopen("https://example.org/", timeout=5)
except (urllib.error.URLError, TimeoutError, OSError): denied = True
print(json.dumps({"allowed": allowed, "denied": denied}))
"""
    run = live_sandbox.open_run()
    # Act
    try:
        result = run.run_command(
            ["python3", "-c", code],
            timeout=180,
            egress=PACKAGE_INDEX_EGRESS,
            phase="network-probe",
        )
        outcome = run.finalize()
        blocked = outcome["phases"][0]["sac"]["retained"]["egress_blocked.jsonl"]
        summary = (
            result.exit_code,
            json.loads(result.stdout),
            "example.org" in Path(blocked["path"]).read_text(),
        )
    finally:
        run.finalize()
    # Assert
    assert summary == (0, {"allowed": True, "denied": True}, True)


@LIVE
def test_cgroup_limits_apply_to_the_actual_sac_container(live_sandbox):
    # Arrange
    live_sandbox.limits = ResourceLimits(memory="512M", cpus="0.5", pids=512)
    code = """from pathlib import Path
import json
relative = Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
group = Path("/sys/fs/cgroup") / relative.lstrip("/")
quota, period = (group / "cpu.max").read_text().split()
print(json.dumps({"memory": int((group / "memory.max").read_text()),
                  "pids": int((group / "pids.max").read_text()),
                  "cpu": int(quota) / int(period)}))
"""
    run = live_sandbox.open_run()
    # Act
    try:
        result = run.run_command(
            ["python3", "-c", code], timeout=180, phase="limit-probe"
        )
        observed = (
            json.loads(result.stdout)
            if result.exit_code == 0
            else {"error": result.stderr}
        )
    finally:
        run.finalize()
    # Assert
    assert observed == {"memory": 512 << 20, "pids": 512, "cpu": 0.5}
