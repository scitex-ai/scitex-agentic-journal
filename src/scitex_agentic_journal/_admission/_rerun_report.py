"""scitex-clew's store-free rerun report: parsed as a HINT, never as a verdict.

``clew bundle rerun <bundle> --project-root P --work-dir DIR --timeout S
--python PY --json`` prints (schema 1.1.0)::

    {"schema": "scitex-clew.rerun-report", "schema_version": "1.1.0",
     "bundle_sha256": str, "executable": bool, "work_dir": str | null,
     "runs": [{"run_id", "exit_code", "status": reproduced|differs|failed|skipped,
               "run_dir": str | null,
               "outputs": [{"path", "expected_sha256", "actual_sha256", "match",
                            "resolved_path"}],
               "stderr_tail"}],
     "claims": [{"claim_id", "status": reproduced|differs|not_checkable,
                 "stated_value", "recomputed_value", "tolerance"}]}

The report is produced inside the sandbox, next to author code (same uid and
PID namespace), so it can be forged. The journal therefore uses it only for
(a) ``resolved_path``, to FIND each replayed output in the kept work dir,
which the host then hashes itself (:mod:`._replay_verify`), and (b) the
``sandbox_reported`` detail. No check passes because of what it says.
"""

from __future__ import annotations

import json
from typing import Any

from scitex_agentic_journal._admission._checks import NOT_RUN, record

REPORT_SCHEMA = "scitex-clew.rerun-report"
REPORT_MAJOR = "1"
RUN_STATUSES = frozenset({"reproduced", "differs", "failed", "skipped"})
CLAIM_STATUSES = frozenset({"reproduced", "differs", "not_checkable"})


class RerunReportError(ValueError):
    """The rerun output is not a rerun report this journal understands."""


def _require(cond: bool, what: str) -> None:
    if not cond:
        raise RerunReportError(what)


def parse_rerun_report(text: str) -> dict[str, Any]:
    """Parse and structurally check a rerun report; raise :class:`RerunReportError`."""
    try:
        report = json.loads(text)
    except json.JSONDecodeError as e:
        raise RerunReportError(f"rerun output is not JSON ({e})") from e
    _require(isinstance(report, dict), "rerun report is not a JSON object")
    _require(
        report.get("schema") == REPORT_SCHEMA,
        f"schema is {report.get('schema')!r}, expected {REPORT_SCHEMA!r}",
    )
    version = str(report.get("schema_version", ""))
    _require(
        version.split(".")[0] == REPORT_MAJOR,
        f"schema_version {version!r} is not {REPORT_MAJOR}.x",
    )
    _require(isinstance(report.get("bundle_sha256"), str), "bundle_sha256 missing")
    _require(isinstance(report.get("executable"), bool), "executable is not a boolean")
    _require(isinstance(report.get("runs"), list), "runs is not a list")
    _require(isinstance(report.get("claims"), list), "claims is not a list")
    for run in report["runs"]:
        _require(isinstance(run, dict) and "run_id" in run, "a run has no run_id")
        _require(run.get("status") in RUN_STATUSES, f"run status {run.get('status')!r}")
        _require(isinstance(run.get("outputs", []), list), "run outputs is not a list")
    for claim in report["claims"]:
        _require(
            isinstance(claim, dict) and isinstance(claim.get("claim_id"), str),
            "a claim has no claim_id",
        )
        _require(
            claim.get("status") in CLAIM_STATUSES,
            f"claim status {claim.get('status')!r}",
        )
    return report


def sandbox_reported(
    report: dict[str, Any] | None, error: str | None
) -> dict[str, Any]:
    """The ``sandbox_reported`` detail: what clew said in the sandbox (a hint only)."""
    if report is None:
        return {"parsed": False, "error": error}
    return {
        "parsed": True,
        "trusted": False,
        "schema_version": report.get("schema_version"),
        "bundle_sha256": report.get("bundle_sha256"),
        "executable": report.get("executable"),
        "work_dir": report.get("work_dir"),
        "runs": {r["run_id"]: r["status"] for r in report["runs"]},
        "claims": {c["claim_id"]: c["status"] for c in report["claims"]},
    }


def not_run_pair(
    reason: str,
    main_claims: list[str],
    *,
    tool: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Both checks ``not-run`` with the same reason."""
    return [
        record(
            "executability", NOT_RUN, reason, required=False, tool=tool, details=details
        ),
        record(
            "reproduction",
            NOT_RUN,
            reason,
            required=False,
            tool=tool,
            details={**(details or {}), "targets": list(main_claims)},
        ),
    ]
