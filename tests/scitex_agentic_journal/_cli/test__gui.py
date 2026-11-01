"""No-mocks tests for the ``scitex-agentic-journal gui`` group.

Covers the canonical §12 shape (``gui {open,serve,status,stop}``):
group registration, verb coverage, and flag placement (``--force``
on serve, ``--no-browser`` on open only, never on serve).

Real CliRunner — no mocks. The server itself is never started here;
that path is owned by ``scitex_sdk.app.embed.serve_gui`` /
``run_standalone`` and exercised by the SDK's own suite.
"""

from __future__ import annotations

from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli


# ──────────────────────────────────────────────────────────────────
# Group registration + verb coverage
# ──────────────────────────────────────────────────────────────────


def test_gui_group_is_registered() -> None:
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


def test_gui_help_lists_open_verb() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert "open" in result.output


def test_gui_help_lists_serve_verb() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert "serve" in result.output


def test_gui_help_lists_status_verb() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert "status" in result.output


def test_gui_help_lists_stop_verb() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "--help"])
    # Assert
    assert "stop" in result.output


# ──────────────────────────────────────────────────────────────────
# Flag placement (serve: headless; open: browser-launching)
# ──────────────────────────────────────────────────────────────────


def test_serve_help_documents_port_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "serve", "--help"])
    # Assert
    assert "--port" in result.output


def test_serve_help_documents_force_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "serve", "--help"])
    # Assert
    assert "--force" in result.output


def test_serve_help_has_no_browser_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "serve", "--help"])
    # Assert
    assert "--no-browser" not in result.output


def test_open_help_documents_no_browser_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "open", "--help"])
    # Assert
    assert "--no-browser" in result.output


def test_status_help_documents_json_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "status", "--help"])
    # Assert
    assert "--json" in result.output


def test_stop_help_documents_yes_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["gui", "stop", "--help"])
    # Assert
    assert "--yes" in result.output
