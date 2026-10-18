"""MCP server surface for the agentic journal.

Exposes the journal end-to-end as MCP tools so reviewer agents,
submitter agents, and editor agents can drive it without going
through the human CLI.

The package is split so the **core types** (tool catalogue, scopes,
audit log) import without the optional ``fastmcp`` dependency. Only
:func:`build_fastmcp_server` requires ``pip install
'scitex-agentic-journal[mcp]'``; the import is deferred to that
function so the rest of the surface tests cleanly in CI without the
extra installed.
"""

from __future__ import annotations

from scitex_agentic_journal._mcp._audit import (
    AuditEntry,
    AuditLog,
)
from scitex_agentic_journal._mcp._scopes import (
    AGENT_SCOPES,
    ALL_SCOPES,
    ScopeDeniedError,
    TokenScope,
)
from scitex_agentic_journal._mcp._server import build_fastmcp_server
from scitex_agentic_journal._mcp._tools import (
    READ_ONLY_TOOLS,
    WRITE_TOOLS,
    ToolDef,
    ToolKind,
    tool_catalogue,
)

__all__ = [
    "AGENT_SCOPES",
    "ALL_SCOPES",
    "AuditEntry",
    "AuditLog",
    "READ_ONLY_TOOLS",
    "ScopeDeniedError",
    "ToolDef",
    "ToolKind",
    "TokenScope",
    "WRITE_TOOLS",
    "build_fastmcp_server",
    "tool_catalogue",
]
