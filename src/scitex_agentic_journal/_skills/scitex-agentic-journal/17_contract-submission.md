---
description: |
  [TOPIC] Contract-based submission (0.2.0)
  [DETAILS] Bundle format, admission checks, preprint snapshot and review ingestion from any source; journal consumes scitex-live-paper contracts by vendored JSON Schema, never by import.
tags: [scitex-agentic-journal-contract-submission]
---

# 17 · Contract-based submission, admission, preprint, review ingestion

The path before review (design: `docs/design/01_contract-submission-and-independent-review.md`).
It sits **alongside** the legacy `submit/review/decide` intake.

## Flow

```
bundle seal DIR  →  bundle validate DIR  →  bundle submit DIR  →  admission evaluate ID  →  preprint create ID vX.Y.Z --yes  →  reviews ingest ID report.json source.json
```

Every command takes `--json`. Records go to
`$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<aj-id>/` (default
`~/.scitex/agentic-journal`).

## Bundle

```
submission/
├── submission.json        # journal manifest (schema: _contracts/schemas/submission.schema.json)
├── manuscript/            # PDF and/or LaTeX
├── evidence-report.json   # scitex-live-paper.evidence-report 1.x (e.g. `clew export-evidence`)
├── review-packet/review.json, review.txt   # `scitex-live-paper export-review`
└── references.bib
```

`submission.json` lists **every** file with `sha256:<hex>`. It also declares:

- `submitter_orcid` and `authors`;
- `repository{url, commit}`;
- `licence{manuscript, code}`;
- `data[]` (public only in v1);
- `produced_by[]`, the humans and agents who made the work, none of whom may
  review it;
- `main_claims[]`;
- `contracts`, and optionally `conversion` and `supersedes`.

The submission id is `aj-` + the first 16 hex digits of the sha256 of the
canonical manifest.

## Admission checks

| check | required | what |
|---|---|---|
| `orcid` | yes | the submitter's ORCID resolves and is among the authors |
| `repository` | yes | `repository.commit` checks out without credentials; `https://` only (operator flag `--allow-local-repositories` for local journals) |
| `scitex-form` | yes | `scitex-dev linter validate-files --json`: `.scitex/dev/config.yaml` declares `project-type: research`, there are 0 errors, and `all_rules_ran` |
| `main-claims-evidence` | yes | every main claim is `supported` with an evidence graph |
| `clew-reverify` | no | `not-run`: Clew state lives in the authors' host store, not in the snapshot |
| `executability`, `reproduction` | no | `not-run` unless an isolated executor is configured; author code never runs on the host |

## Preprint

`preprint create` requires an admitted submission. It records:

- an internal persistent ID, with the DOI `unregistered` until a minter runs;
- hashes of the manifest, evidence report, review packet and admission
  record;
- `peer_reviewed: false`.

## Review ingestion (any source)

`reviews ingest ID report.json source.json --channel operator-cli|self-declared`

Both channels are recorded as `verified_by_journal: false`. Verified channels (ORCID login, journal-issued service keys) come with an authenticated portal/API surface, not the CLI.

- **report**: `_contracts/schemas/review-report.schema.json`. It holds:
  - `claim_findings[]`, each with `claim_id`, `verdict`, `graph_nodes`,
    `severity`, `dimension` and `comment`;
  - `general_findings[]` for text that is not a registered claim (no
    verdict);
  - `recommendation`.
- **source**: `_contracts/schemas/review-source.schema.json`. Its `kind` is
  `human`, `external-service` or `journal-panel`, and it carries the
  identity, `declared_independence` and `disclosure`.

What the journal does on ingestion:

- writes each claim's `packet_state` itself and records every unmentioned
  claim as `not-assessed`;
- rejects unknown claims and graph nodes, and rejects authors or producers
  as reviewers;
- assigns per-submission pseudonyms (`r1`, `r2`, …);
- adds findings to `findings.json` under stable keys, so re-filing never
  duplicates them.

## Decision guard

`decide` (legacy path) refuses review records whose `adapter_mode` is not
`live`, including the `local-deterministic` placeholder.
