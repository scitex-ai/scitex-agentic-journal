"""scitex-clew's store-free rerun report, and the check records derived from it.

``clew bundle rerun <bundle> --project-root P --timeout S --json`` prints::

    {"schema": "scitex-clew.rerun-report", "schema_version": "1.x.y",
     "bundle_sha256": str, "executable": bool,
     "runs": [{"run_id", "exit_code", "status": reproduced|differs|failed|skipped,
               "outputs": [{"path", "expected_sha256", "actual_sha256", "match"}],
               "stderr_tail"}],
     "claims": [{"claim_id", "status": reproduced|differs|not_checkable,
                 "stated_value", "recomputed_value", "tolerance"}]}

``tolerance`` is the claim's declared precision, decided upstream (design §11
D13). The structure is checked here field by field; once scitex-clew publishes
a JSON schema for it, it is vendored and pinned like the live-paper contracts.
"""

from __future__ import annotations

import json
from typing import Any

from scitex_agentic_journal._admission._checks import FAILED, NOT_RUN, PASSED, record

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


def _runs_detail(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run["run_id"],
            "status": run["status"],
            "exit_code": run.get("exit_code"),
            "outputs": [
                {
                    "path": out.get("path"),
                    "match": out.get("match"),
                    "expected_sha256": out.get("expected_sha256"),
                    "actual_sha256": out.get("actual_sha256"),
                }
                for out in run.get("outputs", [])
            ],
        }
        for run in report["runs"]
    ]


def executability_record(
    report: dict[str, Any], *, tool: dict[str, Any], details: dict[str, Any]
) -> dict[str, Any]:
    """``executability`` passes iff the report says the project is executable."""
    runs = report["runs"]
    failed = [r["run_id"] for r in runs if r["status"] == "failed"]
    body = {
        **details,
        "executable": report["executable"],
        "runs": len(runs),
        "failed_runs": failed,
    }
    if report["executable"]:
        return record(
            "executability",
            PASSED,
            f"executable in isolation ({len(runs)} run(s), {len(failed)} failed)",
            required=False,
            tool=tool,
            details=body,
        )
    return record(
        "executability",
        FAILED,
        f"not executable in isolation; failed run(s): {failed}",
        required=False,
        tool=tool,
        details=body,
    )


def reproduction_record(
    report: dict[str, Any],
    main_claims: list[str],
    *,
    bundle_sha256: str,
    tool: dict[str, Any],
    details: dict[str, Any],
) -> dict[str, Any]:
    """``reproduction`` passes iff every main claim is ``reproduced``."""
    by_id = {c["claim_id"]: c for c in report["claims"]}
    claims = [
        {
            "claim_id": c["claim_id"],
            "main": c["claim_id"] in main_claims,
            "status": c["status"],
            "stated_value": c.get("stated_value"),
            "recomputed_value": c.get("recomputed_value"),
            "tolerance": c.get("tolerance"),
        }
        for c in report["claims"]
    ]
    not_reproduced = {
        cid: (by_id[cid]["status"] if cid in by_id else "not in rerun report")
        for cid in main_claims
        if cid not in by_id or by_id[cid]["status"] != "reproduced"
    }
    body = {
        **details,
        "targets": list(main_claims),
        "bundle_sha256": report["bundle_sha256"],
        "claims": claims,
        "runs": _runs_detail(report),
        "not_reproduced": not_reproduced,
    }
    if report["bundle_sha256"] != bundle_sha256:
        return record(
            "reproduction",
            FAILED,
            f"the rerun report is for bundle {report['bundle_sha256']}, not the "
            f"submitted bundle {bundle_sha256}",
            required=False,
            tool=tool,
            details=body,
        )
    if not_reproduced:
        return record(
            "reproduction",
            FAILED,
            f"{len(not_reproduced)} main claim(s) not reproduced: {not_reproduced}",
            required=False,
            tool=tool,
            details=body,
        )
    return record(
        "reproduction",
        PASSED,
        f"all {len(main_claims)} main claim(s) reproduced",
        required=False,
        tool=tool,
        details=body,
    )


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
