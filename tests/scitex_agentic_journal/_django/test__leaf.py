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
    body = _leaf.list_archive(home=tmp_path)
    assert body["submissions"] == []
    assert body["placeholder"] is True


def test_list_archive_reads_real_records(tmp_path: Path) -> None:
    sub = tmp_path / "submissions"
    _write(sub, "sub_2026_10_16_aaaaaa", "gate1.json", {"submission_id": "x", "gate": "gate1"})
    _write(
        sub,
        "sub_2026_10_16_aaaaaa",
        "decision.json",
        {"record": {"verdict": "accept", "decided_at": "2026-10-16T00:00:00+00:00"}},
    )
    body = _leaf.list_archive(home=tmp_path)
    assert body["placeholder"] is False
    assert len(body["submissions"]) == 1
    item = body["submissions"][0]
    assert item["submission_id"] == "sub_2026_10_16_aaaaaa"
    assert item["has_gate1"] is True
    assert item["verdict"] == "accept"


def test_get_summary_unknown_is_none(tmp_path: Path) -> None:
    assert _leaf.get_submission_summary("nope", home=tmp_path) is None


def test_validator_mock_is_explicit(tmp_path: Path) -> None:
    body = _leaf.validator_mock_report("sub_x")
    assert body["mock"] is True
    assert body["submission_id"] == "sub_x"
    assert len(body["checks"]) == 3


def test_share_unknown_is_none(tmp_path: Path) -> None:
    assert _leaf.share_record("nope", home=tmp_path) is None


def test_share_prefers_persistent_id(tmp_path: Path) -> None:
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    body = _leaf.share_record("sub_1", home=tmp_path)
    assert body is not None
    assert body["persistent_id"] == "pid-1"
    assert body["share"] == {"persistent_id": "pid-1"}


def test_html_unknown_found_false(tmp_path: Path) -> None:
    body = _leaf.html_payload("pid-missing", home=tmp_path)
    assert body["found"] is False
    assert body["renderer"] == "live-paper-ports"
    assert body["badge"] is None


def test_html_found_without_badge_still_ports(tmp_path: Path) -> None:
    sub = tmp_path / "submissions"
    _write(sub, "sub_1", "persistent_id.json", {"record": {"persistent_id": "pid-1"}})
    body = _leaf.html_payload("pid-1", home=tmp_path)
    assert body["found"] is True
    assert body["submission_id"] == "sub_1"
    assert body["renderer"] == "live-paper-ports"


def test_decision_dashboard_empty_is_placeholder(tmp_path: Path) -> None:
    body = _leaf.decision_dashboard(home=tmp_path)
    assert body["rows"] == []
    assert body["placeholder"] is True
    assert body["total"] == 0
    assert body["counts"]["stale"] == 0


def test_decision_dashboard_maps_verdicts_to_status(tmp_path: Path) -> None:
    sub = tmp_path / "submissions"
    _write(sub, "sub_accept", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_accept", "decision.json", {"record": {"verdict": "accept"}})
    _write(sub, "sub_revise", "gate1.json", {"gate": "gate1"})
    _write(sub, "sub_revise", "decision.json", {"record": {"verdict": "revise"}})
    _write(sub, "sub_undecided", "gate1.json", {"gate": "gate1"})
    body = _leaf.decision_dashboard(home=tmp_path)
    assert body["placeholder"] is False
    assert body["total"] == 3
    by_id = {r["submission_id"]: r for r in body["rows"]}
    assert by_id["sub_accept"]["status"] == "verified"
    assert by_id["sub_revise"]["status"] == "concerns"
    assert by_id["sub_undecided"]["status"] == "stale"
    assert body["counts"]["verified"] == 1
    assert body["counts"]["concerns"] == 1
    assert body["counts"]["stale"] == 1
