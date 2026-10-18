"""Mint a persistent ID for a persisted submission.

The publish stage runs after gate-3 (editorial decision) returns
``accept``. :func:`mint_for_submission` is the public entry point —
load the submission's gate-1 record from disk, derive the
:class:`MintInput`, dispatch to the configured backend, and return
the :class:`PersistentId`.

Title resolution policy
-----------------------
M4 keeps the contract tight by *not* requiring an upstream rename
of ``bundle.yaml`` to add a mandatory ``title`` key. We:

1. Read ``bundle.yaml`` next to the persisted ``gate1.json`` if
   the bundle directory still exists; use ``title`` from it when
   present.
2. Otherwise fall back to a deterministic title derived from the
   submission id so the mint still succeeds.

This keeps M4 unblocked by M5 (decision engine) and by any future
manifest-schema bump that adds a first-class ``title`` field.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from scitex_agentic_journal._publish._select import select_minter
from scitex_agentic_journal._publish._types import (
    Backend,
    MintInput,
    PersistentId,
)

GATE1_RECORD_FILENAME = "gate1.json"
"""Mirror of `_submit._persist.GATE1_RECORD_FILENAME` (kept local to
avoid pulling the producer module into the publish dependency tree)."""


class MintLoadError(Exception):
    """The persisted submission record needed for minting is missing or malformed."""


@dataclass(frozen=True)
class _MintContext:
    """Internal view: everything :class:`MintInput` needs, sourced from disk."""

    submission_id: str
    title: str
    corresponding_author_orcid: str
    bundle_dir: Path


def _submission_home() -> Path:
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _load_gate1_payload(submission_id: str, home: Path) -> dict:
    submission_dir = home / "submissions" / submission_id
    if not submission_dir.is_dir():
        raise MintLoadError(
            f"no persisted submission at {submission_dir} — run "
            "`scitex-agentic-journal submit` first."
        )
    gate1_path = submission_dir / GATE1_RECORD_FILENAME
    if not gate1_path.is_file():
        raise MintLoadError(
            f"submission {submission_id} is missing its {GATE1_RECORD_FILENAME} "
            f"({gate1_path}) — re-run `scitex-agentic-journal submit`."
        )
    try:
        payload = json.loads(gate1_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise MintLoadError(
            f"{GATE1_RECORD_FILENAME} at {gate1_path} is not valid JSON: {e}"
        ) from e
    if not isinstance(payload, dict):
        raise MintLoadError(
            f"{GATE1_RECORD_FILENAME} at {gate1_path} root is not a JSON object."
        )
    return payload


def _title_from_bundle(bundle_dir: Path) -> Optional[str]:
    """Read ``title`` from ``<bundle>/bundle.yaml`` if available.

    Returns ``None`` when the bundle directory or manifest is gone,
    when the YAML is malformed, or when the manifest simply lacks
    a ``title`` key. Title is not a Gate-1 required field today, so
    we treat its absence as soft.
    """
    manifest = bundle_dir / "bundle.yaml"
    if not manifest.is_file():
        return None
    try:
        loaded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    raw = loaded.get("title")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _build_context(submission_id: str, payload: dict) -> _MintContext:
    submission_block = payload.get("submission")
    if not isinstance(submission_block, dict):
        raise MintLoadError(
            f"{GATE1_RECORD_FILENAME} for {submission_id} missing 'submission' block."
        )
    bundle_dir_raw = submission_block.get("bundle_dir")
    orcid = submission_block.get("orcid_id")
    if not isinstance(bundle_dir_raw, str) or not bundle_dir_raw.strip():
        raise MintLoadError(
            f"{GATE1_RECORD_FILENAME} for {submission_id} missing 'bundle_dir'."
        )
    if not isinstance(orcid, str) or not orcid.strip():
        raise MintLoadError(
            f"{GATE1_RECORD_FILENAME} for {submission_id} missing 'orcid_id'."
        )
    bundle_dir = Path(bundle_dir_raw)
    title = _title_from_bundle(bundle_dir) or f"Submission {submission_id}"
    return _MintContext(
        submission_id=submission_id,
        title=title,
        corresponding_author_orcid=orcid,
        bundle_dir=bundle_dir,
    )


def mint_for_submission(
    submission_id: str,
    *,
    backend: Backend = "internal",
    home: Optional[Path] = None,
    now: Optional[datetime] = None,
    decision_record: Optional[dict] = None,
) -> PersistentId:
    """Mint a :class:`PersistentId` for ``submission_id``.

    Parameters
    ----------
    submission_id :
        The ``sub_YYYY_MM_DD_<hex>`` token written by M1.
    backend :
        Which :class:`IdMinter` backend to use. Defaults to
        ``"internal"`` so M4 can mint without any external auth.
    home :
        Override the submission-home root. ``None`` honours
        ``$SCITEX_AGENTIC_JOURNAL_HOME``; tests inject ``tmp_path``.
    now :
        Fallback for ``decided_at`` when no decision record is
        present. Tests inject a deterministic value.
    decision_record :
        Optional decision payload from M5 (#7). When present and it
        carries an ISO-8601 ``decided_at`` field, that timestamp is
        used as ``MintInput.decided_at``.

    Returns
    -------
    PersistentId
        The minted identifier + backend tag.

    Raises
    ------
    MintLoadError
        Submission directory or ``gate1.json`` is missing / malformed.
    """
    root = home if home is not None else _submission_home()
    payload = _load_gate1_payload(submission_id, root)
    ctx = _build_context(submission_id, payload)

    decided_at = _decided_at_from_records(decision_record, now)

    mint_input = MintInput(
        submission_id=ctx.submission_id,
        title=ctx.title,
        corresponding_author_orcid=ctx.corresponding_author_orcid,
        decided_at=decided_at,
    )
    minter = select_minter(backend)
    return minter.mint(mint_input)


def _decided_at_from_records(
    decision_record: Optional[dict],
    now: Optional[datetime],
) -> datetime:
    """Prefer a real decision timestamp; fall back to ``now`` then UTC now."""
    if isinstance(decision_record, dict):
        raw = decision_record.get("decided_at")
        if isinstance(raw, str) and raw.strip():
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                # Fall through to ``now`` below — a malformed decision
                # timestamp should not block minting; the operator can
                # see the bad value in the decision record itself.
                pass
    if now is not None:
        return now
    return datetime.now(timezone.utc)
