"""Submission identity validation never turns untrusted identifiers into paths."""

import pytest

from scitex_agentic_journal._submit._ids import validate_submission_id


@pytest.mark.parametrize(
    "value", ["../bob", "a/b", "a\\b", "", ".", "x" * 129, " leading"]
)
def test_invalid_identifier_rejected(value):
    # Arrange
    invalid = value
    # Act
    # Assert
    with pytest.raises(ValueError):
        validate_submission_id(invalid)


@pytest.mark.parametrize("value", ["sub_2026_06_13_123abc", "sub-opaque", "A1"])
def test_existing_and_content_identifiers_remain_valid(value):
    # Arrange
    existing = value
    # Act
    result = validate_submission_id(existing)
    # Assert
    assert result == value
