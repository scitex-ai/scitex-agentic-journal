"""Tests for the ReReviewBadge dataclass + verdict mapping.

The shape must match :class:`scitex_live_paper._types.ReReviewBadge`
byte-for-byte — we cannot import live-paper here (would create a
runtime dependency), but the field names, defaults, and the
``frozen`` + ``slots`` flavour are checked explicitly. No mocks.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from scitex_agentic_journal._re_review_badge import (
    ReReviewBadge,
    verdict_to_status,
)


def test_re_review_badge_is_a_dataclass() -> None:
    # Arrange
    cls = ReReviewBadge
    # Act
    flag = is_dataclass(cls)
    # Assert
    assert flag is True


def test_re_review_badge_field_names_match_live_paper_contract() -> None:
    """The hub hands the dataclass straight to live-paper, so the
    field names MUST match the live-paper PR #38 shape verbatim.
    """
    # Arrange
    expected = {"status", "last_reviewed_at", "reviewer", "log_url", "notes"}
    # Act
    names = {f.name for f in fields(ReReviewBadge)}
    # Assert
    assert names == expected


def test_re_review_badge_is_frozen() -> None:
    # Arrange
    badge = ReReviewBadge(status="verified")
    # Act
    ctx = pytest.raises(FrozenInstanceError)
    # Assert
    with ctx:
        badge.status = "stale"  # type: ignore[misc]


def test_re_review_badge_optional_fields_default_to_none() -> None:
    # Arrange
    badge = ReReviewBadge(status="verified")
    # Act
    null_count = sum(
        getattr(badge, attr) is None
        for attr in ("last_reviewed_at", "reviewer", "log_url", "notes")
    )
    # Assert
    assert null_count == 4


def test_verdict_accept_maps_to_verified() -> None:
    # Arrange
    verdict = "accept"
    # Act
    status = verdict_to_status(verdict)
    # Assert
    assert status == "verified"


def test_verdict_revise_maps_to_concerns() -> None:
    # Arrange
    verdict = "revise"
    # Act
    status = verdict_to_status(verdict)
    # Assert
    assert status == "concerns"


def test_verdict_reject_maps_to_contradicted() -> None:
    # Arrange
    verdict = "reject"
    # Act
    status = verdict_to_status(verdict)
    # Assert
    assert status == "contradicted"


def test_verdict_none_maps_to_stale() -> None:
    # Arrange
    verdict = None
    # Act
    status = verdict_to_status(verdict)
    # Assert
    assert status == "stale"


def test_verdict_unknown_string_collapses_to_stale() -> None:
    """An M3 verdict we don't know about MUST still produce a valid
    badge (live-paper's SPA must not crash on a render). The fallback
    is the muted grey ``stale`` chip — same as "no recent re-review".
    """
    # Arrange
    verdict = "appeal-pending"
    # Act
    status = verdict_to_status(verdict)
    # Assert
    assert status == "stale"
