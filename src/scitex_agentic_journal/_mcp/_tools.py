"""Tool catalogue — the stable surface area MCP clients see.

A ``ToolDef`` is a passive metadata record. The actual MCP server
construction (FastMCP decorators, parameter schemas) happens in
:mod:`scitex_agentic_journal._mcp._server`. Splitting it lets us
build dashboards, generate docs, and validate scopes without
importing ``fastmcp``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from scitex_agentic_journal._mcp._scopes import TokenScope


class ToolKind(str, Enum):
    """Side-effect / scope band a tool belongs to."""

    READ_ONLY = "read-only"
    WRITE = "write"


@dataclass(frozen=True, slots=True)
class ToolDef:
    """Stable metadata for one MCP tool.

    The ``name`` is the agent-facing identifier and is part of the
    public contract — renames are breaking changes that bump the
    package minor version.
    """

    name: str
    kind: ToolKind
    summary: str
    required_scope: TokenScope


# ---------------------------------------------------------------------------
# READ-ONLY surface — side-effect-free; any token (even unauthenticated
# read sessions) can call these.
# ---------------------------------------------------------------------------

READ_ONLY_TOOLS: Final[tuple[ToolDef, ...]] = (
    ToolDef(
        name="aj_get_submission",
        kind=ToolKind.READ_ONLY,
        summary="Read one submission record.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_list_submissions",
        kind=ToolKind.READ_ONLY,
        summary="List submissions for an ORCID.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_check_orcid",
        kind=ToolKind.READ_ONLY,
        summary="Gate-1 ORCID resolvability probe.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_check_code_repo",
        kind=ToolKind.READ_ONLY,
        summary="Gate-1 code-repo cloneability probe.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_check_clew_dag",
        kind=ToolKind.READ_ONLY,
        summary="Gate-1 Clew DAG completeness probe.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_run_gate1",
        kind=ToolKind.READ_ONLY,
        summary="Aggregate all three gate-1 probes.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_get_review_record",
        kind=ToolKind.READ_ONLY,
        summary="Read one review record.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_list_review_records",
        kind=ToolKind.READ_ONLY,
        summary="List all review attempts for one submission.",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_get_decision_record",
        kind=ToolKind.READ_ONLY,
        summary="Read one decision record.",
        required_scope=TokenScope.SUBMITTER,
    ),
)


# ---------------------------------------------------------------------------
# WRITE surface — guarded by required scope. Cross-role calls return
# `ScopeDeniedError` (mapped to HTTP 403 by the FastMCP transport).
# ---------------------------------------------------------------------------

WRITE_TOOLS: Final[tuple[ToolDef, ...]] = (
    ToolDef(
        name="aj_submit",
        kind=ToolKind.WRITE,
        summary="Submit a new bundle (kicks off gate-1).",
        required_scope=TokenScope.SUBMITTER,
    ),
    ToolDef(
        name="aj_start_review",
        kind=ToolKind.WRITE,
        summary="Enqueue a reviewer-agent run.",
        required_scope=TokenScope.EDITOR,
    ),
    ToolDef(
        name="aj_submit_review",
        kind=ToolKind.WRITE,
        summary="Reviewer agent submits a finished review record.",
        required_scope=TokenScope.REVIEWER_AGENT,
    ),
    ToolDef(
        name="aj_apply_decision",
        kind=ToolKind.WRITE,
        summary="Run gate-3 rules over the latest review record.",
        required_scope=TokenScope.EDITOR,
    ),
    ToolDef(
        name="aj_mint_id",
        kind=ToolKind.WRITE,
        summary="Mint a persistent ID via the configured backend.",
        required_scope=TokenScope.EDITOR,
    ),
    ToolDef(
        name="aj_publish",
        kind=ToolKind.WRITE,
        summary="Hand off accepted bundle to scitex-live-paper.",
        required_scope=TokenScope.EDITOR,
    ),
)


def tool_catalogue() -> tuple[ToolDef, ...]:
    """Stable ordering: read-only first, then write. Used for docs."""
    return READ_ONLY_TOOLS + WRITE_TOOLS
