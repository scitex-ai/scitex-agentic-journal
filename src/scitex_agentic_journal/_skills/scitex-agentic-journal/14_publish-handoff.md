---
description: |
  [TOPIC] Gate-4 persistent ID + publish hand-off
  [DETAILS] Sandbox -> Zenodo -> JaLC ID minting and the bundle hand-off into scitex-live-paper.
tags: [scitex-agentic-journal-publish-handoff]
---

# 05 · Gate-4 persistent ID + publish hand-off

After gate-3 returns `accept`, the manuscript needs a **persistent identifier** and a **rendered Live Paper**. Gate-4 + publish hand-off cover both.

## Gate-4 — Persistent ID

The persistent ID strategy is **staged** because we don't have JaLC incorporation yet:

| Phase | Backend | When to use |
|-------|---------|-------------|
| **Dev / pre-alpha** | `_publish/internal_id_minter.py` | Default. Mints `scitex-aj-{YYYYMMDD}-{slug}-{hash6}`. No external dependency. |
| **Pre-incorporation public** | Zenodo Sandbox DOI | When testing the publish pipeline against a real DOI registry without burning real DOIs. |
| **Public live** | Zenodo (production) | After alpha sign-off, before JaLC. Real DOI. |
| **Post-incorporation** | JaLC | Final state — required for the journal-of-record positioning. |

Adapter pattern:

```python
class IdMinter(Protocol):
    backend: str           # "internal" | "zenodo-sandbox" | "zenodo" | "jalc"
    def mint(self, decision_record: DecisionRecord) -> PersistentId: ...
```

The selected backend is configured per deployment via `SCITEX_AJ_ID_BACKEND` env var (no silent fallback — an unknown backend raises at startup).

### Why internal IDs default

Until we have either Zenodo Sandbox creds in CI or real JaLC keys, the default minter MUST produce a valid persistent string that the rest of the pipeline (Live Paper, hub URLs, citation export) can consume. Treating "no DOI yet" as a fallback to `None` would silently break every downstream consumer — exactly the kind of fallback `CLAUDE.md` forbids.

## Publish hand-off — Live Paper

`scitex-agentic-journal` does **not** render papers. After acceptance + ID minting, it hands the bundle to `scitex-live-paper`:

```
agentic_journal:
  Submission + DecisionRecord(accept) + PersistentId
        |
        v   _publish/live_paper_proxy.py
        v
scitex_live_paper.publish(
    manuscript_dir=...,
    claims=...,
    dag=...,
    persistent_id=...,
    review_record=...,        # for the "Reviews" tab in Live Paper
    decision_record=...,
)
```

The proxy is intentionally thin — Live Paper owns rendering, hosting, and the interactive viewer. Agentic-journal just packages and hands off.

### What ships to Live Paper

| Asset | Why |
|-------|-----|
| Final manuscript LaTeX + assets | Rendered to the live page |
| Claims + DAG | Powers the in-paper claim cards + "Verify yourself" buttons |
| Review record | Powers the "AI Reviewers" tab (transparency) |
| Decision record | Powers the "Editorial Decision" footer (auditability) |
| Persistent ID | Permanent citation handle |

## Revise / Reject hand-off

- `revise` — no Live Paper publication. Agentic-journal emits a `RevisionPacket` (review record + decision rationale + change-request list) addressed to the corresponding-author ORCID via SciTeX-hub notification surface.
- `reject` — same as revise but flagged terminal; corresponding author may re-submit a new manuscript but not the same bundle ID.

## Citation format (interim, internal-id phase)

```
Watanabe, Y. et al. (2026). Title of the paper.
SciTeX Agentic Journal (scitex-aj-20260613-title-of-paper-a1b2c3).
https://scitex.ai/aj/scitex-aj-20260613-title-of-paper-a1b2c3
```

Once we move to Zenodo / JaLC, the resolver URL becomes the DOI; the internal ID survives as the canonical short handle.

## What this stage does NOT do

- It does **not** retract papers (post-publication retraction is M8+).
- It does **not** route to author institution OA servers (out of scope).
- It does **not** notify Scholar — Scholar indexes scitex.ai/aj/* on its own crawl.
