"""Tests for the `scitex-agentic-journal skills {list,get,install}` CLI group.

Audit §1a requires the package to ship a `skills` Click sub-group;
this file exercises every public path against the real bundled
`_skills/scitex-agentic-journal/` tree via Click's `CliRunner`.

No-mocks rule: `CliRunner` is the canonical Click way of driving a
command from inside the test process — it isolates streams and exit
codes without monkey-patching anything. The `install` test writes
to a real `tmp_path` directory, never a fake filesystem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli_main


# ---------------------------------------------------------------------------
# `skills list`
# ---------------------------------------------------------------------------


def test_skills_list_exits_zero_when_bundle_present() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "list"])
    # Assert
    assert result.exit_code == 0, result.output


def test_skills_list_includes_skill_md_index_leaf() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "list"])
    # Assert
    assert "SKILL.md" in result.output


def test_skills_list_includes_canonical_installation_leaf() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "list"])
    # Assert
    assert "01_installation.md" in result.output


def test_skills_list_json_returns_object_with_skills_key() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "list", "--json"])
    # Assert
    assert "skills" in json.loads(result.output)


def test_skills_list_json_payload_is_sorted_lexicographically() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "list", "--json"])
    # Assert
    skills = json.loads(result.output)["skills"]
    assert skills == sorted(skills)


# ---------------------------------------------------------------------------
# `skills get`
# ---------------------------------------------------------------------------


def test_skills_get_emits_skill_md_content_for_bare_skill_alias() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "get", "SKILL"])
    # Assert
    assert "scitex-agentic-journal Skill" in result.output


def test_skills_get_accepts_md_suffix_without_double_suffix() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "get", "SKILL.md"])
    # Assert
    assert result.exit_code == 0


def test_skills_get_emits_named_leaf_content() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "get", "01_installation"])
    # Assert
    assert "# Installation" in result.output


def test_skills_get_json_envelope_includes_content_field() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(
        cli_main, ["skills", "get", "01_installation", "--json"]
    )
    # Assert
    assert "content" in json.loads(result.output)


def test_skills_get_unknown_name_exits_nonzero_with_hint() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "get", "does-not-exist"])
    # Assert
    assert result.exit_code != 0


def test_skills_get_unknown_name_lists_available_leaves_in_hint() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli_main, ["skills", "get", "does-not-exist"])
    # Assert
    assert "available:" in result.output


# ---------------------------------------------------------------------------
# `skills install`
# ---------------------------------------------------------------------------


def test_skills_install_dry_run_does_not_create_destination_directory(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    dest = tmp_path / "claude-skills"
    # Act
    runner.invoke(
        cli_main, ["skills", "install", "--dest", str(dest), "--dry-run"]
    )
    # Assert
    assert not dest.exists()


def test_skills_install_dry_run_emits_would_copy_lines(tmp_path: Path) -> None:
    # Arrange
    runner = CliRunner()
    dest = tmp_path / "claude-skills"
    # Act
    result = runner.invoke(
        cli_main, ["skills", "install", "--dest", str(dest), "--dry-run"]
    )
    # Assert
    assert "would copy:" in result.output


def test_skills_install_writes_skill_md_to_destination(tmp_path: Path) -> None:
    # Arrange
    runner = CliRunner()
    dest = tmp_path / "claude-skills"
    # Act
    runner.invoke(cli_main, ["skills", "install", "--dest", str(dest)])
    # Assert
    assert (dest / "SKILL.md").is_file()


def test_skills_install_writes_canonical_installation_leaf_to_destination(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    dest = tmp_path / "claude-skills"
    # Act
    runner.invoke(cli_main, ["skills", "install", "--dest", str(dest)])
    # Assert
    assert (dest / "01_installation.md").is_file()


def test_skills_install_into_non_empty_destination_without_force_exits_nonzero(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    dest = tmp_path / "claude-skills"
    dest.mkdir()
    (dest / "preexisting.md").write_text("hi", encoding="utf-8")
    # Act
    result = runner.invoke(cli_main, ["skills", "install", "--dest", str(dest)])
    # Assert
    assert result.exit_code != 0


def test_skills_install_into_non_empty_destination_with_force_succeeds(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = CliRunner()
    dest = tmp_path / "claude-skills"
    dest.mkdir()
    (dest / "preexisting.md").write_text("hi", encoding="utf-8")
    # Act
    result = runner.invoke(
        cli_main, ["skills", "install", "--dest", str(dest), "--force"]
    )
    # Assert
    assert result.exit_code == 0


def test_skills_install_with_force_preserves_unrelated_files_in_destination(
    tmp_path: Path,
) -> None:
    """`--force` overwrites bundle leaves but does not touch unrelated
    files the operator may have placed alongside.
    """
    # Arrange
    runner = CliRunner()
    dest = tmp_path / "claude-skills"
    dest.mkdir()
    (dest / "notes.md").write_text("operator notes", encoding="utf-8")
    # Act
    runner.invoke(
        cli_main, ["skills", "install", "--dest", str(dest), "--force"]
    )
    # Assert
    assert (dest / "notes.md").read_text(encoding="utf-8") == "operator notes"
