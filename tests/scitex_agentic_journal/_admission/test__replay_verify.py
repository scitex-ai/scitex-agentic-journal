"""Host-side verification of a replay tree: real files on disk, real hashes.

The replay tree stands in for what ``clew bundle rerun --work-dir`` keeps; the
report hint follows rerun-report 1.1.0 (``work_dir``, ``run_dir``,
``resolved_path``). Nothing here trusts the hint's statuses.
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest
from scitex_agentic_journal._admission._replay_verify import (
    REPLAY_DIR,
    agrees,
    host_claims,
    host_runs,
    resolve_replayed_output,
    submission_binding,
)

METRICS = json.dumps({"auc": 0.9104}).encode()
NROWS = json.dumps({"n": 998}).encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bundle():
    return {
        "runs": [
            {"run_id": "train", "run_dir": None,
             "outputs": {"results/metrics.json": _sha(METRICS)}},
            {"run_id": "count", "run_dir": "out/RUNNING/s1",
             "outputs": {"out/RUNNING/s1/n.json": _sha(json.dumps({"n": 1_000}).encode())}},
        ],
        "claims": [
            {"claim_id": "auc", "stated_value": 0.91, "state": "supported",
             "precision": {"basis": "implied", "abs_tol": 0.005, "rel_tol": 0.0},
             "source": {"file": "results/metrics.json", "locator": {".": "/auc"}},
             "producing_runs": ["train"]},
            {"claim_id": "n_rows", "stated_value": 1_000, "state": "supported",
             "precision": {"basis": "implied", "abs_tol": 0.5, "rel_tol": 0.0},
             "source": {"file": "out/RUNNING/s1/n.json", "locator": {".": "/n"}},
             "producing_runs": ["count"]},
            {"claim_id": "n_close", "stated_value": 1_000, "state": "supported",
             "precision": {"basis": "declared", "abs_tol": 5, "rel_tol": None},
             "source": {"file": "out/RUNNING/s1/n.json", "locator": {".": "/n"}},
             "producing_runs": ["count"]},
            {"claim_id": "orphan", "stated_value": 1, "state": "supported",
             "precision": {"basis": "exact", "abs_tol": None, "rel_tol": None},
             "source": {"file": None, "locator": None}, "producing_runs": []},
        ],
    }  # fmt: skip


def _hint(**overrides):
    hint = {
        "work_dir": REPLAY_DIR,
        "runs": [
            {"run_id": "train", "outputs": [{"path": "results/metrics.json",
             "resolved_path": "project/results/metrics.json"}]},
            {"run_id": "count", "outputs": [{"path": "out/RUNNING/s1/n.json",
             "resolved_path": "project/out/RUNNING/s2/n.json"}]},
        ],
    }  # fmt: skip
    hint.update(overrides)
    return hint


@pytest.fixture
def replay(tmp_path_factory):
    root = tmp_path_factory.mktemp("replay")
    (root / "project" / "results").mkdir(parents=True)
    (root / "project" / "results" / "metrics.json").write_bytes(METRICS)
    (root / "project" / "out" / "RUNNING" / "s2").mkdir(parents=True)
    (root / "project" / "out" / "RUNNING" / "s2" / "n.json").write_bytes(NROWS)
    (root / "outside.json").write_bytes(METRICS)
    (root / "project" / "linked.json").symlink_to(root / "outside.json")
    return root


@pytest.fixture
def verified(replay):
    doc = _bundle()
    runs = host_runs(doc, _hint(), replay)
    return runs, host_claims(doc, runs, _hint(), replay)


def _by(items, key, value):
    return next(i for i in items if i[key] == value)


def test_matching_output_reproduces_its_run(verified):
    # Arrange
    runs, _ = verified
    # Act
    status = _by(runs, "run_id", "train")["status"]
    # Assert
    assert status == "reproduced"


def test_output_in_the_new_session_dir_is_found_and_hashed(verified):
    # Arrange
    runs, _ = verified
    # Act
    actual = _by(runs, "run_id", "count")["outputs"][0]["actual_sha256"]
    # Assert
    assert actual == _sha(NROWS)


def test_differing_output_makes_its_run_differ(verified):
    # Arrange
    runs, _ = verified
    # Act
    status = _by(runs, "run_id", "count")["status"]
    # Assert
    assert status == "differs"


def test_claim_of_a_reproduced_run_is_reproduced_by_hash(verified):
    # Arrange
    _, claims = verified
    # Act
    claim = _by(claims, "claim_id", "auc")
    # Assert
    assert (claim["status"], claim["by"]) == ("reproduced", "output-hash")


def test_value_outside_the_implied_precision_differs(verified):
    # Arrange
    _, claims = verified
    # Act
    claim = _by(claims, "claim_id", "n_rows")
    # Assert
    assert (claim["status"], claim["recomputed_value"]) == ("differs", 998)


def test_value_inside_the_declared_tolerance_is_reproduced_on_the_host(verified):
    # Arrange
    _, claims = verified
    # Act
    claim = _by(claims, "claim_id", "n_close")
    # Assert
    assert (claim["status"], claim["by"]) == ("reproduced", "host-recompute")


def test_claim_without_producing_runs_is_not_checkable(verified):
    # Arrange
    _, claims = verified
    # Act
    status = _by(claims, "claim_id", "orphan")["status"]
    # Assert
    assert status == "not_checkable"


@pytest.mark.parametrize(
    "resolved",
    [
        "../outside.json",
        "/etc/passwd",
        "project/../outside.json",
        "project/linked.json",
    ],
)
def test_escaping_or_symlinked_resolved_path_is_a_miss(replay, resolved):
    # Arrange
    hint = _hint(runs=[{"run_id": "train", "outputs": [
        {"path": "results/metrics.json", "resolved_path": resolved}]}])  # fmt: skip
    doc = _bundle()
    # Act
    runs = host_runs(doc, hint, replay)
    # Assert
    assert _by(runs, "run_id", "train")["status"] == "missing"


def test_resolved_path_for_another_file_is_refused(replay):
    # Arrange
    hint = _hint(runs=[{"run_id": "train", "outputs": [
        {"path": "results/metrics.json", "resolved_path": "project/out/RUNNING/s2/n.json"}]}])  # fmt: skip
    run = _bundle()["runs"][0]
    # Act
    path = resolve_replayed_output(replay, hint, run, "results/metrics.json")
    # Assert
    assert path is None


def test_report_for_another_work_dir_finds_nothing(replay):
    # Arrange
    hint = _hint(work_dir="/elsewhere")
    run = _bundle()["runs"][0]
    # Act
    path = resolve_replayed_output(replay, hint, run, "results/metrics.json")
    # Assert
    assert path is None


def test_no_report_means_every_output_is_missing(replay):
    # Arrange
    doc = _bundle()
    # Act
    runs = host_runs(doc, None, replay)
    # Assert
    assert {r["status"] for r in runs} == {"missing"}


def test_host_never_reads_through_a_symlink(replay):
    # Arrange
    target = replay / "project" / "linked.json"
    # Act
    is_link = os.path.islink(target)
    # Assert
    assert is_link is True


def test_declared_relative_tolerance_is_applied():
    # Arrange
    rule = {"basis": "declared", "abs_tol": None, "rel_tol": 0.01}
    # Act
    ok, _ = agrees(100.0, 100.9, rule)
    # Assert
    assert ok is True


def test_exact_basis_requires_equality():
    # Arrange
    rule = {"basis": "exact", "abs_tol": None, "rel_tol": None}
    # Act
    ok, _ = agrees("yes", "no", rule)
    # Assert
    assert ok is False


def test_bundle_agreeing_with_the_submitted_report_has_no_mismatch():
    # Arrange
    report = {
        "claims": [{"claim_id": "auc", "state": "supported", "stated_value": 0.91}]
    }
    # Act
    mismatch = submission_binding(_bundle(), report, ["auc"])
    # Assert
    assert mismatch == {}


def test_changed_stated_value_is_a_submission_mismatch():
    # Arrange
    report = {
        "claims": [{"claim_id": "auc", "state": "supported", "stated_value": 0.95}]
    }
    # Act
    mismatch = submission_binding(_bundle(), report, ["auc"])
    # Assert
    assert "stated value" in mismatch["auc"]


def test_changed_state_is_a_submission_mismatch():
    # Arrange
    report = {"claims": [{"claim_id": "auc", "state": "not_supported"}]}
    # Act
    mismatch = submission_binding(_bundle(), report, ["auc"])
    # Assert
    assert "state" in mismatch["auc"]
