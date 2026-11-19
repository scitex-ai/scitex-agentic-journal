"""Review ingestion from any source (design §7a).

The journal does not produce reviews here; it accepts them. A review comes
from an external AI review service, a human researcher, or another user, as
a ``review-report`` plus a ``review-source`` block. The journal:

* validates both against its published schemas;
* checks every claim id and cited graph node against the submission's own
  evidence report (nodes it cannot check are recorded as unverified);
* writes each claim's evidence ``packet_state`` itself and records every
  packet claim the reviewer did not mention as ``not-assessed``;
* refuses reviews from anyone the manifest lists as an author or producer;
* records how the identity was established (``channel``). Statements inside
  the payload are kept as declarations, never as verified facts;
* adds each finding to the submission's local finding ledger under a stable
  key, so re-filing the same review never duplicates findings (design §12.3).

Hosted issue tracking (§12) is designed but not shipped in this version.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from scitex_agentic_journal._bundle import bundle_path, load_intake, validate_bundle
from scitex_agentic_journal._contracts import journal_schema, validate
from scitex_agentic_journal._preprint import load_preprint
from scitex_agentic_journal._records import (
    RecordError,
    record_lock,
    canonical_json,
    read_record,
    sha256_hex,
    submission_dir,
    utcnow_iso,
    write_record,
)

REVIEWERS = "reviewers.json"
FINDINGS = "findings.json"
REVIEWS_DIR = "reviews"
OPEN_SEVERITIES = {"minor", "major", "critical"}
SEVERITY_ORDER = ("none", "minor", "major", "critical")
#: How a reviewer's identity reached the journal. Neither channel below is
#: verified by the journal: the operator CLI carries the operator's word, and
#: self-declared carries none. Verified channels (ORCID login, a
#: journal-issued service key) arrive with an authenticated surface (portal
#: or API) and are not accepted until that surface exists.
CHANNELS = {
    "operator-cli": False,
    "self-declared": False,
}


class ReviewRejectedError(ValueError):
    """The review was not accepted; ``problems`` lists every reason."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("review rejected:\n" + "\n".join(f"- {p}" for p in problems))


def _identity_key(source: dict[str, Any]) -> str:
    ident = source["identity"]
    model = ident.get("model") or {}
    basis = {
        "kind": source["kind"],
        "orcid": ident.get("orcid"),
        "name": _norm(ident.get("name")),
        "service": ident.get("service"),
        "model": [model.get("provider"), model.get("name")],
    }
    return sha256_hex(canonical_json(basis))


def _norm(name: str | None) -> str | None:
    return " ".join(name.casefold().split()) if name else None


def _graph_nodes(report: dict[str, Any]) -> dict[str, set[str] | None]:
    out: dict[str, set[str] | None] = {}
    for claim in report["claims"]:
        graph = claim.get("graph")
        out[claim["claim_id"]] = {n["id"] for n in graph["nodes"]} if graph else None
    return out


def _lineage(intake: dict[str, Any], home: Path | None) -> str:
    seen = {intake["submission_id"]}
    current = intake
    while current.get("supersedes"):
        parent = current["supersedes"]
        if parent in seen:
            break
        seen.add(parent)
        try:
            current = load_intake(parent, home=home)
        except RecordError:
            return parent
    return current["submission_id"]


def _anchor_general(location: str) -> str:
    return "general:" + re.sub(r"\s+", " ", location.strip().lower())


def file_review(
    submission_id: str,
    report: dict[str, Any],
    source: dict[str, Any],
    *,
    channel: str,
    home: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate and record one review; return the ingested-review record (idempotent)."""
    problems = [
        f"report {e}" for e in validate(report, journal_schema("review-report"))
    ]
    problems += [
        f"source {e}" for e in validate(source, journal_schema("review-source"))
    ]
    if channel not in CHANNELS:
        problems.append(f"channel {channel!r} is not one of {sorted(CHANNELS)}")
    if problems:
        raise ReviewRejectedError(problems)
    if report["submission_id"] != submission_id:
        raise ReviewRejectedError(
            [f"report is for {report['submission_id']!r}, not {submission_id!r}"]
        )

    intake = load_intake(submission_id, home=home)
    try:
        load_preprint(submission_id, home=home)
    except RecordError as e:
        raise ReviewRejectedError(
            [
                f"{submission_id} is not a preprint yet; reviews are filed against preprints"
            ]
        ) from e
    validation = validate_bundle(bundle_path(submission_id, home=home))
    if not validation.ok:
        raise RecordError(f"the journal's copy of {submission_id} no longer validates")
    manifest, evidence = validation.manifest, validation.evidence_report
    assert manifest is not None and evidence is not None

    ident = source["identity"]
    author_orcids = {a.get("orcid") for a in manifest["authors"]} | {
        manifest["submitter_orcid"]
    }
    producer_ids = {p["id"] for p in manifest["produced_by"]}
    author_names = {_norm(a["name"]) for a in manifest["authors"]}
    if _norm(ident.get("name")) in author_names:
        problems.append(f"reviewer name {ident['name']!r} is an author of the submission")
    if ident.get("orcid") and ident["orcid"] in author_orcids:
        problems.append(
            f"reviewer ORCID {ident['orcid']} is an author of the submission"
        )
    for name in (ident.get("service"), ident.get("name")):
        if name and name in producer_ids:
            problems.append(
                f"reviewer {name!r} is listed as a producer of the submission"
            )
    if source["declared_independence"]["not_an_author"] is not True:
        problems.append(
            "source declares it is an author; authors cannot review their own work"
        )

    states = {c["claim_id"]: c["state"] for c in evidence["claims"]}
    nodes = _graph_nodes(evidence)
    findings = []
    unverified: dict[str, list[str]] = {}
    for i, f in enumerate(report["claim_findings"]):
        cid = f["claim_id"]
        if cid not in states:
            problems.append(f"claim_findings[{i}]: {cid!r} is not a registered claim")
            continue
        cited = f.get("graph_nodes", [])
        known = nodes[cid]
        if known is None:
            if cited:
                unverified[cid] = sorted(set(unverified.get(cid, [])) | set(cited))
        else:
            missing = sorted(set(cited) - known)
            if missing:
                problems.append(
                    f"claim_findings[{i}]: nodes {missing} are not in claim {cid}'s graph"
                )
        findings.append({**f, "packet_state": states[cid]})
    if problems:
        raise ReviewRejectedError(problems)
    mentioned = {f["claim_id"] for f in findings}
    for cid in states:
        if cid not in mentioned:
            findings.append(
                {
                    "claim_id": cid,
                    "verdict": "not-assessed",
                    "severity": "none",
                    "comment": "not mentioned by the reviewer (recorded by the journal)",
                    "packet_state": states[cid],
                    "journal_filled": True,
                }
            )

    record_dir = submission_dir(submission_id, home)
    with record_lock(record_dir):
        return _record_review(
            record_dir, intake, report, source, channel, findings, unverified,
            home=home, now=now,
        )


def _record_review(
    record_dir: Path,
    intake: dict[str, Any],
    report: dict[str, Any],
    source: dict[str, Any],
    channel: str,
    findings: list[dict[str, Any]],
    unverified: dict[str, list[str]],
    *,
    home: Path | None,
    now: datetime | None,
) -> dict[str, Any]:
    """Assign the pseudonym, write the review and update the ledger (under lock)."""
    submission_id = intake["submission_id"]
    reviewers_path = record_dir / REVIEWERS
    reviewers = (
        read_record(reviewers_path) if reviewers_path.exists() else {"by_identity": {}}
    )
    key = _identity_key(source)
    pseudonym = reviewers["by_identity"].get(key, {}).get("pseudonym")
    if pseudonym is None:
        pseudonym = f"r{len(reviewers['by_identity']) + 1}"
        reviewers["by_identity"][key] = {
            "pseudonym": pseudonym,
            "kind": source["kind"],
            "first_seen": utcnow_iso(now),
        }
        write_record(reviewers_path, reviewers)

    review_id = (
        "rv-" + sha256_hex(canonical_json({"report": report, "identity": key}))[:12]
    )
    review_path = record_dir / REVIEWS_DIR / f"{review_id}.json"
    if review_path.exists():
        return read_record(review_path)

    round_no = report.get("round", 1)
    payload = {
        "schema": "scitex-agentic-journal.ingested-review",
        "schema_version": "1.0",
        "review_id": review_id,
        "submission_id": submission_id,
        "round": round_no,
        "reviewer_pseudonym": pseudonym,
        "source": source,
        "attestation": {
            "channel": channel,
            "verified_by_journal": CHANNELS[channel],
        },
        "recommendation": report["recommendation"],
        "confidence": report.get("confidence"),
        "summary": report["summary"],
        "claim_findings": findings,
        "general_findings": report["general_findings"],
        "unverified_graph_nodes": unverified,
        "received_at": utcnow_iso(now),
    }
    write_record(review_path, payload)
    _update_ledger(
        record_dir, _lineage(intake, home), pseudonym, review_id, round_no, payload
    )
    return payload


def _update_ledger(
    record_dir: Path,
    lineage: str,
    pseudonym: str,
    review_id: str,
    round_no: int,
    review: dict[str, Any],
) -> None:
    path = record_dir / FINDINGS
    ledger = (
        read_record(path) if path.exists() else {"lineage": lineage, "findings": {}}
    )
    entries = []
    for f in review["claim_findings"]:
        if f.get("journal_filled"):
            continue
        nodes = sorted(f.get("graph_nodes", []))
        anchor = f"claim:{f['claim_id']}" + (
            f"/node:{','.join(nodes)}" if nodes else ""
        )
        entries.append((anchor, f))
    for f in review["general_findings"]:
        entries.append((_anchor_general(f["location"]), f))
    touched: set[str] = set()
    for anchor, f in entries:
        # One issue per (reviewer, anchor, dimension): two findings on the
        # same claim about different dimensions stay separate.
        anchor = f"{anchor}#{f.get('dimension') or 'unspecified'}"
        key = sha256_hex(canonical_json([lineage, pseudonym, anchor]))
        item = ledger["findings"].setdefault(
            key,
            {"anchor": anchor, "reviewer_pseudonym": pseudonym, "comments": [],
             "rounds": [], "issue": None},
        )
        if key not in touched:
            # The latest round's findings replace the item's current state.
            item["current"] = []
            touched.add(key)
        entry = {"review_id": review_id, "round": round_no,
                 "severity": f["severity"], "verdict": f.get("verdict"),
                 "comment": f["comment"]}
        item["comments"].append(entry)
        item["current"].append(entry)
        if round_no not in item["rounds"]:
            item["rounds"].append(round_no)
        worst = max((c["severity"] for c in item["current"]), key=SEVERITY_ORDER.index)
        item.update({
            "severity": worst,
            "dimension": f.get("dimension"),
            "verdict": f.get("verdict"),
            "packet_state": f.get("packet_state"),
            "status": "open" if worst in OPEN_SEVERITIES else "noted",
        })
    write_record(path, ledger)


def list_reviews(
    submission_id: str, *, home: Path | None = None
) -> list[dict[str, Any]]:
    folder = submission_dir(submission_id, home) / REVIEWS_DIR
    if not folder.is_dir():
        return []
    return [read_record(p) for p in sorted(folder.glob("rv-*.json"))]


def load_findings(submission_id: str, *, home: Path | None = None) -> dict[str, Any]:
    path = submission_dir(submission_id, home) / FINDINGS
    return read_record(path) if path.exists() else {"findings": {}}
