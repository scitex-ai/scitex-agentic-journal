---
description: |
  [TOPIC] Python API — extended walk-through
  [DETAILS] Deeper coverage of the Submission / Gate1 / Review / Decision / Publish types beyond the standard 03_python-api.md leaf.
tags: [scitex-agentic-journal-python-api-detailed]
---

# 06 · Python API

Top-level Python surface for `scitex-agentic-journal`. Most users hit the CLI / MCP; the Python API exists for programmatic submission pipelines (CI gates, batch re-reviews, end-to-end tests).

> **Surface stability:** alpha. Anything marked **planned** is the M-target shape; only the gate-1 entry points are wired today.

## Import

```python
import scitex_agentic_journal as saj
saj.__version__   # "0.1.0-alpha"
```

The `scitex.agentic_journal` umbrella form is **not** wired during alpha. Use the standalone import.

## Submission (planned)

```python
from scitex_agentic_journal import Submission

bundle = Submission.from_directory("./paper/")
# - reads submission.yaml + claims.yaml + dag/
# - validates schema (raises Saj.SchemaError on failure — no silent fill-in)
print(bundle.title, bundle.corresponding_author_orcid)
```

## Gate-1 (landed)

```python
from scitex_agentic_journal._gate1 import check_orcid, check_code_repo

orcid_result = check_orcid("0000-0001-2345-678X")
if not orcid_result.passed:
    for reason in orcid_result.reasons:
        print(reason)

repo_result = check_code_repo("https://github.com/owner/repo")
print(repo_result.evidence)   # {"ls_remote_lines": 12, "default_branch": "develop"}
```

Aggregate runner (planned):

```python
from scitex_agentic_journal import Gate1
verdict = Gate1.run(bundle)        # runs orcid + code_repo + clew_dag in parallel
print(verdict.passed, verdict.failed_checks)
```

## Gate-2 review (planned, M2)

```python
from scitex_agentic_journal import Review

record = Review.run(
    bundle,
    adapter="qwen-self-hosted",        # or "spartan", "claude-haiku", ...
    prompts_version="v1",
)
record.reproducibility.passed
record.claim_verify.green_count
record.novelty.overlap_score
record.methodology.criticisms
```

## Gate-3 decision (planned, M3)

```python
from scitex_agentic_journal import Decision

decision = Decision.apply(record, rules_version="v1")
decision.outcome          # "accept" | "revise" | "reject"
decision.firing_branch    # which rule arm fired
```

## Gate-4 + publish (planned, M4–M5)

```python
from scitex_agentic_journal import Publish

if decision.outcome == "accept":
    pid = Publish.mint_id(decision, backend="zenodo-sandbox")
    Publish.hand_off_to_live_paper(bundle, record, decision, pid)
elif decision.outcome == "revise":
    Publish.emit_revision_packet(bundle, record, decision)
```

## ORCID client (planned, M1.5 — aj-orcid card)

```python
from scitex_agentic_journal import OrcidClient

client = OrcidClient(env="prod")   # or "sandbox"
person = client.fetch("0000-0001-2345-678X")
person.name           # "Yusuke Watanabe"
person.is_public      # True
```

ORCID client is separate from the gate-1 check: the check is a yes/no resolvability probe; the client is a typed reader for downstream use (Live Paper authorship card, Hub user-link).

## Ports / adapters (planned, aj-ports card)

`_ports/` holds the loose-coupling interfaces:

```python
from scitex_agentic_journal._ports import (
    WriterPort,        # reads scitex-writer manuscript dir
    ClewPort,          # reads scitex-clew claims + DAG
    SchedulerPort,     # accepts reviewer-agent jobs
    HubPort,           # publishes hub notifications
    LivePaperPort,     # hands off accepted bundles
    UiPort,            # reviewer dashboard hooks
)
```

Each port is a `typing.Protocol`. Default implementations live next to the port; alternative implementations (e.g. in-memory for tests, mock-server for staging) plug in via env or explicit injection.

## Error policy

- Every public callable raises a typed `SajError` subclass on failure.
- No `try: ... except: return None` — failures are explicit and carry a `reasons: list[str]` and `evidence: dict`.
- Schema errors during bundle load are **non-recoverable** at the API level (no partial-bundle "best effort"); the caller fixes the bundle and retries.

## Testing

```python
import pytest
from scitex_agentic_journal._gate1 import check_orcid

@pytest.mark.network
def test_real_orcid_resolves():
    assert check_orcid("0000-0001-2345-678X").passed
```

Network tests are opt-in via `SCITEX_RUN_NETWORK_TESTS=1` (see `pyproject.toml` `[tool.pytest.ini_options].markers`).
