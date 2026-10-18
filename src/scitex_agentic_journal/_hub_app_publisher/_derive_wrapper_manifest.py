"""Derive the hub-schema ``manifest.json`` from the upstream :data:`HUB_APP_MANIFEST`.

scitex-hub's ``app submit`` reads a workspace-UI-oriented
``manifest.json`` from the scaffold dir (per proj-scitex-hub's 2026-06-13
spec hand-off: ``apps/workspace/apps_app/views/api_registry.py::api_submit_jwt``
+ ADR-0002). Our upstream :data:`HUB_APP_MANIFEST` carries the same
authoritative values in a pip-package-oriented shape. The two are at
different layers; this helper maps one to the other so the scaffold
does not have to hand-fill values that already live upstream.

The mapping was agreed with proj-scitex-hub (msg 2a286d5d):

* ``display_name`` → ``label``
* ``description`` → ``subtitle`` (first sentence) + ``about`` +
  ``description`` (full text in both)
* ``requires[]`` (PEP 508) → ``dependencies.python[]`` (package names
  only — version specs dropped per hub-schema convention)
* ``permissions[]`` → ``privileges[]``
* ``python_requires`` → ``dependencies.python`` constraint (carried as
  the first array entry, prefixed ``python``)
* ``upstream`` → not mapped (upstream-only metadata)
* ``category="app"`` → handled at the hub-server side via the
  ``_app`` suffix on ``name`` (per PR #274); not copied to the
  output

This helper is intentionally pure — no I/O, no Django, no
scitex-hub imports. The scaffolder calls it, writes the returned
dict as JSON, and the hub server validates the file at
``app submit`` time.
"""

from __future__ import annotations

import re
from typing import Any, Final, Optional

from scitex_agentic_journal._hub_app_publisher._manifest import (
    HUB_APP_MANIFEST,
)


DEFAULT_HUB_SCHEMA_VERSION: Final[str] = "2.0.0"
"""scitex-hub workspace manifest schema version (proj-scitex-hub
confirmed 2026-06-13 ``$schema_version="2.0.0"`` is the in-flight
spec; bump when ADR-0002 promotes a new revision)."""


def _split_description(description: str) -> tuple[str, str]:
    """Split a multi-sentence description into ``(subtitle, full)``.

    ``subtitle`` takes the first sentence (terminated by ``.``, ``!``
    or ``?``); ``full`` is the whole text. Empty / sentence-less input
    yields ``("", description)``.
    """
    text = description.strip()
    if not text:
        return "", description
    # Match through the first sentence terminator. Greedy up to the
    # punctuation so abbreviations inside the sentence (e.g. "e.g.")
    # do not break the match.
    match = re.match(r"(?P<first>.+?[.!?])\s", text + " ")
    if match:
        first = match.group("first").strip()
    else:
        first = text
    return first, description


def _drop_version_spec(requirement: str) -> str:
    """Strip the PEP 508 version specifier from a single requirement.

    ``scitex-live-paper>=0.1.0a0`` → ``scitex-live-paper``. Mirrors the
    hub-schema convention that ``dependencies.python[]`` holds bare
    package names (versions live elsewhere). Conservative: only
    splits on the canonical specifier characters so an unusual
    requirement is left untouched.
    """
    # PEP 508 specifiers all start with a comparator character.
    return re.split(r"[<>=!~;\s\[]", requirement, maxsplit=1)[0].strip()


def derive_wrapper_manifest(
    *,
    label: Optional[str] = None,
    subtitle: Optional[str] = None,
    schema_version: str = DEFAULT_HUB_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Build the hub-schema ``manifest.json`` dict from :data:`HUB_APP_MANIFEST`.

    Parameters
    ----------
    label :
        Override for the workspace-UI label. ``None`` defaults to
        :data:`HUB_APP_MANIFEST` ``display_name``.
    subtitle :
        Override for the workspace-UI subtitle. ``None`` derives it
        from the first sentence of
        :data:`HUB_APP_MANIFEST` ``description``.
    schema_version :
        Workspace-manifest ``$schema_version`` to embed. Defaults to
        :data:`DEFAULT_HUB_SCHEMA_VERSION`. Overridable so a wrapper
        targeting an older / newer hub schema can bump without
        editing this module.

    Returns
    -------
    dict[str, Any]
        A JSON-serialisable dict matching the hub-schema. The
        scaffolder writes it to disk as the wrapper's
        ``manifest.json``.
    """
    description = HUB_APP_MANIFEST["description"]
    derived_subtitle, full_description = _split_description(description)

    requires: list[str] = list(HUB_APP_MANIFEST.get("requires", []))
    python_packages = [_drop_version_spec(r) for r in requires]
    # Prepend the Python-runtime constraint so the wrapper's
    # ``dependencies.python`` carries it alongside the pip names.
    python_packages.insert(0, "python" + HUB_APP_MANIFEST["python_requires"])

    return {
        "$schema_version": schema_version,
        "name": HUB_APP_MANIFEST["name"],
        "label": label or HUB_APP_MANIFEST["display_name"],
        "subtitle": subtitle if subtitle is not None else derived_subtitle,
        "about": full_description,
        "description": full_description,
        "dependencies": {
            "python": python_packages,
        },
        "privileges": list(HUB_APP_MANIFEST.get("permissions", [])),
    }
