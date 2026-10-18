"""Allow ``python -m scitex_agentic_journal``.

Delegates to the click group declared in :mod:`scitex_agentic_journal._cli`
so the module-execution path and the console script behave identically.
"""

from __future__ import annotations

from scitex_agentic_journal._cli import main


if __name__ == "__main__":  # pragma: no cover
    main()
