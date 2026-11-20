"""Process limits for sandbox phases, exercised with the journal's own interpreter.

These run a trivial journal-owned command (never author code) to check the
output cap, the timeout kill and the disk watchdog of ``run_limited``.
"""

from __future__ import annotations

import sys

from scitex_agentic_journal._admission._sandbox_proc import (
    cgroup_delegation,
    host_env,
    run_limited,
)


def test_output_beyond_the_cap_is_counted_but_not_kept(tmp_path):
    # Arrange
    argv = [sys.executable, "-c", "import sys; sys.stdout.write('x' * 100_000)"]
    # Act
    res = run_limited(argv, env=host_env(tmp_path), timeout_s=60, output_cap=1_000)
    # Assert
    assert (len(res["stdout"]), res["stdout_total"]) == (1_000, 100_000)


def test_timeout_kills_the_process_group(tmp_path):
    # Arrange
    argv = [sys.executable, "-c", "import time; time.sleep(60)"]
    # Act
    res = run_limited(argv, env=host_env(tmp_path), timeout_s=1)
    # Assert
    assert (res["timed_out"], res["exit_code"]) == (True, None)


def test_disk_cap_kills_a_phase_that_writes_too_much(tmp_path):
    # Arrange
    work = tmp_path / "work"
    work.mkdir()
    code = (
        "import time\n"
        f"f = open({str(work / 'fill.bin')!r}, 'wb')\n"
        "for _ in range(400):\n"
        "    f.write(b'x' * 65_536); f.flush(); time.sleep(0.05)\n"
    )
    argv = [sys.executable, "-c", code]
    # Act
    res = run_limited(
        argv, env=host_env(tmp_path), timeout_s=60, watch=(work, 200_000, 0.1)
    )
    # Assert
    assert res["disk_exceeded"] is True


def test_cgroup_delegation_states_a_reason():
    # Arrange
    probe = cgroup_delegation
    # Act
    enforced, reason = probe()
    # Assert
    assert isinstance(enforced, bool) and reason
