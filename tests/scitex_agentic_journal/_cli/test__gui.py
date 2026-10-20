"""No-mocks tests for the ``scitex-agentic-journal gui`` subcommand.

Covers the SDK-canonical standalone-launcher surface (mirrors what
``scitex-sdk app init`` scaffolds):

1. Subcommand registration + ``--help`` documents the flags
2. ``--help`` exits zero and names the SDK behaviours (exact port,
   ``--force`` ownership rule)

Real CliRunner — no mocks. The server itself is never started here;
that path is owned by ``scitex_sdk.app.embed.serve_gui`` /
``run_standalone`` and exercised by the SDK's own suite.
"""

from __future__ import annotations

from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli


# ──────────────────────────────────────────────────────────────────
# Subcommand registration + help
# ──────────────────────────────────────────────────────────────────


def test_gui_subcommand_is_registered() -> None:
    # Arrange
    # Act
    commands = cli.commands
    # Assert
    assert "gui" in commands


def test_top_level_help_lists_gui() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--help"])
    # Assert
    assert "gui" in result.output


def test_gui_help_exits_zero() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert result.exit_code == 0


def test_gui_help_documents_port_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert "--port" in result.output


def test_gui_help_documents_force_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert "--force" in result.output


def test_gui_help_documents_no_browser_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert "--no-browser" in result.output
