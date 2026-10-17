"""Tests for the gate-1 Clew-DAG check (issue #4 / M1.3).

The no-mocks rule (NM001-003 / PA-306) forbids monkey-patching
``subprocess`` or stubbing the ``clew`` CLI in-process. Instead we
materialise a tiny **real** Python shim at ``tmp_path/clew`` that
emits a hard-coded JSON payload and exits with a hard-coded code,
and point :func:`verify_clew_dag` at it via the ``clew_bin``
override. Every assertion below runs against the same shape the
real CLI would produce — only the values are deterministic.

One opt-in test exercises the **real** ``clew`` binary when the
operator sets ``SCITEX_RUN_CLEW_TESTS=1`` (mirroring the existing
``SCITEX_RUN_NETWORK_TESTS`` pattern from #11 / #13); the full-pass
test additionally needs ``SCITEX_RUN_CLEW_STORE_TESTS=1`` (a
provisioned PostgreSQL clew store).
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import textwrap
from pathlib import Path

import pytest

from scitex_agentic_journal._gate1 import (
    CLEW_MARKER_DIR,
    ClewVerification,
    GateFailure,
    verify_clew_dag,
)
from scitex_agentic_journal._gate1._clew_dag import (
    _find_clew_project_dir,
    _parse_verification_payload,
    _resolve_clew_binary,
)


# ---------------------------------------------------------------------------
# Real `clew`-shim factory — writes a tiny Python script that the real
# subprocess machinery actually execs. NO MOCKS; the script runs.
# ---------------------------------------------------------------------------


def _write_clew_shim(
    tmp_path: Path,
    *,
    stdout_payload: str,
    stderr_payload: str = "",
    exit_code: int = 0,
    sleep_s: float = 0.0,
) -> Path:
    """Write an executable Python script behaving like ``clew dag``.

    The shim records its argv as JSON to ``tmp_path/clew.argv``,
    unconditionally emits ``stdout_payload`` / ``stderr_payload``,
    then exits with ``exit_code``. Set ``sleep_s`` > 0 to exercise the
    timeout branch via a real ``time.sleep``.
    """
    shim = tmp_path / "clew"
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import sys, time, json
        if {sleep_s!r} > 0:
            time.sleep({sleep_s!r})
        open(sys.argv[0] + ".argv", "w").write(json.dumps(sys.argv[1:]))
        sys.stdout.write({stdout_payload!r})
        sys.stderr.write({stderr_payload!r})
        sys.exit({exit_code!r})
        """
    )
    shim.write_text(body)
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return shim


def _shim_argv(tmp_path: Path) -> list:
    """Read back the argv the shim recorded during the gate run."""
    return json.loads((tmp_path / "clew.argv").read_text(encoding="utf-8"))


def _make_clew_project(root: Path) -> Path:
    """Materialise a minimal ``<root>/.clew/`` so the locator finds it."""
    (root / CLEW_MARKER_DIR).mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# _find_clew_project_dir
# ---------------------------------------------------------------------------


def test_find_clew_project_dir_returns_bundle_root_when_marker_at_root(
    tmp_path: Path,
) -> None:
    # Arrange
    project = _make_clew_project(tmp_path)
    # Act
    found = _find_clew_project_dir(project)
    # Assert
    assert found == project


def test_find_clew_project_dir_returns_child_when_marker_inside_child(
    tmp_path: Path,
) -> None:
    # Arrange
    child = _make_clew_project(tmp_path / "paper")
    # Act
    found = _find_clew_project_dir(tmp_path)
    # Assert
    assert found == child


def test_find_clew_project_dir_raises_gate_failure_when_root_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    missing = tmp_path / "does-not-exist"
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _find_clew_project_dir(missing)


def test_find_clew_project_dir_raises_gate_failure_when_root_is_file(
    tmp_path: Path,
) -> None:
    # Arrange
    not_a_dir = tmp_path / "bundle.txt"
    not_a_dir.write_text("hi")
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _find_clew_project_dir(not_a_dir)


def test_find_clew_project_dir_raises_gate_failure_when_no_marker_anywhere(
    tmp_path: Path,
) -> None:
    # Arrange
    (tmp_path / "paper").mkdir()
    (tmp_path / "assets").mkdir()
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _find_clew_project_dir(tmp_path)


# ---------------------------------------------------------------------------
# _resolve_clew_binary
# ---------------------------------------------------------------------------


def test_resolve_clew_binary_returns_explicit_absolute_path_when_executable(
    tmp_path: Path,
) -> None:
    # Arrange
    shim = _write_clew_shim(tmp_path, stdout_payload="[]")
    # Act
    resolved = _resolve_clew_binary(str(shim))
    # Assert
    assert Path(resolved).resolve() == shim.resolve()


def test_resolve_clew_binary_raises_gate_failure_when_explicit_path_missing(
    tmp_path: Path,
) -> None:
    # Arrange
    missing = tmp_path / "no-such-clew"
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _resolve_clew_binary(str(missing))


@pytest.fixture
def empty_path_env(tmp_path: Path):
    """Set ``$PATH`` to a real-but-empty dir for the duration of one test.

    Hand-rolled yield-teardown fixture — does NOT use the forbidden
    ``monkeypatch`` fixture (NM002). The teardown restores the original
    ``PATH`` even if the test body raises.
    """
    empty = tmp_path / "empty-path-dir"
    empty.mkdir()
    original = os.environ.get("PATH")
    os.environ["PATH"] = str(empty)
    try:
        yield empty
    finally:
        if original is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = original


def test_resolve_clew_binary_raises_gate_failure_when_no_clew_on_path(
    empty_path_env: Path,
) -> None:
    # Arrange
    _ = empty_path_env  # the yield-fixture has already shrunk PATH
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _resolve_clew_binary(None)


# ---------------------------------------------------------------------------
# _parse_verification_payload
# ---------------------------------------------------------------------------


def test_parse_verification_payload_accepts_top_level_claims_object() -> None:
    # Arrange
    payload = json.dumps(
        {"claims": [{"id": "c1", "status": "green"}, {"id": "c2", "status": "red"}]}
    )
    # Act
    green, red = _parse_verification_payload(payload)
    # Assert
    assert (green, red) == (("c1",), ("c2",))


def test_parse_verification_payload_accepts_top_level_bare_list() -> None:
    # Arrange
    payload = json.dumps([{"id": "c1", "status": "green"}])
    # Act
    green, _red = _parse_verification_payload(payload)
    # Assert
    assert green == ("c1",)


def test_parse_verification_payload_buckets_non_green_status_as_red() -> None:
    # Arrange
    payload = json.dumps(
        [{"id": "c1", "status": "unknown"}, {"id": "c2", "status": "RED"}]
    )
    # Act
    green, red = _parse_verification_payload(payload)
    # Assert
    assert (green, red) == ((), ("c1", "c2"))


def test_parse_verification_payload_is_case_insensitive_on_green() -> None:
    # Arrange
    payload = json.dumps([{"id": "c1", "status": "GREEN"}])
    # Act
    green, _red = _parse_verification_payload(payload)
    # Assert
    assert green == ("c1",)


def test_parse_verification_payload_raises_gate_failure_on_non_json() -> None:
    # Arrange
    payload = "not-json-at-all"
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _parse_verification_payload(payload)


def test_parse_verification_payload_raises_gate_failure_on_unknown_top_level_shape() -> None:
    # Arrange
    payload = json.dumps("just a string")
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _parse_verification_payload(payload)


def test_parse_verification_payload_raises_gate_failure_when_claims_is_not_list() -> None:
    # Arrange
    payload = json.dumps({"claims": {"id": "c1"}})
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _parse_verification_payload(payload)


def test_parse_verification_payload_raises_gate_failure_on_non_object_entry() -> None:
    # Arrange
    payload = json.dumps([{"id": "c1", "status": "green"}, "oops"])
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        _parse_verification_payload(payload)


# ---------------------------------------------------------------------------
# verify_clew_dag — end-to-end via a real subprocess against the shim.
# ---------------------------------------------------------------------------


def test_verify_clew_dag_invokes_dag_claims_json(tmp_path: Path) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            {
                "target_files": [],
                "status": "verified",
                "is_verified": True,
                "num_runs": 1,
                "num_edges": 0,
                "topological_order": [],
                "runs": [{"session_id": "s1", "is_verified": True}],
                "edges": [],
            }
        ),
    )
    # Act
    verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert _shim_argv(tmp_path) == ["dag", "--claims", "--json"]


def _dag_runs_payload(runs: list[dict]) -> str:
    """Minimal ``clew dag --claims --json`` stdout for the given runs."""
    return json.dumps(
        {
            "status": "verified",
            "is_verified": True,
            "runs": runs,
        }
    )


def test_verify_clew_dag_passes_on_dag_shape_with_verified_run(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=_dag_runs_payload(
            [
                {"session_id": "s1", "is_verified": True},
                {"session_id": "s2", "is_verified": False},
            ]
        ),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.green_claims == ("s1",)


def test_verify_clew_dag_records_unverified_runs_as_red(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=_dag_runs_payload(
            [
                {"session_id": "s1", "is_verified": True},
                {"session_id": "s2", "is_verified": False},
            ]
        ),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.red_claims == ("s2",)


def test_verify_clew_dag_counts_total_runs(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=_dag_runs_payload(
            [
                {"session_id": "s1", "is_verified": True},
                {"session_id": "s2", "is_verified": False},
            ]
        ),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.total_claims == 2


def _unprovisioned_store_shim(tmp_path: Path) -> Path:
    """Shim mimicking a clew that dies with ``StoreProvisionError``."""
    return _write_clew_shim(
        tmp_path,
        stdout_payload="",
        stderr_payload=(
            "Traceback (most recent call last):\n"
            "scitex_dev.store._errors.StoreProvisionError: Store 'claims' "
            "needs PostgreSQL DDL ... Run provision_store_acl(target, "
            "schema) through the authorized migration identity, then retry "
            "Store().\n"
        ),
        exit_code=1,
    )


def _run_gate1_dag_check(bundle: Path, clew_bin: Path | str) -> GateFailure | None:
    """Run the gate against the binary; return the caught failure (or None)."""
    try:
        verify_clew_dag(bundle, clew_bin=str(clew_bin))
    except GateFailure as f:
        return f
    return None


def test_verify_clew_dag_store_failure_check_is_clew_dag(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _unprovisioned_store_shim(tmp_path)
    # Act
    captured = _run_gate1_dag_check(bundle, shim)
    # Assert
    assert captured is not None and captured.check == "clew_dag"


def test_verify_clew_dag_store_failure_names_provisioning(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _unprovisioned_store_shim(tmp_path)
    # Act
    captured = _run_gate1_dag_check(bundle, shim)
    # Assert
    assert captured is not None and (
        captured.reason == "clew store not provisioned for this project"
    )


def test_parse_verification_payload_accepts_dag_runs_shape() -> None:
    # Arrange
    payload = _dag_runs_payload(
        [
            {"session_id": "s1", "is_verified": True},
            {"session_id": "s2", "is_verified": False},
            {"session_id": "s3"},
        ]
    )
    # Act
    green, _ = _parse_verification_payload(payload)
    # Assert
    assert green == ("s1",)


def test_parse_verification_payload_buckets_unverified_runs_red() -> None:
    # Arrange
    payload = _dag_runs_payload(
        [
            {"session_id": "s1", "is_verified": True},
            {"session_id": "s2", "is_verified": False},
            {"session_id": "s3"},
        ]
    )
    # Act
    _, red = _parse_verification_payload(payload)
    # Assert
    assert red == ("s2", "s3")


def test_find_clew_project_dir_returns_root_for_state_dir(
    tmp_path: Path,
) -> None:
    # Arrange
    root = tmp_path / "bundle"
    (root / ".scitex" / "clew").mkdir(parents=True)
    # Act
    found = _find_clew_project_dir(root)
    # Assert
    assert found == root


def test_verify_clew_dag_returns_verification_when_at_least_one_claim_green(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            [{"id": "c1", "status": "green"}, {"id": "c2", "status": "red"}]
        ),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert isinstance(result, ClewVerification)


def test_verify_clew_dag_records_green_claim_ids_in_returned_verification(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            [{"id": "c1", "status": "green"}, {"id": "c2", "status": "green"}]
        ),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.green_claims == ("c1", "c2")


def test_verify_clew_dag_records_red_claim_ids_in_returned_verification(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            [{"id": "c1", "status": "green"}, {"id": "c2", "status": "red"}]
        ),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.red_claims == ("c2",)


def test_verify_clew_dag_records_total_claim_count_in_returned_verification(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            [{"id": f"c{i}", "status": "green"} for i in range(3)]
        ),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.total_claims == 3


def test_verify_clew_dag_records_resolved_project_dir_in_returned_verification(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps([{"id": "c1", "status": "green"}]),
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.project_dir == bundle


def test_verify_clew_dag_ignores_clew_nonzero_exit_when_one_claim_green(
    tmp_path: Path,
) -> None:
    """`clew` returns nonzero when any claim is red; the gate only cares
    about the >=1-green floor, so a green-mixed-with-red payload with
    exit code 2 must still pass.
    """
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            [{"id": "c1", "status": "green"}, {"id": "c2", "status": "red"}]
        ),
        exit_code=2,
    )
    # Act
    result = verify_clew_dag(bundle, clew_bin=str(shim))
    # Assert
    assert result.green_claims == ("c1",)


def test_verify_clew_dag_raises_gate_failure_when_clew_emits_zero_claims(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(tmp_path, stdout_payload=json.dumps([]))
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        verify_clew_dag(bundle, clew_bin=str(shim))


def test_verify_clew_dag_raises_gate_failure_when_every_claim_is_red(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            [{"id": "c1", "status": "red"}, {"id": "c2", "status": "unknown"}]
        ),
    )
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        verify_clew_dag(bundle, clew_bin=str(shim))


def test_verify_clew_dag_all_red_failure_lists_failing_claim_ids_in_detail(
    tmp_path: Path,
) -> None:
    """Issue #4 acceptance: 'Return a structured GateFailure listing the
    failing claims if all are red.' Uses ``pytest.raises(match=)`` so
    the single assertion (the context manager) checks both shape and
    payload simultaneously — TQ007-compliant.
    """
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps(
            [{"id": "claim-A", "status": "red"}, {"id": "claim-B", "status": "red"}]
        ),
    )
    # Act
    ctx = pytest.raises(GateFailure, match=r"claim-A.*claim-B")
    # Assert
    with ctx:
        verify_clew_dag(bundle, clew_bin=str(shim))


def test_verify_clew_dag_raises_gate_failure_when_subprocess_times_out(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(
        tmp_path,
        stdout_payload=json.dumps([{"id": "c1", "status": "green"}]),
        sleep_s=1.0,
    )
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        verify_clew_dag(bundle, clew_bin=str(shim), timeout_s=0.1)


def test_verify_clew_dag_raises_gate_failure_when_clew_emits_invalid_json(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = _make_clew_project(tmp_path / "bundle")
    shim = _write_clew_shim(tmp_path, stdout_payload="not-json-at-all")
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        verify_clew_dag(bundle, clew_bin=str(shim))


def test_verify_clew_dag_raises_gate_failure_when_bundle_root_does_not_exist(
    tmp_path: Path,
) -> None:
    # Arrange
    missing = tmp_path / "nope"
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        verify_clew_dag(missing, clew_bin="/usr/bin/true")


def test_verify_clew_dag_raises_gate_failure_when_no_clew_project_in_bundle(
    tmp_path: Path,
) -> None:
    # Arrange
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    # Act
    ctx = pytest.raises(GateFailure)
    # Assert
    with ctx:
        verify_clew_dag(bundle, clew_bin="/usr/bin/true")


# ---------------------------------------------------------------------------
# Opt-in real-clew test — exercises the actual scitex-clew CLI when the
# operator sets SCITEX_RUN_CLEW_TESTS=1 (mirrors SCITEX_RUN_NETWORK_TESTS).
# ---------------------------------------------------------------------------


@pytest.fixture
def real_clew_project(tmp_path: Path) -> Path:
    """Register a real Clew project via the actual 0.21.0 CLI.

    ``clew register-source`` writes the current ``.scitex/clew/``
    state dir without needing the PostgreSQL store, so the marker
    half works everywhere ``clew`` is installed. Anything that
    verifies (``dag`` / ``claim``) still needs a provisioned store —
    see ``SCITEX_RUN_CLEW_STORE_TESTS`` below.

    Skips the dependent test when `clew` is not on PATH OR when the
    opt-in env var ``SCITEX_RUN_CLEW_TESTS=1`` is not set. Mirrors the
    ``SCITEX_RUN_NETWORK_TESTS`` shape from #11 / #13.
    """
    if os.environ.get("SCITEX_RUN_CLEW_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_CLEW_TESTS=1")
    if shutil.which("clew") is None:
        pytest.skip("`clew` binary not on PATH")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "result.txt").write_text("value = 42\n", encoding="utf-8")
    import subprocess as _sp

    _sp.run(
        ["clew", "register-source", "result.txt"],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    return bundle


def test_real_clew_project_marker_is_discoverable(
    real_clew_project: Path,
) -> None:
    """A real `clew register-source` project is found by the locator."""
    # Arrange
    bundle = real_clew_project
    # Act
    found = _find_clew_project_dir(bundle)
    # Assert
    assert found == bundle


@pytest.fixture
def unprovisioned_clew_project(real_clew_project: Path) -> Path:
    """``real_clew_project``, but only where the store is NOT provisioned.

    Lead decision (a): where ``SCITEX_RUN_CLEW_STORE_TESTS=1`` the
    store is provisioned, so the unprovisioned premise cannot occur —
    accepting either reason there would weaken the assertion. The
    skip lives here (not in the test body) per STX-TQ007.
    """
    if os.environ.get("SCITEX_RUN_CLEW_STORE_TESTS") == "1":
        pytest.skip("provisioned store: unprovisioned premise cannot occur")
    return real_clew_project


def test_real_clew_binary_store_failure_names_provisioning(
    unprovisioned_clew_project: Path,
) -> None:
    """Unprovisioned-only: the gate names the store, not the JSON.

    A freshly registered project has no provisioned store, so the
    real ``clew dag`` dies with ``StoreProvisionError`` instead of
    JSON. The gate must surface that cause actionably rather than
    reporting unparseable output.
    """
    # Arrange
    bundle = unprovisioned_clew_project
    # Act
    captured = _run_gate1_dag_check(bundle, shutil.which("clew") or "clew")
    # Assert
    assert captured is not None and (
        captured.reason == "clew store not provisioned for this project"
    )


@pytest.fixture
def registered_only_bundle(tmp_path: Path) -> Path:
    """Register-only bundle: marker present, zero claims, needs the store.

    The ``dag`` half needs a provisioned store, so this is gated on
    ``SCITEX_RUN_CLEW_STORE_TESTS=1`` like the other verifying
    fixtures. With no claims registered, the gate must fail loud on
    the empty DAG — never pass, never silently empty.
    """
    if os.environ.get("SCITEX_RUN_CLEW_STORE_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_CLEW_STORE_TESTS=1")
    if shutil.which("clew") is None:
        pytest.skip("`clew` binary not on PATH")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "result.txt").write_text("value = 42\n", encoding="utf-8")
    import subprocess as _sp

    _sp.run(
        ["clew", "register-source", "result.txt"],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    return bundle


def test_real_clew_binary_zero_runs_fails_loud(
    registered_only_bundle: Path,
) -> None:
    """A registered-but-claimless project fails on the empty DAG."""
    # Arrange
    bundle = registered_only_bundle
    # Act
    captured = _run_gate1_dag_check(bundle, shutil.which("clew") or "clew")
    # Assert
    assert captured is not None and (
        captured.reason == "Clew DAG present but verifies zero claims"
    )


@pytest.fixture
def provisioned_clew_bundle(tmp_path: Path) -> Path:
    """Build a fully tracked bundle against a live provisioned store.

    Runs a real ``clew.session()`` step that produces ``result.txt``
    with input→output edges, then registers the source and the claim
    — so the DAG has a tracked run producing the claimed source
    instead of a claim-only bundle nothing computed.

    Gating lives here (not in the test body) per the repo's AAA
    convention — ``pytest.skip`` counts as an assertion construct
    (STX-TQ007), so skips belong in fixtures. Setting
    ``SCITEX_RUN_CLEW_STORE_TESTS=1`` declares a provisioned
    PostgreSQL clew store reachable from this environment.
    """
    if os.environ.get("SCITEX_RUN_CLEW_STORE_TESTS") != "1":
        pytest.skip("opt in by setting SCITEX_RUN_CLEW_STORE_TESTS=1")
    if shutil.which("clew") is None:
        pytest.skip("`clew` binary not on PATH")
    if shutil.which("git") is None:
        pytest.skip("`git` not on PATH")
    try:
        import scitex_clew  # noqa: F401
    except ImportError:
        pytest.skip("scitex_clew python package not importable")
    import subprocess as _sp

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "paper.tex").write_text("The answer is 42\n", encoding="utf-8")
    (bundle / "make_result.py").write_text(
        "import scitex_clew as clew\n"
        'with clew.session(script_path="make_result.py") as run:\n'
        '    run.record_input("paper.tex")\n'
        '    with open("result.txt", "w") as fh:\n'
        '        fh.write("value = 42\\n")\n'
        '    run.record_output("result.txt")\n',
        encoding="utf-8",
    )
    _sp.run(
        [sys.executable, "make_result.py"],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    _sp.run(
        ["clew", "register-source", "result.txt"],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    _sp.run(
        [
            "clew",
            "claim",
            "add",
            "--file-path",
            "paper.tex",
            "--type",
            "value",
            "--value",
            "42",
            "--source-file",
            "result.txt",
            "--line-number",
            "1",
        ],
        cwd=str(bundle),
        check=True,
        capture_output=True,
    )
    return bundle


def test_real_clew_binary_verifies_a_provisioned_project(
    provisioned_clew_bundle: Path,
) -> None:
    """Full pass — real register + claim + verify against a live store."""
    # Arrange
    bundle = provisioned_clew_bundle
    # Act
    result = verify_clew_dag(bundle)
    # Assert
    assert result.green_claims
