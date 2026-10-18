# Examples

Runnable examples for `scitex-agentic-journal`.

The MVP submit → review → decide → publish loop is wired end-to-end:
each CLI subcommand below executes real code and persists structured
records under `$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/`. The
shell scripts in this directory still cover only the two Gate-1
public-API smokes; the CLI examples below exercise the whole loop
without a wrapper script.

## Gate-1 ORCID resolvability check (issue #2)

```python
from scitex_agentic_journal._gate1 import verify_orcid, GateFailure

try:
    rec = verify_orcid("0000-0002-1825-0097")
    print(rec.display_name, "->", rec.orcid_id)
except GateFailure as fail:
    print(fail)
```

## Gate-1 code-repo cloneability (issue #3)

```python
from scitex_agentic_journal._gate1 import cloned_code_repo, GateFailure

try:
    with cloned_code_repo(
        "https://github.com/octocat/Hello-World.git"
    ) as repo:
        print("HEAD at", repo.head_commit, "—", repo.head_subject)
except GateFailure as fail:
    print(fail)
```

## Gate-1 Clew-DAG verification (issue #4)

```python
from pathlib import Path
from scitex_agentic_journal._gate1 import verify_clew_dag, GateFailure

try:
    result = verify_clew_dag(Path("./paper"))
    print(
        f"GATE-1 PASS — {result.total_claims} claims; "
        f"green={list(result.green_claims)}"
    )
except GateFailure as fail:
    print(fail)
```

## M1 submission orchestrator (issue #5)

```console
$ scitex-agentic-journal submit ./paper/
GATE-1 PASS submission_id=sub_2026_06_13_abc123
```

A failing structural check prints one structured line with the
failure detail and exits non-zero — no Python traceback:

```console
$ scitex-agentic-journal submit ./paper-bad-orcid/
GATE-1 FAIL [orcid]: malformed iD -- "not-an-orcid-id" failed the
ISO 7064 MOD 11-2 checksum
```

## M2 reviewer-agent harness (issue #6)

```console
$ scitex-agentic-journal review sub_2026_06_13_abc123
REVIEW DONE submission_id=sub_2026_06_13_abc123 adapter=local \
content_hash=sha256:f3b1...
```

`--adapter local` is the deterministic in-memory adapter that ships in
this package. `--adapter qwen` is a NotImplementedError stub until the
live endpoint is wired.

## M3 editorial decision engine (issue #7)

```console
$ scitex-agentic-journal decide sub_2026_06_13_abc123
DECISION submission_id=sub_2026_06_13_abc123 verdict=accept \
rules_version=v1 content_hash=sha256:5b89...
```

The verdict (`accept | revise | reject`) is derived from the
versioned YAML rules-set at
`src/scitex_agentic_journal/_decide/rules/v1.yaml`. Every evaluated
rule contributes a `RuleHit` to the persisted `decision.json`, so
auditors can verify which rules passed alongside which failed.

## M5 publish hand-off to scitex-live-paper (issue #9)

```console
$ scitex-agentic-journal publish sub_2026_06_13_abc123 --dry-run
PLAN submission_id=sub_2026_06_13_abc123 \
persistent_id=scitex-aj-20260613-sample-paper-a1b2c3 \
viewer_url=file:///tmp/.../bundle.json

$ scitex-agentic-journal publish sub_2026_06_13_abc123 --yes
PUBLISHED submission_id=sub_2026_06_13_abc123 \
viewer_url=file:///tmp/.../bundle.json \
persistent_id=scitex-aj-20260613-sample-paper-a1b2c3
```

The default port is `LocalFilesystemLivePaperPort` — it writes the
Live Paper bundle envelope to `<home>/published/<submission_id>/bundle.json`,
which is the bundle shape `scitex-live-paper` consumes. Wire a remote
HTTP / MCP port in production by constructing `LivePaperProxy(port)`
directly.

## CLI smoke

```console
$ scitex-agentic-journal --version
scitex-agentic-journal, version <X.Y.Z>
$ scitex-agentic-journal --help
Usage: scitex-agentic-journal [OPTIONS] COMMAND [ARGS]...
$ scitex-agentic-journal --help-recursive
# (prints --help for every subcommand of the tree)
```
