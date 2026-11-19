"""Host-side verification of a sandboxed replay: the journal, not the sandbox, decides.

After the sandbox exits, the replay tree clew kept (``--work-dir``) is still
on the host under the run's ``work/replay``. For each run recorded in the
evidence bundle the host locates every recorded output there
(:func:`resolve_replayed_output`), hashes it itself without following
symlinks, and sets the run's status from those hashes. A claim is
``reproduced`` when every one of its producing runs reproduced by host hash;
otherwise, for numeric JSON-pointer locators into ``.json`` sources, the host
re-reads the replayed value and compares it with the stated value using the
bundle's ``precision`` (mirroring scitex-clew's ``_claim._locator.compare``);
anything else is ``differs``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path, PurePosixPath
from typing import Any

from scitex_agentic_journal._admission._paths import (
    read_nofollow,
    safe_relpath,
    sha256_nofollow,
)

#: Where the sandboxed rerun keeps its tree (``clew bundle rerun --work-dir``).
REPLAY_DIR = "/work/replay"
MAX_SOURCE_BYTES = 64 << 20
WHOLE_VALUE = "."


def resolve_replayed_output(
    replay_root: Path,
    report: dict[str, Any] | None,
    run: dict[str, Any],
    rel: str,
) -> Path | None:
    """Host path of output ``rel`` of bundle run ``run`` in the kept replay tree.

    Uses the rerun report's ``resolved_path`` (rerun-report 1.1.0, relative to
    the report's ``work_dir``) only as a pointer: it must be a plain relative
    path, ``work_dir`` must be the sandbox's replay dir, and the resolved path
    must end with the recorded path (below the run's ``run_dir`` when the
    output lives there). None means "not found", i.e. a miss.
    """
    if report is None or report.get("work_dir") != REPLAY_DIR:
        return None
    hint = next(
        (r for r in report.get("runs", []) if r.get("run_id") == run.get("run_id")),
        None,
    )
    if hint is None:
        return None
    entry = next(
        (
            o
            for o in hint.get("outputs", [])
            if isinstance(o, dict) and o.get("path") == rel
        ),
        None,
    )
    resolved = safe_relpath((entry or {}).get("resolved_path"))
    recorded = safe_relpath(rel)
    if resolved is None or recorded is None:
        return None
    tail = recorded
    run_dir = safe_relpath(run.get("run_dir"))
    if run_dir is not None:
        try:
            tail = recorded.relative_to(run_dir)
        except ValueError:
            tail = recorded
    if resolved.parts[-len(tail.parts) :] != tail.parts:
        return None
    return replay_root / str(resolved)


def _hash_matches(expected: Any, actual: str | None) -> bool:
    if not isinstance(expected, str) or actual is None:
        return False
    if len(expected) == 32:  # legacy truncated record
        return actual.startswith(expected)
    return actual == expected


def host_runs(
    doc: dict[str, Any], report: dict[str, Any] | None, replay_root: Path
) -> list[dict[str, Any]]:
    """Each bundle run's outputs hashed on the host, and its status from them."""
    runs = []
    for run in doc.get("runs") or []:
        if not isinstance(run, dict):
            continue
        outputs = []
        for rel, expected in sorted((run.get("outputs") or {}).items()):
            path = resolve_replayed_output(replay_root, report, run, rel)
            actual = (
                sha256_nofollow(replay_root, str(path.relative_to(replay_root)))
                if path is not None
                else None
            )
            outputs.append(
                {
                    "path": rel,
                    "host_path": str(path) if path is not None else None,
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                    "match": _hash_matches(expected, actual),
                }
            )
        if not outputs:
            status = "no_outputs"
        elif all(o["match"] for o in outputs):
            status = "reproduced"
        elif all(o["actual_sha256"] is None for o in outputs):
            status = "missing"
        else:
            status = "differs"
        runs.append({"run_id": run.get("run_id"), "status": status, "outputs": outputs})
    return runs


def _resolve_pointer(doc: Any, pointer: str) -> Any:
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer!r}")
    node = doc
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and token in node:
            node = node[token]
        elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        else:
            raise ValueError(f"pointer {pointer!r} does not resolve at {token!r}")
    return node


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def agrees(claimed: Any, actual: Any, rule: dict[str, Any]) -> tuple[bool, str]:
    """Mirror of scitex-clew ``compare`` for numbers, given the bundle's precision rule."""
    basis = rule.get("basis")
    c_num, a_num = _number(claimed), _number(actual)
    if basis == "exact" or c_num is None or a_num is None:
        ok = claimed == actual
        return ok, f"claimed {claimed!r} vs replayed {actual!r} (exact)"
    abs_tol = rule.get("abs_tol")
    rel_tol = rule.get("rel_tol")
    if basis == "implied" and abs_tol is None:
        return False, "implied precision without a resolved abs_tol"
    abs_tol = float(abs_tol or 0.0)
    rel_tol = float(rel_tol or 0.0)
    ok = math.isclose(c_num, a_num, rel_tol=rel_tol, abs_tol=abs_tol + 1e-12)
    return ok, (
        f"claimed {claimed!r} vs replayed {actual!r} (abs_tol={abs_tol:g}, "
        f"rel_tol={rel_tol:g}, {basis})"
    )


def _locators(locator: Any) -> dict[str, dict[str, Any]] | None:
    """``{field: {"pointer": p}}`` when every locator is a JSON pointer, else None."""
    if not isinstance(locator, dict) or not locator:
        return None
    out = {}
    for fld, loc in locator.items():
        if isinstance(loc, str):
            loc = {"pointer": loc}
        if not isinstance(loc, dict) or not isinstance(loc.get("pointer"), str):
            return None
        out[str(fld)] = loc
    return out


def _source_path(
    claim: dict[str, Any],
    doc: dict[str, Any],
    report: dict[str, Any] | None,
    replay_root: Path,
) -> Path | None:
    rel = (claim.get("source") or {}).get("file")
    if safe_relpath(rel) is None or PurePosixPath(rel).suffix.lower() != ".json":
        return None
    for run in doc.get("runs") or []:
        if (
            isinstance(run, dict)
            and rel in (run.get("outputs") or {})
            and run.get("run_id") in (claim.get("producing_runs") or [])
        ):
            return resolve_replayed_output(replay_root, report, run, rel)
    return None


def recompute_on_host(
    claim: dict[str, Any],
    doc: dict[str, Any],
    report: dict[str, Any] | None,
    replay_root: Path,
) -> dict[str, Any] | None:
    """Re-read a numeric JSON-pointer claim from the replayed source; None if not applicable."""
    locators = _locators((claim.get("source") or {}).get("locator"))
    path = _source_path(claim, doc, report, replay_root)
    if locators is None or path is None:
        return None
    raw = read_nofollow(
        replay_root, str(path.relative_to(replay_root)), limit=MAX_SOURCE_BYTES
    )
    if raw is None:
        return {"status": "differs", "recomputed_value": None,
                "detail": "the replayed source is missing, a symlink or too large"}  # fmt: skip
    try:
        source = json.loads(raw)
    except ValueError as e:
        return {"status": "differs", "recomputed_value": None,
                "detail": f"the replayed source is not JSON ({e})"}  # fmt: skip
    precision = claim.get("precision") or {}
    stated = claim.get("stated_value")
    values, oks, details = {}, [], []
    for fld, loc in locators.items():
        if fld == WHOLE_VALUE:
            claimed = stated
        elif isinstance(stated, dict) and fld in stated:
            claimed = stated[fld]
        else:
            return None
        if _number(claimed) is None:
            return None
        try:
            actual = _resolve_pointer(source, loc["pointer"])
        except ValueError as e:
            return {
                "status": "differs",
                "recomputed_value": values or None,
                "detail": str(e),
            }
        rule = (precision.get("fields") or {}).get(fld) or precision
        ok, detail = agrees(claimed, actual, rule)
        values[fld] = actual
        oks.append(ok)
        details.append(f"{fld}: {detail}")
    recomputed = values[WHOLE_VALUE] if list(values) == [WHOLE_VALUE] else values
    return {
        "status": "reproduced" if all(oks) else "differs",
        "recomputed_value": recomputed,
        "detail": "; ".join(details),
    }


def host_claims(
    doc: dict[str, Any],
    runs: list[dict[str, Any]],
    report: dict[str, Any] | None,
    replay_root: Path,
) -> list[dict[str, Any]]:
    """Each bundle claim's reproduction status as the host establishes it."""
    status_of = {r["run_id"]: r["status"] for r in runs}
    out = []
    for claim in doc.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        producing = list(claim.get("producing_runs") or [])
        entry = {
            "claim_id": claim.get("claim_id"),
            "stated_value": claim.get("stated_value"),
            "tolerance": claim.get("precision"),
            "producing_runs": producing,
            "recomputed_value": None,
        }
        if not producing:
            out.append({**entry, "status": "not_checkable", "by": None,
                        "detail": "the claim names no producing run"})  # fmt: skip
            continue
        if all(status_of.get(rid) == "reproduced" for rid in producing):
            out.append({**entry, "status": "reproduced", "by": "output-hash",
                        "detail": "every producing run's outputs match by host hash"})  # fmt: skip
            continue
        got = recompute_on_host(claim, doc, report, replay_root)
        if got is None:
            not_ok = {rid: status_of.get(rid, "not in bundle") for rid in producing}
            out.append({**entry, "status": "differs", "by": "output-hash",
                        "detail": f"producing run(s) not reproduced: {not_ok}"})  # fmt: skip
        else:
            out.append({**entry, **got, "by": "host-recompute"})
    return out


def submission_binding(
    doc: dict[str, Any], report: dict[str, Any] | None, main_claims: list[str]
) -> dict[str, str]:
    """Main claims whose bundle entry disagrees with the submitted evidence report."""
    if report is None:
        return {}
    bundle = {
        c.get("claim_id"): c for c in doc.get("claims") or [] if isinstance(c, dict)
    }
    submitted = {c.get("claim_id"): c for c in report.get("claims") or []}
    mismatches = {}
    for cid in main_claims:
        b, s = bundle.get(cid), submitted.get(cid)
        if b is None:
            mismatches[cid] = "not in the snapshot's evidence bundle"
        elif s is None:
            mismatches[cid] = "not in the submitted evidence report"
        elif b.get("state") != s.get("state"):
            mismatches[cid] = (
                f"state {b.get('state')!r} in the bundle vs {s.get('state')!r} submitted"
            )
        elif "stated_value" in s and b.get("stated_value") != s.get("stated_value"):
            mismatches[cid] = (
                f"stated value {b.get('stated_value')!r} in the bundle vs "
                f"{s.get('stated_value')!r} submitted"
            )
    return mismatches
