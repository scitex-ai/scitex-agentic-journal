"""Manifest helpers — Django-free.

The manifest is consumed by the SciTeX Hub app-store loader, by docs
generators, and by Django's AppConfig. None of those should require
each other to import.
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


class ManifestDict(TypedDict):
    """Typed view of ``manifest.json``."""

    app: str
    label: str
    title: str
    icon: str
    mount: str
    permissions: list[str]
    version: str


def load_manifest(path: Path | None = None) -> ManifestDict:
    """Load and validate the manifest. Raises on schema drift.

    No silent fallback to a hard-coded dict: if the manifest goes
    missing or its required keys disappear we want the deployment
    to fail at start-up, not lie to operators about the app surface.
    """
    real_path = path or APP_MANIFEST_PATH
    if not real_path.exists():
        raise FileNotFoundError(f"agentic-journal manifest missing at {real_path}")
    body = json.loads(real_path.read_text(encoding="utf-8"))
    required = {"app", "label", "title", "icon", "mount", "permissions", "version"}
    missing = sorted(required - body.keys())
    if missing:
        raise KeyError(
            f"agentic-journal manifest at {real_path} is missing required keys: "
            f"{missing}"
        )
    return body  # type: ignore[return-value]
