"""Branch-coverage tests for ``_resolver`` — the fallback paths.

The headline tests in ``test__resolver.py`` cover the happy paths +
no-match + the two unreadable-JSON shapes. This file picks up the
remaining branches the resolver promises but the headline tests do
not exercise:

* env-var resolution in ``_submission_home`` (both branches).
* the iteration filters in ``_find_submission_for_paper`` (non-dir
  entry under submissions/, submission dir without persistent_id.json).
* back-compat top-level reads on ``persistent_id.json`` /
  ``decision.json`` / ``review.json`` (hand-written records without
  the canonical ``record:`` wrap).
* ``_notes_from_rule_hits`` degraded shapes — non-list rule_hits and
  rule_hits items that are not dicts.
* ``last_reviewed_at`` collapses to ``None`` when neither
  ``decided_at`` nor ``written_at_utc`` is a string.

One assertion per test (PA-307 §3 STX-TQ001). No mocks, no
monkeypatch — env-var paths use try/finally save-and-restore around
the smallest possible block.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scitex_agentic_journal._re_review_badge import (
    BADGE_REVIEWER_PREFIX,
    ReReviewBadge,
    resolve_badge_for_paper,
)
from scitex_agentic_journal._re_review_badge._resolver import _submission_home

_PERSISTENT_ID = "scitex-aj-20260613-sample-paper-a1b2c3"
_SUBMISSION_ID = "sub_2026_06_13_abc123"


# ---------------------------------------------------------------------------
# _submission_home — env-var resolution branches
# ---------------------------------------------------------------------------


def test_submission_home_uses_explicit_env_var_when_set(tmp_path: Path) -> None:
    """``SCITEX_AGENTIC_JOURNAL_HOME`` wins over the default home."""
    # Arrange
    expected = (tmp_path / "aj-home").resolve()
    expected.mkdir()
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(expected)
    try:
        # Act
        resolved = _submission_home()
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert resolved == expected


def test_submission_home_falls_back_to_default_when_env_var_missing() -> None:
    """No env var → ``~/.scitex/agentic-journal`` (the canonical default)."""
    # Arrange
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
    try:
        # Act
        resolved = _submission_home()
    finally:
        if original is not None:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    expected = Path.home() / ".scitex" / "agentic-journal"
    # Assert
    assert resolved == expected


# ---------------------------------------------------------------------------
# _find_submission_for_paper — iteration filters
# ---------------------------------------------------------------------------


def test_resolver_skips_non_directory_entry_under_submissions(tmp_path: Path) -> None:
    """A stray file under ``submissions/`` MUST not crash the scan;
    the iterator just skips it.
    """
    # Arrange
    submissions = tmp_path / "submissions"
    submissions.mkdir()
    (submissions / "stray.txt").write_text("not a dir", encoding="utf-8")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert badge is None


def test_resolver_skips_submission_directory_without_persistent_id_json(
    tmp_path: Path,
) -> None:
    """A half-materialised submission (gate1.json only, no
    persistent_id.json) is skipped by the scan, not raised on.
    """
    # Arrange
    sub_dir = tmp_path / "submissions" / "sub_2026_06_13_halfdone"
    sub_dir.mkdir(parents=True)
    (sub_dir / "gate1.json").write_text("{}", encoding="utf-8")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert badge is None


# ---------------------------------------------------------------------------
# Top-level back-compat reads — hand-written records without ``record:`` wrap
# ---------------------------------------------------------------------------


def _write_flat_persistent_id_json(
    home: Path, submission_id: str, persistent_id: str
) -> None:
    """Hand-write a ``persistent_id.json`` with ``persistent_id`` at top
    level (pre-M4-persister shape — back-compat path).
    """
    sub_dir = home / "submissions" / submission_id
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "persistent_id.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "persistent_id": persistent_id,
                "backend": "internal",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_flat_decision_json(home: Path, submission_id: str, verdict: str) -> None:
    """Hand-write a ``decision.json`` with ``verdict`` at top level
    (pre-M3-persister shape — back-compat path)."""
    sub_dir = home / "submissions" / submission_id
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "decision.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "verdict": verdict,
                "decided_at": "2026-06-13T12:30:00+00:00",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_flat_review_json(home: Path, submission_id: str, adapter: str) -> None:
    """Hand-write a ``review.json`` with ``adapter`` at top level."""
    sub_dir = home / "submissions" / submission_id
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "review.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "adapter": adapter,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_resolver_reads_persistent_id_at_top_level_for_back_compat(
    tmp_path: Path,
) -> None:
    """A persistent_id.json without the ``record:`` wrap (hand-written
    legacy / mock) MUST still match by id.
    """
    # Arrange
    _write_flat_persistent_id_json(tmp_path, _SUBMISSION_ID, _PERSISTENT_ID)
    _write_flat_decision_json(tmp_path, _SUBMISSION_ID, "accept")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert isinstance(badge, ReReviewBadge)


def test_resolver_reads_verdict_at_top_level_for_back_compat(
    tmp_path: Path,
) -> None:
    """A decision.json without the ``record:`` wrap MUST still resolve
    the verdict to a status.
    """
    # Arrange
    _write_flat_persistent_id_json(tmp_path, _SUBMISSION_ID, _PERSISTENT_ID)
    _write_flat_decision_json(tmp_path, _SUBMISSION_ID, "revise")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert badge is not None and badge.status == "concerns"


def test_resolver_reads_adapter_at_top_level_for_back_compat(
    tmp_path: Path,
) -> None:
    """A review.json without the ``record:`` wrap MUST still surface the
    adapter id as the prefixed reviewer.
    """
    # Arrange
    _write_flat_persistent_id_json(tmp_path, _SUBMISSION_ID, _PERSISTENT_ID)
    _write_flat_decision_json(tmp_path, _SUBMISSION_ID, "accept")
    _write_flat_review_json(tmp_path, _SUBMISSION_ID, "qwen-7b-instruct")
    expected = f"{BADGE_REVIEWER_PREFIX}:qwen-7b-instruct"
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert badge is not None and badge.reviewer == expected


# ---------------------------------------------------------------------------
# _notes_from_rule_hits — degraded payload shapes
# ---------------------------------------------------------------------------


def _write_decision_with_rule_hits(
    home: Path, submission_id: str, rule_hits: object
) -> None:
    """Write a decision.json whose ``record.rule_hits`` is the given
    raw object — used to drive the rule_hits-shape branches."""
    sub_dir = home / "submissions" / submission_id
    sub_dir.mkdir(parents=True, exist_ok=True)
    (sub_dir / "decision.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "content_hash": "sha256:" + "b" * 64,
                "written_at_utc": "2026-06-13T12:30:01+00:00",
                "record": {
                    "submission_id": submission_id,
                    "verdict": "reject",
                    "rules_version": "v1",
                    "rule_hits": rule_hits,
                    "decided_at": "2026-06-13T12:30:00+00:00",
                    "review_content_hash": "sha256:" + "a" * 64,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_resolver_notes_is_none_when_rule_hits_is_not_a_list(
    tmp_path: Path,
) -> None:
    """A malformed decision record with ``rule_hits`` as a non-list
    (here a dict) must not crash; notes collapses to ``None``."""
    # Arrange
    _write_flat_persistent_id_json(tmp_path, _SUBMISSION_ID, _PERSISTENT_ID)
    _write_decision_with_rule_hits(
        tmp_path, _SUBMISSION_ID, {"unexpected": "shape"}
    )
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert badge is not None and badge.notes is None


def test_resolver_skips_non_dict_rule_hit_entries_when_synthesising_notes(
    tmp_path: Path,
) -> None:
    """A ``rule_hits`` list containing non-dict junk + one valid failing
    hit must surface the valid hit's message; the junk is skipped."""
    # Arrange
    _write_flat_persistent_id_json(tmp_path, _SUBMISSION_ID, _PERSISTENT_ID)
    _write_decision_with_rule_hits(
        tmp_path,
        _SUBMISSION_ID,
        [
            "this-is-a-string-not-a-dict",
            42,
            {
                "rule_id": "methodology_major",
                "version": "v1",
                "passed": False,
                "message": "methodology.max_severity='major'; revises.",
            },
        ],
    )
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert (
        badge is not None
        and badge.notes == "methodology.max_severity='major'; revises."
    )


# ---------------------------------------------------------------------------
# last_reviewed_at — non-string / missing fallback
# ---------------------------------------------------------------------------


def test_resolver_last_reviewed_at_is_none_when_decided_at_and_written_at_are_missing(
    tmp_path: Path,
) -> None:
    """Neither the decision record nor the envelope carries a usable
    timestamp ⇒ ``last_reviewed_at`` MUST be ``None`` (not a stale
    placeholder, not a crash)."""
    # Arrange
    _write_flat_persistent_id_json(tmp_path, _SUBMISSION_ID, _PERSISTENT_ID)
    sub_dir = tmp_path / "submissions" / _SUBMISSION_ID
    (sub_dir / "decision.json").write_text(
        json.dumps(
            {
                "submission_id": _SUBMISSION_ID,
                # No written_at_utc.
                "record": {
                    "submission_id": _SUBMISSION_ID,
                    "verdict": "accept",
                    # No decided_at.
                    "rules_version": "v1",
                    "rule_hits": [],
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert badge is not None and badge.last_reviewed_at is None


def test_resolver_last_reviewed_at_is_none_when_timestamp_fields_are_non_string(
    tmp_path: Path,
) -> None:
    """If a future writer pushes a number (Unix epoch) into either
    timestamp field by accident, the badge MUST refuse to surface a
    non-string — live-paper's SPA expects ISO-8601 string or null."""
    # Arrange
    _write_flat_persistent_id_json(tmp_path, _SUBMISSION_ID, _PERSISTENT_ID)
    sub_dir = tmp_path / "submissions" / _SUBMISSION_ID
    (sub_dir / "decision.json").write_text(
        json.dumps(
            {
                "submission_id": _SUBMISSION_ID,
                "written_at_utc": 1718280600,  # non-string
                "record": {
                    "submission_id": _SUBMISSION_ID,
                    "verdict": "accept",
                    "decided_at": 1718280600,  # non-string
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=tmp_path)
    # Assert
    assert badge is not None and badge.last_reviewed_at is None
