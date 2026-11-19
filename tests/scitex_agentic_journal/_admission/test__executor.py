"""ClewRerunExecutor: the paths that decide before any sandbox run (always on).

The sealed runs themselves are in ``test__sandbox_live.py`` (opt-in).
"""

from __future__ import annotations

import pytest
from scitex_agentic_journal._admission._executor import (
    EVIDENCE_BUNDLE,
    clew_tool,
    rerun_preflight,
)

TOOL = clew_tool("scitex-clew==0.0.0")


def _project(root, *, bundle=True, requirements=None):
    root.mkdir(parents=True, exist_ok=True)
    if bundle:
        (root / EVIDENCE_BUNDLE).parent.mkdir(parents=True)
        (root / EVIDENCE_BUNDLE).write_text("{}\n")
    if requirements is not None:
        (root / "requirements.txt").write_text(requirements)
    return root


@pytest.fixture(scope="module")
def without_bundle(tmp_path_factory):
    project = _project(tmp_path_factory.mktemp("nobundle") / "p", bundle=False)
    return rerun_preflight(project, ["auc"], tool=TOOL)


@pytest.fixture(scope="module")
def with_url_dependency(tmp_path_factory):
    project = _project(
        tmp_path_factory.mktemp("urldep") / "p",
        requirements="pkg @ https://evil.example/pkg.whl\n",
    )
    return rerun_preflight(project, ["auc"], tool=TOOL)


def test_missing_bundle_makes_both_checks_not_run(without_bundle):
    # Arrange
    records = without_bundle
    # Act
    statuses = [(r["check"], r["status"]) for r in records]
    # Assert
    assert statuses == [("executability", "not-run"), ("reproduction", "not-run")]


def test_missing_bundle_reason_names_the_bundle_path(without_bundle):
    # Arrange
    records = without_bundle
    # Act
    reason = records[0]["reason"]
    # Assert
    assert str(EVIDENCE_BUNDLE) in reason


def test_missing_bundle_reproduction_lists_the_main_claims(without_bundle):
    # Arrange
    records = without_bundle
    # Act
    targets = records[1]["details"]["targets"]
    # Assert
    assert targets == ["auc"]


def test_url_dependency_fails_executability(with_url_dependency):
    # Arrange
    records = with_url_dependency
    # Act
    status = records[0]["status"]
    # Assert
    assert status == "failed"


def test_url_dependency_leaves_reproduction_not_run(with_url_dependency):
    # Arrange
    records = with_url_dependency
    # Act
    status = records[1]["status"]
    # Assert
    assert status == "not-run"


def test_executor_checks_are_not_required_for_admission(with_url_dependency):
    # Arrange
    records = with_url_dependency
    # Act
    required = {r["required"] for r in records}
    # Assert
    assert required == {False}


def test_runnable_project_needs_the_sandbox(tmp_path):
    # Arrange
    project = _project(tmp_path / "p", requirements="six==1.16.0\n")
    # Act
    early = rerun_preflight(project, ["auc"], tool=TOOL)
    # Assert
    assert early is None
