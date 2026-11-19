"""Accept a valid bundle: snapshot it into the journal home and record intake.

The submission id is ``aj-`` plus the first 16 hex digits of the SHA-256 of
the canonical manifest. Since the manifest lists every file's hash, the id
names the exact content: resubmitting identical bytes is idempotent, and any
changed byte is a new submission (a revision links back via ``supersedes``).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scitex_agentic_journal._bundle._validate import BundleValidation, validate_bundle
from scitex_agentic_journal._records import (
    RecordError,
    read_record,
    submission_dir,
    utcnow_iso,
    write_record,
)

INTAKE_RECORD = "intake.json"
BUNDLE_COPY = "bundle"


class BundleInvalidError(ValueError):
    """The bundle failed validation; ``validation.findings`` says why."""

    def __init__(self, validation: BundleValidation) -> None:
        self.validation = validation
        lines = [f"- [{f.code}] {f.message}" for f in validation.findings]
        super().__init__(
            f"bundle {validation.bundle_dir} is invalid "
            f"({len(lines)} finding(s)):\n" + "\n".join(lines)
        )


@dataclass(frozen=True)
class IntakeReceipt:
    submission_id: str
    record_dir: Path
    created: bool


def submit_bundle(
    bundle_dir: Path | str,
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> IntakeReceipt:
    """Validate ``bundle_dir`` and record it; raise :class:`BundleInvalidError` if invalid."""
    validation = validate_bundle(bundle_dir)
    if not validation.ok:
        raise BundleInvalidError(validation)
    assert validation.manifest is not None and validation.submission_id is not None
    sid = validation.submission_id
    record_dir = submission_dir(sid, home)
    intake_path = record_dir / INTAKE_RECORD
    if intake_path.exists():
        existing = read_record(intake_path)
        if existing.get("manifest_sha256") != validation.manifest_sha256:
            raise RecordError(
                f"{intake_path} belongs to a different manifest "
                f"({existing.get('manifest_sha256')}); refusing to overwrite"
            )
        return IntakeReceipt(sid, record_dir, created=False)

    record_dir.mkdir(parents=True, exist_ok=True)
    staging = record_dir / f".{BUNDLE_COPY}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(validation.bundle_dir, staging, symlinks=True)
    copied = validate_bundle(staging)
    if not copied.ok or copied.manifest_sha256 != validation.manifest_sha256:
        shutil.rmtree(staging)
        raise RecordError("the bundle changed while it was being copied; resubmit it")
    final = record_dir / BUNDLE_COPY
    if final.exists():
        shutil.rmtree(final)
    staging.rename(final)

    manifest = validation.manifest
    write_record(
        intake_path,
        {
            "schema": "scitex-agentic-journal.intake-record",
            "schema_version": "1.0",
            "submission_id": sid,
            "manifest_sha256": validation.manifest_sha256,
            "received_at": utcnow_iso(now),
            "source_path": str(validation.bundle_dir),
            "title": manifest["title"],
            "submitter_orcid": manifest["submitter_orcid"],
            "repository": manifest["repository"],
            "main_claims": manifest["main_claims"],
            "supersedes": manifest.get("supersedes"),
            "evidence_report": {
                "schema_version": validation.evidence_report["schema_version"],
                "provider": validation.evidence_report["provider"],
                "claims": len(validation.evidence_report["claims"]),
            },
        },
    )
    return IntakeReceipt(sid, record_dir, created=True)


def load_intake(submission_id: str, *, home: Path | None = None) -> dict:
    """Read the intake record of a submission."""
    return read_record(submission_dir(submission_id, home) / INTAKE_RECORD)


def bundle_path(submission_id: str, *, home: Path | None = None) -> Path:
    """Path of the journal's immutable copy of the submitted bundle."""
    return submission_dir(submission_id, home) / BUNDLE_COPY
