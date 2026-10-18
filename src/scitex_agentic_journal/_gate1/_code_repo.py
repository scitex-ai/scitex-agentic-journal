"""Code-repository cloneability — gate-1 structural check.

This module implements :func:`clone_code_repo` (explicit destination) and
its context-manager helper :func:`cloned_code_repo` (auto-tempdir). Both
shell out to the real ``git`` binary via :mod:`subprocess`; we do not
embed any pure-Python git, do not mock the subprocess call in CI, and do
not silently fall back.

The production path is what the CLI orchestrator (M1, issue #5) will
also call from inside the submission gate to materialise the author's
code repo for downstream gates and AI review.

References
----------
- ``git clone --depth N`` (shallow clone)
  https://git-scm.com/docs/git-clone#Documentation/git-clone.txt---depthltdepthgt
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterator

from scitex_agentic_journal._gate1._errors import GateFailure

DEFAULT_CLONE_DEPTH: Final[int] = 1
"""Shallow clone by default — we only need HEAD for the structural gate."""

DEFAULT_CLONE_TIMEOUT_S: Final[float] = 60.0
"""Fail loud on slowness; the gate must not hang the pipeline."""


@dataclass(frozen=True)
class ClonedRepo:
    """A successfully cloned code repository on local disk.

    Attributes
    ----------
    repo_url :
        The URL we cloned from (verbatim, as the author submitted it).
    path :
        Absolute path to the working tree we materialised.
    head_commit :
        Full 40-char commit hash at ``HEAD``.
    head_subject :
        First line of the ``HEAD`` commit message (subject).
    """

    repo_url: str
    path: Path
    head_commit: str
    head_subject: str


def clone_code_repo(
    repo_url: str,
    destination: Path,
    *,
    depth: int = DEFAULT_CLONE_DEPTH,
    ref: str | None = None,
    timeout_s: float = DEFAULT_CLONE_TIMEOUT_S,
) -> ClonedRepo:
    """Shallow-clone ``repo_url`` into ``destination`` via real ``git``.

    Parameters
    ----------
    repo_url :
        Anything ``git`` accepts: ``https://...``, ``git@host:path.git``,
        ``ssh://...``, ``file:///abs/path``, or a bare local path.
    destination :
        Target directory. **Must not already exist** — we refuse to
        clobber an existing path. We create it.
    depth :
        ``git clone --depth N``. ``0`` means full history; default ``1``.
    ref :
        Optional branch / tag to check out. Passed via ``--branch``.
        Note: ``git clone --depth N --branch <commit-sha>`` does not
        work; for a pinned commit, use ``depth=0`` and a separate
        ``checkout`` (out of scope for this gate).
    timeout_s :
        Subprocess timeout.

    Returns
    -------
    ClonedRepo

    Raises
    ------
    GateFailure
        On empty URL, missing ``git`` binary, pre-existing destination,
        clone failure, or timeout. Loud, structured, actionable.
    """
    url = (repo_url or "").strip()
    if not url:
        raise GateFailure(
            check="code_repo",
            reason="empty repository url",
            detail="submission bundle did not provide a code repository url",
        )

    if shutil.which("git") is None:
        raise GateFailure(
            check="code_repo",
            reason="git binary not on PATH",
            detail=(
                "scitex-agentic-journal requires the system git client; "
                "install it (e.g. apt-get install git)"
            ),
        )

    destination = Path(destination)
    if destination.exists():
        raise GateFailure(
            check="code_repo",
            reason="destination already exists",
            detail=(
                f"{destination} already exists; refusing to clobber it. "
                "Use a fresh temp dir or remove the existing path."
            ),
        )

    cmd: list[str] = ["git", "clone", "--quiet"]
    if depth and depth > 0:
        cmd += ["--depth", str(depth)]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(destination)]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # destination may be half-populated — clean up so callers do not
        # see a stale partial clone.
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise GateFailure(
            check="code_repo",
            reason="git clone timed out",
            detail=(
                f"timeout after {timeout_s:.1f}s cloning {url} -> {destination}"
            ),
        ) from exc

    if completed.returncode != 0:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        stderr = (completed.stderr or "").strip()
        raise GateFailure(
            check="code_repo",
            reason="git clone failed",
            detail=(
                f"exit {completed.returncode} cloning {url}: "
                f"{stderr[:400] or '<empty stderr>'}"
            ),
        )

    head_commit, head_subject = _read_head(destination, url=url)
    return ClonedRepo(
        repo_url=url,
        path=destination.resolve(),
        head_commit=head_commit,
        head_subject=head_subject,
    )


@contextmanager
def cloned_code_repo(
    repo_url: str,
    *,
    depth: int = DEFAULT_CLONE_DEPTH,
    ref: str | None = None,
    timeout_s: float = DEFAULT_CLONE_TIMEOUT_S,
) -> Iterator[ClonedRepo]:
    """Clone into a tempdir, yield the :class:`ClonedRepo`, then clean up.

    The CLI orchestrator will use this so the downstream gates see a
    real on-disk repo without the caller having to manage cleanup.
    """
    tmp = Path(tempfile.mkdtemp(prefix="scitex-aj-clone-"))
    # The clone wants an empty target, so use a child path.
    target = tmp / "repo"
    try:
        yield clone_code_repo(
            repo_url,
            target,
            depth=depth,
            ref=ref,
            timeout_s=timeout_s,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _read_head(repo_path: Path, *, url: str) -> tuple[str, str]:
    """Return (full commit hash, subject line) of HEAD via real ``git``."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%H%n%s"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise GateFailure(
            check="code_repo",
            reason="cloned repo has no readable HEAD",
            detail=f"git log failed in {repo_path} (url={url}): {exc}",
        ) from exc
    lines = out.splitlines()
    if not lines or len(lines[0]) != 40:
        raise GateFailure(
            check="code_repo",
            reason="cloned repo HEAD shape unexpected",
            detail=f"git log output: {out!r}",
        )
    commit = lines[0]
    subject = lines[1] if len(lines) > 1 else ""
    return commit, subject
