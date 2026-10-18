---
name: scitex-agentic-journal
description: |
  [WHAT] `scitex-agentic-journal` is the publication-venue substrate of SciTeX: a journal where AI agents (Spartan/Qwen-class reviewer agents) — not volunteer reviewers — perform peer review, reproducibility re-run, claim verification, novelty triangulation, methodology critique, and editorial decision (accept / revise / reject). The package ingests a manuscript bundle (LaTeX + claims + Clew DAG + code repo + ORCID), runs gate-1 structural checks, gate-2 AI review, gate-3 editorial decision, gate-4 persistent ID, then hands off to scitex-live-paper.
  [WHEN] Use when the user asks to submit, review, accept, reject, revise, mint a DOI for, or publish a manuscript via the SciTeX agentic journal; or mentions ARA-native publishing, gate-1 / gate-2 checks, ORCID validation, Clew DAG submission gate, Live Paper hand-off, reviewer agents, or editorial decision engine.
  [HOW] `pip install scitex-agentic-journal` (CLI + library) or `pip install scitex-agentic-journal[mcp]` (+ MCP server for agents). See the leaf skills for submission bundle shape, gate-1 implementation, review engine, decision rules, and publish hand-off.
tags: [scitex-agentic-journal]
primary_interface: cli
interfaces:
  python: 2
  cli: 1
  mcp: 2
  django: 3
  skills: 2
---

# scitex-agentic-journal Skill

> **Status:** pre-alpha (v0.1.0-alpha). Skeleton + gate-1 implementation in progress. Skills documented here describe the **target** surface; leaves note implemented vs. planned.

> **Interfaces:** CLI ⭐ · Python ⭐⭐ · MCP ⭐⭐ · Django ⭐⭐⭐ · Skills ⭐⭐

`scitex-agentic-journal` is the journal substrate of SciTeX. It is **not** a new claim model and **not** a new manuscript format; it consumes Clew's claim/DAG model and emits Live Paper bundles. AI agents do the editorial work that volunteer reviewers traditionally do.

## Install & smoke verify

```bash
pip install scitex-agentic-journal           # CLI + library
pip install scitex-agentic-journal[mcp]      # + MCP server for AI agents
python -c "import scitex_agentic_journal; print(scitex_agentic_journal.__version__)"
```

The umbrella `import scitex.agentic_journal` is **not** wired yet — the
sub-package only exposes the standalone import path during alpha.

## Sub-skills (leaves)

### Core (01–09) — standard scaffold (SK-105/106/107/108)

- [01_installation.md](01_installation.md) — install + extras + smoke verify
- [02_quick-start.md](02_quick-start.md) — five-minute tour: ORCID + code repo + Clew DAG end-to-end
- [03_python-api.md](03_python-api.md) — public Python surface (`_gate1`, `_orcid`, `_ports`, `_publish`, `_review`, `_django`, `_mcp`)
- [04_cli-reference.md](04_cli-reference.md) — every console-script subcommand

### Domain leaves (10–19)

- [10_overview.md](10_overview.md) — what the package is, MVP loop, full pipeline, dependency direction
- [11_submission-bundle.md](11_submission-bundle.md) — manuscript bundle shape (LaTeX + claims + Clew DAG + code repo + ORCID)
- [12_gate1-checks.md](12_gate1-checks.md) — structural checks (ORCID resolvable, code repo cloneable, Clew DAG present + ≥1 green claim)
- [13_review-and-decision.md](13_review-and-decision.md) — gate-2 AI review (reproducibility, claim verify, novelty, methodology) + gate-3 editorial decision (accept / revise / reject)
- [14_publish-handoff.md](14_publish-handoff.md) — gate-4 persistent ID (sandbox → Zenodo → JaLC) + hand-off to scitex-live-paper
- [15_python-api-detailed.md](15_python-api-detailed.md) — deeper Python-surface walk-through beyond 03_python-api.md

### Configuration & state (20–29)

- [20_env-vars.md](20_env-vars.md) — inventory of `SCITEX_AGENTIC_JOURNAL_*` env vars + the pytest opt-in flags

### Architecture (30–39)

- [30_django-and-hub.md](30_django-and-hub.md) — `_django` reviewer dashboard mounted into scitex-hub via `apps/workspace/agentic_journal_app`
- [31_mcp-and-agents.md](31_mcp-and-agents.md) — `_mcp` server: submit / review / decide / publish tools for AI agents

## When NOT to use this skill

- For Clew claim DAGs themselves — that's `scitex-clew`.
- For paper rendering / interactive Live Paper — that's `scitex-live-paper`.
- For literature search — that's `scitex-scholar` (we **consume** it for novelty triangulation but don't reimplement).
- For the host platform (auth, app store, Gitea) — that's `scitex-hub`.

## Dependency direction (read-only summary)

```
scitex-agentic-journal   --reads-->   scitex-clew         (claim model + DAG)
scitex-agentic-journal   --reads-->   scitex-scholar      (literature triangulation)
scitex-agentic-journal   --emits-->   scitex-live-paper   (rendered artefact)
scitex-agentic-journal   --hosts-on-> scitex-hub          (reviewer dashboard, auth)
```

See [01_overview.md](01_overview.md) for the full pipeline diagram and milestone breakdown.
