"""Append-only audit log for MCP write tools.

The journal's transparency promise — public review + decision records
— extends to admin action: every write tool call is appended to the
audit log so operators can reconstruct who minted / accepted / rejected
what.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._mcp._scopes import TokenScope


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One row in the audit log.

    ``payload_summary`` carries a small dict of structured context
    (submission id, persistent id, decision outcome) — not full record
    bodies. The records themselves are persisted by the journal store;
    the audit log is a navigation index, not a replica.
    """

    tool_name: str
    actor_scope: TokenScope
    ts: datetime
    payload_summary: dict[str, str] = field(default_factory=dict)


class AuditLog:
    """Append-only newline-delimited JSON log.

    Each line is a self-contained :class:`AuditEntry`. The log is
    write-once-per-line so a log corruption only loses the in-flight
    line — never silently truncates earlier entries.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(
        self,
        tool_name: str,
        actor_scope: TokenScope,
        payload_summary: dict[str, str] | None = None,
    ) -> AuditEntry:
        """Append + return the entry.

        Times are timezone-aware UTC so round-trips through JSON keep
        the offset (and naive logs don't mix with aware records).
        """
        entry = AuditEntry(
            tool_name=tool_name,
            actor_scope=actor_scope,
            ts=datetime.now(tz=timezone.utc),
            payload_summary=dict(payload_summary or {}),
        )
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(_entry_to_json_line(entry))
            fh.write("\n")
        return entry

    def read_all(self) -> tuple[AuditEntry, ...]:
        """Read every entry as a tuple. Empty file -> empty tuple."""
        if not self._path.exists():
            return ()
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return tuple(_json_line_to_entry(line) for line in lines if line.strip())


def _entry_to_json_line(entry: AuditEntry) -> str:
    body = asdict(entry)
    body["actor_scope"] = entry.actor_scope.value
    body["ts"] = entry.ts.isoformat()
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def _json_line_to_entry(line: str) -> AuditEntry:
    body = json.loads(line)
    return AuditEntry(
        tool_name=body["tool_name"],
        actor_scope=TokenScope(body["actor_scope"]),
        ts=datetime.fromisoformat(body["ts"]),
        payload_summary=dict(body.get("payload_summary") or {}),
    )
