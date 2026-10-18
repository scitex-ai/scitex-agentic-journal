"""Bearer-token scopes for the MCP surface.

Every write tool is enforced with a per-token scope; cross-role calls
return 403 (not 401) so debuggers see the real reason. Scopes are an
:class:`enum.Enum` to keep typo classes out of dashboards.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class TokenScope(str, Enum):
    """Roles a bearer token can carry.

    Multiple scopes per token are allowed (a "reviewer-agent" token
    may also carry "submitter" for self-test) — :class:`AGENT_SCOPES`
    documents the canonical assignments.
    """

    SUBMITTER = "submitter"
    REVIEWER_AGENT = "reviewer-agent"
    EDITOR = "editor"
    ADMIN = "admin"


ALL_SCOPES: Final[tuple[TokenScope, ...]] = tuple(TokenScope)
"""Canonical iteration order for dashboards / docs."""


AGENT_SCOPES: Final[dict[str, frozenset[TokenScope]]] = {
    "submitter": frozenset({TokenScope.SUBMITTER}),
    "reviewer-agent": frozenset({TokenScope.REVIEWER_AGENT}),
    "editor": frozenset({TokenScope.EDITOR}),
    "admin": frozenset(ALL_SCOPES),
}
"""Canonical per-role bundles operators dispense.

The admin bundle is the only one that overlaps multiple roles —
auditing intentionally separates the four roles so writes attribute
correctly.
"""


class ScopeDeniedError(PermissionError):
    """Raised when a token's scopes don't cover a tool's required scope."""

    def __init__(
        self,
        tool_name: str,
        required: TokenScope,
        held: frozenset[TokenScope],
    ) -> None:
        self.tool_name = tool_name
        self.required = required
        self.held = held
        super().__init__(
            f"tool {tool_name!r} requires scope {required.value!r}; "
            f"token holds {sorted(s.value for s in held)!r}"
        )
