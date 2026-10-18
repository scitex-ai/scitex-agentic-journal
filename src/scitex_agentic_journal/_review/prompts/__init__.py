"""Versioned reviewer prompts.

Each version is a sibling subdirectory (``v1/``, ``v2/``, ...). A
version is **immutable** once a record is written against it —
prompt drift would break record reproducibility.

The adapter is responsible for locating its prompt files; this
package only carries the markdown so they ship in the wheel
(`pyproject.toml`'s `[tool.setuptools.package-data]` already lists
``_review/prompts/**/*``).
"""
