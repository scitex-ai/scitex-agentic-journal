"""Publish backends — persistent-ID minting + Live Paper hand-off.

The publish stage runs after gate-3 (editorial decision) returns
``accept``. It mints a persistent identifier and hands the bundle off
to ``scitex-live-paper`` for rendering.

This package ships:

* :class:`InternalIdMinter` — default, no external deps; mints
  ``scitex-aj-{YYYYMMDD}-{slug}-{hash6}``.
* :class:`ZenodoStub`, :class:`ZenodoSandboxStub`, :class:`JalcStub`,
  :class:`CrossrefStub` — typed placeholders that explicitly raise
  :class:`NotImplementedError` so callers fail loud until the real
  adapters ship. No silent fallback to the internal minter.
* :class:`LivePaperProxy` — thin shim over :class:`LivePaperPort` so
  callers can hand off without importing the port directly.
* :func:`select_minter` — pick an :class:`IdMinter` from a backend
  name (raises on unknown).
* :func:`mint_for_submission` — orchestrate a mint over a persisted
  Gate-1 record; raise :class:`MintLoadError` if the submission is
  missing.
* :func:`persist_persistent_id` — write ``persistent_id.json`` next
  to the existing gate-1 / review / decision records.
* :func:`publish_submission` — hand off an accepted submission to a
  :class:`LivePaperPort` (default ``LocalFilesystemLivePaperPort``);
  raise :class:`PublishLoadError` if the on-disk pre-conditions
  (gate1 / review / decision / persistent_id) are not all met.
"""

from __future__ import annotations

from scitex_agentic_journal._publish._crossref import CrossrefStub
from scitex_agentic_journal._publish._handoff import (
    BUNDLE_FILENAME,
    LocalFilesystemLivePaperPort,
    PUBLISHED_DIRNAME,
    RemoteLivePaperPortStub,
    build_bundle,
    publish_submission,
)
from scitex_agentic_journal._publish._internal import InternalIdMinter
from scitex_agentic_journal._publish._jalc import JalcStub
from scitex_agentic_journal._publish._live_paper_proxy import LivePaperProxy
from scitex_agentic_journal._publish._load_records import (
    PublishLoadError,
    PublishRecords,
    load_submission_records,
)
from scitex_agentic_journal._publish._mint import (
    MintLoadError,
    mint_for_submission,
)
from scitex_agentic_journal._publish._persist import (
    PersistedPersistentId,
    persist_persistent_id,
)
from scitex_agentic_journal._publish._select import (
    UnknownBackendError,
    select_minter,
)
from scitex_agentic_journal._publish._types import (
    IdMinter,
    MintInput,
    PersistentId,
)
from scitex_agentic_journal._publish._zenodo import (
    ZenodoSandboxStub,
    ZenodoStub,
)

__all__ = [
    "BUNDLE_FILENAME",
    "CrossrefStub",
    "IdMinter",
    "InternalIdMinter",
    "JalcStub",
    "LivePaperProxy",
    "LocalFilesystemLivePaperPort",
    "MintInput",
    "MintLoadError",
    "PUBLISHED_DIRNAME",
    "PersistedPersistentId",
    "PersistentId",
    "PublishLoadError",
    "PublishRecords",
    "RemoteLivePaperPortStub",
    "UnknownBackendError",
    "ZenodoSandboxStub",
    "ZenodoStub",
    "build_bundle",
    "load_submission_records",
    "mint_for_submission",
    "persist_persistent_id",
    "publish_submission",
    "select_minter",
]
