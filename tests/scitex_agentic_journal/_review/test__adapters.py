"""Tests for `_review/_adapters.py` — provider-pluggable adapter registry."""

from __future__ import annotations

import pytest

from scitex_agentic_journal._review import (
    LocalDeterministicAdapter,
    QwenAdapterStub,
    ReviewerAdapter,
    UnknownAdapterError,
    list_adapter_names,
    select_adapter,
)


def test_select_adapter_local_returns_local_deterministic_instance() -> None:
    # Arrange
    name = "local"
    # Act
    adapter = select_adapter(name)
    # Assert
    assert isinstance(adapter, LocalDeterministicAdapter)


def test_select_adapter_qwen_returns_qwen_adapter_stub_instance() -> None:
    # Arrange
    name = "qwen"
    # Act
    adapter = select_adapter(name)
    # Assert
    assert isinstance(adapter, QwenAdapterStub)


def test_select_adapter_returned_instance_satisfies_reviewer_adapter_protocol() -> None:
    # Arrange
    name = "local"
    # Act
    adapter = select_adapter(name)
    # Assert
    assert isinstance(adapter, ReviewerAdapter)


def test_select_adapter_unknown_name_raises_unknown_adapter_error() -> None:
    # Arrange
    name = "no-such-provider"
    # Act
    ctx = pytest.raises(UnknownAdapterError)
    # Assert
    with ctx:
        select_adapter(name)


def test_select_adapter_unknown_error_message_lists_available_names() -> None:
    # Arrange
    name = "no-such-provider"
    # Act
    captured: UnknownAdapterError | None = None
    try:
        select_adapter(name)
    except UnknownAdapterError as e:
        captured = e
    # Assert
    assert captured is not None and "available:" in str(captured)


def test_list_adapter_names_includes_local_and_qwen() -> None:
    # Arrange
    expected = {"local", "qwen"}
    # Act
    names = set(list_adapter_names())
    # Assert
    assert expected.issubset(names)


def test_list_adapter_names_returns_sorted_tuple() -> None:
    # Arrange
    names = list_adapter_names()
    # Act
    is_sorted = list(names) == sorted(names)
    # Assert
    assert is_sorted
