"""Run every admission check for a submission and record the outcome.

A submission is **admitted** when every *required* check passed. Checks
that are not required (Clew re-verification, executability, reproduction)
are still recorded, including ``not-run`` with its reason. They inform the
later acceptance gate (design §13.1); they never count as passes.

Each run writes ``admission/<timestamp>.json`` and replaces
``admission.json``, which always holds the latest run.
"""

from __future__ import annotations

from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from scitex_agentic_journal._admission._checks import (
    PASSED,
    Executor,
    NoExecutor,
    check_clew_reverify,
    check_main_claims,
    check_orcid,
    check_scitex_form,
    checkout_repository,
)
from scitex_agentic_journal._admission._proc import child_env
from scitex_agentic_journal._bundle import bundle_path, load_intake, validate_bundle
from scitex_agentic_journal._gate1._orcid import ORCID_PUB_API_BASE
from scitex_agentic_journal._records import (
    RecordError,
    read_record,
    submission_dir,
    utcnow_iso,
    write_record,
)

ADMISSION_RECORD = "admission.json"


def _journal_version() -> str:
    try:
        return metadata.version("scitex-agentic-journal")
    except metadata.PackageNotFoundError:
        return "0.0.0+local"


def run_admission(
    submission_id: str,
    *,
    home: Path | None = None,
    orcid_base_url: str = ORCID_PUB_API_BASE,
    lint_argv: list[str] | None = None,
    executor: Executor | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run the admission checks for an accepted intake; return the admission record."""
    load_intake(submission_id, home=home)  # raises RecordError if never submitted
    record_dir = submission_dir(submission_id, home)
    validation = validate_bundle(bundle_path(submission_id, home=home))
    if not validation.ok:
        raise RecordError(
            f"the journal's copy of {submission_id} no longer validates: "
            + "; ".join(f.message for f in validation.findings)
        )
    manifest = validation.manifest
    report = validation.evidence_report
    assert manifest is not None and report is not None
    env = child_env(record_dir / "work" / "home")
    started = utcnow_iso(now)

    checks: list[dict[str, Any]] = [check_orcid(manifest, base_url=orcid_base_url)]
    repo_check, project = checkout_repository(
        manifest, record_dir / "work" / "checkout", env=env
    )
    checks.append(repo_check)
    checks.append(check_scitex_form(project, env=env, lint_argv=lint_argv))
    checks.append(check_main_claims(manifest, report))
    checks.append(check_clew_reverify())
    runner = executor or NoExecutor()
    if project is not None:
        checks.extend(runner.run(project, manifest))
    else:
        checks.extend(NoExecutor().run(Path("."), manifest))

    required_failed = [
        c["check"] for c in checks if c["required"] and c["status"] != PASSED
    ]
    payload = {
        "schema": "scitex-agentic-journal.admission-record",
        "schema_version": "1.0",
        "submission_id": submission_id,
        "admitted": not required_failed,
        "blocking": required_failed,
        "checks": checks,
        "executor": runner.name,
        "started_at": started,
        "finished_at": utcnow_iso(),
        "journal_version": _journal_version(),
    }
    stamp = started.replace(":", "").replace("+", "Z")
    write_record(record_dir / "admission" / f"{stamp}.json", payload)
    write_record(record_dir / ADMISSION_RECORD, payload)
    return payload


def load_admission(submission_id: str, *, home: Path | None = None) -> dict[str, Any]:
    """The latest admission record of a submission."""
    return read_record(submission_dir(submission_id, home) / ADMISSION_RECORD)
