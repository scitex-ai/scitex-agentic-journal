"""Single-component identifiers shared by persistence and web record readers."""

import re


def validate_submission_id(value: str) -> str:
    """Reject traversal, aliases and unsupported identifiers before joining paths."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value
    ):
        raise ValueError("Invalid journal submission identifier")
    return value
