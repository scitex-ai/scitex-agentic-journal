"""Hand an accepted submission off to ``scitex-live-paper`` (M5).

This module is the public entry point for the publish stage. The CLI
verb ``scitex-agentic-journal publish`` calls :func:`publish_submission`;
the records loader reads four JSON files written by upstream stages,
and the :class:`LivePaperProxy` forwards the resulting bundle to
whichever :class:`LivePaperPort` implementation the caller wires.

In M5 we ship :class:`LocalFilesystemLivePaperPort` as the default
port: it writes the bundle envelope JSON to disk and returns a
``file://`` viewer URL. That is enough to satisfy "Emits a Live Paper
bundle that the scitex-live-paper renderer accepts unmodified" — the
on-disk bundle JSON IS the renderer input contract. A real
HTTP / MCP port (e.g. POSTing to a live-paper deployment) drops in
without touching anything else in this package.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scitex_agentic_journal._ports import (
    LivePaperBundle,
    LivePaperPort,
    PublishReceipt,
)
from scitex_agentic_journal._publish._live_paper_proxy import LivePaperProxy
from scitex_agentic_journal._publish._load_records import (
    PublishLoadError,
    PublishRecords,
    load_submission_records,
)
from scitex_agentic_journal._publish._types import PersistentId


PUBLISHED_DIRNAME = "published"
"""Subdirectory under ``$SCITEX_AGENTIC_JOURNAL_HOME`` where the
local-filesystem port drops bundle envelopes."""

BUNDLE_FILENAME = "bundle.json"
"""On-disk name of the bundle envelope written by the local port."""


def _bundle_to_jsonable(bundle: LivePaperBundle) -> dict:
    """Serialise the bundle envelope into the renderer hand-off shape.

    Keeping this in one place means the on-disk format the
    :class:`LocalFilesystemLivePaperPort` writes is exactly the
    payload a future HTTP port will POST — both are derived from
    the same :class:`LivePaperBundle`.
    """
    return {
        "submission_id": bundle.submission_id,
        "persistent_id": bundle.persistent_id,
        "manuscript_dir": str(bundle.manuscript_dir),
        "review_record_id": bundle.review_record_id,
        "decision_record_id": bundle.decision_record_id,
    }


@dataclass(frozen=True, slots=True)
class LocalFilesystemLivePaperPort:
    """Default M5 port — write the bundle envelope to disk.

    The viewer URL is a ``file://`` path pointing at the written
    envelope. A production deployment swaps this out for an HTTP /
    MCP port that POSTs to a real live-paper instance.

    Parameters
    ----------
    home :
        Submission-home root. The port writes the envelope under
        ``<home>/published/<submission_id>/bundle.json``. The same
        root the M1/M2 persisters use, so the operator only sets
        ``SCITEX_AGENTIC_JOURNAL_HOME`` in one place.
    """

    home: Path

    def publish(self, bundle: LivePaperBundle) -> PublishReceipt:
        """Write ``bundle.json`` under ``home/published/<submission_id>/``."""
        out_dir = self.home / PUBLISHED_DIRNAME / bundle.submission_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / BUNDLE_FILENAME
        out_path.write_text(
            json.dumps(_bundle_to_jsonable(bundle), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return PublishReceipt(
            persistent_id=bundle.persistent_id,
            viewer_url=out_path.as_uri(),
        )


class RemoteLivePaperPortStub:
    """Explicit placeholder for the real HTTP / MCP port.

    The CLI exposes this via ``--port remote-stub`` so an operator
    can confirm the wiring path is reachable; the actual remote
    transport lands when ``scitex-live-paper`` exposes a stable URL.
    """

    def publish(self, bundle: LivePaperBundle) -> PublishReceipt:  # noqa: ARG002
        raise NotImplementedError(
            "Remote live-paper port is not implemented yet — the real "
            "HTTP / MCP transport lands when scitex-live-paper exposes "
            "a stable URL. Use the default local-filesystem port for now."
        )


def build_bundle(records: PublishRecords) -> LivePaperBundle:
    """Pure helper — build a :class:`LivePaperBundle` from loaded records.

    Exposed so the ``--dry-run`` path can show the operator the exact
    envelope that would be handed off, without touching any port.
    """
    return LivePaperBundle(
        submission_id=records.submission_id,
        persistent_id=records.persistent_id,
        manuscript_dir=records.manuscript_dir,
        review_record_id=records.review_record_id,
        decision_record_id=records.decision_record_id,
    )


def publish_submission(
    submission_id: str,
    *,
    port: LivePaperPort,
    home: Path | None = None,
) -> PublishReceipt:
    """Load records, package the bundle, hand off to ``port``.

    Parameters
    ----------
    submission_id :
        The submission token printed by ``submit``.
    port :
        A :class:`LivePaperPort` implementation. M5 ships
        :class:`LocalFilesystemLivePaperPort` as the default; a real
        HTTP / MCP port replaces it for production.
    home :
        Override the submission-home root. ``None`` honours
        ``$SCITEX_AGENTIC_JOURNAL_HOME``.

    Returns
    -------
    PublishReceipt
        Receipt straight from the port — no rewriting.

    Raises
    ------
    PublishLoadError
        Whenever a required record is absent / malformed / not accepted.
    Exception
        Whatever the port raises on transport failure. No silent
        fallback; M5 fails loud and stays out of the way.
    """
    records = load_submission_records(submission_id, home=home)
    proxy = LivePaperProxy(port)
    return proxy.publish(
        submission_id=records.submission_id,
        persistent_id=PersistentId(
            persistent_id=records.persistent_id,
            backend="internal",
        ),
        manuscript_dir=records.manuscript_dir,
        review_record_id=records.review_record_id,
        decision_record_id=records.decision_record_id,
    )


__all__ = [
    "BUNDLE_FILENAME",
    "LocalFilesystemLivePaperPort",
    "PUBLISHED_DIRNAME",
    "RemoteLivePaperPortStub",
    "build_bundle",
    "publish_submission",
]
