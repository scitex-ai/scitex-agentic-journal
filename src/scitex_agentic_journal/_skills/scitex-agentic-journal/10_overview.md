---
description: |
  [TOPIC] Overview
  [DETAILS] What scitex-agentic-journal is, MVP loop, full pipeline, dependency direction.
tags: [scitex-agentic-journal-overview]
---

# 01 · Overview

`scitex-agentic-journal` is the **journal substrate** of SciTeX: a publication venue where AI agents — not volunteer reviewers — perform peer review, reproducibility re-run, claim verification, novelty triangulation, methodology critique, and editorial decision.

Human authors still write and revise. AI agents read, run, verify, critique, and decide.

## Problem framing

Traditional peer review is slow, opaque, volunteer-limited, and cannot keep pace with the preprint flood. AI agents can now read, run, and verify the entire research workflow — code, data, claims, provenance — in minutes. `scitex-agentic-journal` turns that capability into a publication venue with **auditable AI-driven editorial decisions**.

## MVP loop

```
   submit → agent review → decision → publish
```

The MVP collapses the long pipeline into the smallest end-to-end useful loop:

1. **submit** — accept a manuscript bundle through CLI / MCP, persist with provenance.
2. **agent review** — run a single reviewer agent against the bundle, persist its report.
3. **decision** — apply rule-based editorial logic over the review record → `accept | revise | reject`.
4. **publish** — emit a Live Paper bundle (accepted) or a revision packet (revise), stamp a persistent ID.

## Full pipeline (design target)

```
   submit (manuscript + project repo + Clew DAG)
      |
      v
   gate 1: ORCID + code repo + DAG completeness check     [03_gate1-checks.md]
      |
      v
   gate 2: AI review (Spartan / Qwen-class reviewer agents)
      |     - reproducibility re-run + claim verify
      |     - novelty + literature triangulation (Scholar)
      |     - methodology critique
      |
      v
   gate 3: editorial decision (accept / revise / reject)  [04_review-and-decision.md]
      |
      v
   gate 4: persistent ID
      |       (JaLC after incorporation; Zenodo DOI interim;
      |        sandbox-DOI for dev)
      |
      v
   publish -> Live Paper (`scitex-live-paper`)            [05_publish-handoff.md]
```

## Milestones

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 | Submission gate (gate-1 only, no AI review) | gate-1 checks landed; CLI `submit` pending |
| M2 | AI review (gate-2): reproducibility + claim verify + novelty + methodology | pending |
| M3 | Editorial decision engine (gate-3) | pending |
| M4 | Persistent ID (sandbox → Zenodo → JaLC) | pending |
| M5 | Publish hand-off to `scitex-live-paper` | pending |
| M6 | Reviewer dashboard on `scitex-hub` (Django app) | pending |
| M7 | MCP server for agents | pending |

GitHub issues `#2`–`#9` track the MVP loop. Anything beyond is deferred.

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

## Non-goals

- New claim ontology (owned by Clew).
- New manuscript bundle format (owned by `scitex-writer`).
- Literature search itself (owned by `scitex-scholar`).
- Hosting / auth / billing (owned by `scitex-hub`).
- Reviewer compensation / reputation systems (volunteer-reviewer infrastructure is explicitly out of scope).
