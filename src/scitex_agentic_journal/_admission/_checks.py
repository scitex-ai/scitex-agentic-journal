"""The individual admission checks (design §13.1).

Each check returns a check record (a plain dict)::

    {"check": str, "required": bool, "status": "passed" | "failed" | "not-run",
     "reason": str, "tool": {"name", "version"} | None, "details": {...}}

``not-run`` always carries the reason it did not run. It is never reported
as a pass.
"""

from __future__ import annotations

import json
import shutil
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol

from scitex_agentic_journal._admission._proc import run, tail
from scitex_agentic_journal._netpolicy import (
    OutboundBlockedError,
    git_pin_args,
    vet_https_url,
)
from scitex_agentic_journal._gate1 import GateFailure, verify_orcid
from scitex_agentic_journal._gate1._orcid import ORCID_PUB_API_BASE

PASSED, FAILED, NOT_RUN = "passed", "failed", "not-run"
LINT_TIMEOUT_S = 900.0
GIT_TIMEOUT_S = 300.0
RESEARCH_CONFIG = Path(".scitex") / "dev" / "config.yaml"


def record(
    check: str,
    status: str,
    reason: str,
    *,
    required: bool,
    tool: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check": check,
        "required": required,
        "status": status,
        "reason": reason,
        "tool": tool,
        "details": details or {},
    }


def _version(dist: str) -> str | None:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


# --- (i) identity ---------------------------------------------------------


def check_orcid(
    manifest: dict[str, Any], *, base_url: str = ORCID_PUB_API_BASE
) -> dict[str, Any]:
    """Gate (i): the submitter's ORCID resolves in the ORCID registry."""
    orcid = manifest["submitter_orcid"]
    tool = {"name": "orcid-public-api", "version": base_url}
    try:
        rec = verify_orcid(orcid, base_url=base_url)
    except GateFailure as e:
        return record(
            "orcid", FAILED, f"{e.reason}: {e.detail}", required=True, tool=tool
        )
    author_orcids = {a.get("orcid") for a in manifest["authors"]}
    details = {
        "orcid": rec.orcid_id,
        "name": rec.display_name,
        "is_author": orcid in author_orcids,
    }
    if orcid not in author_orcids:
        return record(
            "orcid",
            FAILED,
            f"submitter ORCID {orcid} resolves but is not listed among the authors",
            required=True,
            tool=tool,
            details=details,
        )
    return record(
        "orcid",
        PASSED,
        f"{orcid} resolves to {rec.display_name}",
        required=True,
        tool=tool,
        details=details,
    )


# --- repository snapshot ----------------------------------------------------


def checkout_repository(
    manifest: dict[str, Any],
    dest: Path,
    *,
    env: dict[str, str],
    allow_local: bool = False,
) -> tuple[dict[str, Any], Path | None]:
    """Clone the declared repository and check out the declared commit exactly.

    Only ``https://`` URLs are accepted unless ``allow_local`` is set (tests,
    operator-run local journals): a submission must never make the journal
    clone a path or ``file://`` repository from its own host. Git is pinned to
    the same protocols through ``GIT_ALLOW_PROTOCOL``, and ``--`` ends option
    parsing so a URL can never be read as a git option.
    """
    repo = manifest["repository"]
    url, commit = repo["url"], repo["commit"]
    tool = {"name": "git", "version": None}
    if not (url.startswith("https://") or allow_local):
        return record(
            "repository",
            FAILED,
            f"repository url {url!r} is not https://; only public https "
            "repositories are accepted",
            required=True,
            tool=tool,
            details={"url": url},
        ), None
    env = {**env, "GIT_ALLOW_PROTOCOL": "https:file" if allow_local else "https"}
    pin: list[str] = []
    if url.startswith("https://"):
        # Resolve-then-connect: refuse private/loopback/link-local targets
        # and pin git to the vetted address (no redirects, no rebinding).
        try:
            pin = git_pin_args(vet_https_url(url))
        except OutboundBlockedError as e:
            return record(
                "repository",
                FAILED,
                str(e),
                required=True,
                tool=tool,
                details={"url": url},
            ), None
    if dest.exists():
        head = run(["git", "-C", str(dest), "rev-parse", "HEAD"], env=env, timeout_s=30)
        dirty = run(["git", "-C", str(dest), "status", "--porcelain"], env=env, timeout_s=60)
        if (
            head.returncode == 0
            and head.stdout.strip() == commit
            and dirty.returncode == 0
            and not dirty.stdout.strip()
        ):
            return record(
                "repository",
                PASSED,
                f"reused clean checkout at {commit}",
                required=True,
                tool=tool,
                details={"url": url, "commit": commit, "path": str(dest)},
            ), dest
        # Stale, partial or modified: the journal owns this directory, so
        # start over rather than trust it.
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone = run(
        ["git", *pin, "clone", "--quiet", "--no-checkout", "--", url, str(dest)],
        env=env,
        timeout_s=GIT_TIMEOUT_S,
    )
    if clone.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        why = "timed out" if clone.timed_out else tail(clone.stderr, 5)
        return record(
            "repository",
            FAILED,
            f"cannot clone {url} without credentials ({why}); private repositories "
            "need the journal's host app (design §12.6)",
            required=True,
            tool=tool,
            details={"url": url},
        ), None
    co = run(
        [
            "git",
            "-C",
            str(dest),
            "-c",
            "advice.detachedHead=false",
            "checkout",
            "--quiet",
            commit,
        ],
        env=env,
        timeout_s=GIT_TIMEOUT_S,
    )
    if co.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        return record(
            "repository",
            FAILED,
            f"commit {commit} is not in {url}: {tail(co.stderr, 3)}",
            required=True,
            tool=tool,
            details={"url": url},
        ), None
    return record(
        "repository",
        PASSED,
        f"checked out {commit}",
        required=True,
        tool=tool,
        details={"url": url, "commit": commit, "path": str(dest)},
    ), dest


# --- (ii) SciTeX standard form ---------------------------------------------


def default_lint_argv(project: Path) -> list[str]:
    import sys

    exe = Path(sys.executable).with_name("scitex-dev")
    return [str(exe), "linter", "validate-files", str(project), "--json", "--no-color"]


def _research_declared(project: Path) -> bool:
    cfg = project / RESEARCH_CONFIG
    if not cfg.is_file():
        return False
    import yaml

    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    kind = data.get("project-type") if isinstance(data, dict) else None
    kinds = kind if isinstance(kind, list) else [kind]
    return "research" in kinds


def check_scitex_form(
    project: Path | None, *, env: dict[str, str], lint_argv: list[str] | None = None
) -> dict[str, Any]:
    """Gate (ii): the snapshot passes scitex-dev's research lint with zero errors."""
    tool = {
        "name": "scitex-dev linter validate-files",
        "version": _version("scitex-dev") if lint_argv is None else None,
    }
    if project is None:
        return record(
            "scitex-form",
            NOT_RUN,
            "no repository checkout to lint",
            required=True,
            tool=tool,
        )
    if not _research_declared(project):
        return record(
            "scitex-form",
            FAILED,
            f"{RESEARCH_CONFIG} does not declare 'project-type: research'",
            required=True,
            tool=tool,
        )
    argv = lint_argv if lint_argv is not None else default_lint_argv(project)
    res = run(argv, env=env, cwd=project, timeout_s=LINT_TIMEOUT_S)
    if res.timed_out or res.returncode is None:
        return record(
            "scitex-form",
            FAILED,
            f"lint did not complete: {tail(res.stderr, 5) or 'timed out'}",
            required=True,
            tool=tool,
        )
    try:
        payload = json.loads(res.stdout) if res.stdout.strip() else {}
    except json.JSONDecodeError:
        return record(
            "scitex-form",
            FAILED,
            f"lint exited {res.returncode} without JSON output: {tail(res.stderr or res.stdout, 8)}",
            required=True,
            tool=tool,
        )
    meta = payload.get("_meta", {}) if isinstance(payload, dict) else {}
    errors = warnings = 0
    error_rules: dict[str, int] = {}
    for key, entry in payload.items():
        if key == "_meta" or not isinstance(entry, dict):
            continue
        summary = entry.get("summary", {})
        errors += int(summary.get("errors", 0))
        warnings += int(summary.get("warnings", 0))
        for issue in entry.get("issues", []):
            if issue.get("severity") == "error":
                error_rules[issue.get("rule_id", "?")] = (
                    error_rules.get(issue.get("rule_id", "?"), 0) + 1
                )
    details = {
        "exit_code": res.returncode,
        "errors": errors,
        "warnings": warnings,
        "error_rules": error_rules,
        "all_rules_ran": meta.get("all_rules_ran"),
    }
    if res.returncode not in (0, 1) or errors:
        return record(
            "scitex-form",
            FAILED,
            f"{errors} lint error(s): {sorted(error_rules)}",
            required=True,
            tool=tool,
            details=details,
        )
    if meta.get("all_rules_ran") is not True:
        return record(
            "scitex-form",
            FAILED,
            f"not every lint rule ran (skipped: {meta.get('skipped_categories')}); "
            "a partial lint is not a pass",
            required=True,
            tool=tool,
            details=details,
        )
    return record(
        "scitex-form",
        PASSED,
        f"0 errors ({warnings} warning(s))",
        required=True,
        tool=tool,
        details=details,
    )


# --- (iii) reproducibility by Clew graph -------------------------------------


def check_main_claims(
    manifest: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    """Gate (iii): every declared main claim is ``supported`` in the evidence report."""
    states = {c["claim_id"]: c for c in report["claims"]}
    provider = report.get("provider", {})
    tool = {
        "name": f"evidence-report:{provider.get('name')}",
        "version": provider.get("version"),
    }
    bad = {}
    for cid in manifest["main_claims"]:
        claim = states.get(cid)
        if claim is None:
            bad[cid] = "not registered"
        elif claim["state"] != "supported":
            bad[cid] = f"{claim['state']}: {claim['reason']}"
        elif not (claim.get("graph") or {}).get("nodes"):
            bad[cid] = "supported but carries no evidence graph"
    details = {
        "main_claims": manifest["main_claims"],
        "not_supported": bad,
        "report_schema_version": report.get("schema_version"),
    }
    if bad:
        return record(
            "main-claims-evidence",
            FAILED,
            f"{len(bad)} main claim(s) lack supported evidence: {sorted(bad)}",
            required=True,
            tool=tool,
            details=details,
        )
    return record(
        "main-claims-evidence",
        PASSED,
        f"all {len(manifest['main_claims'])} main claim(s) are supported with an evidence graph",
        required=True,
        tool=tool,
        details=details,
    )


def check_clew_reverify() -> dict[str, Any]:
    """Re-deriving the evidence states needs Clew's project state, which the snapshot lacks."""
    return record(
        "clew-reverify",
        NOT_RUN,
        "Clew keeps runs and claims in the authors' host store, not in the repository "
        "snapshot, so the journal cannot re-derive the evidence report yet (needs a portable "
        "Clew export; design §11 D16). The submitted report is validated against the "
        "pinned contract instead.",
        required=False,
    )


# --- executability / reproduction ---------------------------------------------


class Executor(Protocol):
    """Runs author code in isolation; returns the executability and reproduction records."""

    name: str

    def run(self, project: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]: ...


class NoExecutor:
    """The default: author code is never executed on the journal host."""

    name = "none"

    def run(self, project: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        reason = (
            "no isolated executor is configured; author code never runs on the journal "
            "host outside an isolated executor (clew rerun is not isolated)"
        )
        return [
            record("executability", NOT_RUN, reason, required=False),
            record(
                "reproduction",
                NOT_RUN,
                reason,
                required=False,
                details={"targets": manifest["main_claims"]},
            ),
        ]
