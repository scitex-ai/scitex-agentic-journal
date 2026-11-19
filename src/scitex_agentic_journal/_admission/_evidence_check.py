"""Record portable evidence format/binding separately from runtime verification."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ._checks import FAILED, NOT_RUN, PASSED, record
from ._paths import nofollow_path
from ._replay_verify import submission_binding


def check_evidence_bundle(
    project: Path | None,
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """Validate the checkout's portable contract without executing author code.

    The repository check pins the checkout commit. This check certifies only
    the evidence format and main-claim binding, never signatures or file hashes.
    Its optional admission status preserves the current journal policy.
    """
    from ._executor import EVIDENCE_BUNDLE, load_bundle

    name = "evidence-bundle"
    tool = {"name": "scitex-clew.evidence-bundle", "version": "1.0.0"}
    if project is None:
        return record(
            name, NOT_RUN, "repository checkout is unavailable", required=False
        )
    located = nofollow_path(project, EVIDENCE_BUNDLE.as_posix())
    if located is not None and not os.path.lexists(located):
        return record(
            name,
            NOT_RUN,
            "the snapshot has no portable Clew evidence bundle",
            required=False,
            tool=tool,
        )
    document, digest, problem = load_bundle(project)
    if document is None:
        return record(name, FAILED, problem, required=False, tool=tool)
    mismatches = submission_binding(document, report, list(manifest["main_claims"]))
    details = {
        "bundle_sha256": digest,
        "main_claims": list(manifest["main_claims"]),
        "binding_errors": mismatches,
        "signature_present": "signature" in document,
        "signature_verified": False,
        "file_hashes_verified": False,
    }
    if mismatches:
        return record(
            name,
            FAILED,
            "portable evidence disagrees with submitted main claims",
            required=False,
            tool=tool,
            details=details,
        )
    return record(
        name,
        PASSED,
        "released evidence format and main-claim binding validated",
        required=False,
        tool=tool,
        details=details,
    )
