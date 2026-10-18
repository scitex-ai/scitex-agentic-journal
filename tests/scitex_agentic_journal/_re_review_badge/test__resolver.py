"""Tests for ``resolve_badge_for_paper`` — TQ AAA, no mocks.

Each test materialises a real submission directory on tmp_path with
exactly the on-disk shapes the M2/M3/M4 persisters write today
(``review.json`` / ``decision.json`` / ``persistent_id.json`` all
wrapped under a ``record`` block). The resolver then runs against
that home and we inspect the returned :class:`ReReviewBadge`. One
assertion per test (PA-307 §3 STX-TQ001).
"""

from __future__ import annotations

import json
from pathlib import Path

from scitex_agentic_journal._re_review_badge import (
    BADGE_REVIEWER_PREFIX,
    ReReviewBadge,
    resolve_badge_for_paper,
)


_PERSISTENT_ID = "scitex-aj-20260613-sample-paper-a1b2c3"
_OTHER_ID = "scitex-aj-20260613-other-paper-99zzzz"
_SUBMISSION_ID = "sub_2026_06_13_abc123"


def _write_persistent_id_json(
    home: Path,
    submission_id: str = _SUBMISSION_ID,
    persistent_id: str = _PERSISTENT_ID,
) -> None:
    submission_dir = home / "submissions" / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    (submission_dir / "persistent_id.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "content_hash": "sha256:" + "c" * 64,
                "written_at_utc": "2026-06-13T13:00:00+00:00",
                "record": {
                    "submission_id": submission_id,
                    "persistent_id": persistent_id,
                    "backend": "internal",
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_decision_json(
    home: Path,
    submission_id: str = _SUBMISSION_ID,
    *,
    verdict: str = "accept",
    decided_at: str = "2026-06-13T12:30:00+00:00",
    failing_rule_message: str | None = None,
) -> None:
    submission_dir = home / "submissions" / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    rule_hits: list[dict] = []
    if failing_rule_message is not None:
        rule_hits.append(
            {
                "rule_id": "methodology_fatal",
                "version": "v1",
                "passed": False,
                "message": failing_rule_message,
            }
        )
    (submission_dir / "decision.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "content_hash": "sha256:" + "b" * 64,
                "written_at_utc": "2026-06-13T12:30:01+00:00",
                "record": {
                    "submission_id": submission_id,
                    "verdict": verdict,
                    "rules_version": "v1",
                    "rule_hits": rule_hits,
                    "decided_at": decided_at,
                    "review_content_hash": "sha256:" + "a" * 64,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_review_json(
    home: Path,
    submission_id: str = _SUBMISSION_ID,
    *,
    adapter: str = "local-deterministic",
) -> None:
    submission_dir = home / "submissions" / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)
    (submission_dir / "review.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "content_hash": "sha256:" + "a" * 64,
                "written_at_utc": "2026-06-13T12:00:00+00:00",
                "record": {
                    "submission_id": submission_id,
                    "adapter": adapter,
                    "adapter_version": "0.1.0",
                    "prompts_version": "v1",
                    "rubric_version": "v1",
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


# ----- no match returns None ------------------------------------------------


def test_resolver_returns_none_when_home_has_no_submissions(
    tmp_path: Path,
) -> None:
    # Arrange — empty home, nothing on disk.
    home = tmp_path
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is None


def test_resolver_returns_none_when_no_submission_matches_paper_id(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home, persistent_id=_OTHER_ID)
    _write_decision_json(home)
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is None


def test_resolver_returns_none_when_matching_submission_has_no_decision(
    tmp_path: Path,
) -> None:
    # Arrange — persistent_id matches but no decision.json yet.
    home = tmp_path
    _write_persistent_id_json(home)
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is None


# ----- happy path -----------------------------------------------------------


def test_resolver_returns_re_review_badge_on_accept(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home, verdict="accept")
    _write_review_json(home)
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert isinstance(badge, ReReviewBadge)


def test_resolver_status_is_verified_on_accept(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home, verdict="accept")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.status == "verified"


def test_resolver_status_is_concerns_on_revise(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home, verdict="revise")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.status == "concerns"


def test_resolver_status_is_contradicted_on_reject(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home, verdict="reject")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.status == "contradicted"


def test_resolver_last_reviewed_at_pulls_decided_at(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home, decided_at="2026-09-01T00:00:00+00:00")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.last_reviewed_at == "2026-09-01T00:00:00+00:00"


def test_resolver_reviewer_is_prefixed_adapter_id(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home)
    _write_review_json(home, adapter="qwen-7b-instruct")
    expected = f"{BADGE_REVIEWER_PREFIX}:qwen-7b-instruct"
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.reviewer == expected


def test_resolver_reviewer_is_none_when_review_record_missing(tmp_path: Path) -> None:
    # Arrange — decision present but no review.json.
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home)
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.reviewer is None


def test_resolver_notes_pulls_first_failing_rule_message(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(
        home,
        verdict="reject",
        failing_rule_message="methodology.max_severity='fatal'; rule fires when severity == 'fatal'.",
    )
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert (
        badge is not None
        and badge.notes
        == "methodology.max_severity='fatal'; rule fires when severity == 'fatal'."
    )


def test_resolver_notes_is_none_when_no_rule_failed(tmp_path: Path) -> None:
    # Arrange — accept verdict, no failing hits.
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home, verdict="accept")
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.notes is None


def test_resolver_log_url_is_passed_through_when_provided(tmp_path: Path) -> None:
    """The hub knows its own URL space — it passes ``log_url`` in;
    the resolver does not synthesise one."""
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home)
    expected = "https://hub.scitex.ai/aj/sub_2026_06_13_abc123"
    # Act
    badge = resolve_badge_for_paper(
        _PERSISTENT_ID, home=home, log_url=expected
    )
    # Assert
    assert badge is not None and badge.log_url == expected


def test_resolver_log_url_is_none_when_not_provided(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    _write_decision_json(home)
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is not None and badge.log_url is None


# ----- malformed records degrade gracefully (no crash) ----------------------


def test_resolver_returns_none_on_unreadable_persistent_id_json(
    tmp_path: Path,
) -> None:
    # Arrange — write garbage into persistent_id.json.
    home = tmp_path
    submission_dir = home / "submissions" / _SUBMISSION_ID
    submission_dir.mkdir(parents=True)
    (submission_dir / "persistent_id.json").write_text(
        "{not-json", encoding="utf-8"
    )
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is None


def test_resolver_returns_none_on_unreadable_decision_json(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path
    _write_persistent_id_json(home)
    submission_dir = home / "submissions" / _SUBMISSION_ID
    (submission_dir / "decision.json").write_text(
        "{not-json", encoding="utf-8"
    )
    # Act
    badge = resolve_badge_for_paper(_PERSISTENT_ID, home=home)
    # Assert
    assert badge is None
