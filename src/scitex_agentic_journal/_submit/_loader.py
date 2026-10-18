"""Load + validate ``<bundle>/bundle.yaml`` into a :class:`Submission`.

Schema-strict by design: every gate-1 input is required, and the
loader raises :class:`SubmissionLoadError` with an actionable message
on every malformed-manifest path. No silent defaults beyond
``clew_project_path`` falling back to the bundle root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scitex_agentic_journal._submit._types import Submission

MANIFEST_FILENAME = "bundle.yaml"
"""Canonical filename for the submission manifest inside a bundle."""

_REQUIRED_FIELDS = ("orcid_id", "code_repo_url")
"""Manifest keys that must be present for Gate-1 to run at all."""


class SubmissionLoadError(Exception):
    """Bundle / manifest is missing, unparseable, or under-specified."""


def _read_yaml_text(text: str, manifest_path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SubmissionLoadError(
            f"manifest {manifest_path} is not valid YAML: {e}"
        ) from e
    if payload is None:
        raise SubmissionLoadError(
            f"manifest {manifest_path} is empty — expected at least "
            f"`orcid_id:` and `code_repo_url:`."
        )
    if not isinstance(payload, dict):
        raise SubmissionLoadError(
            f"manifest {manifest_path} must be a YAML mapping at the "
            f"top level; got {type(payload).__name__}."
        )
    return payload


def _require_string(payload: dict[str, Any], key: str, manifest_path: Path) -> str:
    if key not in payload:
        raise SubmissionLoadError(
            f"manifest {manifest_path} is missing required key {key!r}."
        )
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise SubmissionLoadError(
            f"manifest {manifest_path} key {key!r} must be a non-empty "
            f"string; got {value!r}."
        )
    return value.strip()


def _resolve_clew_project_dir(
    payload: dict[str, Any], bundle_dir: Path, manifest_path: Path
) -> Path:
    if "clew_project_path" not in payload:
        return bundle_dir
    raw = payload["clew_project_path"]
    if not isinstance(raw, str) or not raw.strip():
        raise SubmissionLoadError(
            f"manifest {manifest_path} key 'clew_project_path' must be "
            f"a non-empty string when present; got {raw!r}."
        )
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (bundle_dir / candidate).resolve()
    return candidate


def load_submission(bundle_dir: Path | str) -> Submission:
    """Parse ``<bundle_dir>/bundle.yaml`` into a :class:`Submission`.

    Parameters
    ----------
    bundle_dir :
        Path to a directory containing a ``bundle.yaml`` manifest.

    Returns
    -------
    Submission
        Frozen dataclass with resolved absolute paths.

    Raises
    ------
    SubmissionLoadError
        - bundle_dir does not exist or is not a directory.
        - manifest is missing, empty, non-YAML, non-mapping, or
          missing a required key.
        - `clew_project_path` is set to a non-string / empty value.

    Notes
    -----
    The loader does not validate the *values* — it only enforces the
    schema. ``verify_orcid`` raises on a malformed ORCID id;
    ``cloned_code_repo`` raises on an unreachable URL; ``verify_clew_dag``
    raises on a bundle that lacks a ``.clew/`` marker. Errors surface
    at gate execution time with the proper structured ``GateFailure``.
    """
    root = Path(bundle_dir).expanduser().resolve()
    if not root.exists():
        raise SubmissionLoadError(
            f"bundle directory does not exist: {root}"
        )
    if not root.is_dir():
        raise SubmissionLoadError(
            f"bundle path is not a directory: {root}"
        )
    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise SubmissionLoadError(
            f"bundle is missing the {MANIFEST_FILENAME} manifest: "
            f"{manifest_path}"
        )
    payload = _read_yaml_text(
        manifest_path.read_text(encoding="utf-8"), manifest_path
    )
    for key in _REQUIRED_FIELDS:
        _require_string(payload, key, manifest_path)
    return Submission(
        bundle_dir=root,
        orcid_id=_require_string(payload, "orcid_id", manifest_path),
        code_repo_url=_require_string(payload, "code_repo_url", manifest_path),
        clew_project_dir=_resolve_clew_project_dir(payload, root, manifest_path),
    )
