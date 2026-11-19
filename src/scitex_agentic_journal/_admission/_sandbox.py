"""Isolated execution of author code in a sealed apptainer container (design §11 D17).

Author code never runs on the journal host. Every command started here runs as::

    apptainer exec --containall --cleanenv --no-home --no-eval
        [--memory M --cpus C --pids-limit P]      # where cgroup v2 is delegated
        --no-mount bind-paths,hostfs,cwd --net --network none
        --bind <run>/work:/work:rw [--bind <run>/work/<sub>:/work/<sub>:ro ...]
        --pwd ... --env NAME=VALUE ... IMAGE /usr/bin/env HOME=/work/home argv...

(the package-index phase alone keeps the host network and apptainer.conf's
``bind path`` entries, i.e. ``--no-mount hostfs,cwd``, so the index resolves).

* **No host access.** ``--containall`` (own PID/IPC namespaces, no host
  ``$HOME``, ``/tmp`` or working directory), ``--no-mount bind-paths`` (the
  site-wide ``bind path`` entries of apptainer.conf are not mounted) and a
  single writable bind: the run's own ``work/`` directory.
* **No environment leak.** ``--cleanenv`` plus explicit ``--env`` entries; the
  apptainer process itself is started with a minimal environment, never the
  journal's ``os.environ``.
* **Egress.** A phase that may run author code gets ``--net --network none``
  (loopback only). The ONE exception is fetching declared dependencies from the
  package index, which is allowed only while no author file is in the run
  (:meth:`SandboxRun.stage_project` closes egress for the rest of the run) and
  only with ``pip download --only-binary=:all:`` (nothing is built or executed).
  Plain apptainer cannot filter that phase's traffic by host; the outcome
  record says so (``egress.enforced``).
* **Resources** (:mod:`._sandbox_proc`): capped stdout/stderr, a polled disk
  cap on ``work/``, and memory/CPU/PID limits where cgroup v2 is delegated;
  the outcome record says which limits were enforced.
* **Per-run reset.** Every run gets a fresh ``<run_root>/<run_id>/``; after the
  run every layer except ``out/`` is removed (permissions restored first).
* **Outcome record.** ``out/outcome.json`` lists the image (path + sha256,
  whether it was pinned), the apptainer version, the seal flags and limits,
  the environment NAMES and every phase (argv, egress, timing, exit code,
  output hashes and sizes).

SAC (scitex-agent-container) 0.40.x seals only TUI agent panes (a harness and a
model key are mandatory: SAC docs/sandbox.md "Limits", ``_sandbox/_spec.py``
``env.model_key``, ``_sandbox/_env_policy._require_tui_runtime``), so the
journal drives apptainer directly with the same seal.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scitex_agentic_journal._admission._paths import force_rmtree, remove_nofollow
from scitex_agentic_journal._admission._sandbox_proc import (
    HOST_PATH,
    ResourceLimits,
    cgroup_delegation,
    host_env,
    run_limited,
)
from scitex_agentic_journal._records import (
    canonical_json,
    file_sha256,
    sha256_hex,
    utcnow_iso,
    write_record,
)

OUTCOME_SCHEMA = "scitex-agentic-journal.sandbox-outcome"
OUTCOME_SCHEMA_VERSION = "1.1"
NO_EGRESS: tuple[str, ...] = ()
#: The only egress a sandbox phase may ask for: the Python package index.
PACKAGE_INDEX_EGRESS: tuple[str, ...] = ("pypi.org:443", "files.pythonhosted.org:443")
PACKAGE_INDEX_URL = "https://pypi.org/simple"
CONTAINER_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
WORK = "/work"
SEAL_FLAGS: tuple[str, ...] = (
    "--containall",
    "--cleanenv",
    "--no-home",
    "--no-eval",
)
#: Offline phases also drop apptainer.conf's ``bind path`` entries (which
#: include /etc/resolv.conf: there is no name resolution at all).
NO_MOUNT_OFFLINE: tuple[str, ...] = ("--no-mount", "bind-paths,hostfs,cwd")
#: The package-index phase keeps them, so the index name resolves.
NO_MOUNT_FETCH: tuple[str, ...] = ("--no-mount", "hostfs,cwd")
NETWORK_NONE: tuple[str, ...] = ("--net", "--network", "none")
TAIL_LINES = 40
#: Never staged: git history would hand author code the deleted outputs back.
STAGE_EXCLUDE: tuple[str, ...] = (".git",)


class SandboxError(RuntimeError):
    """The sandbox cannot be used as configured (missing runtime or image, bad egress)."""


@dataclass(frozen=True)
class CommandResult:
    phase: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float
    killed_for: str | None = None


@dataclass(frozen=True)
class SandboxResult:
    """What :meth:`ApptainerSandbox.run_command` returns."""

    exit_code: int | None
    stdout: str
    stderr: str
    outcome_record: dict[str, Any]


def _tail(text: str, lines: int = TAIL_LINES) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


class ApptainerSandbox:
    """A sealed apptainer runtime bound to one image."""

    kind = "apptainer"

    def __init__(
        self,
        image: Path,
        *,
        run_root: Path | None = None,
        expected_sha256: str | None = None,
        limits: ResourceLimits | None = None,
    ) -> None:
        apptainer = shutil.which("apptainer", path=HOST_PATH)
        if apptainer is None:
            raise SandboxError(f"apptainer is not installed (searched {HOST_PATH})")
        image = Path(image).expanduser().resolve()
        if not image.is_file():
            raise SandboxError(f"sandbox image {image} does not exist")
        self.apptainer = apptainer
        self.image = image
        self.run_root = run_root
        self.limits = limits or ResourceLimits()
        self.expected_sha256 = expected_sha256.lower() if expected_sha256 else None
        self._image_sha256: str | None = None
        self._version: str | None = None
        self.cgroups, self.cgroups_reason = cgroup_delegation()
        if (
            self.expected_sha256 is not None
            and self.image_sha256 != self.expected_sha256
        ):
            raise SandboxError(
                f"sandbox image {image} has sha256 {self.image_sha256}, not the "
                f"pinned {self.expected_sha256}"
            )

    @property
    def version(self) -> str:
        if self._version is None:
            home = Path(self.run_root or self.image.parent)
            res = run_limited(
                [self.apptainer, "--version"], env=host_env(home), timeout_s=30
            )
            if res["exit_code"] != 0:
                raise SandboxError(
                    f"apptainer --version failed: {_tail(res['stderr'], 3)}"
                )
            self._version = res["stdout"].strip()
        return self._version

    @property
    def image_sha256(self) -> str:
        if self._image_sha256 is None:
            self._image_sha256 = file_sha256(self.image)
        return self._image_sha256

    def limit_flags(self) -> list[str]:
        if not self.cgroups:
            return []
        lim = self.limits
        return [
            "--memory",
            lim.memory,
            "--cpus",
            lim.cpus,
            "--pids-limit",
            str(lim.pids),
        ]

    def identity(self) -> dict[str, Any]:
        """What the outcome record and check records name as the sandbox."""
        lim = self.limits
        return {
            "kind": self.kind,
            "apptainer": self.apptainer,
            "apptainer_version": self.version,
            "image": str(self.image),
            "image_sha256": self.image_sha256,
            "image_pinned": self.expected_sha256 is not None,
            "seal_flags": list(SEAL_FLAGS),
            "offline_flags": [*NO_MOUNT_OFFLINE, *NETWORK_NONE],
            "fetch_flags": list(NO_MOUNT_FETCH),
            "limits": {
                "cgroup": {
                    "enforced": self.cgroups,
                    "reason": self.cgroups_reason,
                    "memory": lim.memory,
                    "cpus": lim.cpus,
                    "pids": lim.pids,
                },
                "disk": {
                    "enforced": True,
                    "by": "poll",
                    "limit_bytes": lim.disk_bytes,
                    "poll_s": lim.disk_poll_s,
                },
                "output_cap_bytes": lim.output_cap_bytes,
            },
        }

    def open_run(self, run_root: Path | None = None) -> SandboxRun:
        root = run_root or self.run_root
        if root is None:
            raise SandboxError(
                "no run root: pass run_root to the sandbox or to open_run"
            )
        return SandboxRun(self, Path(root))

    def run_command(
        self,
        project_dir: Path | None,
        argv: Sequence[str],
        *,
        timeout: float,
        egress: Sequence[str] = NO_EGRESS,
        run_root: Path | None = None,
    ) -> SandboxResult:
        """Run ``argv`` once, in a fresh run, on a copy of ``project_dir`` at /work/project."""
        run = self.open_run(run_root)
        try:
            if project_dir is not None:
                run.stage_project(project_dir)
            res = run.run_command(
                argv,
                timeout=timeout,
                egress=egress,
                phase="command",
                pwd=f"{WORK}/project" if project_dir is not None else WORK,
            )
        finally:
            outcome = run.finalize()
        return SandboxResult(res.exit_code, res.stdout, res.stderr, outcome)


@dataclass
class SandboxRun:
    """One per-run reset: a fresh run directory, its phases and its outcome record."""

    sandbox: ApptainerSandbox
    root: Path
    run_id: str = field(init=False)
    dir: Path = field(init=False)
    work: Path = field(init=False)
    out: Path = field(init=False)
    outcome: dict[str, Any] = field(init=False)
    _staged: bool = field(init=False, default=False)
    _readonly: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        stamp = re.sub(r"[^0-9T]", "", utcnow_iso()[:19]) + "Z"
        self.run_id = f"{stamp}-{secrets.token_hex(4)}"
        self.dir = self.root / self.run_id
        self.work = self.dir / "work"
        self.out = self.dir / "out"
        for sub in (
            self.work / "home",
            self.work / "tmp",
            self.out,
            self.dir / "host-home",
        ):
            sub.mkdir(parents=True, exist_ok=False)
        self.outcome = {
            "schema": OUTCOME_SCHEMA,
            "schema_version": OUTCOME_SCHEMA_VERSION,
            "run_id": self.run_id,
            "status": "running",
            "started_at": utcnow_iso(),
            "sandbox": self.sandbox.identity(),
            "env": {"names": sorted(self._container_env())},
            "project": None,
            "phases": [],
            "notes": {},
            "layers": {"after": "remove", "kept": ["out"]},
        }

    @staticmethod
    def _container_env() -> dict[str, str]:
        return {
            "PATH": CONTAINER_PATH,
            "HOME": f"{WORK}/home",
            "TMPDIR": f"{WORK}/tmp",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_NO_INPUT": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "NO_COLOR": "1",
        }

    def stage_project(self, project_dir: Path, *, remove: Sequence[str] = ()) -> Path:
        """Copy the checkout (minus .git) to /work/project; closes egress for good.

        Symlinks are copied as links, never followed. Each path in ``remove``
        (repo-relative) is then deleted from the copy without following links.
        """
        dest = self.work / "project"
        shutil.copytree(
            project_dir,
            dest,
            symlinks=True,
            ignore=shutil.ignore_patterns(*STAGE_EXCLUDE),
        )
        self._staged = True
        removed = [rel for rel in remove if remove_nofollow(dest, rel)]
        files = 0
        for dirpath, _dirs, names in os.walk(dest, followlinks=False):
            files += sum(
                1 for n in names if not os.path.islink(os.path.join(dirpath, n))
            )
        self.outcome["project"] = {
            "source": str(project_dir),
            "container_path": f"{WORK}/project",
            "excluded": list(STAGE_EXCLUDE),
            "files": files,
            "removed_outputs": removed,
        }
        return dest

    def make_readonly(self, relative: str) -> None:
        """Bind ``/work/<relative>`` read-only in every later phase."""
        self._readonly.append(relative)

    def note(self, key: str, value: Any) -> None:
        self.outcome["notes"][key] = value

    def _argv(self, argv: Sequence[str], *, network: bool, pwd: str) -> list[str]:
        out = [
            self.sandbox.apptainer,
            "exec",
            *SEAL_FLAGS,
            *self.sandbox.limit_flags(),
        ]
        if network:
            out += list(NO_MOUNT_FETCH)
        else:
            out += [*NO_MOUNT_OFFLINE, *NETWORK_NONE]
        out += ["--bind", f"{self.work}:{WORK}:rw"]
        for rel in self._readonly:
            out += ["--bind", f"{self.work / rel}:{WORK}/{rel}:ro"]
        out += ["--pwd", pwd]
        env = self._container_env()
        for name, value in sorted(env.items()):
            if name != "HOME":
                out += ["--env", f"{name}={value}"]
        # apptainer refuses to override HOME through --env; env(1) sets it.
        return [
            *out,
            str(self.sandbox.image),
            "/usr/bin/env",
            f"HOME={env['HOME']}",
            *argv,
        ]

    def run_command(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        egress: Sequence[str] = NO_EGRESS,
        phase: str,
        pwd: str = WORK,
    ) -> CommandResult:
        egress = tuple(egress)
        if egress and egress != PACKAGE_INDEX_EGRESS:
            raise SandboxError(
                f"egress {list(egress)} is not allowed; only none or the package "
                f"index {list(PACKAGE_INDEX_EGRESS)}"
            )
        if egress and self._staged:
            raise SandboxError(
                "egress is closed once author files are staged into the run"
            )
        full = self._argv(argv, network=bool(egress), pwd=pwd)
        lim = self.sandbox.limits
        started, t0 = utcnow_iso(), time.monotonic()
        res = run_limited(
            full,
            env=host_env(self.dir / "host-home", systemd_bus=self.sandbox.cgroups),
            timeout_s=timeout,
            output_cap=lim.output_cap_bytes,
            watch=(self.work, lim.disk_bytes, lim.disk_poll_s),
        )
        duration = round(time.monotonic() - t0, 3)
        killed_for = (
            "timeout" if res["timed_out"] else "disk" if res["disk_exceeded"] else None
        )
        self.outcome["phases"].append(
            {
                "phase": phase,
                "argv": list(argv),
                "apptainer_argv": full,
                "egress": {
                    "mode": "package-index" if egress else "none",
                    "hosts": list(egress),
                    # Plain apptainer has no per-host filter: a package-index phase
                    # has the host network, and is bounded by having no author file
                    # in the run and by pip --only-binary (nothing executed).
                    "enforced": not egress,
                    "author_files_present": self._staged,
                },
                "started_at": started,
                "duration_s": duration,
                "timeout_s": timeout,
                "timed_out": res["timed_out"],
                "killed_for": killed_for,
                "disk_peak_bytes": res["disk_peak"],
                "exit_code": res["exit_code"],
                "stdout_sha256": sha256_hex(res["stdout"].encode()),
                "stdout_bytes": res["stdout_total"],
                "stderr_bytes": res["stderr_total"],
                "output_truncated": max(res["stdout_total"], res["stderr_total"])
                > lim.output_cap_bytes,
                "stderr_tail": _tail(res["stderr"]),
            }
        )
        return CommandResult(
            phase,
            res["exit_code"],
            res["stdout"],
            res["stderr"],
            res["timed_out"],
            duration,
            killed_for,
        )

    def finalize(self) -> dict[str, Any]:
        """Write ``out/outcome.json``, remove every other layer, return the record."""
        if self.outcome["status"] == "finalized":
            return self.outcome
        self.outcome["status"] = "finalized"
        self.outcome["finalized_at"] = utcnow_iso()
        write_record(self.out / "outcome.json", self.outcome)
        for child in self.dir.iterdir():
            if child.name != "out":
                force_rmtree(child)
        return self.outcome


def outcome_sha256(outcome: dict[str, Any]) -> str:
    """The hash check records cite for an outcome record."""
    return sha256_hex(canonical_json(outcome))
