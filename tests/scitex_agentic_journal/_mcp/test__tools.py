"""Unit tests for :mod:`scitex_agentic_journal._mcp` — no fastmcp required."""

from __future__ import annotations

from datetime import timezone
from pathlib import Path

import pytest
from scitex_agentic_journal._mcp import (
    AGENT_SCOPES,
    ALL_SCOPES,
    READ_ONLY_TOOLS,
    WRITE_TOOLS,
    AuditEntry,
    AuditLog,
    ScopeDeniedError,
    TokenScope,
    ToolKind,
    tool_catalogue,
)

# ----- Tool catalogue -------------------------------------------------------


def test_tool_catalogue_first_is_read_only() -> None:
    # Arrange
    catalogue = tool_catalogue()
    # Act
    first_kind = catalogue[0].kind
    # Assert
    assert first_kind is ToolKind.READ_ONLY


def test_read_only_tools_are_all_read_only() -> None:
    # Arrange
    kinds = {tool.kind for tool in READ_ONLY_TOOLS}
    # Act
    only_read_only = kinds == {ToolKind.READ_ONLY}
    # Assert
    assert only_read_only is True


def test_write_tools_are_all_write() -> None:
    # Arrange
    kinds = {tool.kind for tool in WRITE_TOOLS}
    # Act
    only_write = kinds == {ToolKind.WRITE}
    # Assert
    assert only_write is True


def test_aj_submit_required_scope_is_submitter() -> None:
    # Arrange
    submit_tool = next(t for t in WRITE_TOOLS if t.name == "aj_submit")
    # Act
    required = submit_tool.required_scope
    # Assert
    assert required is TokenScope.SUBMITTER


def test_aj_apply_decision_required_scope_is_editor() -> None:
    # Arrange
    decide_tool = next(t for t in WRITE_TOOLS if t.name == "aj_apply_decision")
    # Act
    required = decide_tool.required_scope
    # Assert
    assert required is TokenScope.EDITOR


def test_aj_submit_review_required_scope_is_reviewer_agent() -> None:
    # Arrange
    review_tool = next(t for t in WRITE_TOOLS if t.name == "aj_submit_review")
    # Act
    required = review_tool.required_scope
    # Assert
    assert required is TokenScope.REVIEWER_AGENT


# ----- Scopes ---------------------------------------------------------------


def test_all_scopes_contains_admin() -> None:
    # Arrange
    has_admin = TokenScope.ADMIN in ALL_SCOPES
    # Act
    # Assert
    assert has_admin is True


def test_admin_bundle_carries_every_scope() -> None:
    # Arrange
    bundle = AGENT_SCOPES["admin"]
    # Act
    same = bundle == frozenset(ALL_SCOPES)
    # Assert
    assert same is True


def test_submitter_bundle_is_single_scope() -> None:
    # Arrange
    bundle = AGENT_SCOPES["submitter"]
    # Act
    size = len(bundle)
    # Assert
    assert size == 1


def test_scope_denied_error_includes_required_scope() -> None:
    # Arrange
    err = ScopeDeniedError(
        tool_name="aj_publish",
        required=TokenScope.EDITOR,
        held=frozenset({TokenScope.SUBMITTER}),
    )
    # Act
    msg = str(err)
    # Assert
    assert "editor" in msg


# ----- AuditLog -------------------------------------------------------------


def test_audit_log_append_returns_entry_with_tool_name(tmp_path: Path) -> None:
    # Arrange
    log = AuditLog(tmp_path / "audit.jsonl")
    # Act
    entry = log.append("aj_submit", TokenScope.SUBMITTER)
    # Assert
    assert entry.tool_name == "aj_submit"


def test_audit_log_append_writes_timezone_aware_timestamp(tmp_path: Path) -> None:
    # Arrange
    log = AuditLog(tmp_path / "audit.jsonl")
    # Act
    entry = log.append("aj_submit", TokenScope.SUBMITTER)
    # Assert
    assert entry.ts.tzinfo is timezone.utc


def test_audit_log_read_all_round_trips_entries(tmp_path: Path) -> None:
    # Arrange
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("aj_submit", TokenScope.SUBMITTER, {"submission_id": "s1"})
    log.append("aj_apply_decision", TokenScope.EDITOR, {"submission_id": "s1"})
    # Act
    entries = log.read_all()
    # Assert
    assert len(entries) == 2


def test_audit_log_round_trip_preserves_actor_scope(tmp_path: Path) -> None:
    # Arrange
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("aj_apply_decision", TokenScope.EDITOR)
    # Act
    entries = log.read_all()
    # Assert
    assert entries[0].actor_scope is TokenScope.EDITOR


def test_audit_log_round_trip_preserves_payload_summary(tmp_path: Path) -> None:
    # Arrange
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("aj_submit", TokenScope.SUBMITTER, {"sid": "s-42"})
    # Act
    entries = log.read_all()
    # Assert
    assert entries[0].payload_summary == {"sid": "s-42"}


def test_audit_log_read_all_on_missing_file_returns_empty(tmp_path: Path) -> None:
    # Arrange
    log = AuditLog(tmp_path / "never-created.jsonl")
    # Act
    entries = log.read_all()
    # Assert
    assert entries == ()


# ----- Server builder requires fastmcp --------------------------------------


def _fastmcp_is_installed() -> bool:
    try:
        import fastmcp  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(
    _fastmcp_is_installed(),
    reason="fastmcp is installed; missing-import path can't be exercised here",
)
def test_build_fastmcp_server_raises_when_fastmcp_missing() -> None:
    # Arrange
    from scitex_agentic_journal._mcp._server import (
        FastmcpMissingError,
        build_fastmcp_server,
    )

    # Act
    # Assert
    with pytest.raises(FastmcpMissingError):
        build_fastmcp_server()


@pytest.mark.skipif(
    not _fastmcp_is_installed(),
    reason="fastmcp not installed in this env",
)
def test_build_fastmcp_server_returns_object_when_fastmcp_present() -> None:
    # Arrange
    from scitex_agentic_journal._mcp._server import build_fastmcp_server

    # Act
    server = build_fastmcp_server()
    # Assert
    assert server is not None
