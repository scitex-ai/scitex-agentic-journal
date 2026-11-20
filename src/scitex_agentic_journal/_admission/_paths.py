"""Host-side path handling for trees that author code has written.

Everything under a sandbox run's ``work/`` may have been created by author
code, so the host never follows a symlink there: every component of a path is
checked with ``lstat`` and files are opened with ``O_NOFOLLOW``. A relative
path from a bundle or report is accepted only when it is a plain repo-relative
POSIX path (no absolute path, drive, backslash, ``..`` or empty component).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path, PurePosixPath

_READ_BLOCK = 1 << 20


def safe_relpath(rel: object) -> PurePosixPath | None:
    """``rel`` as a normalised relative POSIX path, or None if it could escape."""
    if not isinstance(rel, str) or not rel or "\\" in rel or "\x00" in rel:
        return None
    if rel.startswith("/") or (len(rel) > 1 and rel[1] == ":"):
        return None
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    return PurePosixPath(*parts)


def nofollow_path(root: Path, rel: object) -> Path | None:
    """``root/rel`` when no component below ``root`` is a symlink, else None.

    The path may not exist (the caller decides what that means); every
    existing component below ``root`` must be a real directory or, for the
    last one, a non-symlink.
    """
    safe = safe_relpath(rel)
    if safe is None:
        return None
    current = root
    for i, part in enumerate(safe.parts):
        current = current / part
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            return root.joinpath(*safe.parts)  # nothing below exists either
        if stat.S_ISLNK(st.st_mode):
            return None
        if i < len(safe.parts) - 1 and not stat.S_ISDIR(st.st_mode):
            return None
    return current


def sha256_nofollow(root: Path, rel: object) -> str | None:
    """sha256 of the regular file ``root/rel``; None if missing, a symlink or not a file."""
    path = nofollow_path(root, rel)
    if path is None:
        return None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return None
        digest = hashlib.sha256()
        for block in iter(lambda: fh.read(_READ_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def read_nofollow(root: Path, rel: object, *, limit: int) -> bytes | None:
    """At most ``limit`` bytes of the regular file ``root/rel`` (None if over or unsafe)."""
    path = nofollow_path(root, rel)
    if path is None:
        return None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return None
        data = fh.read(limit + 1)
    return None if len(data) > limit else data


def remove_nofollow(root: Path, rel: object) -> bool:
    """Delete ``root/rel`` (file, symlink or directory) without following links."""
    path = nofollow_path(root, rel)
    if path is None:
        return False
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISDIR(st.st_mode):
        force_rmtree(path)
    else:
        path.unlink()
    return True


def force_rmtree(path: Path) -> None:
    """``rmtree`` that first restores ``u+rwx`` on directories author code locked."""
    if not os.path.lexists(path):
        return
    if os.path.islink(path) or not os.path.isdir(path):
        os.unlink(path)
        return
    for dirpath, dirnames, _files in os.walk(path, topdown=True, followlinks=False):
        for name in [dirpath, *(os.path.join(dirpath, d) for d in dirnames)]:
            try:
                st = os.lstat(name)
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(st.st_mode):
                os.chmod(name, stat.S_IMODE(st.st_mode) | stat.S_IRWXU)
    shutil.rmtree(path)
