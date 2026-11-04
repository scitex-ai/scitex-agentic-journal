"""Public Django-free archive reads backed by the existing persistence reader."""

from pathlib import Path
from typing import Any


def get_submission(submission_id: str, *, home: Path | None = None) -> dict[str, Any]:
    """Return the existing detail payload; no checks, writes or network calls."""
    from scitex_agentic_journal._django._leaf import get_submission_summary
    from scitex_agentic_journal._submit._ids import validate_submission_id

    validate_submission_id(submission_id)
    summary = get_submission_summary(submission_id, home=home)
    if summary is None:
        return {"submission_id": submission_id, "found": False}
    return {**summary, "found": True, "placeholder": False}
