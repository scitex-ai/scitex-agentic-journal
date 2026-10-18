"""No-mocks tests for the ``scitex-agentic-journal hub-manifest`` subcommand.

Mirrors live-paper PR #45's
``tests/cli/test_hub_manifest_cmd.py`` verbatim so the two upstream
packages stay symmetric — same pins:

1. Subcommand registration + ``--help`` documents the flags
2. Default JSON output is indented + sorted (stable VCS diffs)
3. ``--compact`` switches to single-line JSON
4. ``--label`` / ``--subtitle`` / ``--schema-version`` overrides win
5. Output, with no overrides, matches :func:`derive_wrapper_manifest`
6. Output is ready to redirect into ``manifest.json`` — no chrome,
   no leading log lines, just JSON.

Real CliRunner + real ``derive_wrapper_manifest`` — no mocks.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli


# ──────────────────────────────────────────────────────────────────
# Subcommand registration + help
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_subcommand_is_registered() -> None:
    # Arrange
    # Act
    commands = cli.commands
    # Assert
    assert "hub-manifest" in commands


def test_top_level_help_lists_hub_manifest() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["--help"])
    # Assert
    assert "hub-manifest" in result.output


def test_hub_manifest_help_exits_zero() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--help"])
    # Assert
    assert result.exit_code == 0


def test_hub_manifest_help_documents_label_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--help"])
    # Assert
    assert "--label" in result.output


def test_hub_manifest_help_documents_subtitle_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--help"])
    # Assert
    assert "--subtitle" in result.output


def test_hub_manifest_help_documents_schema_version_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--help"])
    # Assert
    assert "--schema-version" in result.output


def test_hub_manifest_help_documents_compact_flag() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--help"])
    # Assert
    assert "--compact" in result.output


def test_hub_manifest_help_mentions_manifest_json_redirect_example() -> None:
    """The whole point of the subcommand is `... > manifest.json`;
    the help text should make that idiom discoverable."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--help"])
    # Assert
    assert "manifest.json" in result.output


# ──────────────────────────────────────────────────────────────────
# Default output — indented, sorted, JSON, exit 0
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_exits_zero() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest"])
    # Assert
    assert result.exit_code == 0, result.output


def test_hub_manifest_default_output_is_valid_json() -> None:
    """Must parse cleanly so the user can `... > manifest.json` and
    downstream ``json.load()`` callers don't choke."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest"])
    parsed = json.loads(result.output)
    # Assert
    assert isinstance(parsed, dict)


def test_hub_manifest_default_output_is_indented() -> None:
    """Indented JSON spans many lines; compact would be exactly one."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest"])
    line_count = sum(1 for ln in result.output.splitlines() if ln.strip())
    # Assert
    assert line_count > 5


def test_hub_manifest_default_output_is_sorted() -> None:
    """Hash keys must round-trip in sorted order so VCS diffs are
    stable across versions of Python / dict insertion order."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest"])
    parsed = json.loads(result.output)
    top_keys = list(parsed.keys())
    # Assert
    assert top_keys == sorted(top_keys)


def test_hub_manifest_default_output_matches_derive_wrapper_manifest() -> None:
    # Arrange
    from scitex_agentic_journal import derive_wrapper_manifest

    runner = CliRunner()
    expected = derive_wrapper_manifest()
    # Act
    result = runner.invoke(cli, ["hub-manifest"])
    parsed = json.loads(result.output)
    # Assert
    assert parsed == expected


# ──────────────────────────────────────────────────────────────────
# --compact — single-line JSON for inline embedding
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_compact_exits_zero() -> None:
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--compact"])
    # Assert
    assert result.exit_code == 0, result.output


def test_hub_manifest_compact_is_single_line() -> None:
    """Trim the trailing newline click.echo adds; the payload itself
    should be exactly one line."""
    # Arrange
    runner = CliRunner()
    # Act
    result = runner.invoke(cli, ["hub-manifest", "--compact"])
    payload = result.output.rstrip("\n")
    # Assert
    assert "\n" not in payload


def test_hub_manifest_compact_carries_same_data_as_indented() -> None:
    # Arrange
    runner = CliRunner()
    compact = runner.invoke(cli, ["hub-manifest", "--compact"]).output
    indented = runner.invoke(cli, ["hub-manifest"]).output
    # Act
    parsed_compact = json.loads(compact)
    parsed_indented = json.loads(indented)
    # Assert
    assert parsed_compact == parsed_indented


# ──────────────────────────────────────────────────────────────────
# Per-wrapper overrides win
# ──────────────────────────────────────────────────────────────────


def test_hub_manifest_label_override_propagates_to_label_field() -> None:
    # Arrange
    runner = CliRunner()
    expected = "Custom Tenant Branding"
    # Act
    result = runner.invoke(
        cli, ["hub-manifest", "--label", expected]
    )
    parsed = json.loads(result.output)
    # Assert
    assert parsed["label"] == expected


def test_hub_manifest_subtitle_override_propagates_to_subtitle_field() -> None:
    # Arrange
    runner = CliRunner()
    expected = "Custom one-liner for this tenant"
    # Act
    result = runner.invoke(
        cli, ["hub-manifest", "--subtitle", expected]
    )
    parsed = json.loads(result.output)
    # Assert
    assert parsed["subtitle"] == expected


def test_hub_manifest_schema_version_override_propagates_to_schema_field() -> None:
    # Arrange
    runner = CliRunner()
    expected = "3.0.0-rc1"
    # Act
    result = runner.invoke(
        cli, ["hub-manifest", "--schema-version", expected]
    )
    parsed = json.loads(result.output)
    # Assert
    assert parsed["$schema_version"] == expected
