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
    SubmissionLoadError,
    load_submission,
    persist_verdict,
)

EXAMPLE_SUBMISSION_ID = "example-project-mnist"
"""Fixed submission id for the demo record (never minted, never duplicated)."""

EXAMPLE_BUNDLE_ENV = "SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE"
"""Env var overriding where the example bundle lives (tests, demos)."""

EXAMPLE_PERSISTENT_ID = "doi:10.5555/example-project-mnist"
"""Reserved-prefix demo DOI (10.5555 is the documentation example block)."""


class ExampleUnavailable(FileNotFoundError):
    """The example bundle is not installed where the loader looked."""


def default_example_bundle_dir() -> Path:
    """Where the example project lives: env override, else ``~/proj``."""
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
    bundle = Path(bundle_dir).expanduser() if bundle_dir is not None else default_example_bundle_dir()
    if not bundle.is_dir():
        raise ExampleUnavailable(
            f"example bundle not found at {bundle} — set "
            f"${EXAMPLE_BUNDLE_ENV} to the {EXAMPLE_SUBMISSION_ID} "
            "checkout, or create it there."
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
    gate1_path.write_text(json.dumps(gate1_payload, indent=2, sort_keys=True), encoding="utf-8")
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
