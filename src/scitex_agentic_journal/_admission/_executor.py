"""The isolated ``Executor`` for the executability and reproduction checks (design §11 D17).

:class:`ClewRerunExecutor` replays the snapshot's Clew evidence bundle inside a
sealed :class:`ApptainerSandbox` run, and then verifies the replay ON THE HOST:

1. ``fetch-dependencies`` / ``fetch-clew`` - the project's declared
   dependencies (canonicalised by :mod:`._deps`) and the pinned scitex-clew,
   downloaded as wheels only (``--only-binary=:all: --no-build-isolation`` on
   the command line) from the package index. The only phases with egress;
   no author file is in the run yet.
2. the checkout (minus ``.git``) is copied into the run and every output the
   bundle records is deleted from the copy, so each must be produced again;
   egress is closed from here on;
3. offline installs: the project's dependencies into ``/work/venv``, clew
   into its own ``/work/clew-venv``; both are read-only in the rerun;
4. ``rerun`` - ``python -I /work/clew-venv/bin/clew bundle rerun ...
   --work-dir /work/replay --python /work/venv/bin/python``, offline;
5. on the host (:mod:`._replay_verify`): each recorded output is located in the
   kept replay tree, hashed without following symlinks, and the run and claim
   statuses are set from those hashes. clew's own report is kept only as the
   ``sandbox_reported`` hint.

``executability`` passes iff the rerun completed and every recorded output
exists in the replay tree. ``reproduction`` passes iff every main claim is
``reproduced`` by the host AND agrees with the submitted evidence report.
Neither is required for admission (design §13.1). Any failure of the executor
itself becomes ``executability: failed`` with the reason; it never raises.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from scitex_agentic_journal._admission._checks import FAILED, NOT_RUN, PASSED, record
from scitex_agentic_journal._admission._deps import (
    canonical_requirement,
    declared_dependencies,
)
from scitex_agentic_journal._admission._paths import nofollow_path, read_nofollow
from scitex_agentic_journal._admission._replay_verify import (
    REPLAY_DIR,
    host_claims,
    host_runs,
    submission_binding,
)
from scitex_agentic_journal._admission._rerun_report import (
    RerunReportError,
    not_run_pair,
    parse_rerun_report,
    sandbox_reported,
)
from scitex_agentic_journal._admission._sandbox import (
    PACKAGE_INDEX_EGRESS,
    PACKAGE_INDEX_URL,
    WORK,
    ApptainerSandbox,
    CommandResult,
    SandboxError,
    SandboxRun,
    outcome_sha256,
)
from scitex_agentic_journal._records import sha256_hex, write_record

EVIDENCE_BUNDLE = Path(".scitex") / "clew" / "evidence-bundle.json"
BUNDLE_SCHEMA = "scitex-clew.evidence-bundle"
MAX_BUNDLE_BYTES = 64 << 20
RERUN_TIMEOUT_S = 1800.0
INSTALL_TIMEOUT_S = 900.0
#: Slack on top of clew's own per-run --timeout for start-up and reporting.
RERUN_GRACE_S = 300.0
WHEEL_ONLY = ("--only-binary=:all:", "--no-build-isolation", "--no-cache-dir")


def clew_tool(clew_requirement: str) -> dict[str, Any]:
    """The ``tool`` both check records name."""
    return {
        "name": "scitex-clew bundle rerun (sealed apptainer sandbox, host-verified)",
        "version": clew_requirement,
    }


def load_bundle(project: Path) -> tuple[dict[str, Any] | None, str | None, str]:
    """``(document, sha256, problem)`` of the snapshot's bundle, read without following links."""
    raw = read_nofollow(project, EVIDENCE_BUNDLE.as_posix(), limit=MAX_BUNDLE_BYTES)
    if raw is None:
        return (
            None,
            None,
            (
                f"{EVIDENCE_BUNDLE} is a symlink, below a symlinked directory, not a "
                f"regular file or larger than {MAX_BUNDLE_BYTES} bytes"
            ),
        )
    try:
        doc = json.loads(raw)
    except ValueError as e:
        return None, None, f"{EVIDENCE_BUNDLE} is not JSON ({e})"
    if not isinstance(doc, dict) or doc.get("schema") != BUNDLE_SCHEMA:
        return None, None, f"{EVIDENCE_BUNDLE} is not a {BUNDLE_SCHEMA} document"
    if str(doc.get("schema_version", "")).split(".")[0] != "1":
        return None, None, f"{EVIDENCE_BUNDLE} schema_version is not 1.x"
    if not isinstance(doc.get("runs"), list) or not isinstance(doc.get("claims"), list):
        return None, None, f"{EVIDENCE_BUNDLE} has no runs/claims lists"
    return doc, sha256_hex(raw), ""


def _failed_pair(
    reason: str, main_claims: list[str], tool: dict[str, Any], details: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        record(
            "executability", FAILED, reason, required=False, tool=tool, details=details
        ),
        record(
            "reproduction",
            NOT_RUN,
            "nothing was replayed (see executability)",
            required=False,
            tool=tool,
            details={**details, "targets": list(main_claims)},
        ),
    ]


def rerun_preflight(
    project: Path, main_claims: list[str], *, tool: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """The two records when nothing can be run, else ``None`` (no sandbox needed).

    * no evidence bundle in the snapshot -> both ``not-run``;
    * a bundle that is a symlink, unreadable or not a 1.x evidence bundle, or a
      declared dependency that is an option, URL or path -> ``executability``
      failed, ``reproduction`` ``not-run``.
    """
    located = nofollow_path(project, EVIDENCE_BUNDLE.as_posix())
    if located is not None and not os.path.lexists(located):
        return not_run_pair(
            f"the snapshot has no Clew evidence bundle at {EVIDENCE_BUNDLE}; "
            "nothing to rerun",
            main_claims,
            tool=tool,
        )
    _doc, _sha, problem = load_bundle(project)
    if problem:
        return _failed_pair(
            f"refused evidence bundle: {problem}", main_claims, tool, {}
        )
    deps = declared_dependencies(project)
    if deps.refused:
        return _failed_pair(
            "declared dependencies that cannot be fetched from the package index in "
            f"isolation (options, URLs, paths or control characters): {deps.refused}",
            main_claims,
            tool,
            {"dependencies": deps.as_dict()},
        )
    return None


class ClewRerunExecutor:
    """Executor protocol implementation: clew's rerun in a sealed sandbox, verified on the host."""

    name = "apptainer"

    def __init__(
        self,
        sandbox: ApptainerSandbox,
        *,
        clew_requirement: str,
        rerun_timeout_s: float = RERUN_TIMEOUT_S,
        install_timeout_s: float = INSTALL_TIMEOUT_S,
        run_root: Path | None = None,
    ) -> None:
        canonical = canonical_requirement(clew_requirement)
        if canonical is None:
            raise SandboxError(
                f"--clew-requirement {clew_requirement!r} is not a plain requirement"
            )
        self.sandbox = sandbox
        self.clew_requirement = canonical
        self.rerun_timeout_s = rerun_timeout_s
        self.install_timeout_s = install_timeout_s
        self.run_root = run_root

    @property
    def tool(self) -> dict[str, Any]:
        return clew_tool(self.clew_requirement)

    def rerun_argv(self) -> list[str]:
        return [
            f"{WORK}/clew-venv/bin/python",
            "-I",
            f"{WORK}/clew-venv/bin/clew",
            "bundle",
            "rerun",
            f"{WORK}/project/{EVIDENCE_BUNDLE.as_posix()}",
            "--project-root",
            f"{WORK}/project",
            "--work-dir",
            REPLAY_DIR,
            "--python",
            f"{WORK}/venv/bin/python",
            "--timeout",
            str(int(self.rerun_timeout_s)),
            "--json",
        ]

    def run(
        self,
        project: Path,
        manifest: dict[str, Any],
        report: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        main_claims = list(manifest["main_claims"])
        run: SandboxRun | None = None
        try:
            early = rerun_preflight(project, main_claims, tool=self.tool)
            if early is not None:
                return early
            run = self.sandbox.open_run(
                self.run_root or project.parent / "sandbox-runs"
            )
            return self._run_sealed(run, project, main_claims, report)
        except Exception as e:  # noqa: BLE001 - the executor must never break admission
            details = {"error": f"{type(e).__name__}: {e}"}
            if run is not None:
                details["sandbox_run_id"] = run.run_id
            return _failed_pair(
                f"the isolated executor failed: {type(e).__name__}: {e}",
                main_claims,
                self.tool,
                details,
            )
        finally:
            if run is not None:
                try:
                    run.finalize()
                except OSError:
                    pass

    def _install(
        self, run: SandboxRun, venv: str, wheels: str, reqs: str
    ) -> CommandResult:
        made = run.run_command(
            ["python3", "-m", "venv", f"{WORK}/{venv}"],
            timeout=self.install_timeout_s,
            phase=f"create-{venv}",
        )
        if made.exit_code != 0:
            return made
        return run.run_command(
            [
                f"{WORK}/{venv}/bin/python",
                "-m",
                "pip",
                "install",
                "--no-index",
                *WHEEL_ONLY,
                "--find-links",
                f"{WORK}/{wheels}",
                "-r",
                f"{WORK}/{reqs}",
            ],
            timeout=self.install_timeout_s,
            phase=f"install-{venv}",
        )

    def _fetch(
        self, run: SandboxRun, wheels: str, reqs: str, phase: str
    ) -> CommandResult:
        return run.run_command(
            [
                "python3",
                "-m",
                "pip",
                "download",
                *WHEEL_ONLY,
                "--index-url",
                PACKAGE_INDEX_URL,
                "--dest",
                f"{WORK}/{wheels}",
                "-r",
                f"{WORK}/{reqs}",
            ],
            timeout=self.install_timeout_s,
            egress=PACKAGE_INDEX_EGRESS,
            phase=phase,
        )

    def _run_sealed(
        self,
        run: SandboxRun,
        project: Path,
        main_claims: list[str],
        report: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        doc, bundle_sha, problem = load_bundle(project)
        if doc is None:
            raise SandboxError(problem)
        deps = declared_dependencies(project).as_dict()
        (run.work / "requirements.txt").write_text(
            "".join(f"{r}\n" for r in deps["requirements"]), encoding="utf-8"
        )
        (run.work / "clew-requirements.txt").write_text(
            f"{self.clew_requirement}\n", encoding="utf-8"
        )
        run.note("dependencies", {**deps, "clew_requirement": self.clew_requirement})
        for wheels, reqs, phase in (
            ("wheels", "requirements.txt", "fetch-dependencies"),
            ("clew-wheels", "clew-requirements.txt", "fetch-clew"),
        ):
            res = self._fetch(run, wheels, reqs, phase)
            if res.exit_code != 0:
                return self._setup_failed(
                    run, main_claims, res, "dependencies are not available as wheels"
                )
        outputs = sorted(
            {
                rel
                for r in doc["runs"]
                if isinstance(r, dict)
                for rel in (r.get("outputs") or {})
            }
        )
        run.stage_project(project, remove=outputs)
        for venv, wheels, reqs in (
            ("venv", "wheels", "requirements.txt"),
            ("clew-venv", "clew-wheels", "clew-requirements.txt"),
        ):
            res = self._install(run, venv, wheels, reqs)
            if res.exit_code != 0:
                return self._setup_failed(
                    run, main_claims, res, f"offline install into {venv} failed"
                )
        run.make_readonly("venv")
        run.make_readonly("clew-venv")
        rerun = run.run_command(
            self.rerun_argv(),
            timeout=self.rerun_timeout_s * max(1, len(doc["runs"])) + RERUN_GRACE_S,
            phase="rerun",
            pwd=f"{WORK}/project",
        )
        hint, hint_error = None, None
        try:
            hint = parse_rerun_report(rerun.stdout)
        except RerunReportError as e:
            hint_error = str(e)
        replay_root = run.work / "replay"
        runs = host_runs(doc, hint, replay_root)
        claims = host_claims(doc, runs, hint, replay_root)
        write_record(
            run.out / "host-verification.json", {"runs": runs, "claims": claims}
        )
        outcome = run.finalize()
        details = {
            **self._details(run, outcome),
            "bundle_sha256": bundle_sha,
            "rerun_exit_code": rerun.exit_code,
            "rerun_killed_for": rerun.killed_for,
            "sandbox_reported": sandbox_reported(hint, hint_error),
        }
        binding = submission_binding(doc, report, main_claims)
        return [
            self._executability(rerun, runs, details),
            self._reproduction(claims, main_claims, binding, runs, details),
        ]

    def _executability(
        self, rerun: CommandResult, runs: list[dict[str, Any]], details: dict[str, Any]
    ) -> dict[str, Any]:
        missing = {
            r["run_id"]: [o["path"] for o in r["outputs"] if o["actual_sha256"] is None]
            for r in runs
            if any(o["actual_sha256"] is None for o in r["outputs"])
        }
        body = {
            **details,
            "host_runs": {r["run_id"]: r["status"] for r in runs},
            "missing_outputs": missing,
        }
        if rerun.killed_for is not None:
            reason = f"the rerun was killed ({rerun.killed_for})"
        elif missing:
            reason = f"{len(missing)} run(s) did not produce their recorded outputs: {sorted(missing)}"
        else:
            return record("executability", PASSED,
                          f"every recorded output of {len(runs)} run(s) was produced in isolation",
                          required=False, tool=self.tool, details=body)  # fmt: skip
        return record(
            "executability",
            FAILED,
            reason,
            required=False,
            tool=self.tool,
            details=body,
        )

    def _reproduction(
        self,
        claims: list[dict[str, Any]],
        main_claims: list[str],
        binding: dict[str, str],
        runs: list[dict[str, Any]],
        details: dict[str, Any],
    ) -> dict[str, Any]:
        by_id = {c["claim_id"]: c for c in claims}
        not_reproduced = {
            cid: by_id[cid]["status"] if cid in by_id else "not in the evidence bundle"
            for cid in main_claims
            if by_id.get(cid, {}).get("status") != "reproduced"
        }
        body = {
            **details,
            "targets": list(main_claims),
            "claims": [{**c, "main": c["claim_id"] in main_claims} for c in claims],
            "runs": runs,
            "not_reproduced": not_reproduced,
            "submission_mismatch": binding,
        }
        if binding:
            return record("reproduction", FAILED,
                          f"the snapshot's bundle disagrees with the submitted report: {binding}",
                          required=False, tool=self.tool, details=body)  # fmt: skip
        if not_reproduced:
            return record("reproduction", FAILED,
                          f"{len(not_reproduced)} main claim(s) not reproduced: {not_reproduced}",
                          required=False, tool=self.tool, details=body)  # fmt: skip
        return record("reproduction", PASSED,
                      f"all {len(main_claims)} main claim(s) reproduced (host-verified)",
                      required=False, tool=self.tool, details=body)  # fmt: skip

    def _details(self, run: SandboxRun, outcome: dict[str, Any]) -> dict[str, Any]:
        return {
            "sandbox": {
                **outcome["sandbox"],
                "run_id": run.run_id,
                "phases": [
                    {
                        "phase": p["phase"],
                        "egress": p["egress"]["mode"],
                        "exit_code": p["exit_code"],
                        "duration_s": p["duration_s"],
                        "killed_for": p["killed_for"],
                    }
                    for p in outcome["phases"]
                ],
            },
            "outcome_path": str(run.out / "outcome.json"),
            "outcome_sha256": outcome_sha256(outcome),
        }

    def _setup_failed(
        self, run: SandboxRun, main_claims: list[str], res: CommandResult, why: str
    ) -> list[dict[str, Any]]:
        outcome = run.finalize()
        details = {
            **self._details(run, outcome),
            "phase": res.phase,
            "exit_code": res.exit_code,
            "killed_for": res.killed_for,
            "stderr_tail": "\n".join(res.stderr.strip().splitlines()[-20:]),
        }
        reason = f"{why} (phase {res.phase}, exit {res.exit_code}"
        reason += f", killed: {res.killed_for})" if res.killed_for else ")"
        return _failed_pair(reason, main_claims, self.tool, details)
