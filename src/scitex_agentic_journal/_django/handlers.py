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

from ._request_home import journal_request, request_home

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

EXAMPLE_LOAD_SUFFIX = "examples/example-project-mnist/load/"
"""URL suffix of the demo-content loader, relative to the app mount."""


def _is_json_request(request: HttpRequest) -> bool:
    return (request.content_type or "").split(";")[0].strip() == "application/json"


@journal_request
def load_example(request: HttpRequest) -> JsonResponse:
    """POST the demo bundle into the archive as labeled example content.

    Loads ``example-project-mnist`` (``$SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE``
    or ``~/proj/example-project-mnist``) through
    :func:`scitex_agentic_journal._django._examples.load_example_project`:
    the real manifest is validated and real-shaped Gate-1 / decision /
    persistent-id records are written, every one carrying
    ``"example": true``. Idempotent — reloading rewrites the same
    record dir (hub double-submit rule).

    Status contract (no tracebacks, always a response):

    * ``201`` ``{"ok": true, "submission_id": "example-project-mnist", ...}``
      on JSON requests.
    * ``303`` redirect to the app index on form posts (the empty-state
      button), so the browser lands on the populated archive.
    * ``405`` on non-POST.
    * ``404`` when the example bundle is not installed server-side.
    * ``422`` when the example bundle manifest is malformed.
    """
    from django.http import HttpResponseRedirect

    from scitex_agentic_journal._django import _examples
    from scitex_agentic_journal._submit import SubmissionLoadError

    if request.method != "POST":
        return _reject("method-not-allowed: use POST.", 405)
    try:
        from ._uploads import UploadConflict, _namespace

        try:
            _namespace(request_home(request), "submissions")
        except UploadConflict:
            return _reject("Journal storage is unavailable.", 503)
        receipt = _examples.load_example_project(home=request_home(request))
    except _examples.ExampleConflict:
        return _reject(
            "Existing example content was preserved; loading was refused.", 409
        )
    except _examples.ExampleUnavailable:
        return JsonResponse(
            {
                "ok": False,
                "reason": "The example bundle is not installed for this service.",
            },
            status=404,
        )
    except SubmissionLoadError as exc:
        return JsonResponse(
            {"ok": False, "reason": f"example bundle invalid: {exc}"}, status=422
        )
    if _is_json_request(request):
        return JsonResponse({"ok": True, **receipt}, status=201)
    index = request.path
    index = index.removesuffix(EXAMPLE_LOAD_SUFFIX)
    return HttpResponseRedirect(index, status=303)


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


def _stage_upload(
    bundle_yaml: str, files: dict, *, home=None
) -> tuple[Path, Path, str]:
    """Stage an uploaded bundle into a server-minted dir.

    Returns ``(home, stage_dir, fingerprint)``. Every filesystem path
    below is server-chosen: ``files`` keys are confined to relative
    paths inside the stage dir (absolute paths and ``..`` climbs are
    rejected). The caller owns cleanup of ``stage_dir``.
    """
    from scitex_agentic_journal._submit._persist import _submission_home

    home = home if home is not None else _submission_home()
    staging = home / "staging"
    if staging.is_symlink() or not staging.resolve().is_relative_to(home.resolve()):
        raise ValueError("Journal staging namespace is not safe")
    stage_dir = home / "staging" / secrets.token_hex(8)
    stage_dir.mkdir(parents=True, exist_ok=False)
    try:
        (stage_dir / "bundle.yaml").write_text(bundle_yaml, encoding="utf-8")
        hasher = hashlib.sha256()
        hasher.update(b"bundle.yaml\x00")
        hasher.update(bundle_yaml.encode("utf-8"))
        hasher.update(b"\x00")
        total = len(bundle_yaml.encode("utf-8"))
        for rel in sorted(files):
            target = (stage_dir / rel).resolve()
            if (
                target != stage_dir.resolve()
                and stage_dir.resolve() not in target.parents
            ):
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

    except BaseException:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise


@journal_request
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
    rejected with 400), and a ``clew_project_path`` that resolves outside
    the staged bundle is rejected with 422. Passing bundles are copied into
    immutable per-user assets and their record paths are rebased before the
    temporary intake directory is cleaned up.

    Retries are idempotent: the submission id derives deterministically
    from the staged content, so a retry returns the original immutable record without
    rewriting a prior review or decision.

    Status contract (no tracebacks, always JSON):

    * ``201`` ``{"ok": true, "submission_id": ...}`` on Gate-1 pass.
    * ``405`` on non-POST.
    * ``400`` on invalid JSON, missing/oversize ``bundle_yaml``,
      malformed ``files``, or a legacy ``bundle_dir`` path.
    * ``422`` when the staged bundle fails to load or Gate-1 rejects
      it (``reason`` mirrors the CLI's single-line failure message).

    Mounted requests require authentication and a configured host user-home
    provider. CSRF is enforced by the host middleware; no exemption is used.
    """
    from scitex_agentic_journal._submit import (
        Gate1Failure,
        SubmissionLoadError,
        load_submission,
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
            'missing-bundle_yaml: POST JSON {"bundle_yaml": "<bundle.yaml text>"}.',
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
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or not rel
            or candidate.as_posix() in {".", "bundle.yaml"}
        ):
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
    if (
        len(bundle_yaml.encode("utf-8"))
        + sum(len(text.encode("utf-8")) for text in files.values())
        > _MAX_TOTAL_BYTES
    ):
        return _reject("Uploaded bundle exceeds the total size limit.", 400)
    try:
        home, stage_dir, fingerprint = _stage_upload(
            bundle_yaml, files, home=request_home(request)
        )
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
        from ._uploads import UploadConflict, persist_uploaded_verdict

        try:
            persisted = persist_uploaded_verdict(
                verdict, home=home, fingerprint=fingerprint
            )
        except UploadConflict:
            return _reject(
                "Submission persistence conflicted; no record was overwritten.", 409
            )
        return JsonResponse(
            {"ok": True, "submission_id": persisted.submission_id},
            status=201,
        )
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
