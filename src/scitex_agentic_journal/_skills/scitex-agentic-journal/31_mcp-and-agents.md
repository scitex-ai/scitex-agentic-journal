---
description: |
  [TOPIC] Read-only MCP submission discovery
  [DETAILS] One implemented local submission reader, actual schema discovery, and explicit unavailable workflow boundaries.
tags: [scitex-agentic-journal-mcp-and-agents]
---

# Read-only MCP submission discovery

`aj_get_submission` reads an existing local submission summary through the same
public Python operation and persisted archive as the Web detail view. It never
submits a bundle, performs validation, starts review, signs, or publishes.

## Discovery

Install `scitex-agentic-journal[mcp]` (FastMCP >=2.14.0), then inspect actual in-memory FastMCP schema:

```bash
scitex-agentic-journal mcp list-tools --json
scitex-agentic-journal list-python-apis --json
scitex-dev dev skills list --package scitex-agentic-journal --json
```

The MCP list contains only implemented handlers: currently `aj_get_submission`.
Its only client argument is `submission_id`; clients cannot supply a filesystem
home or user selector. Invalid identifiers raise an error. A valid unknown ID
returns `{"submission_id": "missing", "found": false}` without creating an archive.
Found records use the existing Web detail summary (`has_gate1`, `has_review`,
`has_decision`, verdict and persistent ID), not a fabricated validation result.

## Python and operator boundary

```python
from scitex_agentic_journal import get_submission

result = get_submission("missing")
```

`get_submission(..., home=path)` is an operator-owned Python override. The default
is `$SCITEX_AGENTIC_JOURNAL_HOME`, then `~/.scitex/agentic-journal`. The read does
not create directories. The server constructor binds one local archive once:

```python
from pathlib import Path
from scitex_agentic_journal._mcp import build_fastmcp_server

server = build_fastmcp_server(home=Path("/operator/owned/journal"))
```

The builder does not launch a transport. There is no `mcp serve`/`start` CLI or
executable `_mcp.__main__`. It does not implement network authentication, per-user
routing, bearer scope enforcement, write auditing or a reviewer-agent loop.
Do not expose a private archive on an unauthenticated network transport.

## Unavailable plans

`tool_catalogue()` retains fifteen planned definitions; `tool.available` is true
only for a bound handler. The other fourteen are not registered with FastMCP or
advertised by CLI discovery. `aj_list_submissions` remains unavailable: its planned
ORCID-filter contract is not implemented by the existing archive reader. Scope
metadata describes planned roles and does not prove authorization.

For actual workflow modules and configured-adapter requirements, use
[03](03_python-api.md), [04](04_cli-reference.md), and
[13](13_review-and-decision.md). Inspect help before business operations.
