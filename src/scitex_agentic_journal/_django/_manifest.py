"""Manifest helpers — Django-free.

The manifest follows the scitex-sdk app contract
(``scitex_sdk.app.appmaker._validate._manifest``): the required keys
are exactly ``name`` / ``slug`` / ``label`` / ``pip_package`` /
``icon`` / ``license``; a hand-written ``version`` is FORBIDDEN (the
version derives at runtime from the installed ``pip_package`` dist);
``scope`` is optional with a closed ``user`` | ``project`` enum
(absent means ``user``).

This module mirrors those rules without importing scitex-sdk so the
leaf stays importable (and hub-mountable) where the SDK isn't
installed. The AppConfig always runs :func:`load_manifest`, so the
fallback never silently loses validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, TypedDict

APP_NAME: Final[str] = "scitex_agentic_journal._django"
"""Dotted-path INSTALLED_APPS entry."""

APP_LABEL: Final[str] = "scitex_agentic_journal"
"""Django app label; must be a valid Python identifier (no dots)."""

APP_MANIFEST_PATH: Final[Path] = Path(__file__).with_name("manifest.json")
"""On-disk path to ``manifest.json`` shipped via package-data."""

REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"name", "slug", "label", "pip_package", "icon", "license"}
)
"""Required manifest keys — mirrors the SDK's MANIFEST_REQUIRED_KEYS."""

VALID_SCOPES: Final[frozenset[str]] = frozenset({"user", "project"})
"""Closed ``scope`` enum — mirrors the SDK's _app_scope contract."""


class _ManifestRequired(TypedDict):
    """The SDK's required six — always present after validation."""

    name: str
    slug: str
    label: str
    pip_package: str
    icon: str
    license: str


class ManifestDict(_ManifestRequired, total=False):
    """Typed view of ``manifest.json`` (plus optional SDK keys)."""

    scope: str
    description: str
    homepage: str


def load_manifest(path: Path | None = None) -> ManifestDict:
    """Load and validate the manifest. Raises on schema drift.

    No silent fallback to a hard-coded dict: if the manifest goes
    missing, loses a required key, declares a hand-written
    ``version``, or carries an unknown ``scope``, we want the
    deployment to fail at start-up, not lie to operators about the
    app surface.
    """
    real_path = path or APP_MANIFEST_PATH
    if not real_path.exists():
        raise FileNotFoundError(f"agentic-journal manifest missing at {real_path}")
    body = json.loads(real_path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise KeyError(f"agentic-journal manifest at {real_path} must be a JSON object")
    missing = sorted(REQUIRED_KEYS - body.keys())
    if missing:
        raise KeyError(
            f"agentic-journal manifest at {real_path} is missing required keys: "
            f"{missing}"
        )
    if "version" in body:
        raise ValueError(
            f"agentic-journal manifest at {real_path} must NOT declare 'version' — "
            "it drifts from the package. The version derives at runtime from "
            "the installed 'pip_package' (importlib.metadata)."
        )
    scope = body.get("scope")
    if scope is not None and scope not in VALID_SCOPES:
        raise ValueError(
            f"agentic-journal manifest at {real_path} has unknown scope {scope!r} — "
            f"expected one of {sorted(VALID_SCOPES)}."
        )
    return body  # type: ignore[return-value]
