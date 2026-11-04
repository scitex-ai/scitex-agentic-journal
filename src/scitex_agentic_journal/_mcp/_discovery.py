"""Actual in-memory MCP discovery without executing a journal handler."""


def list_implemented_tools() -> list[dict]:
    """Get schema from FastMCP; proposed placeholders are not capabilities."""
    import asyncio

    try:
        from fastmcp import Client
    except ImportError as exc:
        raise ImportError("Install scitex-agentic-journal[mcp] for MCP discovery.") from exc

    from ._server import build_fastmcp_server
    from ._tools import tool_catalogue

    implemented = {tool.name for tool in tool_catalogue() if tool.handler is not None}

    async def discover():
        async with Client(build_fastmcp_server()) as client:
            return [
                tool.model_dump(mode="json", by_alias=True)
                for tool in await client.list_tools()
                if tool.name in implemented
            ]

    return asyncio.run(discover())
