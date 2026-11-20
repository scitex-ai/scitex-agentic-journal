"""Host-side process control for sandbox phases: limits, capped output, disk cap.

* :class:`ResourceLimits` - the per-phase limits a sandbox applies.
* :func:`cgroup_delegation` - whether apptainer can apply memory/CPU/PID
  limits for this user (cgroup v2 with systemd delegation); the outcome
  record states the answer, so a limit is never silently missing.
* :func:`run_limited` - runs the apptainer argv in its own process group,
  keeps at most ``output_cap`` bytes of stdout/stderr (the rest is counted
  and dropped), kills the group on timeout, and polls the run's ``work/``
  size, killing the group when it outgrows the disk cap.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

HOST_PATH = "/usr/local/bin:/usr/bin:/bin"
APPTAINER_CONF = Path("/etc/apptainer/apptainer.conf")
CGROUP_ROOT = Path("/sys/fs/cgroup")


@dataclass(frozen=True)
class ResourceLimits:
    """Per-phase limits. cgroup limits apply only where delegation exists (recorded)."""

    memory: str = "8G"
    cpus: str = "4"
    pids: int = 4_096
    #: Cap on everything written under the run's work/ (polled; see DiskWatchdog).
    disk_bytes: int = 16 << 30
    #: Bytes of stdout/stderr kept per phase; the rest is counted and dropped.
    output_cap_bytes: int = 1 << 20
    disk_poll_s: float = 2.0


def user_bus() -> tuple[str, Path]:
    """This user's systemd runtime dir and session bus socket (derived, not inherited)."""
    runtime = Path("/run/user") / str(os.getuid())
    return str(runtime), runtime / "bus"


def host_env(home: Path, *, systemd_bus: bool = False) -> dict[str, str]:
    """The ONLY environment the apptainer process itself is started with.

    With ``systemd_bus`` (cgroup limits in use), apptainer also gets the
    user's runtime dir and session bus address, which it needs to create the
    limited cgroup through systemd; both are derived from the uid, never
    copied from the journal's own environment.
    """
    env = {"PATH": HOST_PATH, "HOME": str(home), "LANG": "C.UTF-8"}
    if systemd_bus:
        runtime, bus = user_bus()
        env["XDG_RUNTIME_DIR"] = runtime
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
    return env


def cgroup_delegation() -> tuple[bool, str]:
    """Whether apptainer can apply --memory/--cpus/--pids-limit for this user."""
    if not (CGROUP_ROOT / "cgroup.controllers").is_file():
        return False, "cgroup v2 is not mounted at /sys/fs/cgroup"
    uid = os.getuid()
    delegated = (
        CGROUP_ROOT
        / "user.slice"
        / f"user-{uid}.slice"
        / f"user@{uid}.service"
        / "cgroup.controllers"
    )
    try:
        controllers = set(delegated.read_text().split())
    except OSError:
        return False, f"no systemd user delegation at {delegated}"
    missing = {"memory", "pids", "cpu"} - controllers
    if missing:
        return False, f"controllers not delegated to uid {uid}: {sorted(missing)}"
    try:
        conf = APPTAINER_CONF.read_text()
    except OSError:
        return False, f"cannot read {APPTAINER_CONF}"
    if not re.search(r"^\s*systemd cgroups\s*=\s*yes\s*$", conf, re.MULTILINE):
        return False, f"'systemd cgroups = yes' is not set in {APPTAINER_CONF}"
    _runtime, bus = user_bus()
    if not bus.is_socket():
        return False, f"no systemd user session bus at {bus}"
    return True, "cgroup v2 with memory/pids/cpu delegated to the user"


class _CappedReader(threading.Thread):
    """Keeps the first ``cap`` bytes of a pipe, counts and discards the rest."""

    def __init__(self, stream: IO[bytes], cap: int) -> None:
        super().__init__(daemon=True)
        self.stream, self.cap = stream, cap
        self.kept = bytearray()
        self.total = 0

    def run(self) -> None:
        for block in iter(lambda: self.stream.read(1 << 16), b""):
            self.total += len(block)
            room = self.cap - len(self.kept)
            if room > 0:
                self.kept += block[:room]

    def text(self) -> str:
        return bytes(self.kept).decode("utf-8", "replace")


def dir_bytes(path: Path) -> int:
    """Allocated bytes under ``path`` (never follows symlinks)."""
    total = 0
    for dirpath, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_blocks * 512
            except OSError:
                continue
    return total


class DiskWatchdog(threading.Thread):
    """Kills the phase's process group when ``root`` grows past ``limit`` bytes."""

    def __init__(self, root: Path, limit: int, pgid: int, poll_s: float) -> None:
        super().__init__(daemon=True)
        self.root, self.limit, self.pgid, self.poll_s = root, limit, pgid, poll_s
        self.peak = 0
        self.exceeded = False
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.wait(self.poll_s):
            used = dir_bytes(self.root)
            self.peak = max(self.peak, used)
            if used > self.limit:
                self.exceeded = True
                _kill_group(self.pgid)
                return


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_limited(
    argv: Sequence[str],
    *,
    env: dict[str, str],
    timeout_s: float,
    output_cap: int = 1 << 20,
    watch: tuple[Path, int, float] | None = None,
) -> dict[str, Any]:
    """Run ``argv`` (no shell) with capped output, a timeout and an optional disk cap.

    ``watch`` is ``(root, limit_bytes, poll_s)``. ``exit_code`` is None when the
    process group was killed (timeout or disk).
    """
    proc = subprocess.Popen(
        list(argv),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert proc.stdout is not None and proc.stderr is not None
    readers = [
        _CappedReader(proc.stdout, output_cap),
        _CappedReader(proc.stderr, output_cap),
    ]
    for reader in readers:
        reader.start()
    dog = None
    if watch is not None:
        dog = DiskWatchdog(watch[0], watch[1], proc.pid, watch[2])
        dog.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(proc.pid)
        proc.wait()
    if dog is not None:
        dog.stop.set()
        dog.join()
    for reader in readers:
        reader.join()
    exceeded = dog is not None and dog.exceeded
    return {
        "exit_code": None if (timed_out or exceeded) else proc.returncode,
        "stdout": readers[0].text(),
        "stderr": readers[1].text(),
        "stdout_total": readers[0].total,
        "stderr_total": readers[1].total,
        "timed_out": timed_out,
        "disk_exceeded": exceeded,
        "disk_peak": dog.peak if dog is not None else None,
    }
