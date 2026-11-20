"""Host-side path handling over trees author code may have written (real files)."""

from __future__ import annotations

import hashlib
import os
import stat

import pytest
from scitex_agentic_journal._admission._paths import (
    force_rmtree,
    read_nofollow,
    remove_nofollow,
    safe_relpath,
    sha256_nofollow,
)


@pytest.mark.parametrize(
    "rel", ["/abs", "../up", "a/../b", "a//b", "a\\b", "C:x", "", "./a", "a/\x00"]
)
def test_unsafe_relative_path_is_refused(rel):
    # Arrange
    candidate = rel
    # Act
    safe = safe_relpath(candidate)
    # Assert
    assert safe is None


def test_plain_relative_path_is_kept():
    # Arrange
    rel = "results/out/metrics.json"
    # Act
    safe = safe_relpath(rel)
    # Assert
    assert str(safe) == rel


def test_regular_file_is_hashed(tmp_path):
    # Arrange
    (tmp_path / "f.txt").write_bytes(b"42\n")
    # Act
    digest = sha256_nofollow(tmp_path, "f.txt")
    # Assert
    assert digest == hashlib.sha256(b"42\n").hexdigest()


def test_symlinked_file_is_not_hashed(tmp_path):
    # Arrange
    (tmp_path / "real.txt").write_bytes(b"42\n")
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
    # Act
    digest = sha256_nofollow(tmp_path, "link.txt")
    # Assert
    assert digest is None


def test_file_below_a_symlinked_directory_is_not_hashed(tmp_path):
    # Arrange
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "f.txt").write_bytes(b"42\n")
    (tmp_path / "dir").symlink_to(tmp_path / "real")
    # Act
    digest = sha256_nofollow(tmp_path, "dir/f.txt")
    # Assert
    assert digest is None


def test_file_over_the_read_limit_is_not_read(tmp_path):
    # Arrange
    (tmp_path / "big.json").write_bytes(b"x" * 100)
    # Act
    data = read_nofollow(tmp_path, "big.json", limit=10)
    # Assert
    assert data is None


def test_removing_a_symlink_leaves_its_target(tmp_path):
    # Arrange
    (tmp_path / "keep.txt").write_bytes(b"keep")
    (tmp_path / "tree").mkdir()
    (tmp_path / "tree" / "out.txt").symlink_to(tmp_path / "keep.txt")
    # Act
    remove_nofollow(tmp_path / "tree", "out.txt")
    # Assert
    assert (tmp_path / "keep.txt").read_bytes() == b"keep"


def test_locked_directories_are_removed(tmp_path):
    # Arrange: author code may leave directories without write permission.
    locked = tmp_path / "run" / "locked"
    locked.mkdir(parents=True)
    (locked / "f.txt").write_bytes(b"x")
    os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
    # Act
    force_rmtree(tmp_path / "run")
    # Assert
    assert not (tmp_path / "run").exists()
