"""The isolated ``Executor`` for the executability and reproduction checks (design §11 D17).

:class:`ClewRerunExecutor` runs scitex-clew's store-free rerun of the
snapshot's evidence bundle inside a sealed :class:`ApptainerSandbox` run:

1. ``fetch-dependencies`` - the project's declared dependencies
   (:mod:`._deps`) plus the pinned scitex-clew, downloaded as wheels only
   (``pip download --only-binary=:all:``) from the package index. This is the
   only phase with egress, and no author file is in the run yet.
2. the checkout is copied into the run (egress is closed from here on);
3. ``create-venv`` / ``install`` - offline (``--network none``) install from
   the downloaded wheels into ``/work/venv``, which later phases see read-only;
4. ``rerun`` - ``clew bundle rerun <bundle> --project-root /work/project
   --timeout S --json``, offline.

The rerun report maps to ``executability`` (passed iff ``executable``) and
``reproduction`` (passed iff every main claim is ``reproduced``). Both records
cite the run's outcome record by hash and name the sandbox (image sha256,
apptainer version). Neither is required for admission (design §13.1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scitex_agentic_journal._admission._checks import FAILED, NOT_RUN, record
from scitex_agentic_journal._admission._deps import declared_dependencies
from scitex_agentic_journal._admission._rerun_report import (
    RerunReportError,
    executability_record,
    not_run_pair,
    parse_rerun_report,
    reproduction_record,
)
from scitex_agentic_journal._admission._sandbox import (
    PACKAGE_INDEX_EGRESS,
    PACKAGE_INDEX_URL,
    WORK,
    ApptainerSandbox,
    CommandResult,
    SandboxRun,
    outcome_sha256,
)
from scitex_agentic_journal._records import file_sha256, write_record

EVIDENCE_BUNDLE = Path(".scitex") / "clew" / "evidence-bundle.json"
RERUN_TIMEOUT_S = 1800.0
INSTALL_TIMEOUT_S = 900.0
#: Slack on top of clew's own --timeout for interpreter start and reporting.
RERUN_GRACE_S = 120.0


def clew_tool(clew_requirement: str) -> dict[str, Any]:
    """The ``tool`` both check records name."""
    return {
        "name": "scitex-clew bundle rerun (sealed apptainer sandbox)",
        "version": clew_requirement,
    }


def rerun_preflight(
    project: Path, main_claims: list[str], *, tool: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """The two records when nothing can be run, else ``None`` (no sandbox needed).

    * no evidence bundle in the snapshot -> both ``not-run``;
    * a declared dependency that is an option, URL or path -> ``executability``
      failed (the project cannot be installed in isolation), ``reproduction``
      ``not-run``.
    """
    if not (project / EVIDENCE_BUNDLE).is_file():
        return not_run_pair(
            f"the snapshot has no Clew evidence bundle at {EVIDENCE_BUNDLE}; "
            "nothing to rerun",
            main_claims,
            tool=tool,
        )
    deps = declared_dependencies(project)
    if not deps.refused:
        return None
    reason = (
        "declared dependencies that cannot be fetched from the package index "
        f"in isolation (options, URLs or paths are refused): {deps.refused}"
    )
    return [
        record(
            "executability",
            FAILED,
            reason,
            required=False,
            tool=tool,
            details={"dependencies": deps.as_dict()},
        ),
        record(
            "reproduction",
            NOT_RUN,
            "the project cannot be installed in isolation (see executability)",
            required=False,
            tool=tool,
            details={"targets": list(main_claims)},
        ),
    ]


class ClewRerunExecutor:
    """Executor protocol implementation: clew's store-free rerun in a sealed sandbox."""

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
        self.sandbox = sandbox
        self.clew_requirement = clew_requirement
        self.rerun_timeout_s = rerun_timeout_s
        self.install_timeout_s = install_timeout_s
        self.run_root = run_root

    @property
    def tool(self) -> dict[str, Any]:
        return clew_tool(self.clew_requirement)

    def rerun_argv(self) -> list[str]:
        return [
            f"{WORK}/venv/bin/clew",
            "bundle",
            "rerun",
            f"{WORK}/project/{EVIDENCE_BUNDLE.as_posix()}",
            "--project-root",
            f"{WORK}/project",
            "--timeout",
            str(int(self.rerun_timeout_s)),
            "--json",
        ]

    def run(self, project: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        main_claims = list(manifest["main_claims"])
        early = rerun_preflight(project, main_claims, tool=self.tool)
        if early is not None:
            return early
        bundle = project / EVIDENCE_BUNDLE
        deps = declared_dependencies(project)
        run = self.sandbox.open_run(self.run_root or project.parent / "sandbox-runs")
        try:
            return self._run_sealed(run, project, bundle, deps.as_dict(), main_claims)
        finally:
            if run.outcome["status"] != "finalized":
                run.finalize()

    def _run_sealed(
        self,
        run: SandboxRun,
        project: Path,
        bundle: Path,
        deps: dict[str, Any],
        main_claims: list[str],
    ) -> list[dict[str, Any]]:
        requirements = [*deps["requirements"], self.clew_requirement]
        (run.work / "requirements.txt").write_text("\n".join(requirements) + "\n")
        run.note("dependencies", {**deps, "clew_requirement": self.clew_requirement})
        fetch = run.run_command(
            [
                "python3",
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                "--no-cache-dir",
                "--index-url",
                PACKAGE_INDEX_URL,
                "--dest",
                f"{WORK}/wheels",
                "-r",
                f"{WORK}/requirements.txt",
            ],
            timeout=self.install_timeout_s,
            egress=PACKAGE_INDEX_EGRESS,
            phase="fetch-dependencies",
        )
        wheels = sorted((run.work / "wheels").glob("*")) if fetch.exit_code == 0 else []
        run.note("wheels", [{"name": w.name, "sha256": file_sha256(w)} for w in wheels])
        if fetch.exit_code != 0:
            return self._setup_failed(
                run, main_claims, fetch, "dependencies are not available as wheels"
            )
        run.stage_project(project)
        venv = run.run_command(
            ["python3", "-m", "venv", f"{WORK}/venv"],
            timeout=self.install_timeout_s,
            phase="create-venv",
        )
        if venv.exit_code != 0:
            return self._setup_failed(
                run, main_claims, venv, "the sandbox image cannot create a venv"
            )
        install = run.run_command(
            [
                f"{WORK}/venv/bin/python",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-cache-dir",
                "--find-links",
                f"{WORK}/wheels",
                "-r",
                f"{WORK}/requirements.txt",
            ],
            timeout=self.install_timeout_s,
            phase="install",
        )
        if install.exit_code != 0:
            return self._setup_failed(
                run, main_claims, install, "offline install of the dependencies failed"
            )
        run.make_readonly("venv")
        rerun = run.run_command(
            self.rerun_argv(),
            timeout=self.rerun_timeout_s + RERUN_GRACE_S,
            phase="rerun",
            pwd=f"{WORK}/project",
        )
        (run.out / "rerun-stdout.txt").write_text(rerun.stdout, encoding="utf-8")
        try:
            report = parse_rerun_report(rerun.stdout)
        except RerunReportError as e:
            return self._setup_failed(
                run, main_claims, rerun, f"the rerun produced no valid report ({e})"
            )
        write_record(run.out / "rerun-report.json", report)
        outcome = run.finalize()
        details = self._details(run, outcome)
        return [
            executability_record(report, tool=self.tool, details=details),
            reproduction_record(
                report,
                main_claims,
                bundle_sha256=file_sha256(bundle),
                tool=self.tool,
                details=details,
            ),
        ]

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
            "timed_out": res.timed_out,
            "stderr_tail": "\n".join(res.stderr.strip().splitlines()[-20:]),
        }
        return [
            record(
                "executability",
                FAILED,
                f"{why} (phase {res.phase}, exit {res.exit_code}"
                f"{', timed out' if res.timed_out else ''})",
                required=False,
                tool=self.tool,
                details=details,
            ),
            record(
                "reproduction",
                NOT_RUN,
                "the rerun did not produce a report (see executability)",
                required=False,
                tool=self.tool,
                details={**details, "targets": main_claims},
            ),
        ]
