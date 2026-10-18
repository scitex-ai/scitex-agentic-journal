"""Versioned editorial decision rules.

Each version is a sibling YAML file (``v1.yaml``, ``v2.yaml``, ...).
A version is **immutable** once a decision record is written against
it — rule drift would break record reproducibility.

The Python decision engine consumes these files via
:func:`scitex_agentic_journal._decide._rules.load_rules`; this
package only carries the YAML so it ships in the wheel
(`pyproject.toml`'s `[tool.setuptools.package-data]` lists
``_decide/rules/**/*``).
"""
