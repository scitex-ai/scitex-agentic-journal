<!-- ---
!-- Timestamp: 2026-06-12
!-- Author: ywatanabe
!-- File: /home/ywatanabe/proj/scitex-agentic-journal/README.md
!-- --- -->

<p align="center">
  <img src="docs/assets/images/scitex-logo-blue-cropped.png" alt="SciTeX" width="320">
</p>

# SciTeX Agentic Journal (`scitex-agentic-journal`)

[![PyPI](https://img.shields.io/pypi/v/scitex-agentic-journal.svg)](https://pypi.org/project/scitex-agentic-journal/)
[![Python](https://img.shields.io/pypi/pyversions/scitex-agentic-journal.svg)](https://pypi.org/project/scitex-agentic-journal/)
[![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-blue.svg)](LICENSE)
[![CI](https://github.com/ywatanabe1989/scitex-agentic-journal/actions/workflows/pr-ci.yml/badge.svg?branch=develop)](https://github.com/ywatanabe1989/scitex-agentic-journal/actions/workflows/pr-ci.yml)
[![coverage](https://img.shields.io/codecov/c/github/ywatanabe1989/scitex-agentic-journal)](https://codecov.io/gh/ywatanabe1989/scitex-agentic-journal)

ARA-native AI-reviewed open publishing on top of [Clew](https://github.com/ywatanabe1989/scitex-clew).

> **Status:** pre-alpha scaffold (v0.1.0-alpha). README + minimum package skeleton. M1 (submission gate) implementation pending — tracked under [open issues](https://github.com/ywatanabe1989/scitex-agentic-journal/issues).

## What it is

`scitex-agentic-journal` is the **journal substrate** of SciTeX: a publication venue where **AI agents — not volunteer reviewers — perform peer review, copy-edit, and publication-readiness work**. Human authors still write and revise; AI agents read, run, verify, critique, and decide.

Concretely the package provides:

- A **submission intake** that ingests a manuscript bundle (LaTeX + claims + DAG + code repo + ORCID).
- **Gate-1 structural checks** (ORCID resolvable, code repo cloneable, Clew DAG present + verifying ≥1 claim).
- An **agent review** stage (Spartan/Qwen-class reviewer agents): reproducibility re-run, claim verification, novelty triangulation, methodology critique.
- An **editorial decision** stage (accept / revise / reject) backed by the review record.
- A **publish hand-off** to [`scitex-live-paper`](https://github.com/ywatanabe1989/scitex-live-paper) with a persistent ID (sandbox → Zenodo DOI → JaLC).

The package is **not** a new claim model and **not** a new manuscript format. It consumes Clew's claim/DAG model and emits Live Paper bundles.

## What problem does it solve?

Traditional peer review is slow, opaque, volunteer-limited, and cannot keep pace with the preprint flood. Meanwhile AI agents can now read, run, and verify the entire research workflow — code, data, claims, provenance — in minutes. `scitex-agentic-journal` turns that capability into a publication venue with auditable AI-driven editorial decisions.

## MVP loop

```
   submit → agent review → decision → publish
```

The MVP collapses the long pipeline into the smallest loop that is end-to-end useful:

1. **submit** — accept a manuscript bundle through CLI / MCP and persist it with provenance.
2. **agent review** — run a single reviewer agent against the bundle and persist its report.
3. **decision** — apply rule-based editorial logic over the review record → `accept | revise | reject`.
4. **publish** — emit a Live Paper bundle (accepted) or a revision packet (revise) and stamp a persistent ID.

Issues [`#2`](https://github.com/ywatanabe1989/scitex-agentic-journal/issues/2)–[`#9`](https://github.com/ywatanabe1989/scitex-agentic-journal/issues/9) track this MVP loop. Post-MVP work (multi-reviewer panels, JaLC, reviewer dashboard, MCP server, AGPL/CLA polish) is deferred.

## Architecture

```
+--------------+        Clew claim/DAG        +---------------------+
| scitex-clew  +----- (read, never owned) --->| scitex-agentic-     |
+--------------+                              |     journal         |
                                              |                     |
+----------------+   literature triangulation |  +--------------+   |
| scitex-scholar +--- (read) ---------------->|  | submission   |   |
+----------------+                            |  | intake (M1)  |   |
                                              |  +------+-------+   |
                                              |         |           |
                                              |         v           |
                                              |  +--------------+   |
                                              |  | reviewer     |   |
                                              |  | agent (M2)   |   |
                                              |  +------+-------+   |
                                              |         |           |
                                              |         v           |
                                              |  +--------------+   |
                                              |  | decision     |   |
                                              |  | engine (M3)  |   |
                                              |  +------+-------+   |
                                              |         |           |
                                              |         v           |
                                              |  +--------------+   |
                                              |  | publish (M5) +--+|
                                              |  +--------------+ ||
                                              +---------------------+
                                                                  ||
+-----------------+                              hand-off bundle  ||
| scitex-live-    |<------------------------------------------------+
|   paper         |
+-----------------+

+----------------+ reviewer dashboard surface
| scitex-hub     |<-- (optional Django app, M6)
+----------------+
```

The dependency direction is strict: data flows in only from `scitex-clew` /
`scitex-scholar`, and flows out only to `scitex-live-paper`. The package
hosts on `scitex-hub` but does not depend on it for review correctness.

## Full pipeline (design target)

```
   submit (manuscript + project repo + Clew DAG)
      |
      v
   gate 1: ORCID + code repo + DAG completeness check
      |
      v
   gate 2: AI review (Spartan / Qwen-class reviewer agents)
      |     - reproducibility re-run + claim verify
      |     - novelty + literature triangulation (Scholar)
      |     - methodology critique
      |
      v
   gate 3: editorial decision (accept / revise / reject)
      |
      v
   gate 4: persistent ID
      |       (JaLC after incorporation; Zenodo DOI interim;
      |        sandbox-DOI for dev)
      |
      v
   publish -> Live Paper (`scitex-live-paper`)
```

## Dependency direction

```
scitex-agentic-journal   --reads-->   scitex-clew         (claim model + DAG)
scitex-agentic-journal   --reads-->   scitex-scholar      (literature triangulation)
scitex-agentic-journal   --emits-->   scitex-live-paper   (rendered artefact)
scitex-agentic-journal   --hosts-on-> scitex-hub          (reviewer dashboard, auth)
```

- The **claim** data model is owned by `scitex-clew` (decision locked in). Agentic-journal is a **consumer** — it does not define new claim types; it reads `VerificationStatus`, the DAG, and the hash-verified provenance graph.
- After acceptance, agentic-journal hands the manuscript bundle (LaTeX + claims + DAG + assets) to `scitex-live-paper` for rendering.
- Hosting (web UI, Auth via Gitea, app surface) is provided by `scitex-hub`. Agentic-journal ships an optional Django app for the reviewer dashboard.

## First milestone (M1, "submission gate")

1. Define `Submission` schema (manuscript bundle + ORCID + code repo URL + clew project path).
2. Implement gate 1 only: structural checks against the submitted bundle — no AI review yet.
   - ORCID resolvable
   - code repo cloneable
   - clew DAG present and `clew claim verify` returns ≥ 1 green claim
3. CLI: `scitex-agentic-journal submit ./paper/` returns gate-1 verdict (pass / fail + reasons).
4. No mocks. No silent fallbacks. Real errors with guidance.

Subsequent milestones (tracked as issues):

- **M2** — AI review (Spartan Qwen reviewer agents): reproducibility re-run, claim verify, novelty triangulation, methodology critique.
- **M3** — Editorial decision engine (accept / revise / reject) over the review record.
- **M4** — Persistent ID (sandbox → Zenodo → JaLC).
- **M5** — Publish hand-off to `scitex-live-paper`.
- **M6** — Reviewer dashboard on `scitex-hub` (Django app).
- **M7** — MCP server for agents.

## Installation

```bash
pip install scitex-agentic-journal           # CLI + library
pip install scitex-agentic-journal[mcp]      # + MCP server for agents
pip install scitex-agentic-journal[dev]      # + dev/test extras
```

From source:

```bash
git clone https://github.com/ywatanabe1989/scitex-agentic-journal.git
cd scitex-agentic-journal
pip install -e ".[dev]"
pytest tests/
```

## Demo

The submit / review / decide / publish subcommands return structured
errors until their tracking issues land. The version + help paths are
the existing smoke surface:

```console
$ scitex-agentic-journal --version
scitex-agentic-journal, version 0.1.0-alpha
$ scitex-agentic-journal --help
Usage: scitex-agentic-journal [OPTIONS] COMMAND [ARGS]...

  ARA-native AI-reviewed open publishing on top of Clew.
  See `scitex-agentic-journal <subcommand> --help`.

Commands:
  decide   Apply the editorial decision engine to a review record.
  publish  Hand off an accepted submission to scitex-live-paper.
  review   Run a single reviewer-agent against a persisted submission.
  submit   Submit a manuscript bundle through Gate-1 (orchestrator stub).
```

Library demos for the Gate-1 ORCID resolver (#2) and code-repo
cloneability check (#3) live under [`examples/`](examples/README.md).

## 4 Interfaces

This package exposes four stable interfaces, each tracked by its own
milestone:

| Interface | Surface | Status | Tracking |
|---|---|---|---|
| **CLI** | `scitex-agentic-journal {submit,review,decide,publish}` | scaffolded (stub subcommands) | #5 M1 CLI |
| **Library** | `scitex_agentic_journal._gate1.{verify_orcid, clone_code_repo, cloned_code_repo, GateFailure, …}` | ORCID #2 ✓ / code-repo #3 ✓ / DAG #4 pending | #2–#4 |
| **MCP server** | `scitex_agentic_journal._mcp` (fastmcp) | not started | post-MVP |
| **Django app** | `scitex_agentic_journal._django` (reviewer dashboard) | not started | #6 M6 |

## Part of SciTeX

`scitex-agentic-journal` is part of [SciTeX](https://scitex.ai).

>Four Freedoms for Research
>
>0. The freedom to **run** your research anywhere — your machine, your terms.
>1. The freedom to **study** how every step works — from raw data to final manuscript.
>2. The freedom to **redistribute** your workflows, not just your papers.
>3. The freedom to **modify** any module and share improvements with the community.
>
>AGPL-3.0 — because we believe research infrastructure deserves the same freedoms as the software it runs on.

Upstream dependencies:

| Package | Provides | Used here for |
|---------|----------|---------------|
| `scitex-clew`    | claim model + DAG + verification | submission gate, AI review evidence |
| `scitex-scholar` | literature search                | novelty / triangulation in AI review |
| `scitex-writer`  | manuscript bundle format         | submission ingestion |
| `scitex-hub`     | hosting (web UI, Auth, app store)| reviewer dashboard surface |
| `scitex-ui`      | UI shell + components            | reviewer dashboard, future viewer wiring |
| `scitex-dev`     | CLI scaffolds, validate-version  | dev tooling |

Downstream consumer:

| Package | Receives | For |
|---------|----------|-----|
| `scitex-live-paper` | accepted manuscript + claims + DAG | rendered interactive paper |

## Status

Pre-alpha — design + scaffold only. Implementation tracked under issues.

## License

AGPL-3.0-only.

---

<p align="center">
  <img src="docs/assets/images/scitex-icon-blue.png" alt="SciTeX" width="64">
  <br>
  <sub>Part of <a href="https://scitex.ai">SciTeX</a> — open, AI-reviewed publishing for science.</sub>
</p>

<!-- EOF -->
