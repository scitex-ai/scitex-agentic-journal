"""FastMCP server wiring (deferred import).

``fastmcp`` is an **optional** dependency (extra: ``[mcp]``). The
import lives inside :func:`build_fastmcp_server` so the rest of the
``_mcp`` surface (catalogue, audit, scopes) imports cleanly in
environments without the extra installed — that's the default CI
test environment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scitex_agentic_journal._mcp._tools import tool_catalogue


class FastmcpMissingError(RuntimeError):
    """Raised when ``fastmcp`` is missing at server-build time.

    The message points the operator at the install incantation so
    they don't have to grep the README — no silent ``return None``
    fallback that would later raise inside the loop.
    """


def build_fastmcp_server(
    *, server_name: str = "scitex-agentic-journal", home: Path | None = None
) -> Any:
    """Build a configured :class:`fastmcp.FastMCP` server.

    Bind read handlers to one operator-owned local archive. Clients cannot
    select a filesystem root. The remaining catalogue entries are explicitly
    unavailable catalogue records and are not registered. This builder does not provide multi-user token
    authorization or a configured network transport.

    Raises
    ------
    FastmcpMissingError
        If ``fastmcp`` is not installed. Install via
        ``pip install 'scitex-agentic-journal[mcp]'``.
    """
    try:
        from fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError as exc:
        raise FastmcpMissingError(
            "fastmcp is not installed. Run "
            "`pip install 'scitex-agentic-journal[mcp]'` to enable the "
            "MCP server."
        ) from exc

    from scitex_agentic_journal._django._leaf import _submission_home

    root = _submission_home(home).expanduser().resolve()
    server = FastMCP(server_name)
    for tool in tool_catalogue():
        if tool.available:
            _register_read(server, tool, root)
    return server


def _register_read(server: Any, tool: Any, home: Path) -> None:
    @server.tool(
        name=tool.name,
        description=tool.summary,
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    def _handler(submission_id: str) -> dict[str, Any]:
        return tool.handler(submission_id, home=home)
