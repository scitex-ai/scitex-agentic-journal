"""POST handlers — ``submit`` is live (M1); the rest await M2–M5.

The handlers are kept separate from :mod:`views` so the auth /
permissions layer can wrap them without touching the read-only
surface. Unshipped handlers sit on :data:`PENDING_HANDLERS` so the
URL config can register them and return a typed 503
(``"not yet implemented"``) instead of 404.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from pathlib import Path
from typing import Final

from django.http import HttpRequest, JsonResponse

PENDING_HANDLERS: Final[tuple[str, ...]] = (
    "start_review",
    "submit_review",
    "apply_decision",
    "mint_id",
    "publish",
)
"""Names of POST handlers reserved for M2–M5 implementations.

Listed here so docs / dashboards can show "wired but not yet
implemented" rather than 404 / silently 200.
"""

_MAX_BUNDLE_YAML_BYTES: Final[int] = 256 * 1024
"""Largest accepted ``bundle_yaml`` body (256 KiB — manifests are small)."""

_MAX_EXTRA_FILE_BYTES: Final[int] = 256 * 1024
"""Per-file cap for the optional ``files`` mapping."""

_MAX_EXTRA_FILES: Final[int] = 50
"""Maximum entries in the optional ``files`` mapping."""

_MAX_TOTAL_BYTES: Final[int] = 2 * 1024 * 1024
"""Total cap over ``bundle_yaml`` + all ``files`` (2 MiB)."""


def _reject(message: str, status: int) -> JsonResponse:
    return JsonResponse({"ok": False, "reason": message}, status=status)


def _stage_upload(bundle_yaml: str, files: dict) -> tuple[Path, Path, str]:
    """Stage an uploaded bundle into a server-minted dir.

    Returns ``(home, stage_dir, fingerprint)``. Every filesystem path
    below is server-chosen: ``files`` keys are confined to relative
    paths inside the stage dir (absolute paths and ``..`` climbs are
    rejected). The caller owns cleanup of ``stage_dir``.
    """
    from scitex_agentic_journal._submit._persist import _submission_home

    home = _submission_home()
    stage_dir = home / "staging" / secrets.token_hex(8)
    stage_dir.mkdir(parents=True, exist_ok=False)
    (stage_dir / "bundle.yaml").write_text(bundle_yaml, encoding="utf-8")
    hasher = hashlib.sha256()
    hasher.update(b"bundle.yaml\x00")
    hasher.update(bundle_yaml.encode("utf-8"))
    hasher.update(b"\x00")
    total = len(bundle_yaml.encode("utf-8"))
    for rel in sorted(files):
        target = (stage_dir / rel).resolve()
        if target != stage_dir.resolve() and stage_dir.resolve() not in target.parents:
            raise ValueError(
                f"files key {rel!r} escapes the bundle — use a relative path."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[rel], encoding="utf-8")
        blob = files[rel].encode("utf-8")
        total += len(blob)
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(blob)
        hasher.update(b"\x00")
    if total > _MAX_TOTAL_BYTES:
        raise ValueError(
            f"uploaded bundle is {total} bytes — over the {_MAX_TOTAL_BYTES} cap."
        )
    return home, stage_dir, hasher.hexdigest()


def submit(request: HttpRequest) -> JsonResponse:
    """POST /aj/submit/ — stage an uploaded bundle, run Gate-1, persist.

    Expects a JSON body ``{"bundle_yaml": "<bundle.yaml text>",
    "files"?: {"<relpath>": "<text>", ...}}``. The server stages the
    upload into a server-minted directory and runs the three
    structural checks (ORCID #2, code-repo #3, Clew DAG #4) against
    the staged copy — the same pipeline the
    ``scitex-agentic-journal submit`` CLI command runs on a local
    bundle directory.

    No caller-supplied filesystem path is ever read: ``files`` keys
    are confined to the stage dir (absolute paths and ``..`` climbs
    rejected with 400), and a ``clew_project_path`` that resolves
    outside the staged bundle is rejected with 422 (hub writer-SITE-1
    rule). The stage dir is always cleaned up.

    Retries are idempotent: the submission id derives deterministically
    from the staged content, so resubmitting the same bundle rewrites
    the same record dir instead of minting a duplicate.

    Status contract (no tracebacks, always JSON):

    * ``201`` ``{"ok": true, "submission_id": ...}`` on Gate-1 pass.
    * ``405`` on non-POST.
    * ``400`` on invalid JSON, missing/oversize ``bundle_yaml``,
      malformed ``files``, or a legacy ``bundle_dir`` path.
    * ``422`` when the staged bundle fails to load or Gate-1 rejects
      it (``reason`` mirrors the CLI's single-line failure message).

    Auth lives on the hub side: hub mounts this urlconf wholesale
    behind ``login_required`` (see
    ``apps/workspace/journal_app/urls/journal_django.py``), so this
    view carries no decorator of its own. CSRF is enforced by the
    host's middleware stack.
    """
    from scitex_agentic_journal._submit import (
        Gate1Failure,
        SubmissionLoadError,
        load_submission,
        persist_verdict,
        run_gate1,
    )

    if request.method != "POST":
        return _reject("method-not-allowed: use POST.", 405)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return _reject("invalid-json: expected a JSON object body.", 400)
    if not isinstance(body, dict):
        return _reject("invalid-json: expected a JSON object body.", 400)
    if "bundle_dir" in body:
        return _reject(
            "bundle_dir paths are not accepted: POST "
            '{"bundle_yaml": "<bundle.yaml text>", '
            '"files"?: {"<relpath>": "<text>"}} instead.',
            400,
        )
    bundle_yaml = body.get("bundle_yaml")
    if not isinstance(bundle_yaml, str) or not bundle_yaml.strip():
        return _reject(
            "missing-bundle_yaml: POST JSON "
            '{"bundle_yaml": "<bundle.yaml text>"}.',
            400,
        )
    if len(bundle_yaml.encode("utf-8")) > _MAX_BUNDLE_YAML_BYTES:
        return _reject(
            f"bundle_yaml is over the {_MAX_BUNDLE_YAML_BYTES}-byte cap.",
            400,
        )
    files = body.get("files", {})
    if not isinstance(files, dict):
        return _reject("invalid-files: expected an object of path → text.", 400)
    if len(files) > _MAX_EXTRA_FILES:
        return _reject(
            f"too many files: {len(files)} over the {_MAX_EXTRA_FILES} cap.",
            400,
        )
    for rel, text in files.items():
        if not isinstance(rel, str) or not isinstance(text, str):
            return _reject("invalid-files: keys and values must be strings.", 400)
        candidate = Path(rel)
        if candidate.is_absolute() or ".." in candidate.parts:
            return _reject(
                f"invalid-files: key {rel!r} must be a relative path without '..'.",
                400,
            )
        if len(text.encode("utf-8")) > _MAX_EXTRA_FILE_BYTES:
            return _reject(
                f"invalid-files: {rel!r} is over the "
                f"{_MAX_EXTRA_FILE_BYTES}-byte per-file cap.",
                400,
            )
    try:
        home, stage_dir, fingerprint = _stage_upload(bundle_yaml, files)
    except ValueError as exc:
        return _reject(str(exc), 400)
    try:
        try:
            submission = load_submission(stage_dir)
        except SubmissionLoadError as exc:
            return _reject(str(exc), 422)
        if submission.clew_project_dir.resolve() != stage_dir.resolve() and (
            stage_dir.resolve() not in submission.clew_project_dir.resolve().parents
        ):
            return _reject(
                "clew_project_path must stay inside the uploaded bundle — "
                "absolute server paths are not accepted.",
                422,
            )
        try:
            verdict = run_gate1(submission)
        except Gate1Failure as exc:
            payload: dict[str, object] = {"ok": False, "reason": str(exc.wrapped)}
            if exc.check:
                payload["check"] = exc.check
            return JsonResponse(payload, status=422)
        persisted = persist_verdict(verdict, home=home, key=fingerprint)
        return JsonResponse(
            {"ok": True, "submission_id": persisted.submission_id},
            status=201,
        )
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
