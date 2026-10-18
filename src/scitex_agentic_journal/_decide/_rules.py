"""Versioned YAML rules-set for the editorial decision engine.

The rules live as bundled package data under
``_decide/rules/<version>.yaml`` so they ship inside the wheel and an
operator can audit the exact threshold set their installed version
applies. The Python module exposes a typed :func:`load_rules` plus the
canonical :data:`RULES_VERSION` constant — the engine never reads the
file directly.

No silent thresholds: every numeric value in the YAML must be
surfaced into :attr:`RuleHit.message` by the engine so an auditor can
verify what the engine compared without re-reading the YAML.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Final

import yaml

RULES_VERSION: Final[str] = "v1"
"""Version stamp embedded in every :class:`DecisionRecord`.

Bump when the rule semantics change (new rule, removed rule, changed
threshold). Records produced under an older version remain valid
forever — re-deciding under a newer version produces a new record.
"""


_PACKAGE = "scitex_agentic_journal._decide.rules"
_FILENAME = f"{RULES_VERSION}.yaml"


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """Declarative shape of one rule loaded from the YAML rules-set."""

    rule_id: str
    verdict: str
    description: str


@dataclass(frozen=True, slots=True)
class RulesThresholds:
    """Numeric thresholds the engine compares against.

    Every numeric the engine uses MUST live here — no constants in
    Python code. The engine surfaces the value into RuleHit.message
    so the audit trail is self-explanatory.

    Attributes
    ----------
    novelty_revise_threshold :
        ``novelty.overlap_score >= this`` triggers a revise verdict.
    """

    novelty_revise_threshold: float


@dataclass(frozen=True, slots=True)
class RulesSet:
    """Full rules-set loaded from the bundled YAML.

    Attributes
    ----------
    version :
        Rules-set version (must equal :data:`RULES_VERSION`).
    thresholds :
        Numeric thresholds compared by the engine.
    rules :
        Ordered tuple of rule specs. Evaluation order matters:
        the first failing rule in the reject tier wins over later
        reject rules; reject wins over revise; revise wins over
        accept. The default-accept rule is always last.
    """

    version: str
    thresholds: RulesThresholds
    rules: tuple[RuleSpec, ...]


class RulesLoadError(RuntimeError):
    """Bundled rules YAML is missing, malformed, or has a wrong version."""


def load_rules() -> RulesSet:
    """Load the bundled ``v1.yaml`` rules-set into typed form.

    Returns
    -------
    RulesSet
        Frozen, typed rules-set. Safe to memoise — the YAML never
        changes at runtime.

    Raises
    ------
    RulesLoadError
        YAML is missing, has the wrong top-level shape, or declares
        a version mismatch with :data:`RULES_VERSION`.
    """
    try:
        text = resources.files(_PACKAGE).joinpath(_FILENAME).read_text(
            encoding="utf-8"
        )
    except FileNotFoundError as e:  # pragma: no cover - bundle bug
        raise RulesLoadError(
            f"bundled rules YAML {_FILENAME!r} is missing — the package "
            "was built without _decide/rules/ included."
        ) from e
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise RulesLoadError(
            f"bundled rules YAML {_FILENAME!r} is not valid YAML: {e}"
        ) from e
    if not isinstance(payload, dict):
        raise RulesLoadError(
            f"bundled rules YAML {_FILENAME!r} root must be a mapping."
        )
    version = payload.get("version")
    if version != RULES_VERSION:
        raise RulesLoadError(
            f"bundled rules YAML declares version {version!r}; expected "
            f"{RULES_VERSION!r}."
        )
    thresholds_block = payload.get("thresholds")
    if not isinstance(thresholds_block, dict):
        raise RulesLoadError(
            f"bundled rules YAML {_FILENAME!r} is missing the 'thresholds' "
            "mapping."
        )
    try:
        thresholds = RulesThresholds(
            novelty_revise_threshold=float(
                thresholds_block["novelty_revise_threshold"]
            ),
        )
    except KeyError as e:
        raise RulesLoadError(
            f"bundled rules YAML {_FILENAME!r} thresholds missing key {e!s}"
        ) from e
    rules_block = payload.get("rules")
    if not isinstance(rules_block, list) or not rules_block:
        raise RulesLoadError(
            f"bundled rules YAML {_FILENAME!r} 'rules' must be a non-empty list."
        )
    rules: list[RuleSpec] = []
    for entry in rules_block:
        if not isinstance(entry, dict):
            raise RulesLoadError(
                f"bundled rules YAML {_FILENAME!r} contains a non-mapping "
                f"rule entry: {entry!r}."
            )
        try:
            rules.append(
                RuleSpec(
                    rule_id=str(entry["id"]),
                    verdict=str(entry["verdict"]),
                    description=str(entry.get("description", "")).strip(),
                )
            )
        except KeyError as e:
            raise RulesLoadError(
                f"bundled rules YAML {_FILENAME!r} rule entry missing key {e!s}"
            ) from e
    return RulesSet(
        version=version,
        thresholds=thresholds,
        rules=tuple(rules),
    )
