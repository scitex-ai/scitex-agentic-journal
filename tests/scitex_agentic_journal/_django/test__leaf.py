"""Unit tests for the leaf helpers — Django-free (tmp_path only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_agentic_journal._django import _leaf


def _write(sub_root: Path, sid: str, name: str, payload: dict) -> None:
    d = sub_root / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def _seeded(tmp_path: Path) -> Path:
    # Arrange
    # one submission with gate1 + accept decision.
    sub = tmp_path / "submissions"
    _write(sub, "sub_2026_10_16_aaaaaa", "gate1.json", {"submission_id": "x", "gate": "gate1"})
    _write(
        sub,
        "sub_2026_10_16_aaaaaa",
        "decision.json",
        {"record": {"verdict": "accept", "decided_at": "2026-10-16T00:00:00+00:00"}},
    )
    return tmp_path


@pytest.fixture
def _dashboard_seed(tmp_path: Path) -> Path:
    # Arrange
    # accept + revise + undecided submissions.
    sub = tmp_path / "submissions"
    _write(sub, "sub_accept", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_accept", "decision.json", {"record": {"verdict": "accept"}})
    _write(sub, "sub_revise", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_revise", "decision.json", {"record": {"verdict": "revise"}})
    _write(sub, "sub_undecided", "gate1.json", {"gate": "gate1"})
    return tmp_path


def test_list_archive_empty_submissions(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert body["submissions"] == []


def test_list_archive_empty_placeholder(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert body["placeholder"] is True


def test_list_archive_seeded_not_placeholder(_seeded: Path) -> None:
    # Arrange
    home = _seeded
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert body["placeholder"] is False


def test_list_archive_seeded_count(_seeded: Path) -> None:
    # Arrange
    home = _seeded
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert len(body["submissions"]) == 1


def test_list_archive_seeded_submission_id(_seeded: Path) -> None:
    # Arrange
    home = _seeded
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert body["submissions"][0]["submission_id"] == "sub_2026_10_16_aaaaaa"


def test_list_archive_seeded_has_gate1(_seeded: Path) -> None:
    # Arrange
    home = _seeded
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert body["submissions"][0]["has_gate1"] is True


def test_list_archive_seeded_verdict(_seeded: Path) -> None:
    # Arrange
    home = _seeded
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert body["submissions"][0]["verdict"] == "accept"


def test_get_summary_unknown_is_none(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    found = _leaf.get_submission_summary("nope", home=home)
    # Assert
    assert found is None


def test_validator_mock_flag(tmp_path: Path) -> None:
    # Arrange
    sid = "sub_x"
    # Act
    body = _leaf.validator_mock_report(sid)
    # Assert
    assert body["mock"] is True


def test_validator_mock_submission_id(tmp_path: Path) -> None:
    # Arrange
    sid = "sub_x"
    # Act
    body = _leaf.validator_mock_report(sid)
    # Assert
    assert body["submission_id"] == "sub_x"


def test_validator_mock_check_count(tmp_path: Path) -> None:
    # Arrange
    sid = "sub_x"
    # Act
    body = _leaf.validator_mock_report(sid)
    # Assert
    assert len(body["checks"]) == 3


def test_share_unknown_is_none(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    found = _leaf.share_record("nope", home=home)
    # Assert
    assert found is None


def test_share_prefers_persistent_id(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    # Act
    body = _leaf.share_record("sub_1", home=tmp_path)
    # Assert
    assert body is not None and body["persistent_id"] == "pid-1"


def test_share_payload_shape(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    # Act
    body = _leaf.share_record("sub_1", home=tmp_path)
    # Assert
    assert body is not None and body["share"] == {"persistent_id": "pid-1"}


def test_html_unknown_found_false(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.html_payload("pid-missing", home=home)
    # Assert
    assert body["found"] is False


def test_html_unknown_renderer(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.html_payload("pid-missing", home=home)
    # Assert
    assert body["renderer"] == "live-paper-ports"


def test_html_unknown_badge_none(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.html_payload("pid-missing", home=home)
    # Assert
    assert body["badge"] is None


def test_html_found_flag(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    # Act
    body = _leaf.html_payload("pid-1", home=tmp_path)
    # Assert
    assert body["found"] is True


def test_html_found_submission_id(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    # Act
    body = _leaf.html_payload("pid-1", home=tmp_path)
    # Assert
    assert body["submission_id"] == "sub_1"


def test_html_found_renderer(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    # Act
    body = _leaf.html_payload("pid-1", home=tmp_path)
    # Assert
    assert body["renderer"] == "live-paper-ports"


def test_decision_dashboard_empty_rows(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["rows"] == []


def test_decision_dashboard_empty_placeholder(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["placeholder"] is True


def test_decision_dashboard_empty_total(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["total"] == 0


def test_decision_dashboard_empty_stale(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["counts"]["stale"] == 0


def test_decision_dashboard_seeded_not_placeholder(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["placeholder"] is False


def test_decision_dashboard_seeded_total(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["total"] == 3


def test_decision_dashboard_accept_status(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert {r["submission_id"]: r for r in body["rows"]}["sub_accept"]["status"] == "verified"


def test_decision_dashboard_revise_status(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert {r["submission_id"]: r for r in body["rows"]}["sub_revise"]["status"] == "concerns"


def test_decision_dashboard_undecided_status(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert {r["submission_id"]: r for r in body["rows"]}["sub_undecided"]["status"] == "stale"


def test_decision_dashboard_verified_count(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["counts"]["verified"] == 1


def test_decision_dashboard_concerns_count(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["counts"]["concerns"] == 1


def test_decision_dashboard_stale_count(_dashboard_seed: Path) -> None:
    # Arrange
    home = _dashboard_seed
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["counts"]["stale"] == 1
