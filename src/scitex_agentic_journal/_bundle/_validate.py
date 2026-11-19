"""Validate a contract-based submission bundle (design §3).

A bundle is a directory::

    submission.json         journal manifest (schema: submission 1.0)
    manuscript/             at least one file (PDF and/or LaTeX)
    evidence-report.json    scitex-live-paper.evidence-report 1.x
    review-packet/
        review.json         scitex-live-paper.review-packet 1.x
        review.txt          its text rendering
    references.bib

Validation never stops at the first problem: it collects every finding so
an author fixes the bundle in one pass. A bundle is valid only when there
are no findings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scitex_agentic_journal._contracts import (
    ContractError,
    journal_schema,
    validate,
    vendored_entry,
    vendored_schema,
)
from scitex_agentic_journal._records import canonical_json, file_sha256, sha256_hex

MANIFEST = "submission.json"
EVIDENCE_REPORT = "evidence-report.json"
PACKET_JSON = "review-packet/review.json"
PACKET_TXT = "review-packet/review.txt"
BIBLIOGRAPHY = "references.bib"
MANUSCRIPT_DIR = "manuscript"

LIVE_PAPER = "scitex-live-paper"
PACKET_SCHEMA_FILE = "review-packet.schema.json"
REPORT_SCHEMA_FILE = "evidence-report.schema.json"
SUPPORTED = "supported"


@dataclass(frozen=True)
class Finding:
    """One problem with a bundle; ``code`` is stable for programmatic use."""

    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "path": self.path}


@dataclass
class BundleValidation:
    """Outcome of :func:`validate_bundle`."""

    bundle_dir: Path
    findings: list[Finding] = field(default_factory=list)
    manifest: dict[str, Any] | None = None
    evidence_report: dict[str, Any] | None = None
    review_packet: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def manifest_sha256(self) -> str | None:
        if self.manifest is None:
            return None
        return sha256_hex(canonical_json(self.manifest))

    @property
    def submission_id(self) -> str | None:
        digest = self.manifest_sha256
        return None if digest is None else f"aj-{digest[:16]}"

    def add(self, code: str, message: str, path: str | None = None) -> None:
        self.findings.append(Finding(code, message, path))


def _load_json(result: BundleValidation, rel: str) -> Any:
    path = result.bundle_dir / rel
    if not path.is_file():
        result.add("missing-file", f"required file {rel} is missing", rel)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        result.add("invalid-json", f"{rel} is not valid JSON: {e}", rel)
        return None


def _check_files(result: BundleValidation, manifest: dict[str, Any]) -> None:
    root = result.bundle_dir
    listed: dict[str, str] = manifest.get("files", {})
    on_disk: set[str] = set()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            result.add(
                "symlink", f"{rel} is a symlink; bundles must hold real files", rel
            )
            continue
        if path.is_file() and rel != MANIFEST:
            on_disk.add(rel)
    for rel in sorted(on_disk - set(listed)):
        result.add("unlisted-file", f"{rel} is in the bundle but not in files{{}}", rel)
    for rel in sorted(set(listed) - on_disk):
        result.add("listed-file-missing", f"{rel} is listed but not present", rel)
    for rel in sorted(on_disk & set(listed)):
        expected = listed[rel].removeprefix("sha256:")
        actual = file_sha256(root / rel)
        if actual != expected:
            result.add(
                "hash-mismatch",
                f"{rel} sha256 {actual} does not match the manifest {expected}",
                rel,
            )
    if not any(rel.startswith(f"{MANUSCRIPT_DIR}/") for rel in on_disk):
        result.add("missing-manuscript", "manuscript/ holds no file", MANUSCRIPT_DIR)
    for rel in (PACKET_TXT, BIBLIOGRAPHY):
        if rel not in on_disk:
            result.add("missing-file", f"required file {rel} is missing", rel)


def _check_policies(result: BundleValidation, manifest: dict[str, Any]) -> None:
    for i, dataset in enumerate(manifest.get("data", [])):
        if dataset.get("access") != "public":
            result.add(
                "data-not-public",
                f"data[{i}] {dataset.get('name')!r} has access "
                f"{dataset.get('access')!r}; v1 accepts public data only",
                MANIFEST,
            )
    conversion = manifest.get("conversion")
    if conversion and conversion.get("author_confirmed") is not True:
        result.add(
            "conversion-unconfirmed",
            "the project was converted by an agent but the author has not "
            "confirmed the conversion",
            MANIFEST,
        )


def _check_report(result: BundleValidation, report: dict[str, Any]) -> None:
    try:
        schema = vendored_schema(LIVE_PAPER, REPORT_SCHEMA_FILE)
    except ContractError as e:
        result.add("contract-unavailable", str(e), EVIDENCE_REPORT)
        return
    for err in validate(report, schema):
        result.add("evidence-report-schema", err, EVIDENCE_REPORT)
    ids = [c.get("claim_id") for c in report.get("claims", []) if isinstance(c, dict)]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        result.add(
            "duplicate-claim-id", f"evidence report repeats {dupes}", EVIDENCE_REPORT
        )


def _packet_entries(packet: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for bucket in ("needs_inspection", "supported"):
        for entry in packet.get(bucket) or []:
            if isinstance(entry, dict):
                out.append((bucket, entry))
    return out


def _check_packet(result: BundleValidation, packet: dict[str, Any]) -> None:
    try:
        vendored_entry(LIVE_PAPER, PACKET_SCHEMA_FILE)
        schema = vendored_schema(LIVE_PAPER, PACKET_SCHEMA_FILE)
    except ContractError:
        schema = None
    if schema is not None:
        for err in validate(packet, schema):
            result.add("review-packet-schema", err, PACKET_JSON)
        return
    # No vendored packet schema: check the documented required fields.
    if packet.get("schema") != "scitex-live-paper.review-packet":
        result.add(
            "review-packet-schema",
            "schema is not scitex-live-paper.review-packet",
            PACKET_JSON,
        )
    version = str(packet.get("schema_version", ""))
    if not version.startswith("1."):
        result.add(
            "review-packet-schema",
            f"schema_version {version!r} is not 1.x",
            PACKET_JSON,
        )
    for key in ("needs_inspection", "supported"):
        if not isinstance(packet.get(key), list):
            result.add("review-packet-schema", f"{key} must be a list", PACKET_JSON)


def _check_consistency(
    result: BundleValidation,
    manifest: dict[str, Any],
    report: dict[str, Any],
    packet: dict[str, Any],
) -> None:
    states = {
        c["claim_id"]: c.get("state")
        for c in report.get("claims", [])
        if isinstance(c, dict) and "claim_id" in c
    }
    entries = _packet_entries(packet)
    packet_ids = [e.get("claim_id") for _, e in entries]
    if sorted(packet_ids) != sorted(states):
        result.add(
            "packet-report-claims",
            f"packet claims {sorted(map(str, packet_ids))} differ from the "
            f"evidence report's {sorted(states)}",
            PACKET_JSON,
        )
    for bucket, entry in entries:
        cid = entry.get("claim_id")
        if cid not in states:
            continue
        if entry.get("state") != states[cid]:
            result.add(
                "packet-report-state",
                f"claim {cid}: packet state {entry.get('state')!r} != report "
                f"state {states[cid]!r}",
                PACKET_JSON,
            )
        should_inspect = states[cid] != SUPPORTED
        if bool(entry.get("needs_inspection")) != should_inspect or (
            (bucket == "needs_inspection") != should_inspect
        ):
            result.add(
                "packet-inspection-flag",
                f"claim {cid}: needs_inspection must be {should_inspect} for "
                f"state {states[cid]!r}",
                PACKET_JSON,
            )
    for cid in manifest.get("main_claims", []):
        if cid not in states:
            result.add(
                "main-claim-unknown",
                f"main claim {cid!r} is not a registered claim in the evidence report",
                MANIFEST,
            )


def validate_bundle(bundle_dir: Path | str) -> BundleValidation:
    """Validate a bundle directory and return every finding."""
    root = Path(bundle_dir).expanduser().resolve()
    result = BundleValidation(bundle_dir=root)
    if not root.is_dir():
        result.add("not-a-directory", f"bundle path is not a directory: {root}")
        return result
    manifest = _load_json(result, MANIFEST)
    if isinstance(manifest, dict):
        errors = validate(manifest, journal_schema("submission"))
        for err in errors:
            result.add("manifest-schema", err, MANIFEST)
        if not errors:
            result.manifest = manifest
            _check_files(result, manifest)
            _check_policies(result, manifest)
    elif manifest is not None:
        result.add("manifest-schema", "submission.json must be a JSON object", MANIFEST)
    report = _load_json(result, EVIDENCE_REPORT)
    if isinstance(report, dict):
        result.evidence_report = report
        _check_report(result, report)
    packet = _load_json(result, PACKET_JSON)
    if isinstance(packet, dict):
        result.review_packet = packet
        _check_packet(result, packet)
    if (
        result.manifest is not None
        and isinstance(report, dict)
        and isinstance(packet, dict)
    ):
        _check_consistency(result, result.manifest, report, packet)
    return result
