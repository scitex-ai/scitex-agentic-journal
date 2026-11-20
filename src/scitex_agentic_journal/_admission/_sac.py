"""SAC's public plain-command CLI behind the journal's host-verification flow.

No SAC Python internals, agent harness, model key or host credential is used.
Its own layers live outside the author-visible bind. The journal bounds the
whole run directory, including SAC's transient output logs, and retains only
SAC outcome/egress metadata after each phase. Captured output stays capped.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .._records import file_sha256, sha256_hex
from ._paths import force_rmtree
from ._sandbox import (
    PACKAGE_INDEX_EGRESS,
    WORK,
    ApptainerSandbox,
    SandboxError,
    SandboxRun,
)
from ._sandbox_proc import HOST_PATH, host_env, run_limited


class SacSandbox(ApptainerSandbox):
    """Run each phase with ``sac sandbox exec`` from SAC 0.42.0 or later."""

    kind = "sac"
    host_filtered_egress = True

    def __init__(self, image: Path, *, sac_bin: Path | None = None, **kwargs):
        super().__init__(image, **kwargs)
        binary = (
            str(sac_bin) if sac_bin is not None else shutil.which("sac", path=HOST_PATH)
        )
        if not binary or not Path(binary).is_file() or not os.access(binary, os.X_OK):
            raise SandboxError(
                "SAC is unavailable; install scitex-agent-container>=0.42.0 and pass --sac-bin"
            )
        self.sac_bin = Path(binary).resolve()
        self._sac_version: str | None = None

    @property
    def sac_version(self) -> str:
        if self._sac_version is None:
            result = run_limited(
                [str(self.sac_bin), "--version"],
                env=host_env(Path(self.run_root or self.image.parent)),
                timeout_s=30,
            )
            match = re.search(
                r"scitex-agent-container, version (\d+)\.(\d+)\.(\d+)", result["stdout"]
            )
            if (
                result["exit_code"] != 0
                or match is None
                or tuple(map(int, match.groups())) < (0, 42, 0)
            ):
                raise SandboxError(
                    "the selected SAC must support sandbox exec (version >=0.42.0)"
                )
            self._sac_version = ".".join(match.groups())
        return self._sac_version

    def identity(self) -> dict[str, Any]:
        identity = super().identity()
        identity.update(
            {
                "runner": str(self.sac_bin),
                "runner_version": self.sac_version,
                "seal_flags": [
                    "--containall",
                    "--cleanenv",
                    "--net",
                    "--network",
                    "none",
                ],
                "offline_flags": ["--net", "--network", "none"],
                "fetch_flags": [
                    arg
                    for host in PACKAGE_INDEX_EGRESS
                    for arg in ("--egress-allow", host)
                ],
            }
        )
        identity["limits"]["cgroup"]["by"] = "systemd scope" if self.cgroups else None
        identity["limits"]["disk"]["includes"] = "author work and SAC layers/logs"
        return identity

    def open_run(self, run_root: Path | None = None) -> SacSandboxRun:
        root = run_root or self.run_root
        if root is None:
            raise SandboxError(
                "no run root: pass run_root to the sandbox or to open_run"
            )
        return SacSandboxRun(self, Path(root))

    def scope_argv(self) -> list[str]:
        """Limit the whole supervisor/container tree when user cgroups exist."""
        if not self.cgroups:
            return []
        binary = shutil.which("systemd-run", path=HOST_PATH)
        if binary is None:
            raise SandboxError(
                "systemd-run is required for the delegated resource limits"
            )
        return [
            binary,
            "--user",
            "--scope",
            "--quiet",
            f"--property=MemoryMax={self.limits.memory}",
            f"--property=TasksMax={self.limits.pids}",
            f"--property=CPUQuota={float(self.limits.cpus) * 100:g}%",
        ]


class SacSandboxRun(SandboxRun):
    """Shared staging and host verification, with SAC owning the runtime seal."""

    def _phase_root(self, phase: str) -> Path:
        name = f"{len(self.outcome['phases']):03d}-{sha256_hex(phase.encode())[:16]}"
        return self.dir / "sac" / name

    def _command_argv(self, argv, *, network, pwd, timeout, phase):
        sandbox = self.sandbox
        full = [
            *sandbox.scope_argv(),
            str(sandbox.sac_bin),
            "sandbox",
            "exec",
            "--image",
            str(sandbox.image),
            "--run-root",
            str(self._phase_root(phase)),
            "--timeout",
            str(timeout),
            "--after",
            "remove",
            "--name",
            "phase",
            "--size-mb",
            str(max(1, sandbox.limits.disk_bytes // (1 << 20))),
            "--bind",
            f"{self.work}:{WORK}:rw",
            "--pwd",
            pwd,
        ]
        for rel in self._readonly:
            full += ["--bind", f"{self.work / rel}:{WORK}/{rel}:ro"]
        if network:
            for host in PACKAGE_INDEX_EGRESS:
                full += ["--egress-allow", host]
        # SAC already sealed the environment. Keep its gateway proxy variables;
        # env -i would remove them and force pip into deliberately blocked DNS.
        env = self._container_env()
        return [
            *full,
            "--",
            "/usr/bin/env",
            *(f"{key}={value}" for key, value in sorted(env.items())),
            *argv,
        ]

    def watch_root(self) -> Path:
        # SAC's own tee files are transient but must count against the disk cap.
        return self.dir

    def command_metadata(self, phase: str) -> dict[str, Any]:
        root = self._phase_root(phase)
        records = list(root.glob("phase/*/out/outcome.json"))
        if len(records) != 1:
            return {"sac": {"outcome_available": False}}
        source = records[0]
        if source.stat().st_size > 64 << 20:
            raise SandboxError("SAC outcome exceeds the metadata size limit")
        document = json.loads(source.read_text())
        dest = self.out / "sac" / root.name
        dest.mkdir(parents=True, exist_ok=False)
        retained = {}
        for name in (
            "outcome.json",
            "egress_allowed.jsonl",
            "egress_blocked.jsonl",
            "egress_gateway.jsonl",
        ):
            path = source.parent / name
            if path.is_file():
                target = dest / name
                limit = (
                    (64 << 20)
                    if name == "outcome.json"
                    else self.sandbox.limits.output_cap_bytes
                )
                with path.open("rb") as stream:
                    target.write_bytes(stream.read(limit))
                retained[name] = {
                    "path": str(target),
                    "sha256": file_sha256(target),
                    "source_bytes": path.stat().st_size,
                    "truncated": path.stat().st_size > limit,
                }
        force_rmtree(root)
        return {
            "sac": {
                "outcome_available": True,
                "status": document.get("status"),
                "exit": document.get("exit"),
                "retained": retained,
            }
        }


__all__ = ["SacSandbox"]
