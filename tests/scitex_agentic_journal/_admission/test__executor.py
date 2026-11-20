"""ClewRerunExecutor: the paths that decide before any sandbox run (always on).

The sealed runs themselves are in ``test__sandbox_live.py`` (opt-in).
"""

from __future__ import annotations

import json

from scitex_agentic_journal._admission._executor import (
    EVIDENCE_BUNDLE,
    clew_tool,
    load_bundle,
    rerun_preflight,
)

TOOL = clew_tool("scitex-clew==0.0.0")
BUNDLE = {
    "schema": "scitex-clew.evidence-bundle",
    "schema_version": "1.0.0",
    "exported_at": "2026-11-20T00:00:00Z",
    "clew_version": "0.36.0",
    "project": {"project_id": "fixture", "root_name": "fixture"},
    "runs": [],
    "edges": [],
    "claims": [],
}


def _project(root, *, bundle=True, requirements=None, bundle_text=None):
    root.mkdir(parents=True, exist_ok=True)
    if bundle:
        (root / EVIDENCE_BUNDLE).parent.mkdir(parents=True)
        (root / EVIDENCE_BUNDLE).write_text(bundle_text or json.dumps(BUNDLE))
    if requirements is not None:
        (root / "requirements.txt").write_text(requirements)
    return root


def _statuses(records):
    return [(r["check"], r["status"]) for r in records]


def test_missing_bundle_makes_both_checks_not_run(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", bundle=False)
    # Act
    records = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert _statuses(records) == [
        ("executability", "not-run"),
        ("reproduction", "not-run"),
    ]


def test_missing_bundle_reproduction_lists_the_main_claims(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", bundle=False)
    # Act
    records = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert records[1]["details"]["targets"] == ["auc"]


def test_symlinked_bundle_is_refused(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", bundle=False)
    (tmp_path / "elsewhere.json").write_text(json.dumps(BUNDLE))
    (project / EVIDENCE_BUNDLE).parent.mkdir(parents=True)
    (project / EVIDENCE_BUNDLE).symlink_to(tmp_path / "elsewhere.json")
    # Act
    records = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert _statuses(records)[0] == ("executability", "failed")


def test_bundle_below_a_symlinked_directory_is_refused(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", bundle=False)
    outside = _project(tmp_path / "outside")
    (project / ".scitex").symlink_to(outside / ".scitex")
    # Act
    records = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert _statuses(records)[0] == ("executability", "failed")


def test_bundle_that_is_not_an_evidence_bundle_is_refused(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", bundle_text='{"schema": "other"}')
    # Act
    _doc, _sha, problem = load_bundle(project)
    # Assert
    assert "is not a scitex-clew.evidence-bundle" in problem


def test_url_dependency_fails_executability(tmp_path):
    # Arrange
    project = _project(
        tmp_path / "p", requirements="pkg @ https://evil.example/p.whl\n"
    )
    # Act
    records = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert _statuses(records) == [
        ("executability", "failed"),
        ("reproduction", "not-run"),
    ]


def test_executor_checks_are_not_required_for_admission(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", requirements="-e .\n")
    # Act
    records = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert {r["required"] for r in records} == {False}


def test_runnable_project_needs_the_sandbox(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", requirements="six==1.16.0\n")
    # Act
    early = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert early is None
