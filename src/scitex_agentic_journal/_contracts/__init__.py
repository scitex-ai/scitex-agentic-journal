"""Published contracts the journal consumes or emits, as JSON Schema.

Two kinds live here:

* **Vendored** schemas of other packages (``vendor/<package>/``), copied
  byte-for-byte at a pinned commit and recorded in ``VENDORED.json``. The
  journal never imports those packages; the schema is the contract.
* **Journal-owned** schemas (``schemas/``) for the records the journal
  writes, published in the wheel so other tools can consume them the same
  way.
"""

from __future__ import annotations

from scitex_agentic_journal._contracts._load import (
    ContractError,
    journal_schema,
    validate,
    vendored_entry,
    vendored_schema,
)

__all__ = [
    "ContractError",
    "journal_schema",
    "validate",
    "vendored_entry",
    "vendored_schema",
]
