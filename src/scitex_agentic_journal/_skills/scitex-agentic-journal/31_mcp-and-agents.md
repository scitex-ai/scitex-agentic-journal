---
description: |
  [TOPIC] MCP server + agent tools
  [DETAILS] The submit / review / decide / publish MCP tools exposed under `_mcp`, scopes, audit log shape.
tags: [scitex-agentic-journal-mcp-and-agents]
---

# 08 · MCP server + AI-agent surface

`scitex-agentic-journal` ships an **MCP server** (`scitex_agentic_journal._mcp`) so AI agents — including the reviewer agents themselves — can drive the journal end-to-end without going through the human CLI.

> **Status:** planned (M7 — `aj-mcp` board card). Not yet implemented.

## Install

```bash
pip install 'scitex-agentic-journal[mcp]'
```

The `[mcp]` extra pulls `fastmcp>=2.0`. Without it the `_mcp` import raises (no silent fallback).

## Run

```bash
scitex-agentic-journal mcp serve --port 6731
# or
python -m scitex_agentic_journal._mcp
```

The server is `fastmcp`-based, listens on stdio by default, and switches to HTTP/SSE when `--http` is passed.

## Tool surface (planned)

Names are stable for agents. Each tool is a thin wrapper over the Python API ([06_python-api.md](06_python-api.md)).

### Submission tools

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `aj_submit` | Submit a bundle | bundle path (or inline tar/zip) | `submission_id`, gate-1 result |
| `aj_get_submission` | Read submission record | `submission_id` | `Submission` |
| `aj_list_submissions` | List for an ORCID | `orcid` | array of `Submission` summaries |

### Gate-1 tools

| Tool | Purpose |
|------|---------|
| `aj_check_orcid` | ORCID resolvability probe |
| `aj_check_code_repo` | Anonymous `git ls-remote` probe |
| `aj_check_clew_dag` | DAG presence + ≥ 1 green claim probe |
| `aj_run_gate1` | All three checks aggregated |

### Review tools

| Tool | Purpose |
|------|---------|
| `aj_start_review` | Enqueue a reviewer-agent run against a `submission_id` |
| `aj_get_review_record` | Read the review record (read-only) |
| `aj_list_review_records` | All review attempts for a `submission_id` |

### Decision + publish tools

| Tool | Purpose |
|------|---------|
| `aj_apply_decision` | Run gate-3 rules over the latest review record |
| `aj_get_decision_record` | Read the decision record |
| `aj_mint_id` | Gate-4 persistent ID mint |
| `aj_publish` | Hand off to scitex-live-paper |

### Read-only tools (always safe for agents to call)

`aj_get_*`, `aj_list_*`, `aj_check_*` are side-effect-free and may be called freely by any agent.

### Write tools (gated)

`aj_submit`, `aj_start_review`, `aj_apply_decision`, `aj_mint_id`, `aj_publish` are write tools. The MCP server enforces:

1. Bearer token in `Authorization` header (rotating; managed by scitex-hub).
2. Per-token scope (`submitter` / `reviewer-agent` / `editor` / `admin`).
3. Audit log of every write to `_mcp/audit.jsonl` (append-only).

A submitter token cannot call `aj_apply_decision`; a reviewer-agent token cannot call `aj_submit`. Cross-role calls return 403, not 401, so debuggers see the real reason.

## Agent-loop example

A reviewer-agent's main loop looks like:

```
while job := mcp.aj_dequeue_review_job():
    bundle = mcp.aj_get_submission(job.submission_id)
    code_dir = clone(bundle.code_repo_url, sandbox=True)
    repro = run_reproducibility(code_dir, bundle.claims)
    claim_verify = verify_claims(bundle.claims, bundle.dag)
    novelty = mcp.scholar_search(bundle.claims.top_level)
    methodology = critique_methodology(bundle.manuscript)
    mcp.aj_submit_review(job.submission_id, {
        "reproducibility": repro,
        "claim_verify": claim_verify,
        "novelty": novelty,
        "methodology": methodology,
        "prompts_version": "v1",
        "adapter": "qwen-self-hosted",
    })
```

Note: the agent never decides accept / revise / reject. It submits a review record and the rules engine runs.

## Why MCP not REST

REST would also work, but MCP is the canonical tool surface used by SciTeX-side agents (Clew, Scholar, Hub, Writer, Live Paper). A reviewer agent that already speaks MCP needs zero glue to drive agentic-journal too.

A REST API may be added later for non-MCP consumers (e.g. a GitHub-Action that submits on `git tag`).

## Safety

- The reviewer-agent sandbox is **not** provided by `scitex-agentic-journal`. The MCP server hands off code-execution to `scitex-clew`'s sandboxed runner (already hardened for claim verification).
- No tool in this server executes manuscript code directly. The closest is `aj_run_gate1`, which only does `git ls-remote` — no clone, no execute.
- The MCP server never reads from `~` or other host paths. All bundles live under `SCITEX_AJ_BUNDLE_DIR` (env-pinned, no fallback).
