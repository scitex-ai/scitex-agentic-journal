"""Tests for ``_gate1._code_repo.clone_code_repo`` + ``cloned_code_repo``.

Discipline (STX-NM001-003 / PA-306, "no mocks"):

- Production path shells out to the real ``git`` binary. We do not
  patch ``subprocess``, do not stub ``git``, do not inject a fake
  binary on ``PATH``.
- For hermetic CI we create a **real local bare git repository** in a
  pytest tempdir, push one real commit into it, and clone via the
  ``file://`` URL. Real ``git``, real subprocess, real disk.
- The "git not on PATH" branch is exercised by editing ``os.environ``
  directly (try/finally save-and-restore via ``_saved_env``) rather
  than ``monkeypatch``: ``monkeypatch`` is a forbidden fixture
  parameter under PA-306. PATH editing is *configuration of where the
  binary is looked up*, not a stub of the binary itself.
- One opt-in ``@pytest.mark.network`` test clones a real GitHub
  repository when ``SCITEX_RUN_NETWORK_TESTS=1``.

Structure (STX-TQ rules):

- Every test carries the three ``# Arrange`` / ``# Act`` / ``# Assert``
  markers on separate lines in that order.
- Each test asserts exactly one fact (``with pytest.raises(...)``
  counts as one assertion and is never paired with a trailing
  ``assert``).
- Test names spell out subject + condition + expected behaviour
  (≥3 word-tokens after ``test_``).
"""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from scitex_agentic_journal._gate1 import (
    ClonedRepo,
    GateFailure,
    clone_code_repo,
    cloned_code_repo,
)


# ---------------------------------------------------------------------------
# Local bare-repo fixture — real git, real commit, real file:// URL.
# ---------------------------------------------------------------------------


def _run_git(*args: str, cwd: Path | None = None) -> None:
    """Run real git, raise on failure. Used only by the fixture builder."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "HOME": "/tmp",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def bare_repo_url(tmp_path: Path) -> str:
    """Build a real bare git repo with one commit; yield its ``file://`` URL."""
    seed = tmp_path / "seed"
    bare = tmp_path / "bare.git"
    seed.mkdir()
    (seed / "README.md").write_text("# fixture\n")
    _run_git("init", "-q", "-b", "main", str(seed))
    _run_git("add", "README.md", cwd=seed)
    _run_git("commit", "-q", "-m", "fixture: seed commit", cwd=seed)
    _run_git("init", "-q", "--bare", "-b", "main", str(bare))
    _run_git("remote", "add", "origin", str(bare), cwd=seed)
    _run_git("push", "-q", "origin", "main", cwd=seed)
    _run_git("symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)
    return f"file://{bare}"


@contextmanager
def _saved_env(name: str, new_value: str | None) -> Iterator[None]:
    """Set / unset an env var, restore on exit. No monkeypatch dependency."""
    sentinel = object()
    original = os.environ.get(name, sentinel)
    if new_value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = new_value
    try:
        yield
    finally:
        if original is sentinel:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# clone_code_repo — pre-flight validation.
# ---------------------------------------------------------------------------


def test_clone_code_repo_rejects_empty_url_with_gate_failure(
    tmp_path: Path,
) -> None:
    # Arrange
    dest = tmp_path / "dest"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        clone_code_repo("", dest)


def test_clone_code_repo_rejects_whitespace_only_url(tmp_path: Path) -> None:
    # Arrange
    dest = tmp_path / "dest"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        clone_code_repo("   \n", dest)


def test_clone_code_repo_refuses_pre_existing_destination_path(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "preexisting"
    dest.mkdir()
    # Act
    # Assert
    with pytest.raises(GateFailure):
        clone_code_repo(bare_repo_url, dest)


def test_clone_code_repo_leaves_pre_existing_destination_untouched(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "preexisting"
    dest.mkdir()
    try:
        clone_code_repo(bare_repo_url, dest)
    except GateFailure:
        pass
    # Act
    surviving_entries = list(dest.iterdir())
    # Assert
    assert surviving_entries == []


# ---------------------------------------------------------------------------
# clone_code_repo — happy paths against the real local bare repo.
# ---------------------------------------------------------------------------


def test_clone_code_repo_returns_cloned_repo_instance(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest)
    # Assert
    assert isinstance(repo, ClonedRepo)


def test_clone_code_repo_records_submitted_url_verbatim(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest)
    # Assert
    assert repo.repo_url == bare_repo_url


def test_clone_code_repo_materialises_destination_path_on_disk(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest)
    # Assert
    assert repo.path == dest.resolve()


def test_clone_code_repo_copies_working_tree_contents(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest)
    # Assert
    assert (repo.path / "README.md").read_text() == "# fixture\n"


def test_clone_code_repo_reports_full_head_commit_hash(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest)
    # Assert
    assert len(repo.head_commit) == 40


def test_clone_code_repo_reports_head_commit_subject(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest)
    # Assert
    assert repo.head_subject == "fixture: seed commit"


def test_clone_code_repo_uses_shallow_clone_by_default(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest)
    # Assert
    assert (repo.path / ".git" / "shallow").exists()


def test_clone_code_repo_full_history_when_depth_is_zero(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest, depth=0)
    # Assert
    assert not (repo.path / ".git" / "shallow").exists()


def test_clone_code_repo_pins_main_branch_when_ref_is_main(
    tmp_path: Path, bare_repo_url: str
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    repo = clone_code_repo(bare_repo_url, dest, ref="main")
    # Assert
    assert repo.head_subject == "fixture: seed commit"


# ---------------------------------------------------------------------------
# clone_code_repo — failure paths against real (mis-)configured URLs.
# ---------------------------------------------------------------------------


def test_clone_code_repo_raises_when_url_does_not_resolve_to_repo(
    tmp_path: Path,
) -> None:
    # Arrange
    ghost = tmp_path / "does-not-exist.git"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        clone_code_repo(f"file://{ghost}", tmp_path / "clone")


def test_clone_code_repo_cleans_up_destination_after_clone_failure(
    tmp_path: Path,
) -> None:
    # Arrange
    ghost = tmp_path / "does-not-exist.git"
    dest = tmp_path / "clone"
    try:
        clone_code_repo(f"file://{ghost}", dest)
    except GateFailure:
        pass
    # Act
    dest_still_exists = dest.exists()
    # Assert
    assert dest_still_exists is False


def test_clone_code_repo_raises_when_target_is_not_a_git_repository(
    tmp_path: Path,
) -> None:
    # Arrange
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    (not_a_repo / "hello.txt").write_text("not git\n")
    # Act
    # Assert
    with pytest.raises(GateFailure):
        clone_code_repo(f"file://{not_a_repo}", tmp_path / "clone")


def test_clone_code_repo_raises_when_git_binary_is_not_on_path(
    tmp_path: Path,
) -> None:
    # Arrange
    dest = tmp_path / "clone"
    # Act
    # Assert
    with _saved_env("PATH", ""):
        with pytest.raises(GateFailure):
            clone_code_repo("file:///tmp/whatever.git", dest)


# ---------------------------------------------------------------------------
# cloned_code_repo — context manager owns its tempdir.
# ---------------------------------------------------------------------------


def test_cloned_code_repo_yields_repo_with_working_tree(
    bare_repo_url: str,
) -> None:
    # Arrange
    readme_exists: bool = False
    # Act
    with cloned_code_repo(bare_repo_url) as repo:
        readme_exists = (repo.path / "README.md").exists()
    # Assert
    assert readme_exists is True


def test_cloned_code_repo_removes_tempdir_after_context_exit(
    bare_repo_url: str,
) -> None:
    # Arrange
    with cloned_code_repo(bare_repo_url) as repo:
        kept_path = repo.path
    # Act
    survived = kept_path.exists()
    # Assert
    assert survived is False


def test_cloned_code_repo_propagates_clone_failure_to_caller(
    tmp_path: Path,
) -> None:
    # Arrange
    bad_url = f"file://{tmp_path / 'never-existed.git'}"
    # Act
    # Assert
    with pytest.raises(GateFailure):
        with cloned_code_repo(bad_url):
            pass


# ---------------------------------------------------------------------------
# Optional real-network test against GitHub.
# ---------------------------------------------------------------------------


@pytest.mark.network
@pytest.mark.skipif(
    os.environ.get("SCITEX_RUN_NETWORK_TESTS") != "1",
    reason="opt in by setting SCITEX_RUN_NETWORK_TESTS=1",
)
def test_real_github_clone_produces_readable_head(tmp_path: Path) -> None:
    # Arrange
    url = "https://github.com/octocat/Hello-World.git"
    dest = tmp_path / "hello"
    # Act
    repo = clone_code_repo(url, dest)
    # Assert
    assert len(repo.head_commit) == 40
