---
description: |
  [TOPIC] Quick start
  [DETAILS] First-five-minutes tour — install, run Gate-1 against a real ORCID + GitHub repo, inspect the bundled skills.
tags: [scitex-agentic-journal-quick-start]
---

# Quick Start

These commands take a fresh machine to a verified Gate-1 run in
under 5 minutes. They exercise the same code path the M1 CLI
orchestrator (#5) will drive once shipped.

## 0. Install

```bash
pip install scitex-agentic-journal
```

See [01_installation.md](01_installation.md) for `uv`, optional
extras, and `.env.example` configuration.

## 1. CLI smoke

```bash
scitex-agentic-journal --version
scitex-agentic-journal --help
scitex-agentic-journal --help-recursive   # full subcommand tree
```

## 2. Gate-1 — ORCID resolvability (issue #2)

```python
from scitex_agentic_journal._gate1 import verify_orcid, GateFailure

try:
    rec = verify_orcid("0000-0002-1825-0097")
except GateFailure as fail:
    print(f"GATE-1 FAIL: {fail}")
else:
    print(f"GATE-1 PASS — {rec.orcid_id} -> {rec.display_name!r}")
```

The bundled shell example does the same call from a one-liner:

```bash
./examples/01_gate1_orcid_resolve.sh 0000-0002-1825-0097
```

## 3. Gate-1 — code-repo cloneability (issue #3)

```python
from scitex_agentic_journal._gate1 import cloned_code_repo, GateFailure

with cloned_code_repo("https://github.com/octocat/Hello-World.git") as repo:
    print(f"GATE-1 PASS — cloned {repo.repo_url}")
    print(f"  on-disk path : {repo.path}")
    print(f"  HEAD commit  : {repo.head_commit}")
    print(f"  HEAD subject : {repo.head_subject}")
```

## 4. Gate-1 — Clew DAG verification (issue #4)

```python
from scitex_agentic_journal._gate1 import verify_clew_dag, GateFailure

result = verify_clew_dag("./my-submission/")
print(f"GATE-1 PASS — {len(result.green_claims)} green, "
      f"{len(result.red_claims)} red")
```

`verify_clew_dag` shells out to the real `clew dag --claims --json` CLI —
no mocks. See [12_gate1-checks.md](12_gate1-checks.md) for the
full structural-check contract.

## 5. Discover the bundled skills

```bash
scitex-agentic-journal skills list
scitex-agentic-journal skills get SKILL
scitex-agentic-journal skills install --dest ~/.claude/skills
```

See [04_cli-reference.md](04_cli-reference.md) for the complete
CLI surface and [03_python-api.md](03_python-api.md) for the
Python entry points.
