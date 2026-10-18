"""FastMCP server wiring (deferred import).

``fastmcp`` is an **optional** dependency (extra: ``[mcp]``). The
import lives inside :func:`build_fastmcp_server` so the rest of the
``_mcp`` surface (catalogue, audit, scopes) imports cleanly in
environments without the extra installed — that's the default CI
test environment.
"""

from __future__ import annotations

from typing import Any

from scitex_agentic_journal._mcp._tools import tool_catalogue


class FastmcpMissingError(RuntimeError):
    """Raised when ``fastmcp`` is missing at server-build time.

    The message points the operator at the install incantation so
    they don't have to grep the README — no silent ``return None``
    fallback that would later raise inside the loop.
    """


def build_fastmcp_server(*, server_name: str = "scitex-agentic-journal") -> Any:
    """Build a configured :class:`fastmcp.FastMCP` server.

    Registers placeholders for every tool in :func:`tool_catalogue`
    so the surface is discoverable immediately. Real handlers will
    plug in once the corresponding gate engines (gate-1 / gate-2 /
    gate-3 / gate-4) ship.

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

    server = FastMCP(server_name)
    for tool in tool_catalogue():
        _register_placeholder(server, tool.name, tool.summary)
    return server


def _register_placeholder(server: Any, name: str, summary: str) -> None:
    """Attach a tool that signals "wired but not yet implemented".

    Importantly the handler **raises** rather than returns a stub
    payload. Reviewer agents need to know the tool isn't really
    answering, not get fed a plausible-looking lie.
    """

    @server.tool(name=name, description=summary)
    def _handler() -> dict[str, str]:
        raise NotImplementedError(
            f"MCP tool {name!r} is wired but not yet implemented. "
            "Track aj-mcp implementation tasks before enabling in production."
        )
