"""Preprint snapshot of an admitted submission (design §13.2).

An admitted submission becomes a preprint: an immutable record that pins the
repository commit, the bundle and its contract files by hash, and gets an
internal persistent ID at once. A DOI is registered separately and later
through an ``IdMinter`` adapter; until then ``doi`` is null and
``doi_status`` is ``unregistered``. Publication never waits on the DOI.

A preprint is not peer reviewed, and its record says so.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scitex_agentic_journal._admission import load_admission
from scitex_agentic_journal._bundle import bundle_path, load_intake, validate_bundle
from scitex_agentic_journal._publish._internal import InternalIdMinter
from scitex_agentic_journal._publish._types import MintInput
from scitex_agentic_journal._records import (
    RecordError,
    canonical_json,
    file_sha256,
    read_record,
    sha256_hex,
    submission_dir,
    utcnow_iso,
    write_record,
)

PREPRINT_RECORD = "preprint.json"
_VERSION_RE = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+$")
NOTICE = (
    "Preprint: admitted by the journal's automated checks; not peer reviewed. "
    "Computational verification of registered claims is not a judgement of "
    "scientific validity."
)


class PreprintRefusedError(RuntimeError):
    """The submission is not admitted, or the preprint already exists differently."""


def create_preprint(
    submission_id: str,
    version: str,
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Snapshot an admitted submission as preprint ``version``; idempotent."""
    if not _VERSION_RE.match(version):
        raise PreprintRefusedError(
            f"version {version!r} is not MAJOR.MINOR.PATCH (optionally v-prefixed)"
        )
    record_dir = submission_dir(submission_id, home)
    path = record_dir / PREPRINT_RECORD
    if path.exists():
        existing = read_record(path)
        if existing.get("preprint_version") != version:
            raise PreprintRefusedError(
                f"{submission_id} is already preprint {existing.get('preprint_version')}; "
                "a new version is a new submission linked by 'supersedes'"
            )
        return existing

    intake = load_intake(submission_id, home=home)
    try:
        admission = load_admission(submission_id, home=home)
    except RecordError as e:
        raise PreprintRefusedError(
            f"{submission_id} has no admission record; run admission first"
        ) from e
    if admission.get("admitted") is not True:
        raise PreprintRefusedError(
            f"{submission_id} is not admitted; blocking checks: {admission.get('blocking')}"
        )
    bundle = bundle_path(submission_id, home=home)
    validation = validate_bundle(bundle)
    if not validation.ok or validation.submission_id != submission_id:
        raise RecordError(f"the journal's copy of {submission_id} no longer validates")
    manifest = validation.manifest
    assert manifest is not None
    created = now or datetime.now(timezone.utc)
    corresponding = next(
        (
            a.get("orcid")
            for a in manifest["authors"]
            if a.get("corresponding") and a.get("orcid")
        ),
        manifest["submitter_orcid"],
    )
    pid = InternalIdMinter().mint(
        MintInput(
            submission_id=submission_id,
            title=manifest["title"],
            corresponding_author_orcid=corresponding,
            decided_at=created,
        )
    )
    payload = {
        "schema": "scitex-agentic-journal.preprint-record",
        "schema_version": "1.0",
        "submission_id": submission_id,
        "preprint_version": version,
        "internal_id": pid.persistent_id,
        "citation": pid.citation_suffix(),
        "doi": None,
        "doi_status": "unregistered",
        "peer_reviewed": False,
        "notice": NOTICE,
        "title": manifest["title"],
        "authors": manifest["authors"],
        "licence": manifest["licence"],
        "repository": manifest["repository"],
        "supersedes": manifest.get("supersedes"),
        "main_claims": manifest["main_claims"],
        "hashes": {
            "manifest_sha256": intake["manifest_sha256"],
            "evidence_report_sha256": file_sha256(bundle / "evidence-report.json"),
            "review_packet_sha256": file_sha256(
                bundle / "review-packet" / "review.json"
            ),
            "admission_record_sha256": sha256_hex(canonical_json(admission)),
        },
        "live_paper": {
            "evidence_report_schema_version": validation.evidence_report[
                "schema_version"
            ],
            "review_packet_schema_version": validation.review_packet["schema_version"],
            "bundle_dir": str(bundle),
        },
        "created_at": utcnow_iso(created),
    }
    write_record(path, payload)
    return payload


def load_preprint(submission_id: str, *, home: Path | None = None) -> dict[str, Any]:
    return read_record(submission_dir(submission_id, home) / PREPRINT_RECORD)
