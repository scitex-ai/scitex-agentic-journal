"""Load a persisted M2 review.json into a typed :class:`ReviewRecord`.

The M3 decision engine consumes the M2 hand-off shape (``review.json``
written by :mod:`scitex_agentic_journal._review._persist`). This
module is the single boundary that turns that on-disk JSON back into
the typed :class:`ReviewRecord` the engine expects.

Kept separate from ``_review._persist`` so the dependency direction
stays: ``_review`` knows nothing about decide. The wiring lives in
the consumer module, not the producer.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from scitex_agentic_journal._review._rubric import (
    ARA_RUBRIC_VERSION,
    Severity,
)
from scitex_agentic_journal._review._types import (
    ClaimVerifyReport,
    Criticism,
    MethodologyReport,
    NoveltyReport,
    ReproducibilityReport,
    ReviewRecord,
)

REVIEW_RECORD_FILENAME = "review.json"
"""On-disk filename for the persisted review record (mirrors M2)."""


class DecisionLoadError(Exception):
    """Persisted review record is missing, unparseable, or shape-broken."""


def _submission_home() -> Path:
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def load_review_record(
    submission_id: str,
    *,
    home: Path | None = None,
) -> ReviewRecord:
    """Read ``submissions/<id>/review.json`` into a :class:`ReviewRecord`.

    Parameters
    ----------
    submission_id :
        The ``sub_YYYY_MM_DD_<hex>`` token printed by ``submit``.
    home :
        Override the submission-home root.

    Raises
    ------
    DecisionLoadError
        - submission directory does not exist.
        - ``review.json`` is missing.
        - JSON is malformed or lacks the expected ``record`` block.
    """
    root = home if home is not None else _submission_home()
    submission_dir = root / "submissions" / submission_id
    if not submission_dir.is_dir():
        raise DecisionLoadError(
            f"no persisted submission at {submission_dir} — run "
            "`scitex-agentic-journal submit` and `review` first."
        )
    review_path = submission_dir / REVIEW_RECORD_FILENAME
    if not review_path.is_file():
        raise DecisionLoadError(
            f"submission {submission_id} is missing its review.json "
            f"({review_path}) — re-run `scitex-agentic-journal review`."
        )
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise DecisionLoadError(
            f"review.json at {review_path} is not valid JSON: {e}"
        ) from e
    if not isinstance(payload, dict):
        raise DecisionLoadError(
            f"review.json at {review_path} root is not a JSON object."
        )
    record_block = payload.get("record")
    if not isinstance(record_block, dict):
        raise DecisionLoadError(
            f"review.json at {review_path} is missing the 'record' block — "
            "it was not produced by the M2 review persister."
        )
    try:
        return _record_from_jsonable(record_block)
    except (KeyError, TypeError, ValueError) as e:
        raise DecisionLoadError(
            f"review.json at {review_path} has unexpected shape: {e}"
        ) from e


def _record_from_jsonable(block: dict) -> ReviewRecord:
    """Rebuild a typed :class:`ReviewRecord` from its JSON form."""
    reproducibility_block = block["reproducibility"]
    claim_verify_block = block["claim_verify"]
    novelty_block = block["novelty"]
    methodology_block = block["methodology"]
    return ReviewRecord(
        submission_id=str(block["submission_id"]),
        adapter=str(block["adapter"]),
        adapter_version=str(block["adapter_version"]),
        prompts_version=str(block["prompts_version"]),
        rubric_version=str(block.get("rubric_version", ARA_RUBRIC_VERSION)),
        reproducibility=ReproducibilityReport(
            passed=bool(reproducibility_block["passed"]),
            sandbox_image=str(reproducibility_block["sandbox_image"]),
            notes=str(reproducibility_block.get("notes", "")),
        ),
        claim_verify=ClaimVerifyReport(
            green_claim_ids=tuple(claim_verify_block.get("green_claim_ids", ())),
            yellow_claim_ids=tuple(
                claim_verify_block.get("yellow_claim_ids", ())
            ),
            red_claim_ids=tuple(claim_verify_block.get("red_claim_ids", ())),
        ),
        novelty=NoveltyReport(
            overlap_score=float(novelty_block["overlap_score"]),
            nearest_neighbour_dois=tuple(
                novelty_block.get("nearest_neighbour_dois", ())
            ),
        ),
        methodology=MethodologyReport(
            criticisms=tuple(
                Criticism(
                    severity=Severity(c["severity"]),
                    section=str(c["section"]),
                    note=str(c["note"]),
                )
                for c in methodology_block.get("criticisms", ())
            ),
        ),
        started_at=datetime.fromisoformat(block["started_at"]),
        finished_at=datetime.fromisoformat(block["finished_at"]),
    )
