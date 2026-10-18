"""Persist a passing :class:`Gate1Verdict` so M2/M3 can retrieve it.

Generates a sortable, opaque submission id and writes the verdict as
JSON under ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/`` (default
``~/.scitex/agentic-journal/submissions/<id>/``). The persisted
record is the only handoff contract between Gate-1 (this PR) and the
M2 reviewer agent (#6) — keep it stable.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from scitex_agentic_journal._submit._orchestrate import Gate1Verdict

GATE1_RECORD_FILENAME = "gate1.json"
"""On-disk filename for the persisted Gate-1 record."""


@dataclass(frozen=True)
class PersistedSubmission:
    """The on-disk artefact written by :func:`persist_verdict`.

    Attributes
    ----------
    submission_id :
        ``sub_YYYY_MM_DD_<6-hex>``. Sortable by mint time without
        leaking the exact second across submissions (the 6 hex
        characters give 16 million collision-free slots per day).
    record_path :
        Absolute path of the JSON file the verdict was written to.
    record_dir :
        Containing directory — also the conventional drop site for
        attachments the reviewer agent may produce.
    """

    submission_id: str
    record_path: Path
    record_dir: Path


def _submission_home() -> Path:
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _mint_submission_id(now: datetime | None = None) -> str:
    moment = now if now is not None else datetime.now(timezone.utc)
    date_part = moment.strftime("%Y_%m_%d")
    rand_part = secrets.token_hex(3)  # 6 hex chars
    return f"sub_{date_part}_{rand_part}"


def _verdict_to_jsonable(verdict: Gate1Verdict) -> dict:
    submission = verdict.submission
    return {
        "submission": {
            "bundle_dir": str(submission.bundle_dir),
            "orcid_id": submission.orcid_id,
            "code_repo_url": submission.code_repo_url,
            "clew_project_dir": str(submission.clew_project_dir),
        },
        "orcid_record": asdict(verdict.orcid_record),
        "code_repo": {
            "head_commit": verdict.code_repo_head_commit,
            "head_subject": verdict.code_repo_head_subject,
        },
        "clew_verification": {
            "project_dir": str(verdict.clew_verification.project_dir),
            "green_claims": list(verdict.clew_verification.green_claims),
            "red_claims": list(verdict.clew_verification.red_claims),
            "total_claims": verdict.clew_verification.total_claims,
        },
    }


def persist_verdict(
    verdict: Gate1Verdict,
    *,
    home: Path | None = None,
    now: datetime | None = None,
) -> PersistedSubmission:
    """Mint a submission id, write the verdict as JSON, return the receipt.

    Parameters
    ----------
    verdict :
        The :class:`Gate1Verdict` produced by ``run_gate1``.
    home :
        Override the submission-home root. When ``None`` we honour
        ``$SCITEX_AGENTIC_JOURNAL_HOME`` then fall back to
        ``~/.scitex/agentic-journal/``. Tests inject ``tmp_path``.
    now :
        Override the mint timestamp. Tests inject a deterministic
        value; production code passes ``None``.

    Returns
    -------
    PersistedSubmission
        Submission id + paths to the written record.
    """
    root = home if home is not None else _submission_home()
    submission_id = _mint_submission_id(now=now)
    record_dir = root / "submissions" / submission_id
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_dir / GATE1_RECORD_FILENAME
    payload = {
        "submission_id": submission_id,
        "gate": "gate1",
        "verdict": "pass",
        "minted_at_utc": (now or datetime.now(timezone.utc)).isoformat(),
        **_verdict_to_jsonable(verdict),
    }
    record_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PersistedSubmission(
        submission_id=submission_id,
        record_path=record_path,
        record_dir=record_dir,
    )
