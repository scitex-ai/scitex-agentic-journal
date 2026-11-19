"""Record helpers: id validation and atomic, hashable records."""

from __future__ import annotations

import pytest

from scitex_agentic_journal._records import (
    RecordError,
    canonical_json,
    read_record,
    submission_dir,
    write_record,
)


@pytest.mark.parametrize("bad", ["aj-0123456789abcdef\n", "../aj-0123456789abcdef", "aj-XYZ"])
def test_malformed_submission_ids_are_refused(tmp_path, bad):
    # Arrange
    home = tmp_path
    # Act
    call = lambda: submission_dir(bad, home)  # noqa: E731
    # Assert
    with pytest.raises(RecordError):
        call()


def test_written_record_round_trips(tmp_path):
    # Arrange
    path = tmp_path / "r.json"
    write_record(path, {"b": 1, "a": [1, 2]})
    # Act
    loaded = read_record(path)
    # Assert
    assert canonical_json(loaded) == canonical_json({"a": [1, 2], "b": 1})
