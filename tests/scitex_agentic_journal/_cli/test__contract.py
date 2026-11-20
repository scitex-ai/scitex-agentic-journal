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
    result = run("preprint", "create", sid, "v1.0.0", "--yes")
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


def _evaluate(tmp_path, *args):
    env = {
        "SCITEX_AGENTIC_JOURNAL_HOME": str(tmp_path / "home"),
        "SCITEX_AGENTIC_JOURNAL_SANDBOX_IMAGE": None,
        "SCITEX_AGENTIC_JOURNAL_CLEW_REQUIREMENT": None,
    }
    return CliRunner().invoke(
        main, ["admission", "evaluate", "aj-0123456789abcdef", *args], env=env
    )


def test_admission_evaluate_offers_none_and_apptainer_executors(tmp_path):
    # Arrange
    args = ("--help",)
    # Act
    result = _evaluate(tmp_path, *args)
    # Assert
    assert "[none|sac|apptainer]" in result.output


def test_admission_evaluate_offers_an_image_pin(tmp_path):
    # Arrange
    args = ("--help",)
    # Act
    result = _evaluate(tmp_path, *args)
    # Assert
    assert "--sandbox-image-sha256" in result.output


def test_admission_evaluate_offers_the_image_interpreter(tmp_path):
    # Arrange
    args = ("--help",)
    # Act
    result = _evaluate(tmp_path, *args)
    # Assert
    assert "--sandbox-python" in result.output


def test_admission_evaluate_rejects_an_unknown_executor(tmp_path):
    # Arrange
    args = ("--executor", "host")
    # Act
    result = _evaluate(tmp_path, *args)
    # Assert
    assert result.exit_code == 2


def test_apptainer_executor_without_an_image_is_a_usage_error(tmp_path):
    # Arrange
    args = ("--executor", "apptainer", "--clew-requirement", "scitex-clew==0.0.0")
    # Act
    result = _evaluate(tmp_path, *args)
    # Assert
    assert "needs --sandbox-image" in result.output


def test_apptainer_executor_without_a_clew_pin_is_a_usage_error(tmp_path):
    # Arrange
    args = ("--executor", "apptainer", "--sandbox-image", str(tmp_path / "x.sif"))
    # Act
    result = _evaluate(tmp_path, *args)
    # Assert
    assert "needs --clew-requirement" in result.output


def test_apptainer_executor_with_a_missing_image_fails_cleanly(tmp_path):
    # Arrange
    args = (
        "--executor",
        "apptainer",
        "--sandbox-image",
        str(tmp_path / "x.sif"),
        "--clew-requirement",
        "scitex-clew==0.0.0",
    )
    # Act
    result = _evaluate(tmp_path, *args)
    # Assert
    assert result.exit_code == 1
