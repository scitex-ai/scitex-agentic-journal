"""Persist uploaded assets before their temporary intake directory is removed."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from django.core.files import locks

from scitex_agentic_journal._submit._persist import PersistedSubmission, persist_verdict


class UploadConflict(ValueError):
    """An upload is busy or conflicts with an existing immutable record."""


def _namespace(home, name):
    root = Path(home).resolve()
    child = root / name
    if child.is_symlink() or child.resolve().parent != root:
        raise UploadConflict("Journal storage namespace is not safe")
    child.mkdir(parents=True, exist_ok=True)
    return child


def _tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise UploadConflict("Uploaded bundles cannot contain symbolic links")
        if path.is_file():
            name = path.relative_to(root).as_posix().encode()
            contents = path.read_bytes()
            digest.update(len(name).to_bytes(8, "big"))
            digest.update(name)
            digest.update(len(contents).to_bytes(8, "big"))
            digest.update(contents)
    return digest.hexdigest()


def persist_uploaded_verdict(verdict, *, home, fingerprint):
    """Create an immutable bundle snapshot and rebase every recorded input path.

    The opaque content ID is stable across retries/dates. A process lock prevents
    concurrent retries from overwriting a prior review's Gate-1 input. Existing
    matching records are returned unchanged; no review or decision is rewritten.
    """
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise UploadConflict("Invalid server upload fingerprint")
    home = Path(home).resolve()
    identifier = "sub_" + fingerprint[:32]
    records = _namespace(home, "submissions")
    assets = _namespace(home, "bundles")
    lock_root = _namespace(home, "locks")
    lock_path = lock_root / f"{identifier}.lock"
    if lock_path.is_symlink():
        raise UploadConflict("Upload lock cannot be a symbolic link")
    descriptor = os.open(
        lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    snapshot = None
    with os.fdopen(descriptor, "a+b") as lock:
        if not locks.lock(lock, locks.LOCK_EX | locks.LOCK_NB):
            raise UploadConflict("This upload is already being persisted; retry later")
        try:
            record_dir = records / identifier
            if record_dir.is_symlink():
                raise UploadConflict("Submission storage cannot be a symbolic link")
            record_path = record_dir / "gate1.json"
            if record_path.is_symlink():
                raise UploadConflict("Submission record cannot be a symbolic link")
            if record_path.exists():
                try:
                    existing = json.loads(record_path.read_text(encoding="utf-8"))
                except (ValueError, OSError) as exc:
                    raise UploadConflict(
                        "Existing submission record needs recovery"
                    ) from exc
                if not isinstance(existing, dict):
                    raise UploadConflict("Existing submission record needs recovery")
                bundle = Path(existing.get("submission", {}).get("bundle_dir", ""))
                if (
                    existing.get("bundle_sha256") != fingerprint
                    or not bundle.is_dir()
                    or bundle.is_symlink()
                    or not bundle.resolve().is_relative_to(assets)
                ):
                    raise UploadConflict(
                        "Existing submission assets need recovery; nothing was overwritten"
                    )
                if existing.get("assets_sha256") != _tree_hash(bundle):
                    raise UploadConflict(
                        "Existing submission assets changed; nothing was overwritten"
                    )
                return PersistedSubmission(identifier, record_path, record_dir)
            source = verdict.submission.bundle_dir.resolve()
            clew_relative = verdict.submission.clew_project_dir.resolve().relative_to(
                source
            )
            checked_relative = (
                verdict.clew_verification.project_dir.resolve().relative_to(source)
            )
            original_hash = _tree_hash(source)
            snapshot = Path(tempfile.mkdtemp(prefix=f"{identifier}-", dir=assets))
            shutil.copytree(source, snapshot, dirs_exist_ok=True, symlinks=True)
            if (
                _tree_hash(snapshot) != original_hash
                or _tree_hash(source) != original_hash
            ):
                raise UploadConflict("Uploaded assets changed during persistence")
            saved_submission = replace(
                verdict.submission,
                bundle_dir=snapshot,
                clew_project_dir=snapshot / clew_relative,
            )
            saved = replace(
                verdict,
                submission=saved_submission,
                clew_verification=replace(
                    verdict.clew_verification, project_dir=snapshot / checked_relative
                ),
            )
            for path in [*snapshot.rglob("*"), snapshot]:
                if path.is_file():
                    with path.open("rb") as stream:
                        os.fsync(stream.fileno())
                elif path.is_dir() and hasattr(os, "O_DIRECTORY"):
                    directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
            if hasattr(os, "O_DIRECTORY"):
                parent = os.open(assets, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(parent)
                finally:
                    os.close(parent)
            # Preserve the snapshot if a record commit is interrupted: a record
            # may already refer to it, and retaining an orphan is safer than a
            # dangling persisted input path.
            snapshot = None
            return persist_verdict(
                saved,
                home=home,
                key=fingerprint,
                submission_id=identifier,
                assets_sha256=original_hash,
            )
        finally:
            locks.unlock(lock)
            if snapshot is not None:
                shutil.rmtree(snapshot)
