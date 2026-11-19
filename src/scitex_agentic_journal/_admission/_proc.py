"""Subprocess helpers for admission checks.

Every child process gets an explicit, minimal environment (never the
journal's own ``os.environ``): a PATH limited to the journal's interpreter
directory and the system bin directories, a private HOME under the
submission's record directory, and no credentials. Git is told never to
prompt, so a private repository fails fast instead of hanging.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcResult:
    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


def child_env(private_home: Path) -> dict[str, str]:
    """The only environment admission subprocesses ever see."""
    private_home.mkdir(parents=True, exist_ok=True)
    bindir = str(Path(sys.executable).parent)
    return {
        "PATH": f"{bindir}:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(private_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def run(
    argv: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
    timeout_s: float,
) -> ProcResult:
    """Run ``argv`` without a shell; capture output; never raise on exit code."""
    try:
        done = subprocess.run(
            argv,
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        return ProcResult(
            tuple(argv),
            None,
            _text(e.stdout),
            _text(e.stderr),
            timed_out=True,
        )
    except FileNotFoundError as e:
        return ProcResult(tuple(argv), None, "", f"executable not found: {e}")
    return ProcResult(tuple(argv), done.returncode, done.stdout, done.stderr)


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def tail(text: str, lines: int = 20) -> str:
    """Last ``lines`` lines of ``text`` (for reasons stored in records)."""
    return "\n".join(text.strip().splitlines()[-lines:])
