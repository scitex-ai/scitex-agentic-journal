---
description: |
  [TOPIC] Environment variables
  [DETAILS] Inventory of `SCITEX_AGENTIC_JOURNAL_*` env vars the CLI and library read, mirroring `.env.example`.
tags: [scitex-agentic-journal-env-vars]
---

# Environment Variables

Inventory of `SCITEX_AGENTIC_JOURNAL_*` env vars the CLI and the
public Python surface read at runtime. Mirrors `.env.example` at
the repo root — that file is the canonical machine-editable source
and remains required by audit rule PS-129. This leaf is the
human-readable counterpart.

## Inventory

| Variable | Read by | Default | Purpose |
|---|---|---|---|
| `SCITEX_AGENTIC_JOURNAL_CONFIG` | `scitex-agentic-journal` CLI help epilog (issue #5 will wire actual config loading) | `./config.yaml` → `~/.scitex/agentic-journal/config.yaml` | Path to an alternate YAML config so a single repo checkout can be re-run against different submission configurations. |
| `SCITEX_AGENTIC_JOURNAL_SKILLS_DEST` | `scitex-agentic-journal skills install` | `~/.claude/skills/scitex-agentic-journal/` | Default destination for `skills install` when no `--dest` is given. Convenient for CI / dotfile bootstrap. |
| `SCITEX_AGENTIC_JOURNAL_CLEW_BIN` | `verify_clew_dag(clew_bin=...)` (M1.3 / issue #4) | resolved via `shutil.which("clew")` | Absolute path to the `clew` binary if it is not on PATH (e.g. virtualenv, sandbox installs). |

## Test-suite opt-ins

Two pytest opt-in env vars gate the **real** network / **real**
`clew` runs. They are NOT used by the package at runtime — only by
the tests under `tests/`.

| Variable | Used by | Effect |
|---|---|---|
| `SCITEX_RUN_NETWORK_TESTS=1` | `tests/scitex_agentic_journal/_gate1/test__orcid.py`, `test__code_repo.py` | Enables the test that resolves a real `pub.orcid.org` ORCID record and the test that clones a real GitHub repo. Skipped by default. |
| `SCITEX_RUN_CLEW_TESTS=1` | `tests/scitex_agentic_journal/_gate1/test__clew_dag.py` | Enables the real-binary tests that need `clew` but no store: marker discoverability on a freshly `clew register-source`-ed bundle, plus the unprovisioned-premise store-failure test (skipped where the store is provisioned). Skipped by default unless `clew` is also on PATH. |
| `SCITEX_RUN_CLEW_STORE_TESTS=1` | `test__clew_dag.py`, `test__orchestrate.py`, `test__submit.py` | Enables the full-pass tests that register + verify against a live provisioned PostgreSQL clew store. Skipped by default. Where set, the unprovisioned-premise test (`test_real_clew_binary_store_failure_names_provisioning`, lead decision (a)) skips instead — its premise cannot occur there. |

## Audit-rule provenance

The PS-129 rule (`readme-banned-trademark-symbol` — really the env-var
documentation check) requires that any `SCITEX_<MODULE>_*` name
referenced in `src/` is documented in either `.env.example` or a
`## Environment Variables` H2 in `README.md`. The combination of the
canonical `.env.example` plus this leaf gives an auditable
single-source-of-truth.

## Setting them

```bash
# One-off shell export
export SCITEX_AGENTIC_JOURNAL_CONFIG=/abs/path/to/config.yaml

# Or copy + edit the bundled template
cp .env.example .env
$EDITOR .env
```
