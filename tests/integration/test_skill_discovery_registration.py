"""Installed leaf metadata registers guidance with the shared dispatcher."""

from __future__ import annotations

from importlib.metadata import distribution
import pytest


@pytest.mark.parametrize("group", ["scitex_dev.docs", "scitex_dev.skills"])
def test_installed_metadata_registers_skill_discovery(group):
    # Arrange
    installed = distribution("scitex-agentic-journal")
    # Act
    entries = {
        entry.name: entry.value
        for entry in installed.entry_points
        if entry.group == group
    }
    # Assert
    assert entries.get("scitex-agentic-journal") == "scitex_agentic_journal"
