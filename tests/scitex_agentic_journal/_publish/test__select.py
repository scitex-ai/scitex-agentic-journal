"""Unit tests for :mod:`scitex_agentic_journal._publish` — no network."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from scitex_agentic_journal._ports import (
    LivePaperBundle,
    PublishReceipt,
)
from scitex_agentic_journal._publish import (
    CrossrefStub,
    InternalIdMinter,
    JalcStub,
    LivePaperProxy,
    MintInput,
    PersistentId,
    UnknownBackendError,
    ZenodoSandboxStub,
    ZenodoStub,
    select_minter,
)


def _mint_input() -> MintInput:
    return MintInput(
        submission_id="s-001",
        title="Example Title — for ID minting",
        corresponding_author_orcid="0000-0002-1825-0097",
        decided_at=datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc),
    )


# ----- InternalIdMinter ----------------------------------------------------


def test_internal_minter_backend_value_is_internal() -> None:
    # Arrange
    minter = InternalIdMinter()
    # Act
    backend = minter.backend
    # Assert
    assert backend == "internal"


def test_internal_minter_id_starts_with_scitex_aj_prefix() -> None:
    # Arrange
    minter = InternalIdMinter()
    # Act
    pid = minter.mint(_mint_input())
    # Assert
    assert pid.persistent_id.startswith("scitex-aj-")


def test_internal_minter_id_embeds_decision_date() -> None:
    # Arrange
    minter = InternalIdMinter()
    # Act
    pid = minter.mint(_mint_input())
    # Assert
    assert "20260613" in pid.persistent_id


def test_internal_minter_is_deterministic_for_same_input() -> None:
    # Arrange
    minter = InternalIdMinter()
    # Act
    first = minter.mint(_mint_input())
    second = minter.mint(_mint_input())
    # Assert
    assert first.persistent_id == second.persistent_id


def test_internal_minter_changes_with_decision_day() -> None:
    # Arrange
    minter = InternalIdMinter()
    base = _mint_input()
    other_day = MintInput(
        submission_id=base.submission_id,
        title=base.title,
        corresponding_author_orcid=base.corresponding_author_orcid,
        decided_at=datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc),
    )
    # Act
    a = minter.mint(base)
    b = minter.mint(other_day)
    # Assert
    assert a.persistent_id != b.persistent_id


def test_internal_minter_slugifies_unicode_title() -> None:
    # Arrange
    minter = InternalIdMinter()
    base = _mint_input()
    weird_title = MintInput(
        submission_id=base.submission_id,
        title="ARÅ: Agents Réviewing — naïve façade ✨",
        corresponding_author_orcid=base.corresponding_author_orcid,
        decided_at=base.decided_at,
    )
    # Act
    pid = minter.mint(weird_title)
    # Assert
    assert "ara" in pid.persistent_id


def test_internal_minter_empty_title_falls_back_to_untitled() -> None:
    # Arrange
    minter = InternalIdMinter()
    base = _mint_input()
    empty_title = MintInput(
        submission_id=base.submission_id,
        title="",
        corresponding_author_orcid=base.corresponding_author_orcid,
        decided_at=base.decided_at,
    )
    # Act
    pid = minter.mint(empty_title)
    # Assert
    assert "untitled" in pid.persistent_id


# ----- PersistentId citation -----------------------------------------------


def test_persistent_id_citation_suffix_includes_id() -> None:
    # Arrange
    pid = PersistentId(persistent_id="scitex-aj-20260613-x-abcdef", backend="internal")
    # Act
    citation = pid.citation_suffix()
    # Assert
    assert "scitex-aj-20260613-x-abcdef" in citation


# ----- Stub backends raise NotImplementedError -----------------------------


def test_jalc_stub_mint_raises_not_implemented() -> None:
    # Arrange
    stub = JalcStub()
    # Act
    # Assert
    with pytest.raises(NotImplementedError):
        stub.mint(_mint_input())


def test_crossref_stub_mint_raises_not_implemented() -> None:
    # Arrange
    stub = CrossrefStub()
    # Act
    # Assert
    with pytest.raises(NotImplementedError):
        stub.mint(_mint_input())


# ----- Backend selection ---------------------------------------------------


def test_select_minter_internal_returns_internal_minter() -> None:
    # Arrange
    backend = "internal"
    # Act
    minter = select_minter(backend)
    # Assert
    assert isinstance(minter, InternalIdMinter)


def test_select_minter_zenodo_returns_zenodo_stub() -> None:
    # Arrange
    backend = "zenodo"
    # Act
    minter = select_minter(backend)
    # Assert
    assert isinstance(minter, ZenodoStub)


def test_select_minter_jalc_returns_jalc_stub() -> None:
    # Arrange
    backend = "jalc"
    # Act
    minter = select_minter(backend)
    # Assert
    assert isinstance(minter, JalcStub)


def test_select_minter_unknown_raises_unknown_backend_error() -> None:
    # Arrange
    backend = "fly-by-night-doi-shop"
    # Act
    # Assert
    with pytest.raises(UnknownBackendError):
        select_minter(backend)


# ----- LivePaperProxy ------------------------------------------------------


class _RecordingLivePaperPort:
    def __init__(self) -> None:
        self.bundles: list[LivePaperBundle] = []

    def publish(self, bundle: LivePaperBundle) -> PublishReceipt:
        self.bundles.append(bundle)
        return PublishReceipt(
            persistent_id=bundle.persistent_id,
            viewer_url=f"https://example.com/{bundle.persistent_id}",
        )


def test_live_paper_proxy_packages_persistent_id_into_bundle() -> None:
    # Arrange
    port = _RecordingLivePaperPort()
    proxy = LivePaperProxy(port)
    pid = PersistentId(persistent_id="scitex-aj-20260613-x-abcdef", backend="internal")
    # Act
    proxy.publish(
        submission_id="s-001",
        persistent_id=pid,
        manuscript_dir=Path("/tmp/manuscript"),
        review_record_id="rev-1",
        decision_record_id="dec-1",
    )
    # Assert
    assert port.bundles[0].persistent_id == pid.persistent_id


def test_live_paper_proxy_returns_port_receipt_unchanged() -> None:
    # Arrange
    port = _RecordingLivePaperPort()
    proxy = LivePaperProxy(port)
    pid = PersistentId(persistent_id="scitex-aj-20260613-y-fedcba", backend="internal")
    # Act
    receipt = proxy.publish(
        submission_id="s-002",
        persistent_id=pid,
        manuscript_dir=Path("/tmp/manuscript"),
        review_record_id="rev-2",
        decision_record_id="dec-2",
    )
    # Assert
    assert receipt.viewer_url.endswith(pid.persistent_id)


class _BrokenLivePaperPort:
    def publish(self, bundle: LivePaperBundle) -> PublishReceipt:
        raise RuntimeError("upstream down")


def test_live_paper_proxy_propagates_port_errors() -> None:
    # Arrange
    proxy = LivePaperProxy(_BrokenLivePaperPort())
    pid = PersistentId(persistent_id="scitex-aj-20260613-z-zzzzzz", backend="internal")
    # Act
    # Assert
    with pytest.raises(RuntimeError):
        proxy.publish(
            submission_id="s-003",
            persistent_id=pid,
            manuscript_dir=Path("/tmp/m"),
            review_record_id="r",
            decision_record_id="d",
        )
