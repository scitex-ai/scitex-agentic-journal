"""The bundle / admission / preprint / reviews CLI groups, through the real entry point."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from scitex_agentic_journal._cli import main

from tests.scitex_agentic_journal._contract_helpers import (
    REFERENCE_BUNDLE,
    copy_reference_bundle,
)


@pytest.fixture
def run(tmp_path):
    env = {"SCITEX_AGENTIC_JOURNAL_HOME": str(tmp_path / "home")}

    def _run(*args):
        return CliRunner().invoke(main, list(args), env=env)

    return _run


def test_bundle_validate_accepts_the_reference_bundle(run):
    # Arrange
    path = str(REFERENCE_BUNDLE)
    # Act
    result = run("bundle", "validate", path)
    # Assert
    assert result.exit_code == 0, result.output


def test_bundle_validate_exits_1_and_names_the_finding(run, tmp_path):
    # Arrange
    bundle = copy_reference_bundle(tmp_path / "bundle")
    (bundle / "stray.txt").write_text("x\n")
    # Act
    result = run("bundle", "validate", str(bundle))
    # Assert
    assert (result.exit_code, "[unlisted-file]" in result.output) == (1, True)


def test_bundle_submit_json_reports_the_submission_id(run):
    # Arrange
    path = str(REFERENCE_BUNDLE)
    # Act
    result = run("bundle", "submit", path, "--json")
    # Assert
    assert json.loads(result.output)["submission_id"].startswith("aj-")


def test_admission_show_without_a_run_is_a_clean_error(run):
    # Arrange
    sid = json.loads(run("bundle", "submit", str(REFERENCE_BUNDLE), "--json").output)[
        "submission_id"
    ]
    # Act
    result = run("admission", "show", sid)
    # Assert
    assert (result.exit_code, "record not found" in result.output) == (1, True)


def test_preprint_create_refuses_an_unadmitted_submission(run):
    # Arrange
    sid = json.loads(run("bundle", "submit", str(REFERENCE_BUNDLE), "--json").output)[
        "submission_id"
    ]
    # Act
    result = run("preprint", "create", sid, "v1.0.0")
    # Assert
    assert "no admission record" in result.output


def test_reviews_list_is_empty_before_any_review(run):
    # Arrange
    sid = json.loads(run("bundle", "submit", str(REFERENCE_BUNDLE), "--json").output)[
        "submission_id"
    ]
    # Act
    result = run("reviews", "list", sid, "--json")
    # Assert
    assert json.loads(result.output) == []
