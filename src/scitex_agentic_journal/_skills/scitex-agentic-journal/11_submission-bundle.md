---
description: |
  [TOPIC] Submission bundle
  [DETAILS] Shape of the manuscript bundle Gate-1 ingests: LaTeX + claims + Clew DAG + code repo + ORCID.
tags: [scitex-agentic-journal-submission-bundle]
---

# 02 · Submission bundle

A **submission** to `scitex-agentic-journal` is a manuscript bundle. It is **read** by the package, never authored by it. The bundle shape is owned upstream (`scitex-writer`); agentic-journal only validates it.

## Required components

| Component | Source | Why agentic-journal needs it |
|-----------|--------|------------------------------|
| LaTeX source + assets | `scitex-writer` manuscript dir | Human-readable manuscript, fed to reviewer agents and to `scitex-live-paper` after acceptance |
| Claims file (`claims.yaml`) | `scitex-clew` | Machine-readable claim set, each linked to provenance nodes in the DAG |
| Clew DAG | `scitex-clew` | Verifies that ≥ 1 claim has a green `VerificationStatus`; provides the reproducibility graph reviewers re-run against |
| Code repo URL | author input | Must be `git clone`-able by the gate-1 checker; reviewer agents clone + run it |
| Corresponding author ORCID | author input | Must resolve via `pub.orcid.org` JSON API; one author MUST be ORCID-bearing for accountability |

## Bundle directory layout (proposed)

```
paper/
├── manuscript/                  # scitex-writer output
│   ├── main.tex
│   ├── figures/
│   └── refs.bib
├── claims.yaml                  # scitex-clew claim manifest
├── dag/                         # scitex-clew DAG (provenance)
│   └── ...
├── code_repo_url.txt            # one line: https://github.com/... (must be cloneable)
└── submission.yaml              # ORCID, title, author list, submitter affiliation, license intent
```

`submission.yaml` schema (M1 target):

```yaml
title: "Title of the paper"
authors:
  - name: "Yusuke Watanabe"
    orcid: "0000-0001-2345-678X"     # required for at least one author
    affiliation: "..."
  - name: "Other Author"
    affiliation: "..."
corresponding_author_orcid: "0000-0001-2345-678X"
code_repo_url: "https://github.com/owner/repo"
license_intent: "CC-BY-4.0"          # publish license; non-publish reviewer artefacts remain AGPL-only
clew_project: "./"                   # path to the Clew project (claims.yaml + dag/)
```

## What gate-1 checks

See [03_gate1-checks.md](03_gate1-checks.md). Briefly: ORCID resolvable, code repo cloneable, Clew DAG present + ≥ 1 green claim. Any failure returns a structured `Gate1Result` with reasons — no silent fallback, no partial pass.

## What gate-2 reads from the bundle

- `manuscript/main.tex` and `manuscript/figures/` — for reproducibility and methodology critique.
- `claims.yaml` + `dag/` — for claim-verification re-runs.
- `code_repo_url.txt` — to clone + execute the bundled code in a sandbox.
- `submission.yaml` — for author / affiliation context (used by novelty triangulation to avoid self-citation noise).

## Not in the bundle (out of scope)

- Cover letter — no human editor reads it.
- Suggested / opposed reviewers — there are no human reviewers.
- Page-count / formatting compliance — Live Paper handles rendering, so author formatting is forgiving.
- APC payment — alpha-stage; pricing is post-incorporation.

## Bundle authoring tools

Authors do **not** assemble the bundle by hand. The expected flow:

1. `scitex-writer init` → manuscript skeleton.
2. `scitex-clew claim add ...` → claims + provenance during the research.
3. `scitex-agentic-journal bundle ./paper/` (planned) → assembles `submission.yaml` interactively from the writer/clew state.
4. `scitex-agentic-journal submit ./paper/` → runs gate-1 and ingests.
