---
description: |
  [TOPIC] Gate-1 structural checks
  [DETAILS] ORCID resolvable, code repo cloneable, Clew DAG present + verifies >=1 green claim — the no-AI gate before reviewer agents run.
tags: [scitex-agentic-journal-gate1-checks]
---

# 03 · Gate-1 structural checks

Gate-1 is the **only gate implemented in M1**. No AI review yet — just structural validation that the submission is even worth reviewing.

## What gate-1 verifies

1. **ORCID resolvable** — the corresponding author's ORCID iD resolves via `pub.orcid.org/v3.0/{orcid}` and returns 200 + a `person` block.
2. **Code repo cloneable** — the URL in `code_repo_url.txt` is reachable via anonymous `git ls-remote` (no clone, no execution at this gate).
3. **Clew DAG present + ≥ 1 green claim** — the `dag/` directory exists, `claims.yaml` parses as Clew claim manifest, and at least one claim has `VerificationStatus.GREEN`.

Implementations live under `scitex_agentic_journal/_gate1/`. Currently landed:

- `_gate1/_orcid.py` — ORCID resolvability (closes #2, PR #11).
- `_gate1/_code_repo.py` — code-repo cloneability (closes #3, PR #13).
- `_gate1/_errors.py` — typed errors emitted by all gate-1 checks.

Pending:
- `_gate1/_clew_dag.py` — DAG presence + green-claim check (closes #4 / aj-checks card).

## Design rules (CLAUDE.md / no silent fallback)

- Each check returns a typed `Gate1CheckResult` (`status: pass | fail`, `reasons: list[str]`, `evidence: dict`).
- A network-dependent check uses HTTP timeouts (5 s default) and surfaces the real HTTP status / exception in `reasons`.
- No retries that mask transient failure as "pass". One try, real error, real guidance.
- Tests use `pytest -m network` opt-in; default suite uses recorded fixtures (see `tests/_gate1/`).

## CLI surface (planned)

```bash
scitex-agentic-journal submit ./paper/
# → runs all gate-1 checks, prints PASS/FAIL per check, exits 0 (all pass) or 1 (any fail).

scitex-agentic-journal check orcid 0000-0001-2345-678X
scitex-agentic-journal check code-repo https://github.com/owner/repo
scitex-agentic-journal check clew-dag ./paper/dag/
```

## Python surface

```python
from scitex_agentic_journal._gate1 import check_orcid, check_code_repo

result = check_orcid("0000-0001-2345-678X")
if not result.passed:
    for reason in result.reasons:
        print(reason)
```

See [06_python-api.md](06_python-api.md) for the consolidated surface.

## What gate-1 does NOT do

- It does **not** execute author code (that's gate-2 reproducibility).
- It does **not** read manuscript prose (gate-2 methodology critique).
- It does **not** mint a DOI / sandbox ID (gate-4).
- It does **not** call a reviewer agent (gate-2).

Gate-1 is intentionally cheap, fast, deterministic, and offline-cacheable. A bundle failing gate-1 should never reach a reviewer agent.

## Error catalogue (selected)

| Error class | When | Guidance shown |
|-------------|------|----------------|
| `OrcidNotResolvable` | `pub.orcid.org` returns 4xx or no `person` block | "Verify the ORCID iD format `0000-0000-0000-000X` and that the iD is public." |
| `CodeRepoUnreachable` | `git ls-remote` non-zero | "Make the repo public, or grant access to the SciTeX bot account, then re-submit." |
| `ClewDagMissing` | `dag/` directory absent | "Run `clew claim list` to populate the DAG before submission." |
| `NoGreenClaim` | All claims `RED` / `YELLOW` | "At least one claim must verify (`clew claim verify`) before submission." |

All gate-1 errors map to `_gate1/_errors.py` and are stable for downstream UI / MCP / Django consumers.
