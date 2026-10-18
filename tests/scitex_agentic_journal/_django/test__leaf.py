"""Unit tests for the leaf helpers — Django-free (tmp_path only)."""

from __future__ import annotations

import json
from pathlib import Path

from scitex_agentic_journal._django import _leaf


def _write(sub_root: Path, sid: str, name: str, payload: dict) -> None:
    d = sub_root / sid
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(payload), encoding="utf-8")


def test_list_archive_empty_is_placeholder(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.list_archive(home=home)
    # Assert
    assert body["placeholder"] is True


def test_list_archive_reads_gate1_flag(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_2026_10_16_aaaaaa", "gate1.json", {"submission_id": "x", "gate": "gate1"})
    # Act
    body = _leaf.list_archive(home=tmp_path)
    # Assert
    assert body["submissions"][0]["has_gate1"] is True


def test_list_archive_reads_verdict(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_2026_10_16_aaaaaa", "gate1.json", {"submission_id": "x", "gate": "gate1"})
    _write(
        sub,
        "sub_2026_10_16_aaaaaa",
        "decision.json",
        {"record": {"verdict": "accept", "decided_at": "2026-10-16T00:00:00+00:00"}},
    )
    # Act
    body = _leaf.list_archive(home=tmp_path)
    # Assert
    assert body["submissions"][0]["verdict"] == "accept"


def test_get_summary_unknown_is_none(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    found = _leaf.get_submission_summary("nope", home=home)
    # Assert
    assert found is None


def test_validator_mock_is_explicit(tmp_path: Path) -> None:
    # Arrange
    sid = "sub_x"
    # Act
    body = _leaf.validator_mock_report(sid)
    # Assert
    assert body["mock"] is True


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
    assert body is not None and body["share"] == {"persistent_id": "pid-1"}


def test_html_unknown_found_false(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.html_payload("pid-missing", home=home)
    # Assert
    assert body["found"] is False


def test_html_found_reports_submission(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    # Act
    body = _leaf.html_payload("pid-1", home=tmp_path)
    # Assert
    assert body["submission_id"] == "sub_1"


def test_decision_dashboard_empty_is_placeholder(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path
    # Act
    body = _leaf.decision_dashboard(home=home)
    # Assert
    assert body["placeholder"] is True


def test_decision_dashboard_accept_maps_verified(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_accept", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_accept", "decision.json", {"record": {"verdict": "accept"}})
    # Act
    body = _leaf.decision_dashboard(home=tmp_path)
    # Assert
    assert {r["submission_id"]: r for r in body["rows"]}["sub_accept"]["status"] == "verified"


def test_decision_dashboard_revise_maps_concerns(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_revise", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_revise", "decision.json", {"record": {"verdict": "revise"}})
    # Act
    body = _leaf.decision_dashboard(home=tmp_path)
    # Assert
    assert {r["submission_id"]: r for r in body["rows"]}["sub_revise"]["status"] == "concerns"


def test_decision_dashboard_undecided_maps_stale(tmp_path: Path) -> None:
    # Arrange
    sub = tmp_path / "submissions"
    _write(sub, "sub_undecided", "gate1.json", {"gate": "gate1"})
    # Act
    body = _leaf.decision_dashboard(home=tmp_path)
    # Assert
    assert {r["submission_id"]: r for r in body["rows"]}["sub_undecided"]["status"] == "stale"
