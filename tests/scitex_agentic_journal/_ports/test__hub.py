"""Unit tests for :mod:`scitex_agentic_journal._ports`.

Validates the protocol surfaces and that a hand-rolled in-memory
implementation satisfies each `Protocol`. No network, no Django.
"""

from __future__ import annotations

from pathlib import Path

from scitex_agentic_journal._ports import (
    ClewClaim,
    ClewDagSnapshot,
    ClewPort,
    ClewVerificationStatus,
    HubNotification,
    HubPort,
    LivePaperBundle,
    LivePaperPort,
    ManuscriptBundle,
    PublishReceipt,
    ReviewJob,
    SchedulerPort,
    SubmissionStatus,
    UiPort,
    WriterPort,
)

# ----- Writer port ---------------------------------------------------------


class _InMemoryWriter:
    def load_bundle(self, manuscript_dir: Path) -> ManuscriptBundle:
        return ManuscriptBundle(
            root=manuscript_dir,
            main_tex=manuscript_dir / "main.tex",
        )


def test_in_memory_writer_satisfies_writer_port() -> None:
    # Arrange
    writer = _InMemoryWriter()
    # Act
    is_port = isinstance(writer, WriterPort)
    # Assert
    assert is_port is True


def test_manuscript_bundle_default_figures_is_empty_tuple() -> None:
    # Arrange
    root = Path("/tmp/x")
    # Act
    bundle = ManuscriptBundle(root=root, main_tex=root / "main.tex")
    # Assert
    assert bundle.figures == ()


def test_manuscript_bundle_default_bibliography_is_empty_tuple() -> None:
    # Arrange
    root = Path("/tmp/x")
    # Act
    bundle = ManuscriptBundle(root=root, main_tex=root / "main.tex")
    # Assert
    assert bundle.bibliography == ()


# ----- Clew port -----------------------------------------------------------


class _InMemoryClew:
    def load_claims(self, project_root: Path) -> tuple[ClewClaim, ...]:
        return (
            ClewClaim(
                claim_id="c1",
                summary="example claim",
                status=ClewVerificationStatus.GREEN,
            ),
        )

    def snapshot_dag(self, project_root: Path) -> ClewDagSnapshot:
        return ClewDagSnapshot(
            project_root=project_root,
            content_hash="deadbeef",
            claim_count=1,
        )


def test_in_memory_clew_satisfies_clew_port() -> None:
    # Arrange
    clew = _InMemoryClew()
    # Act
    is_port = isinstance(clew, ClewPort)
    # Assert
    assert is_port is True


def test_clew_verification_status_green_string_value_is_stable() -> None:
    # Arrange
    status = ClewVerificationStatus.GREEN
    # Act
    raw = status.value
    # Assert
    assert raw == "green"


def test_clew_claim_is_frozen() -> None:
    # Arrange
    claim = ClewClaim(claim_id="c1", summary="x", status=ClewVerificationStatus.RED)
    # Act / Assert
    try:
        claim.claim_id = "c2"  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001 — verifying immutability raises
        # Assert
        assert "frozen" in str(exc).lower() or "FrozenInstance" in type(exc).__name__
    else:
        # Assert
        raise AssertionError("ClewClaim should be frozen but assignment succeeded")


# ----- Scheduler port ------------------------------------------------------


class _InMemoryScheduler:
    def __init__(self) -> None:
        self._queue: list[ReviewJob] = []

    def enqueue(self, job: ReviewJob) -> None:
        self._queue.append(job)

    def dequeue(self) -> ReviewJob | None:
        return self._queue.pop(0) if self._queue else None


def test_in_memory_scheduler_satisfies_scheduler_port() -> None:
    # Arrange
    scheduler = _InMemoryScheduler()
    # Act
    is_port = isinstance(scheduler, SchedulerPort)
    # Assert
    assert is_port is True


def test_empty_scheduler_dequeue_returns_none() -> None:
    # Arrange
    scheduler = _InMemoryScheduler()
    # Act
    job = scheduler.dequeue()
    # Assert
    assert job is None


def test_scheduler_enqueue_dequeue_roundtrip() -> None:
    # Arrange
    scheduler = _InMemoryScheduler()
    expected = ReviewJob(
        submission_id="s1",
        prompts_version="v1",
        adapter="qwen-self-hosted",
    )
    scheduler.enqueue(expected)
    # Act
    actual = scheduler.dequeue()
    # Assert
    assert actual == expected


# ----- Hub port ------------------------------------------------------------


class _InMemoryHub:
    def __init__(self) -> None:
        self.sent: list[HubNotification] = []

    def notify(self, event: HubNotification) -> None:
        self.sent.append(event)


def test_in_memory_hub_satisfies_hub_port() -> None:
    # Arrange
    hub = _InMemoryHub()
    # Act
    is_port = isinstance(hub, HubPort)
    # Assert
    assert is_port is True


def test_hub_notify_records_event() -> None:
    # Arrange
    hub = _InMemoryHub()
    event = HubNotification(
        submission_id="s1",
        kind="decision_accept",
        recipient_orcid="0000-0002-1825-0097",
        summary="accepted",
    )
    # Act
    hub.notify(event)
    # Assert
    assert hub.sent == [event]


# ----- LivePaper port ------------------------------------------------------


class _InMemoryLivePaper:
    def publish(self, bundle: LivePaperBundle) -> PublishReceipt:
        return PublishReceipt(
            persistent_id=bundle.persistent_id,
            viewer_url=f"https://example.com/{bundle.persistent_id}",
        )


def test_in_memory_live_paper_satisfies_live_paper_port() -> None:
    # Arrange
    live_paper = _InMemoryLivePaper()
    # Act
    is_port = isinstance(live_paper, LivePaperPort)
    # Assert
    assert is_port is True


def test_live_paper_publish_returns_receipt_with_same_persistent_id() -> None:
    # Arrange
    live_paper = _InMemoryLivePaper()
    bundle = LivePaperBundle(
        submission_id="s1",
        persistent_id="scitex-aj-20260613-x-abc123",
        manuscript_dir=Path("/tmp/manuscript"),
        review_record_id="r1",
        decision_record_id="d1",
    )
    # Act
    receipt = live_paper.publish(bundle)
    # Assert
    assert receipt.persistent_id == bundle.persistent_id


# ----- UI port -------------------------------------------------------------


class _InMemoryUi:
    def __init__(self) -> None:
        self.updates: list[tuple[str, SubmissionStatus]] = []

    def update_status(self, submission_id: str, status: SubmissionStatus) -> None:
        self.updates.append((submission_id, status))


def test_in_memory_ui_satisfies_ui_port() -> None:
    # Arrange
    ui = _InMemoryUi()
    # Act
    is_port = isinstance(ui, UiPort)
    # Assert
    assert is_port is True


def test_ui_update_status_records_pair() -> None:
    # Arrange
    ui = _InMemoryUi()
    # Act
    ui.update_status("s1", SubmissionStatus.UNDER_REVIEW)
    # Assert
    assert ui.updates == [("s1", SubmissionStatus.UNDER_REVIEW)]


def test_submission_status_decided_accept_value_is_stable() -> None:
    # Arrange
    status = SubmissionStatus.DECIDED_ACCEPT
    # Act
    raw = status.value
    # Assert
    assert raw == "decided-accept"
