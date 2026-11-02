"""Demo-content loader — materialize the shared example project.

``example-project-mnist`` is the fleet-wide example research project
(living in user space, e.g. ``~/proj/example-project-mnist``) that
every SciTeX app uses to demonstrate its surface. This module loads
its submission bundle into the journal archive through the SAME
records a real Gate-1 pass persists — deterministic pure
construction, no network, no reviewer run — so the archive,
validator, dashboard and share views render genuine content instead
of the wired-but-empty placeholder.

Every record carries ``"example": true`` and the submission id is the
fixed ``example-project-mnist`` (never a minted ``sub_*`` id), so
demo content is unmistakable. Loading is explicit (button / POST)
and idempotent: reloading rewrites the same record dir, mirroring
the hub double-submit rule.

Django-free (like :mod:`scitex_agentic_journal._django._leaf`) so
unit tests exercise it with ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from scitex_agentic_journal._gate1 import ClewVerification, OrcidRecord
from scitex_agentic_journal._submit import (
    Gate1Verdict,
    load_submission,
    persist_verdict,
)

EXAMPLE_SUBMISSION_ID = "example-project-mnist"
"""Fixed submission id for the demo record (never minted, never duplicated)."""

EXAMPLE_BUNDLE_ENV = "SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE"
"""Env var overriding where the example bundle lives (tests, demos)."""

EXAMPLE_PERSISTENT_ID = "doi:10.5555/example-project-mnist"
"""Reserved-prefix demo DOI (10.5555 is the documentation example block)."""


class ExampleConflict(ValueError):
    """An existing directory cannot safely be replaced by example records."""


def _check_example_target(target):
    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink() or not target.is_dir():
        raise ExampleConflict("Existing example target must be preserved")
    allowed = {"gate1.json", "decision.json", "persistent_id.json"}
    for path in target.iterdir():
        if path.name not in allowed or path.is_symlink() or not path.is_file():
            raise ExampleConflict("Unexpected example content must be preserved")
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError, UnicodeError) as exc:
            raise ExampleConflict(
                "Unreadable example content must be preserved"
            ) from exc
        block = payload.get("record", payload) if isinstance(payload, dict) else {}
        if not isinstance(block, dict) or block.get("example") is not True:
            raise ExampleConflict("Non-example records must be preserved")


class ExampleUnavailable(FileNotFoundError):
    """The example bundle is not installed where the loader looked."""


#: Operator's user-space checkout on compute-03 — the documented fleet
#: location of the shared example project. Last resort only: the env
#: var wins, then the process home. ``$SCITEX_FLEET_HOME`` (default
#: ``/home/ywatanabe``) keeps the fallback testable off-fleet.
#: Graceful 404 everywhere else.
def _fleet_fallback_bundle_dir() -> Path:
    return (
        Path(os.environ.get("SCITEX_FLEET_HOME", "/home/ywatanabe"))
        / "proj"
        / EXAMPLE_SUBMISSION_ID
    )


def _candidate_bundle_dirs() -> list[Path]:
    """Where the example project may live, in priority order.

    ``/example-project-mnist`` is the intended dev-service container
    path (read-only mount to be added in hub ``docker_dev``, the
    ``paper-scitex-clew`` precedent); the env var and process home
    cover standalone runs, and the fleet fallback covers compute-03.
    """
    candidates = []
    explicit = os.environ.get(EXAMPLE_BUNDLE_ENV)
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(Path.home() / "proj" / EXAMPLE_SUBMISSION_ID)
    container = Path("/") / EXAMPLE_SUBMISSION_ID
    if container not in candidates:
        candidates.append(container)
    fallback = _fleet_fallback_bundle_dir()
    if fallback not in candidates:
        candidates.append(fallback)
    return candidates


def default_example_bundle_dir() -> Path:
    """First existing candidate, else the primary default (for errors)."""
    candidates = _candidate_bundle_dirs()
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    explicit = os.environ.get(EXAMPLE_BUNDLE_ENV)
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / "proj" / EXAMPLE_SUBMISSION_ID


def load_example_project(
    bundle_dir: Path | str | None = None,
    *,
    home: Path | None = None,
    now=None,
) -> dict[str, Any]:
    """Materialize the example bundle as one labeled demo submission.

    Validates the real ``bundle.yaml`` via :func:`load_submission`,
    persists a real-shaped Gate-1 record via :func:`persist_verdict`
    (pure construction — Gate-1 itself is NOT executed), renames the
    record dir to the fixed example id, and adds the labeled demo
    decision + persistent-id records the dashboard / share views read.

    Raises
    ------
    ExampleUnavailable
        No bundle directory at the resolved location.
    SubmissionLoadError
        The bundle manifest is malformed (same contract as submit).
    """
    bundle = (
        Path(bundle_dir).expanduser()
        if bundle_dir is not None
        else default_example_bundle_dir()
    )
    if not bundle.is_dir():
        tried = ", ".join(str(p) for p in _candidate_bundle_dirs())
        raise ExampleUnavailable(
            f"example bundle not found at {bundle} (tried: {tried}) — set "
            f"${EXAMPLE_BUNDLE_ENV} to the {EXAMPLE_SUBMISSION_ID} "
            "checkout, or create it there."
        )
    from ._leaf import _submission_home

    _check_example_target(
        _submission_home(home) / "submissions" / EXAMPLE_SUBMISSION_ID
    )
    submission = load_submission(bundle)
    verdict = Gate1Verdict(
        submission=submission,
        orcid_record=OrcidRecord(
            orcid_id=submission.orcid_id,
            given_name="Example",
            family_name="Author",
            credit_name="Example Author",
        ),
        code_repo_head_commit="example",
        code_repo_head_subject="example bundle — gate-1 not executed",
        clew_verification=ClewVerification(
            project_dir=submission.clew_project_dir,
            green_claims=("claim-mnist-accuracy",),
            red_claims=(),
            total_claims=1,
            raw_stdout="example record — clew not executed",
        ),
    )
    persisted = persist_verdict(verdict, home=home, now=now, key=EXAMPLE_SUBMISSION_ID)
    target = persisted.record_dir.parent / EXAMPLE_SUBMISSION_ID
    if target.is_dir():
        shutil.rmtree(target)
    persisted.record_dir.rename(target)
    gate1_path = target / "gate1.json"
    gate1_payload = json.loads(gate1_path.read_text(encoding="utf-8"))
    gate1_payload["example"] = True
    gate1_payload["note"] = "demo record — gate-1 checks not executed"
    gate1_path.write_text(
        json.dumps(gate1_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    (target / "decision.json").write_text(
        json.dumps(
            {
                "record": {
                    "verdict": "accept",
                    "example": True,
                    "note": "demo record — editorial decision not run",
                }
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (target / "persistent_id.json").write_text(
        json.dumps(
            {
                "record": {
                    "persistent_id": EXAMPLE_PERSISTENT_ID,
                    "example": True,
                }
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {
        "submission_id": EXAMPLE_SUBMISSION_ID,
        "example": True,
        "records": ["gate1.json", "decision.json", "persistent_id.json"],
    }
