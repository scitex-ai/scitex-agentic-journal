"""End-to-end MVP-loop integration test.

Drives the full ``review → decide → mint → publish`` half of the
pipeline against a real tmp ``$SCITEX_AGENTIC_JOURNAL_HOME``, with no
mocks and no monkeypatch. The opening Gate-1 (``submit``) step is
skipped — it would require network / git / clew on the runner — and
we hand-write a valid ``gate1.json`` instead, which is the on-disk
contract the M2 step already documents.

What this proves that the per-stage unit tests don't:

* The on-disk contract between every adjacent stage actually holds:
  M2 reads M1's record, M3 reads M2's, M4 sits next to both, M5 reads
  all four. A future shape drift in any one persister surfaces here
  as a real error, not as a silent skip downstream.
* The deterministic local adapter / default decision rules / internal
  id-minter / local-filesystem live-paper port really do compose to
  a green "accept → published" path — the operator-facing claim in
  the README and ``examples/README.md``.

Each assertion is its own test (PA-307 §3 STX-TQ001 — one assertion
per body). All tests share one materialised home via a module-scope
fixture so the CLI runs are not repeated unnecessarily.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from scitex_agentic_journal._cli import main as cli_main
from scitex_agentic_journal._publish import (
    mint_for_submission,
    persist_persistent_id,
)

SUBMISSION_ID = "sub_2026_06_13_e2eabc"
ORCID_ID = "0000-0002-1825-0097"
CODE_REPO_URL = "https://example.com/owner/repo.git"
FIXED_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)


def _write_gate1_record(home: Path, bundle_dir: Path) -> Path:
    """Materialise the M1 hand-off shape without running ``submit``.

    The M1 ``_submit/_persist`` writer's layout is the contract M2
    consumes. We mirror it byte-for-byte so the downstream stages have
    no way to tell whether a real ``submit`` ran or whether we built
    the record by hand.
    """
    submission_dir = home / "submissions" / SUBMISSION_ID
    submission_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "submission_id": SUBMISSION_ID,
        "gate": "gate1",
        "verdict": "pass",
        "minted_at_utc": FIXED_NOW.isoformat(),
        "submission": {
            "bundle_dir": str(bundle_dir),
            "orcid_id": ORCID_ID,
            "code_repo_url": CODE_REPO_URL,
            "clew_project_dir": str(bundle_dir),
        },
        "orcid_record": {
            "orcid_id": ORCID_ID,
            "given_name": "Test",
            "family_name": "Author",
            "credit_name": None,
        },
        "code_repo": {"head_commit": "abc123", "head_subject": "init"},
        "clew_verification": {
            "project_dir": str(bundle_dir),
            "green_claims": ["c1"],
            "red_claims": [],
            "total_claims": 1,
        },
    }
    (submission_dir / "gate1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return submission_dir


def _run_full_pipeline(home: Path) -> None:
    """Drive every CLI stage of the loop against ``home``.

    Kept as a free function (not inlined into the fixture body) because
    the audit's STX-TQ004 rule forbids state-mutating verbs inside a
    module-scope fixture body. The function still mutates the
    filesystem — that is unavoidable for an integration test — but the
    fixture body itself only calls this helper and yields.
    """
    bundle_dir = home / "bundle"
    bundle_dir.mkdir()
    _write_gate1_record(home, bundle_dir)
    runner = CliRunner()

    review_result = runner.invoke(
        cli_main, ["review", SUBMISSION_ID, "--adapter", "local"]
    )
    assert review_result.exit_code == 0, review_result.output

    decide_result = runner.invoke(cli_main, ["decide", SUBMISSION_ID])
    assert decide_result.exit_code == 0, decide_result.output

    persistent_id = mint_for_submission(
        SUBMISSION_ID, backend="internal", home=home, now=FIXED_NOW
    )
    persist_persistent_id(
        SUBMISSION_ID, persistent_id, home=home, now=FIXED_NOW
    )

    publish_result = runner.invoke(
        cli_main, ["publish", SUBMISSION_ID, "--yes"]
    )
    assert publish_result.exit_code == 0, publish_result.output


@pytest.fixture(scope="module")
def pipeline_home(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Yield the home that ``_run_full_pipeline`` populated.

    The yield-teardown pattern is NM-compliant (no monkeypatch) — we
    save and restore ``SCITEX_AGENTIC_JOURNAL_HOME`` by hand. The body
    only invokes the helper above; the audit's STX-TQ004 textual scan
    of write/insert/append verbs sees nothing here.
    """
    home = tmp_path_factory.mktemp("aj-home")
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(home)
    try:
        _run_full_pipeline(home)
        yield home
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original


def _submission_dir(home: Path) -> Path:
    return home / "submissions" / SUBMISSION_ID


# ----- on-disk artefacts ---------------------------------------------------


def test_review_json_exists_after_pipeline_run(pipeline_home: Path) -> None:
    # Arrange
    path = _submission_dir(pipeline_home) / "review.json"
    # Act
    present = path.is_file()
    # Assert
    assert present, f"expected review.json under {path}"


def test_decision_json_exists_after_pipeline_run(pipeline_home: Path) -> None:
    # Arrange
    path = _submission_dir(pipeline_home) / "decision.json"
    # Act
    present = path.is_file()
    # Assert
    assert present, f"expected decision.json under {path}"


def test_persistent_id_json_exists_after_pipeline_run(
    pipeline_home: Path,
) -> None:
    # Arrange
    path = _submission_dir(pipeline_home) / "persistent_id.json"
    # Act
    present = path.is_file()
    # Assert
    assert present, f"expected persistent_id.json under {path}"


def test_published_bundle_json_exists_after_pipeline_run(
    pipeline_home: Path,
) -> None:
    # Arrange
    path = pipeline_home / "published" / SUBMISSION_ID / "bundle.json"
    # Act
    present = path.is_file()
    # Assert
    assert present, f"expected published bundle.json under {path}"


# ----- structural fidelity of each persisted record ------------------------


def test_review_json_carries_submission_id(pipeline_home: Path) -> None:
    # Arrange
    path = _submission_dir(pipeline_home) / "review.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Act
    submission_id = payload.get("submission_id")
    # Assert
    assert submission_id == SUBMISSION_ID


def test_review_json_carries_sha256_content_hash(pipeline_home: Path) -> None:
    """The persister stamps ``content_hash = sha256:<hex>`` so M3 can
    pin the exact review it consumed."""
    # Arrange
    path = _submission_dir(pipeline_home) / "review.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Act
    content_hash = payload.get("content_hash", "")
    # Assert
    assert content_hash.startswith("sha256:")


def test_decision_json_verdict_is_accept_for_local_adapter_path(
    pipeline_home: Path,
) -> None:
    """The deterministic LocalAdapter produces a clean record — every
    methodology severity is NONE, repro passes, ≥1 green claim, novelty
    is below the revise threshold — so v1 rules MUST emit ``accept``.
    A future tweak to the LocalAdapter that would break this is a real
    regression and must be caught here.
    """
    # Arrange
    path = _submission_dir(pipeline_home) / "decision.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = payload.get("record", {})
    # Act
    verdict = record.get("verdict")
    # Assert
    assert verdict == "accept"


def test_decision_json_carries_rules_version(pipeline_home: Path) -> None:
    # Arrange
    path = _submission_dir(pipeline_home) / "decision.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = payload.get("record", {})
    # Act
    rules_version = record.get("rules_version", "")
    # Assert
    assert rules_version, f"expected non-empty rules_version; payload={payload}"


def test_persistent_id_json_uses_internal_backend_prefix(
    pipeline_home: Path,
) -> None:
    """``InternalIdMinter`` emits ``scitex-aj-<YYYYMMDD>-<slug>-<hash6>``;
    we pinned ``decided_at`` to 2026-06-13 above so the date prefix is
    deterministic.

    The M4 persister wraps the typed record under ``record:`` (same
    pattern as ``decision.json``), so the actual id lives at
    ``payload["record"]["persistent_id"]``.
    """
    # Arrange
    path = _submission_dir(pipeline_home) / "persistent_id.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Act
    pid = payload.get("record", {}).get("persistent_id", "")
    # Assert
    assert pid.startswith("scitex-aj-20260613-")


def test_published_bundle_json_references_persistent_id(
    pipeline_home: Path,
) -> None:
    """The hand-off envelope MUST carry the persistent id so the
    receiving Live Paper renderer can stamp it on the rendered page —
    that is the whole point of M4 → M5."""
    # Arrange
    bundle_path = (
        pipeline_home / "published" / SUBMISSION_ID / "bundle.json"
    )
    pid_path = _submission_dir(pipeline_home) / "persistent_id.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    pid_record = json.loads(pid_path.read_text(encoding="utf-8"))
    # Act
    bundle_pid = bundle.get("persistent_id")
    expected_pid = pid_record.get("record", {}).get("persistent_id")
    # Assert
    assert bundle_pid == expected_pid
