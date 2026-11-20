"""Released Clew wire formats; importing Clew is unnecessary for validation."""

from __future__ import annotations

from typing import Any

from ._load import ContractError, validate, vendored_schema

PACKAGE = "scitex-clew"
SUPPORTED = {
    "evidence-bundle": {"1.0.0"},
    "rerun-report": {"1.0.0", "1.1.0"},
}


def contract_errors(document: dict[str, Any], kind: str) -> list[str]:
    """Check an exact released contract while preserving unknown extension keys."""
    version = document.get("schema_version")
    if not isinstance(version, str) or version not in SUPPORTED[kind]:
        return [f"unsupported {kind} schema_version {version!r}"]
    schema = vendored_schema(PACKAGE, f"{kind}.schema.{version}.json")
    errors = validate(document, schema)
    if errors:
        return errors
    # JSON Schema cannot express uniqueness by one property of array items.
    for collection, key in (("runs", "run_id"), ("claims", "claim_id")):
        ids = [entry[key] for entry in document[collection]]
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {key} in {collection}")
    return errors


__all__ = ["ContractError", "contract_errors"]
