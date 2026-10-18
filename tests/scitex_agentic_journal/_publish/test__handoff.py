"""Tests for `_publish/_handoff.py` — M5 publish_submission + ports.

These tests use the on-disk file shape directly so the suite stays
independent of M3 (decision engine, #7) and M4 (persistent-ID minting,
#8) landing first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scitex_agentic_journal._ports import LivePaperBundle, PublishReceipt
from scitex_agentic_journal._publish import (
    BUNDLE_FILENAME,
    LocalFilesystemLivePaperPort,
    PUBLISHED_DIRNAME,
    PublishLoadError,
    RemoteLivePaperPortStub,
    build_bundle,
    load_submission_records,
    publish_submission,
)

SUBMISSION_ID = "sub_2026_06_13_abc123"


def _materialise(
    home: Path,
    *,
    verdict: str = "accept",
    persistent_id: str = "scitex-aj-20260613-test-abcdef",
    review_hash: str = "sha256:" + "a" * 64,
    decision_hash: str = "sha256:" + "b" * 64,
    skip_gate1: bool = False,
    skip_review: bool = False,
    skip_decision: bool = False,
    skip_persistent_id: bool = False,
) -> Path:
    """Materialise the on-disk shape the publish stage reads.

    Mirrors what M1 / M2 / M3 / M4 write so M5 tests do not depend on
    importing their Python types.
    """
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = home / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    if not skip_gate1:
        gate1_payload = {
            "submission_id": SUBMISSION_ID,
            "gate": "gate1",
            "verdict": "pass",
            "submission": {
                "bundle_dir": str(bundle_dir),
                "orcid_id": "0000-0002-1825-0097",
                "code_repo_url": "https://example.com/r.git",
                "clew_project_dir": str(bundle_dir),
            },
            "clew_verification": {
                "project_dir": str(bundle_dir),
                "green_claims": ["c1"],
                "red_claims": [],
                "total_claims": 1,
            },
            "orcid_record": {
                "orcid_id": "0000-0002-1825-0097",
                "given_name": "Test",
                "family_name": "Author",
                "credit_name": None,
            },
            "code_repo": {"head_commit": "abc123", "head_subject": "init"},
        }
        (submission_dir / "gate1.json").write_text(
            json.dumps(gate1_payload, indent=2), encoding="utf-8"
        )
    if not skip_review:
        (submission_dir / "review.json").write_text(
            json.dumps(
                {
                    "submission_id": SUBMISSION_ID,
                    "content_hash": review_hash,
                    "written_at_utc": "2026-06-13T12:00:00+00:00",
                    "record": {"submission_id": SUBMISSION_ID},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if not skip_decision:
        (submission_dir / "decision.json").write_text(
            json.dumps(
                {
                    "submission_id": SUBMISSION_ID,
                    "verdict": verdict,
                    "content_hash": decision_hash,
                    "written_at_utc": "2026-06-13T12:30:00+00:00",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if not skip_persistent_id:
        (submission_dir / "persistent_id.json").write_text(
            json.dumps(
                {
                    "submission_id": SUBMISSION_ID,
                    "persistent_id": persistent_id,
                    "backend": "internal",
                    "minted_at_utc": "2026-06-13T13:00:00+00:00",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return submission_dir


# ----- build_bundle ---------------------------------------------------------


def test_build_bundle_returns_live_paper_bundle_with_expected_fields(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home)
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Act
    bundle = build_bundle(records)
    # Assert
    assert isinstance(bundle, LivePaperBundle)


def test_build_bundle_threads_persistent_id_through(tmp_path: Path) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home, persistent_id="scitex-aj-20260613-xyz-fedcba")
    records = load_submission_records(SUBMISSION_ID, home=home)
    # Act
    bundle = build_bundle(records)
    # Assert
    assert bundle.persistent_id == "scitex-aj-20260613-xyz-fedcba"


# ----- LocalFilesystemLivePaperPort.publish --------------------------------


def test_local_port_publish_writes_bundle_json_under_published(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home)
    port = LocalFilesystemLivePaperPort(home=home)
    bundle = LivePaperBundle(
        submission_id=SUBMISSION_ID,
        persistent_id="scitex-aj-20260613-test-abcdef",
        manuscript_dir=home / "bundle",
        review_record_id="sha256:" + "a" * 64,
        decision_record_id="sha256:" + "b" * 64,
    )
    expected_path = (
        home / PUBLISHED_DIRNAME / SUBMISSION_ID / BUNDLE_FILENAME
    )
    # Act
    port.publish(bundle)
    # Assert
    assert expected_path.is_file()


def test_local_port_publish_returns_file_uri_viewer_url(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    port = LocalFilesystemLivePaperPort(home=home)
    bundle = LivePaperBundle(
        submission_id=SUBMISSION_ID,
        persistent_id="scitex-aj-20260613-test-abcdef",
        manuscript_dir=home / "bundle",
        review_record_id="sha256:" + "a" * 64,
        decision_record_id="sha256:" + "b" * 64,
    )
    # Act
    receipt = port.publish(bundle)
    # Assert
    assert receipt.viewer_url.startswith("file://")


def test_local_port_publish_receipt_carries_persistent_id(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    port = LocalFilesystemLivePaperPort(home=home)
    bundle = LivePaperBundle(
        submission_id=SUBMISSION_ID,
        persistent_id="scitex-aj-20260613-test-abcdef",
        manuscript_dir=home / "bundle",
        review_record_id="sha256:" + "a" * 64,
        decision_record_id="sha256:" + "b" * 64,
    )
    # Act
    receipt = port.publish(bundle)
    # Assert
    assert receipt.persistent_id == "scitex-aj-20260613-test-abcdef"


def test_local_port_bundle_json_carries_all_envelope_fields(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    port = LocalFilesystemLivePaperPort(home=home)
    bundle = LivePaperBundle(
        submission_id=SUBMISSION_ID,
        persistent_id="scitex-aj-20260613-test-abcdef",
        manuscript_dir=home / "bundle",
        review_record_id="sha256:" + "a" * 64,
        decision_record_id="sha256:" + "b" * 64,
    )
    # Act
    port.publish(bundle)
    payload = json.loads(
        (home / PUBLISHED_DIRNAME / SUBMISSION_ID / BUNDLE_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    # Assert
    assert set(payload) == {
        "submission_id",
        "persistent_id",
        "manuscript_dir",
        "review_record_id",
        "decision_record_id",
    }


# ----- RemoteLivePaperPortStub ---------------------------------------------


def test_remote_stub_publish_raises_not_implemented_with_clear_message() -> None:
    # Arrange
    stub = RemoteLivePaperPortStub()
    bundle = LivePaperBundle(
        submission_id=SUBMISSION_ID,
        persistent_id="scitex-aj-20260613-test-abcdef",
        manuscript_dir=Path("/tmp/m"),
        review_record_id="sha256:" + "a" * 64,
        decision_record_id="sha256:" + "b" * 64,
    )
    # Act
    # Assert
    with pytest.raises(NotImplementedError, match="Remote live-paper port"):
        stub.publish(bundle)


# ----- publish_submission (happy path against local port) -------------------


def test_publish_submission_happy_path_returns_publish_receipt(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home)
    port = LocalFilesystemLivePaperPort(home=home)
    # Act
    receipt = publish_submission(SUBMISSION_ID, port=port, home=home)
    # Assert
    assert isinstance(receipt, PublishReceipt)


def test_publish_submission_happy_path_writes_bundle_json_to_disk(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home)
    port = LocalFilesystemLivePaperPort(home=home)
    expected_path = (
        home / PUBLISHED_DIRNAME / SUBMISSION_ID / BUNDLE_FILENAME
    )
    # Act
    publish_submission(SUBMISSION_ID, port=port, home=home)
    # Assert
    assert expected_path.is_file()


def test_publish_submission_threads_persistent_id_into_receipt(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home, persistent_id="scitex-aj-20260613-xyz-fedcba")
    port = LocalFilesystemLivePaperPort(home=home)
    # Act
    receipt = publish_submission(SUBMISSION_ID, port=port, home=home)
    # Assert
    assert receipt.persistent_id == "scitex-aj-20260613-xyz-fedcba"


# ----- publish_submission refusal branches ----------------------------------


def test_publish_submission_refuses_when_decision_verdict_is_reject(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home, verdict="reject")
    port = LocalFilesystemLivePaperPort(home=home)
    # Act
    # Assert
    with pytest.raises(PublishLoadError, match="cannot be published"):
        publish_submission(SUBMISSION_ID, port=port, home=home)


def test_publish_submission_refuses_when_review_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home, skip_review=True)
    port = LocalFilesystemLivePaperPort(home=home)
    # Act
    # Assert
    with pytest.raises(PublishLoadError, match="review.json"):
        publish_submission(SUBMISSION_ID, port=port, home=home)


def test_publish_submission_refuses_when_gate1_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home, skip_gate1=True)
    port = LocalFilesystemLivePaperPort(home=home)
    # Act
    # Assert
    with pytest.raises(PublishLoadError, match="gate1.json"):
        publish_submission(SUBMISSION_ID, port=port, home=home)


def test_publish_submission_refuses_when_persistent_id_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home, skip_persistent_id=True)
    port = LocalFilesystemLivePaperPort(home=home)
    # Act
    # Assert
    with pytest.raises(PublishLoadError, match="persistent_id.json"):
        publish_submission(SUBMISSION_ID, port=port, home=home)


# ----- publish_submission propagates port errors (no silent fallback) ------


class _BrokenLivePaperPort:
    def publish(self, bundle):  # noqa: ARG002
        raise RuntimeError("upstream down")


def test_publish_submission_propagates_port_runtime_errors(
    tmp_path: Path,
) -> None:
    # Arrange
    home = tmp_path / "home"
    _materialise(home)
    port = _BrokenLivePaperPort()
    # Act
    # Assert
    with pytest.raises(RuntimeError, match="upstream down"):
        publish_submission(SUBMISSION_ID, port=port, home=home)
