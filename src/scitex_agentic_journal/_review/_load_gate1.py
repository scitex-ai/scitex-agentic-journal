"""Load a persisted Gate-1 record into :class:`SubmissionInputs`.

The M2 reviewer agent consumes the M1 hand-off shape (``gate1.json``
written by :mod:`scitex_agentic_journal._submit._persist`). This
module is the single boundary that turns that on-disk JSON into the
typed inputs `ReviewRunner` expects.

Kept separate from `_submit._persist` so the dependency direction
stays: ``_submit`` knows nothing about review. The wiring lives in
the consumer module, not the producer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scitex_agentic_journal._review._types import SubmissionInputs


class ReviewLoadError(Exception):
    """Persisted Gate-1 record is missing, unparseable, or shape-broken."""


def _submission_home() -> Path:
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def load_submission_inputs(
    submission_id: str,
    *,
    home: Path | None = None,
) -> SubmissionInputs:
    """Read ``submissions/<id>/gate1.json`` and build :class:`SubmissionInputs`.

    Parameters
    ----------
    submission_id :
        The ``sub_YYYY_MM_DD_<hex>`` token printed by
        ``scitex-agentic-journal submit``.
    home :
        Override the submission-home root.

    Raises
    ------
    ReviewLoadError
        - submission directory does not exist.
        - ``gate1.json`` is missing.
        - JSON is malformed or lacks the expected keys.
    """
    root = home if home is not None else _submission_home()
    submission_dir = root / "submissions" / submission_id
    if not submission_dir.is_dir():
        raise ReviewLoadError(
            f"no persisted submission at {submission_dir} — run "
            "`scitex-agentic-journal submit` first."
        )
    gate1_path = submission_dir / "gate1.json"
    if not gate1_path.is_file():
        raise ReviewLoadError(
            f"submission {submission_id} is missing its gate1.json "
            f"({gate1_path}) — re-run `scitex-agentic-journal submit`."
        )
    try:
        payload = json.loads(gate1_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReviewLoadError(
            f"gate1.json at {gate1_path} is not valid JSON: {e}"
        ) from e
    if not isinstance(payload, dict):
        raise ReviewLoadError(
            f"gate1.json at {gate1_path} root is not a JSON object."
        )
    submission_block = payload.get("submission")
    clew = payload.get("clew_verification")
    if not isinstance(submission_block, dict) or not isinstance(clew, dict):
        raise ReviewLoadError(
            f"gate1.json at {gate1_path} is missing 'submission' or "
            "'clew_verification' blocks — it was not produced by the "
            "M1 orchestrator."
        )
    required_submission_keys = ("bundle_dir", "orcid_id", "code_repo_url")
    for key in required_submission_keys:
        if key not in submission_block:
            raise ReviewLoadError(
                f"gate1.json submission block missing required key {key!r}."
            )
    bundle_dir = Path(submission_block["bundle_dir"])
    clew_project_dir = Path(
        submission_block.get("clew_project_dir") or bundle_dir
    )
    return SubmissionInputs(
        submission_id=submission_id,
        manuscript_dir=bundle_dir,
        claims_path=clew_project_dir / "claims.json",
        dag_dir=clew_project_dir,
        code_repo_url=submission_block["code_repo_url"],
        corresponding_author_orcid=submission_block["orcid_id"],
    )
