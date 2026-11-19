---
description: |
  [TOPIC] MCP prototype and agent discovery
  [DETAILS] Passive tool catalogue, placeholder server boundary, and working non-executing discovery commands.
tags: [scitex-agentic-journal-mcp-and-agents]
---

# MCP prototype and agent discovery

The package contains a passive tool catalogue and a prototype FastMCP server builder. **No journal MCP workflow handler is implemented.** The builder registers every catalogue entry through `_register_placeholder`; each handler raises `NotImplementedError`. Catalogue membership does not establish an executable capability.

## Working discovery

These commands inspect metadata without submitting, reviewing or publishing:

```bash
scitex-agentic-journal mcp list-tools --json
scitex-agentic-journal list-python-apis --json
scitex-dev dev skills list --package scitex-agentic-journal --json
```

`mcp list-tools --json` currently returns `{"tools": []}`. It does not enumerate the separate passive catalogue. To inspect that design metadata directly:

```python
from scitex_agentic_journal._mcp import tool_catalogue

for tool in tool_catalogue():
    print(tool.name, tool.kind.value, tool.required_scope.value)
```

The catalogue contains proposed submission, gate-1, review, decision and publication operations. Its read/write classifications and required scopes describe intended contracts; they do not prove transport authorization or handler execution.

## Optional prototype dependency

```bash
pip install 'scitex-agentic-journal[mcp]'
```

The extra provides FastMCP for `build_fastmcp_server()`. Importing `_mcp` and inspecting `tool_catalogue()` do not require FastMCP; the dependency import is deferred until server construction. Installing the extra does not implement any journal tool handler.

There is no `mcp serve` or `mcp start` CLI command, and `_mcp` has no executable `__main__.py`. No supported server-launch command is documented here.

## Implementation boundaries

`_mcp._scopes` and `_mcp._audit` supply scope and audit primitives. The prototype server builder does not connect them to its placeholder handlers. Bearer-token verification, role enforcement, write auditing, configured transports and sandbox handoffs must be implemented and qualified before agents can rely on them. The prototype does not provide a working reviewer-agent loop.

For implemented workflow modules and their configured-adapter requirements, use the CLI/API guides: [03_python-api.md](03_python-api.md), [04_cli-reference.md](04_cli-reference.md), and [13_review-and-decision.md](13_review-and-decision.md). Inspect each command's help before invoking a business workflow.
