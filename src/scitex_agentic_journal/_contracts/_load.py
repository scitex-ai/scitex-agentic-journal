"""Load contract schemas from package data and validate instances.

Vendored files are checked against the SHA-256 recorded in
``VENDORED.json`` every time they are loaded, so an edited copy fails
loudly instead of silently changing the contract.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

_PKG = "scitex_agentic_journal._contracts"


class ContractError(RuntimeError):
    """A contract file is missing, unreadable or does not match its pin."""


def _read(*parts: str) -> bytes:
    node = resources.files(_PKG)
    for part in parts:
        node = node.joinpath(part)
    try:
        return node.read_bytes()
    except FileNotFoundError as e:
        raise ContractError(f"contract file not packaged: {'/'.join(parts)}") from e


@cache
def _vendored_index(package: str) -> dict[str, Any]:
    return json.loads(_read("vendor", package, "VENDORED.json"))


def vendored_entry(package: str, filename: str) -> dict[str, Any]:
    """Return the ``VENDORED.json`` entry (ref, commit, sha256, ...) for a file."""
    files = _vendored_index(package)["files"]
    if filename not in files:
        raise ContractError(
            f"{package}/{filename} is not vendored; vendored: {sorted(files)}"
        )
    return files[filename]


@cache
def vendored_schema(package: str, filename: str) -> dict[str, Any]:
    """Load a vendored schema after checking it against its recorded hash."""
    entry = vendored_entry(package, filename)
    raw = _read("vendor", package, filename)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry["sha256"]:
        raise ContractError(
            f"vendored {package}/{filename} sha256 {digest} does not match the "
            f"pinned {entry['sha256']} (commit {entry['commit']}); re-vendor it "
            "instead of editing it."
        )
    schema = json.loads(raw)
    Draft202012Validator.check_schema(schema)
    return schema


@cache
def journal_schema(name: str) -> dict[str, Any]:
    """Load a journal-owned schema, e.g. ``journal_schema("submission")``."""
    schema = json.loads(_read("schemas", f"{name}.schema.json"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Return every validation error as ``<json-path>: <message>``; empty if valid."""
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    return [f"{e.json_path}: {e.message}" for e in errors]
