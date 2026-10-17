"""Clew-DAG presence + claim verification — gate-1 structural check.

This module implements :func:`verify_clew_dag`, which:

1. Locates a Clew project directory inside the submission bundle.
2. Shells out to the real ``clew dag --claims --json`` CLI (no mocks, no
   embedded re-implementation of Clew's DAG semantics).
3. Returns a structured :class:`ClewVerification` summarising green
   and red runs.
4. Raises :class:`GateFailure` when the bundle has no Clew project,
   the DAG covers zero runs, or every run is red — the conditions under
   which the submission cannot proceed to AI review.

The dependency direction is strict: we *consume* ``scitex-clew``'s
verification result. We do not redefine ``VerificationStatus`` and
we do not parse Clew's internal DAG format ourselves — the CLI is
the contract.

Targeted CLI surface: ``scitex-clew`` 0.21.0. The project marker is
``.scitex/clew/`` (what ``clew register-source`` writes); the legacy
``.clew/`` marker is still accepted. The every-claim JSON entry point
is ``clew dag --claims --json``; the legacy bare-list payload shape
(``[{\"id\": ..., \"status\": ...}]``) is still parsed so older
installs keep working.

Acceptance — issue #4 (M1.3):

- "Locate the Clew project directory inside the submission bundle."
  → :func:`_find_clew_project_dir` looks for the current
  ``.scitex/clew/`` marker (or the legacy ``.clew/`` marker) at the
  bundle root or one level down.
- "Invoke the every-claim verify entry point (real subprocess) and
  assert at least one run returns verified." → :func:`_run_clew_dag_verify`
  runs ``clew dag --claims --json``.
- "Return a structured ``GateFailure`` listing the failing claims
  if all are red." → :func:`verify_clew_dag` raises
  ``GateFailure("clew_dag", ...)`` enumerating non-verified run
  session ids in ``detail``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Sequence

from scitex_agentic_journal._gate1._errors import GateFailure

DEFAULT_VERIFY_TIMEOUT_S: Final[float] = 120.0
"""Hard ceiling for ``clew claim verify`` — the gate must not hang."""

CLEW_MARKER_DIR: Final[str] = ".clew"
"""Legacy marker: ``clew init`` wrote project metadata here. Still accepted."""

CLEW_STATE_DIR: Final[str] = ".scitex/clew"
"""Current marker (``scitex-clew`` 0.21.0): ``clew register-source`` writes
project state under ``<root>/.scitex/clew/``."""

CLEW_MARKER_DIRS: Final[tuple[str, ...]] = (CLEW_STATE_DIR, CLEW_MARKER_DIR)
"""Marker candidates, current first. Either one marks a Clew project."""


@dataclass(frozen=True)
class ClewVerification:
    """The structured outcome of running ``clew dag --claims``.

    Attributes
    ----------
    project_dir :
        Absolute path to the Clew project root we ran against.
    green_claims :
        Ordered list of verified run session ids (``scitex-clew``
        0.21.0 ``dag`` shape; claim ids on legacy installs).
    red_claims :
        Ordered list of non-verified run session ids.
    total_claims :
        ``len(green_claims) + len(red_claims)``. Stored explicitly so
        downstream callers do not need to recompute it.
    raw_stdout :
        The raw CLI stdout — kept for the editorial provenance record.
    """

    project_dir: Path
    green_claims: tuple[str, ...] = field(default_factory=tuple)
    red_claims: tuple[str, ...] = field(default_factory=tuple)
    total_claims: int = 0
    raw_stdout: str = ""


def _has_marker(candidate: Path) -> bool:
    """True when ``candidate`` carries any known Clew project marker."""
    return any((candidate / marker).is_dir() for marker in CLEW_MARKER_DIRS)


def _find_clew_project_dir(bundle_root: Path) -> Path:
    """Return the directory containing a Clew project marker.

    Search order:

    1. ``bundle_root`` itself.
    2. Each immediate child directory of ``bundle_root``.

    We refuse to descend further: a deeply-nested Clew project is a
    bundle-layout bug, not a happy-path. Raise :class:`GateFailure` if
    no candidate is found.
    """
    if not bundle_root.exists():
        raise GateFailure(
            "clew_dag",
            "submission bundle root does not exist",
            f"path: {bundle_root}",
        )
    if not bundle_root.is_dir():
        raise GateFailure(
            "clew_dag",
            "submission bundle root is not a directory",
            f"path: {bundle_root}",
        )
    if _has_marker(bundle_root):
        return bundle_root
    for child in sorted(bundle_root.iterdir()):
        if child.is_dir() and _has_marker(child):
            return child
    raise GateFailure(
        "clew_dag",
        "no Clew project found in submission bundle",
        (
            f"searched {bundle_root} and immediate children for "
            f"`{CLEW_STATE_DIR}/` (or legacy `{CLEW_MARKER_DIR}/`); none "
            "matched. Register the project (e.g. `clew register-source`) "
            "before submission."
        ),
    )


def _resolve_clew_binary(explicit: str | None) -> str:
    """Return the absolute path to a usable ``clew`` binary or raise."""
    if explicit:
        path = shutil.which(explicit) or (explicit if Path(explicit).is_file() else None)
        if not path:
            raise GateFailure(
                "clew_dag",
                "configured `clew` binary not found",
                f"requested: {explicit!r}",
            )
        return path
    path = shutil.which("clew")
    if not path:
        raise GateFailure(
            "clew_dag",
            "`clew` CLI not on PATH",
            (
                "Install `scitex-clew` (`pip install scitex-clew`) or set "
                "`SCITEX_AGENTIC_JOURNAL_CLEW_BIN` to an absolute path."
            ),
        )
    return path


_STORE_PROVISION_MARKERS: Final[tuple[str, ...]] = (
    "StoreProvisionError",
    "provision_store_acl",
)
"""stderr fragments proving the clew store is not provisioned.

``clew dag`` needs its PostgreSQL tables; when the store was never
provisioned the CLI dies with a traceback instead of JSON. Matching
on these fragments lets the gate name the real cause instead of
reporting "did not emit valid JSON"."""


def _run_clew_dag_verify(
    clew_bin: str,
    project_dir: Path,
    *,
    timeout_s: float,
) -> tuple[str, str, int]:
    """Return ``(stdout, stderr, returncode)`` from ``clew dag --claims --json``."""
    cmd = [clew_bin, "dag", "--claims", "--json"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except FileNotFoundError as e:
        raise GateFailure(
            "clew_dag",
            "`clew` binary disappeared between resolve and exec",
            f"{e}",
        ) from e
    except subprocess.TimeoutExpired as e:
        raise GateFailure(
            "clew_dag",
            f"`clew dag --claims` exceeded {timeout_s:.0f}s",
            f"cwd: {project_dir}",
        ) from e
    return result.stdout, result.stderr, result.returncode


def _raise_for_unprovisioned_store(stderr: str, project_dir: Path) -> None:
    """Raise the actionable store GateFailure when the markers match."""
    if any(marker in stderr for marker in _STORE_PROVISION_MARKERS):
        tail = stderr.strip().splitlines()[-1] if stderr.strip() else "<empty stderr>"
        raise GateFailure(
            "clew_dag",
            "clew store not provisioned for this project",
            (
                f"project: {project_dir}; clew refused before verifying: "
                f"{tail[:200]}. Run provision_store_acl through the "
                "authorized migration identity (infra), then resubmit."
            ),
        )


def _parse_dag_payload(payload: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(green_ids, red_ids)`` from a ``clew dag --json`` payload.

    Runs carry ``session_id`` + ``is_verified`` (``scitex-clew`` 0.21.0
    ``_dag_payload`` shape). A run counts green only when
    ``is_verified`` is literally true; anything else — including a
    missing flag — buckets red. Green entries surface the
    ``session_id`` so the failure detail names the exact runs.
    """
    runs = payload.get("runs", [])
    if not isinstance(runs, list):
        raise GateFailure(
            "clew_dag",
            "`clew dag --json` runs field is not a list",
            f"got: {type(runs).__name__}",
        )
    green: list[str] = []
    red: list[str] = []
    for i, run in enumerate(runs):
        if not isinstance(run, dict):
            raise GateFailure(
                "clew_dag",
                "run entry is not an object",
                f"entry index {i}: {run!r}",
            )
        run_id = str(run.get("session_id", f"<run-{i}>"))
        if run.get("is_verified") is True:
            green.append(run_id)
        else:
            red.append(run_id)
    return tuple(green), tuple(red)


def _parse_legacy_claims_payload(
    claims: list,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(green_ids, red_ids)`` from the legacy bare-list shape.

    Kept so installs older than 0.21.0 keep working: a top-level list
    (or ``{"claims": [...]}`` object) of ``{"id": ..., "status": ...}``
    entries. Any non-``"green"`` status (case-insensitive) buckets red.
    """
    green: list[str] = []
    red: list[str] = []
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise GateFailure(
                "clew_dag",
                "claim entry is not an object",
                f"entry index {i}: {claim!r}",
            )
        claim_id = str(claim.get("id", f"<claim-{i}>"))
        status = str(claim.get("status", "")).lower()
        if status == "green":
            green.append(claim_id)
        else:
            red.append(claim_id)
    return tuple(green), tuple(red)


def _parse_verification_payload(
    stdout: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(green_ids, red_ids)`` from a clew JSON stdout payload.

    Two shapes are accepted so that we tolerate Clew's evolving JSON
    schema across releases:

    1. ``clew dag --claims --json`` (0.21.0): an object with a
       ``runs`` list of ``{"session_id": ..., "is_verified": bool}``.
    2. Legacy: ``{"claims": [{"id": ..., "status": ...}]}`` or a bare
       ``[{"id": ..., "status": ...}]`` list.
    """
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise GateFailure(
            "clew_dag",
            "`clew dag --claims --json` did not emit valid JSON",
            f"first 200 chars of stdout: {stdout[:200]!r} (error: {e})",
        ) from e
    if isinstance(payload, dict) and "runs" in payload:
        return _parse_dag_payload(payload)
    if isinstance(payload, dict) and "claims" in payload:
        claims = payload["claims"]
    elif isinstance(payload, list):
        claims = payload
    else:
        raise GateFailure(
            "clew_dag",
            "`clew dag --claims --json` returned an unknown shape",
            f"top-level type: {type(payload).__name__}",
        )
    if not isinstance(claims, list):
        raise GateFailure(
            "clew_dag",
            "`clew dag --claims --json` claims field is not a list",
            f"got: {type(claims).__name__}",
        )
    return _parse_legacy_claims_payload(claims)


def verify_clew_dag(
    bundle_root: Path | str,
    *,
    clew_bin: str | None = None,
    timeout_s: float = DEFAULT_VERIFY_TIMEOUT_S,
) -> ClewVerification:
    """Run gate-1's Clew-DAG check on a submission bundle.

    Parameters
    ----------
    bundle_root :
        Path to the submission bundle (LaTeX + Clew project + assets).
        We locate the ``.clew/`` project under this root.
    clew_bin :
        Optional explicit path to the ``clew`` binary. When ``None`` we
        resolve from ``PATH``.
    timeout_s :
        Hard ceiling for the ``clew claim verify`` subprocess. Defaults
        to :data:`DEFAULT_VERIFY_TIMEOUT_S`.

    Returns
    -------
    ClewVerification
        On success — at least one green claim — the structured outcome.

    Raises
    ------
    GateFailure
        - No Clew project marker in the bundle.
        - ``clew`` binary not resolvable.
        - ``clew dag --claims`` timed out.
        - ``clew dag --claims --json`` emitted unparseable JSON.
        - Clew store not provisioned (actionable: infra migration identity).
        - Verification returned zero runs (DAG empty).
        - Verification returned runs but none verified.

    Notes
    -----
    The non-``green`` bucket is emitted verbatim in
    :attr:`GateFailure.detail` so the operator can see which claim ids
    blocked submission — this is the "list the failing claims" half of
    issue #4's acceptance criteria.
    """
    root = Path(bundle_root)
    project_dir = _find_clew_project_dir(root)
    resolved_bin = _resolve_clew_binary(clew_bin)
    stdout, stderr, returncode = _run_clew_dag_verify(
        resolved_bin, project_dir, timeout_s=timeout_s
    )
    _raise_for_unprovisioned_store(stderr, project_dir)
    green, red = _parse_verification_payload(stdout)
    total = len(green) + len(red)
    verification = ClewVerification(
        project_dir=project_dir,
        green_claims=green,
        red_claims=red,
        total_claims=total,
        raw_stdout=stdout,
    )
    if total == 0:
        raise GateFailure(
            "clew_dag",
            "Clew DAG present but verifies zero claims",
            (
                f"project: {project_dir}; `clew dag --claims` returncode={returncode}; "
                "submission requires the project to declare at least one claim."
            ),
        )
    if not green:
        raise GateFailure(
            "clew_dag",
            f"all {total} Clew claim(s) red",
            (
                f"project: {project_dir}; failing run session ids: "
                f"{', '.join(red) if red else '<none>'}; returncode={returncode}; "
                "Gate-1 requires at least one verified run."
            ),
        )
    # At least one green — gate passes regardless of `clew`'s exit code.
    # The CLI may return non-zero when *some* runs are red even though
    # others verified; gate-1 only cares about the >=1 verified floor.
    return verification


__all__: Sequence[str] = (
    "CLEW_MARKER_DIR",
    "CLEW_MARKER_DIRS",
    "CLEW_STATE_DIR",
    "ClewVerification",
    "DEFAULT_VERIFY_TIMEOUT_S",
    "verify_clew_dag",
)
