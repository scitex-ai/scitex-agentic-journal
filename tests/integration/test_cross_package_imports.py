"""PS-140 runtime gate — every cross-package module the source imports
must still be importable.

The audit rule (``scitex-dev ecosystem audit-project``) collects every
``scitex_<peer>`` / ``scitex.<peer>`` import that escapes the package's
own import root and requires this file to:

  1. exist at ``tests/integration/test_cross_package_imports.py``;
  2. expose a ``CROSS_PACKAGE_IMPORTS`` list literal naming every
     such cross-package module.

Without this file, a peer rename or move (e.g. ``scitex_io._load_cache``
in 2026-05) surfaces as a silent ``ModuleNotFoundError`` at user
runtime instead of breaking CI here first.

If a new cross-package import is added to ``src/scitex_agentic_journal``,
append it to the list below. To regenerate from scratch, see the audit
diagnostic which lists the missing names explicitly.
"""

from __future__ import annotations

import importlib

import pytest

# Single source of truth — keep in sync with the audit-detected set.
# `scitex_dev._cli._completion.attach_shell_completion` is wired by
# `_cli.py` to add `<TAB>` completion to the console script.
CROSS_PACKAGE_IMPORTS: list[str] = [
    "scitex_dev._cli._completion",
]


@pytest.mark.parametrize("module_name", CROSS_PACKAGE_IMPORTS)
def test_each_declared_cross_package_module_loads_without_raising(
    module_name: str,
) -> None:
    """Importing each declared cross-package module returns a module
    object — a peer rename/move would surface as ``ModuleNotFoundError``
    here instead of at user runtime (the PS-140 doctrine).
    """
    # Arrange
    name = module_name
    # Act
    module = importlib.import_module(name)
    # Assert
    assert module is not None
