"""Load the on-disk records the publish hand-off needs.

M5 ("publish hand-off") consumes four JSON files written by upstream
stages under ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/``:

* ``gate1.json`` — written by ``scitex-agentic-journal submit`` (M1).
  Carries the manuscript / bundle path. The ``LivePaperBundle`` needs
  it as ``manuscript_dir``.
* ``review.json`` — written by ``scitex-agentic-journal review`` (M2).
  Its top-level ``content_hash`` (already prefixed ``sha256:``) is the
  ``review_record_id`` the bundle references.
* ``decision.json`` — written by ``scitex-agentic-journal decide``
  (M3 — issue #7, lands in a sibling PR). Its top-level
  ``content_hash`` is the ``decision_record_id`` and its ``verdict``
  must be ``"accept"``. M5 refuses to publish anything else.
* ``persistent_id.json`` — written by ``scitex-agentic-journal``
  (M4 — issue #8, lands in a sibling PR). Carries the minted
  ``persistent_id`` and the minter ``backend``.

The loader stays deliberately schema-loose w.r.t. M3 / M4: it reads
the JSON as plain dicts so this PR does not import their Python types.
Once #7 / #8 land, this stays compatible because both modules write
the exact keys we read here.

No silent fallback: each missing or malformed record raises a
:class:`PublishLoadError` whose message points at the upstream command
that produces it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class PublishLoadError(Exception):
    """A record required by ``publish`` is missing, unreadable, or has
    the wrong shape.

    Every raise call carries an actionable message naming the offending
    file and the upstream command that produces it, so the operator
    can fix the gap with one command.
    """


@dataclass(frozen=True, slots=True)
class PublishRecords:
    """The four loaded record handles M5 needs to build a bundle.

    Attributes
    ----------
    submission_id :
        The submission id (echoed for convenience — same string the
        caller passed in).
    manuscript_dir :
        Absolute path to the manuscript bundle directory, read from
        ``gate1.json``. The :class:`LivePaperBundle` carries this so
        the downstream renderer can read the LaTeX + assets directly.
    review_record_id :
        ``sha256:<hex>`` — the content hash of the review record. The
        renderer can dereference this to fetch the full review
        on its own schedule.
    decision_record_id :
        ``sha256:<hex>`` — the content hash of the decision record.
    persistent_id :
        The minted id string written by M4 (e.g.
        ``scitex-aj-20260613-foo-abcdef``).
    """

    submission_id: str
    manuscript_dir: Path
    review_record_id: str
    decision_record_id: str
    persistent_id: str


def _submission_home() -> Path:
    """Mirror the home-resolution in `_submit._persist` / `_review._persist`."""
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def _read_json(path: Path, *, missing_msg: str, role: str) -> dict:
    """Read a record file as JSON. Raise :class:`PublishLoadError` on any failure."""
    if not path.is_file():
        raise PublishLoadError(missing_msg)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PublishLoadError(
            f"{role} at {path} is not valid JSON: {e}"
        ) from e
    if not isinstance(payload, dict):
        raise PublishLoadError(
            f"{role} at {path} root is not a JSON object."
        )
    return payload


def load_submission_records(
    submission_id: str,
    *,
    home: Path | None = None,
) -> PublishRecords:
    """Load all four records needed to publish ``submission_id``.

    Parameters
    ----------
    submission_id :
        The ``sub_YYYY_MM_DD_<hex>`` token printed by
        ``scitex-agentic-journal submit``.
    home :
        Override the submission-home root. ``None`` falls back to
        ``$SCITEX_AGENTIC_JOURNAL_HOME`` / ``~/.scitex/agentic-journal``.

    Raises
    ------
    PublishLoadError
        Whenever a required record is absent, malformed, or the
        decision verdict is not ``"accept"``.
    """
    root = home if home is not None else _submission_home()
    submission_dir = root / "submissions" / submission_id
    if not submission_dir.is_dir():
        raise PublishLoadError(
            f"no persisted submission at {submission_dir} — run "
            "`scitex-agentic-journal submit` first."
        )

    # ----- gate1.json (manuscript / bundle dir) -----------------------------
    gate1_path = submission_dir / "gate1.json"
    gate1 = _read_json(
        gate1_path,
        missing_msg=(
            f"submission {submission_id} is missing its gate1.json "
            f"({gate1_path}) — re-run `scitex-agentic-journal submit`."
        ),
        role="gate1.json",
    )
    submission_block = gate1.get("submission")
    if not isinstance(submission_block, dict):
        raise PublishLoadError(
            f"gate1.json at {gate1_path} is missing its 'submission' "
            "block — it was not produced by the M1 orchestrator."
        )
    bundle_dir_raw = submission_block.get("bundle_dir")
    if not isinstance(bundle_dir_raw, str):
        raise PublishLoadError(
            f"gate1.json at {gate1_path} submission block has no "
            "'bundle_dir' string."
        )
    manuscript_dir = Path(bundle_dir_raw)

    # ----- review.json (review_record_id = content_hash) --------------------
    review_path = submission_dir / "review.json"
    review = _read_json(
        review_path,
        missing_msg=(
            f"submission {submission_id} is missing its review.json "
            f"({review_path}) — run `scitex-agentic-journal review` first."
        ),
        role="review.json",
    )
    review_record_id = review.get("content_hash")
    if not isinstance(review_record_id, str) or not review_record_id:
        raise PublishLoadError(
            f"review.json at {review_path} is missing its top-level "
            "'content_hash' — re-run `scitex-agentic-journal review`."
        )

    # ----- decision.json (decision_record_id + verdict gate) ----------------
    decision_path = submission_dir / "decision.json"
    decision = _read_json(
        decision_path,
        missing_msg=(
            f"submission {submission_id} is missing its decision.json "
            f"({decision_path}) — run `scitex-agentic-journal decide` first."
        ),
        role="decision.json",
    )
    decision_record_id = decision.get("content_hash")
    if not isinstance(decision_record_id, str) or not decision_record_id:
        raise PublishLoadError(
            f"decision.json at {decision_path} is missing its "
            "top-level 'content_hash' — re-run "
            "`scitex-agentic-journal decide`."
        )
    # The M3 persister puts ``verdict`` inside the ``record`` block (it
    # is a typed-record field, not envelope metadata). Read it there
    # first; fall back to the top level so older synthetic records
    # (and the M5 mocks built before M3 landed in develop) keep
    # loading. Either location wins; both is illegal only if they
    # disagree, in which case we trust the nested record because that
    # is what the persister actually writes today.
    record_block = decision.get("record") if isinstance(decision.get("record"), dict) else None
    verdict = None
    if record_block is not None:
        verdict = record_block.get("verdict")
    if verdict is None:
        verdict = decision.get("verdict")
    if verdict != "accept":
        raise PublishLoadError(
            f"submission {submission_id} cannot be published: "
            f"decision verdict is {verdict!r}, not 'accept'. Only "
            "accepted submissions hand off to scitex-live-paper."
        )

    # ----- persistent_id.json (minted id from M4) ---------------------------
    persistent_id_path = submission_dir / "persistent_id.json"
    minted = _read_json(
        persistent_id_path,
        missing_msg=(
            f"submission {submission_id} is missing its "
            f"persistent_id.json ({persistent_id_path}) — the M4 "
            "minting step must run before `publish`."
        ),
        role="persistent_id.json",
    )
    # Same pattern as ``decision.json`` above: the M4 persister wraps
    # the typed record under a ``record:`` block so ``persistent_id``
    # is nested. Read there first, top-level fall back for the M5
    # pre-M4 synthetic mocks.
    record_block = minted.get("record") if isinstance(minted.get("record"), dict) else None
    persistent_id = None
    if record_block is not None:
        persistent_id = record_block.get("persistent_id")
    if not isinstance(persistent_id, str) or not persistent_id:
        persistent_id = minted.get("persistent_id")
    if not isinstance(persistent_id, str) or not persistent_id:
        raise PublishLoadError(
            f"persistent_id.json at {persistent_id_path} is missing "
            "its 'persistent_id' string."
        )

    return PublishRecords(
        submission_id=submission_id,
        manuscript_dir=manuscript_dir,
        review_record_id=review_record_id,
        decision_record_id=decision_record_id,
        persistent_id=persistent_id,
    )


__all__ = [
    "PublishLoadError",
    "PublishRecords",
    "load_submission_records",
]
