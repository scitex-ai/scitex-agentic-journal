"""Tests for `_decide/_rules.py` — YAML rules-set loader."""

from __future__ import annotations

from scitex_agentic_journal._decide import (
    RULES_VERSION,
    RulesSet,
    RuleSpec,
    RulesThresholds,
    load_rules,
)


def test_rules_version_constant_is_v1() -> None:
    # Arrange
    expected = "v1"
    # Act
    version = RULES_VERSION
    # Assert
    assert version == expected


def test_load_rules_returns_rules_set_instance() -> None:
    # Arrange
    # Act
    rules = load_rules()
    # Assert
    assert isinstance(rules, RulesSet)


def test_load_rules_version_matches_constant() -> None:
    # Arrange
    # Act
    rules = load_rules()
    # Assert
    assert rules.version == RULES_VERSION


def test_load_rules_carries_thresholds_block() -> None:
    # Arrange
    # Act
    rules = load_rules()
    # Assert
    assert isinstance(rules.thresholds, RulesThresholds)


def test_load_rules_novelty_revise_threshold_is_declared() -> None:
    """The threshold MUST live in YAML, not in code (#7 acceptance)."""
    # Arrange
    # Act
    rules = load_rules()
    # Assert
    assert rules.thresholds.novelty_revise_threshold == 0.7


def test_load_rules_returns_non_empty_rule_list() -> None:
    # Arrange
    # Act
    rules = load_rules()
    # Assert
    assert len(rules.rules) > 0


def test_load_rules_entries_are_rule_spec_instances() -> None:
    # Arrange
    # Act
    rules = load_rules()
    # Assert
    assert all(isinstance(r, RuleSpec) for r in rules.rules)


def test_load_rules_includes_methodology_fatal_rule() -> None:
    # Arrange
    # Act
    rules = load_rules()
    ids = {r.rule_id for r in rules.rules}
    # Assert
    assert "methodology_fatal" in ids


def test_load_rules_includes_reproducibility_failed_rule() -> None:
    # Arrange
    # Act
    rules = load_rules()
    ids = {r.rule_id for r in rules.rules}
    # Assert
    assert "reproducibility_failed" in ids


def test_load_rules_includes_default_accept_anchor() -> None:
    # Arrange
    # Act
    rules = load_rules()
    ids = {r.rule_id for r in rules.rules}
    # Assert
    assert "default_accept" in ids


def test_load_rules_default_accept_is_last_rule() -> None:
    """Accept-anchor MUST be evaluated last so reject/revise wins first."""
    # Arrange
    # Act
    rules = load_rules()
    # Assert
    assert rules.rules[-1].rule_id == "default_accept"


def test_load_rules_each_rule_carries_verdict_tier() -> None:
    # Arrange
    allowed = {"accept", "revise", "reject"}
    # Act
    rules = load_rules()
    # Assert
    assert all(r.verdict in allowed for r in rules.rules)
