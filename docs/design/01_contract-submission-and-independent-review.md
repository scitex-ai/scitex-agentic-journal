# Design 01 — Contract-based submission, admission and review ingestion

Status: **accepted with re-scope (2026-11-19)**. See §0. Phase 2 (the stages
*before* review) shipped in 0.2.0; see §10.

Scope: submission → admission checks → preprint snapshot → review
ingestion → decision. Every verdict points at a registered claim. Findings
are tracked as issues on the authors' git host (§12). The two stages,
preprint and then journal, are covered with their gates and DOIs (§13), and
transparency is the answer to the "predatory journal" criticism (§14). Each
accepted claim is also exported as a corpus record (§15).

## 0. Decisions and re-scope (operator, 2026-11-19)

- **D1 = Option A.** The new path is added alongside the legacy one and
  nothing existing breaks.
- **Reviewing is not the focus now.** The journal **accepts** reviews; it
  does not produce them. Reviews may come from:
  - external AI review services;
  - human researchers writing reviews manually;
  - other users.

  The K-sealed-SAC reviewer panel (§6, `_panel`) is kept as a **future
  option** and is not built in Phase 2. D4 and D6 are moot.
- **Review ingestion (§7a)** is a generic interface. Any source files a
  `review-report` (§7) together with a `source` provenance block. The
  journal validates it against the packet, records it, and tracks its
  findings as issues (§12). The journal never assumes it produced a review.
- **Phase 2** covers the stages before review: intake (repo or bundle, ORCID
  link, licence), admission checks (SciTeX form, Clew verify, executability
  and reproduction), preprint snapshot (version, Live Paper contract,
  internal ID, DOI adapter later), and the fix for defect 1 (no decision
  without a real review on record).
- **D2:** live-paper publishes the review-packet JSON schema (separate PR
  there), and the journal vendors it pinned by commit.
- **D3, D5:** as recommended in §11.

## 1. Where the repo stands (audit of `develop` @ 3824d01, v0.1.0a4)

What exists and works (691 tests pass, 14 opt-in skips for network/Clew):

| Stage | Module | State |
|---|---|---|
| Intake | `_submit` | `bundle.yaml` = `{orcid_id, code_repo_url, clew_project_path}`; strict loader; JSON records under `$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/` |
| Gate 1 | `_gate1` | ORCID resolves, repo clones, `clew dag --claims --json` (subprocess, CLI-pinned to scitex-clew 0.21.0) has ≥1 verified run |
| Review | `_review` | one `ReviewerAdapter` per run, four ARA sub-reports (reproducibility, claim_verify, novelty, methodology). Adapters: `local-deterministic` (no LLM) and `qwen` (stub that raises) |
| Decision | `_decide` | rule engine `rules/v1.yaml` over one `ReviewRecord` → accept / revise / reject |
| Publish | `_publish`, `_ports/_live_paper` | persistent-ID minting interfaces; hand-off envelope to live-paper |
| Surfaces | `_cli`, `_django`, `_mcp` | CLI verbs submit/review/decide/publish; Django author portal; MCP catalogue (all handlers `NotImplementedError`; draft PR #67 adds one read handler) |

Loose coupling is already respected: nothing imports `scitex_clew` or
`scitex_live_paper`; Clew is reached through its CLI and live-paper through
a port protocol.

In flight: only draft PR #67 (one read-only MCP handler, idle since
2026-11-04); it does not touch the areas below. Released: v0.1.0a4 (PyPI).

Defects found:

1. **A placeholder review can produce an "accept".** `local-deterministic`
   reports `reproducibility.passed=True` without running anything and
   `novelty.overlap_score=0.0` without searching
   (`_review/_local_adapter.py`); for any bundle that passed Gate 1 (≥1 green
   claim, none red) `decide` then fires `default_accept`. Neither the
   persisted review nor `_decide` carries or checks the adapter's `mode`.
   Whatever option is chosen, `decide` must reject records from non-live
   adapters.
2. **No reviewer exists that actually reviews.** The only live-capable
   adapter is a stub; there is no path that runs a model.
3. **Reviewers would run in-process on the journal host**, with whatever the
   host can see (author files, network, the operator's credentials). There is
   no isolation and no record of which model reviewed.
4. **README "Status: Pre-alpha — design + scaffold only"** contradicts the
   alpha status line at the top of the same file.

## 2. Direction conflict (decided: Option A, §0)

The repo's documented design (`_skills/.../13_review-and-decision.md`) and the
vision this document serves disagree on four points:

| # | Repo today | Vision |
|---|---|---|
| C1 | One in-process LLM adapter; "**No reviewer identity** … the reviewer is `adapter@version`" | K independent reviewers, each in its own sealed SAC container; reviewer identity and **model identity recorded per review**; humans may review too |
| C2 | Bundle = ORCID + repo URL + Clew project; journal re-derives claim status by running the Clew CLI | Bundle = manuscript + live-paper **review packet** + **evidence report** + bibliography, validated against vendored, version-pinned live-paper JSON schemas; the journal runs no Clew code |
| C3 | Review = four ARA sub-reports with claim ids bucketed green/yellow/red | Review = **per-claim findings** referencing claim ids and graph nodes, plus an overall recommendation |
| C4 | Decision = automatic rule engine, "**No human reviewer override**" | Editor summary aggregates K reports; a named editor (human or agent) records the decision |

Not a conflict: live-paper as a post-acceptance renderer (`_publish`) and
live-paper as the producer of the review packet can both hold.

### Option A — add a contract-based path beside the existing one (recommended)

New modules (`_contracts`, `_bundle`, `_panel`, `_report`, `_editor`) and CLI
verbs implement §3–§7. Gate 1, ARA adapters and `rules/v1` stay untouched
and are labelled *legacy intake*; `decide` gains a guard that refuses stub
adapter records (defect 1). The Django portal and MCP keep working. After the
new path has run on real submissions (scitex-template MNIST showcase, the scitex-clew paper), a follow-up
retires or rebases the legacy path.

- For: no breaking change to released alpha surfaces or the portal; slice is
  shippable as 0.2.0; existing tests keep guarding the old path.
- Against: two intake formats coexist for a while; docs must say which is
  canonical.

### Option B — replace the review/decision core

Retire `_gate1`'s Clew subprocess, the ARA adapters and `rules/v1`; rebuild
`submit/review/decide` around the packet. Smaller code base at the end, but it
breaks the released CLI/portal behaviour, rewrites the `_gate1`, `_review`
and `_decide` test suites, and
couples the first SAC slice to a large migration.

**Recommendation: A**, plus fixing defect 1 immediately in the same release.
The skill page `13_review-and-decision.md` is updated to state that the
"no reviewer identity / no human override" stance applies to the legacy path
only.

## 3. Submission bundle (`scitex-agentic-journal.submission` 1.0)

A directory (or a `.tar.gz` of one):

```
submission/
├── submission.json        # manifest (journal-owned schema)
├── manuscript/            # main.pdf (required) and/or LaTeX sources
├── review-packet/         # `scitex-live-paper export-review` output, unchanged
│   ├── review.json        #   scitex-live-paper.review-packet 1.x
│   └── review.txt         #   its plain-text rendering
├── evidence-report.json   # scitex-live-paper.evidence-report 1.x, unchanged
└── references.bib         # bibliography
```

`submission.json`:

```json
{
  "schema": "scitex-agentic-journal.submission",
  "schema_version": "1.0",
  "title": "…",
  "authors": [{"name": "…", "orcid": "0000-…", "corresponding": true}],
  "produced_by": [{"kind": "agent", "id": "paper-scitex-clew", "model": "…"}],
  "repository": {"host": "github", "url": "https://github.com/…/…", "commit": "<sha>"},
  "supersedes": null,
  "contracts": {
    "review_packet":   "scitex-live-paper.review-packet@1",
    "evidence_report": "scitex-live-paper.evidence-report@1"
  },
  "files": {"manuscript/main.pdf": "sha256:…", "…": "sha256:…"}
}
```

Validation at intake (all failures are loud, structured, and stored):

1. Manifest validates against the journal's own schema.
2. Every file listed in `files` exists and its SHA-256 matches; no unlisted
   files (prevents smuggling inputs to reviewers).
3. `evidence-report.json` validates against the **vendored** live-paper
   schema (§4); `schema_version` must be `1.x.y`, and a minor newer than the
   vendored one is accepted only if it validates. `review.json` validates
   against the vendored packet schema once live-paper publishes one (§11 D2);
   until then the journal checks the packet's documented required fields and
   its `schema`/`schema_version`.
4. The packet is consistent with the report: same claim-id set, same `state`
   per claim, and `needs_inspection` true exactly when `state != supported`.
   The packet is what reviewers read, so a packet that disagrees with the
   report is rejected rather than reconciled.
5. `produced_by` is recorded for the independence check (§6).

The submission id is the SHA-256 of the canonicalised manifest, so a
re-submission of identical content is idempotent and a changed byte is a new
revision.

## 4. Contracts: vendored, pinned, never imported

```
src/scitex_agentic_journal/_contracts/vendor/scitex-live-paper/v0.4.0/
    evidence-report.schema.json   # $id …/evidence-report/1.1.0 (draft 2020-12)
    review-packet.schema.json     # once published upstream (§11 D2)
    VENDORED.json   # {source_repo, tag, commit, path, sha256 per file}
```

Facts relied on (live-paper v0.4.0, both contracts at 1.1.0): a claim has
`claim_id`, `location`, `state ∈ {supported, not_supported, not_checkable,
no_evidence_graph}`, `reason`, and optionally `graph{nodes[{id,kind,…}],
edges}`; anything but `supported` means *needs inspection*; only registered
claims appear, and text that is not a registered claim is not assessed.

A test recomputes the SHA-256 of each vendored file against `VENDORED.json`.
Updating a contract is an explicit PR that bumps the vendored tag. The journal
never imports `scitex_live_paper` or `scitex_clew`; `jsonschema` is the only
new runtime dependency. Journal-owned schemas (submission, review report,
editor summary, reviewer spec) live in `_contracts/schemas/` and are
published in the wheel so live-paper or a dashboard can consume them the same
way.

## 5. Workflow

```
submitted ──validate──▶ validated ──assign K──▶ assigned
    │ invalid                                     │ launch (SAC, one container per reviewer)
    ▼                                             ▼
 rejected-at-intake                          reviewing ──collect──▶ reviewed
                                                                    │ aggregate
                                                                    ▼
                                         decided ◀──editor── editor-summary
                    (accept | minor-revision | major-revision | reject)
```

Review is iterative: after `collect`, the journal files each finding as an
issue in the submission's repository (§12); the author answers with linked
commits/PRs and resubmits; round N+1 re-runs the *same* reviewer slots, which
close or re-open their own issues. `decided` is reached when the editor rules
on a round's summary.

Every transition writes one immutable JSON record into
`$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/` (existing layout; no
database). A revision is a new submission linked by `supersedes`.

CLI (shipped in 0.2.0; every command takes `--json`):

```
scitex-agentic-journal bundle validate   <dir>
scitex-agentic-journal bundle submit     <dir>                     # → aj-<16 hex> submission id
scitex-agentic-journal admission evaluate <id>                      # §13.1 checks → admission.json
scitex-agentic-journal admission show    <id>
scitex-agentic-journal preprint create   <id> <vX.Y.Z>             # admitted only; internal id, DOI later
scitex-agentic-journal preprint show     <id>
scitex-agentic-journal reviews ingest    <id> report.json source.json --channel orcid-login|service-key|operator-cli|self-declared
scitex-agentic-journal reviews list      <id>
```

Future (not in 0.2.0): `panel assign|run|collect` for the in-house reviewer
panel (§6), the editor summary and the contract-path `decide` (§8), and hosted
issue filing (§12).

## 6. Reviewer independence (future option: in-house reviewer panel)

*Not built in Phase 2 (§0). For ingested reviews, the journal records the
independence facts the source declares (§7a); it guarantees them only for
reviews it runs itself.*

Independence is enforced by construction, recorded, and reported — never
assumed.

| Guarantee | Mechanism |
|---|---|
| Reviewer sees only the submission | SAC sealed run (`sandbox` block, jail, `comms` denied, `to_home_layers: [per-agent]`, no author skills/memory). The working directory is a fresh copy of the bundle's `review-packet/`, `manuscript/`, `evidence-report.json`, `references.bib` plus the fixed prompt. SAC 0.40.1 cannot mount it read-only, so the journal manifests it before the run and rejects the report if any input byte changed (§11 D3) |
| No side channels | `sandbox.egress.allow` = the model provider endpoint only; `sandbox.env.allow: []` plus the model key. A literature endpoint may be added per spec and is then recorded. SAC's `egress_blocked.jsonl` is kept with the outcome |
| Fresh state per review | `sandbox.run` per-run reset (fresh overlay, `$HOME`, `/tmp`); one agent per (submission, reviewer); `sac agents stop` → wait for `outcome.json` `status: finalized` → `sac agents delete` |
| Fixed instructions | Reviewer prompt is a versioned file in this repo (`_panel/prompts/reviewer-v1.md`); its SHA-256 is recorded in the report |
| Blind to each other | Reports are collected only after all K runs end; no reviewer receives another's report |
| Not the author | Assignment refuses a reviewer whose `id` appears in the manifest's `produced_by` |
| Model identity | Each report records the model engine/provider/name from the rendered SAC spec (the journal writes this, not the reviewer) plus the outcome's `image.sha256`, `sac_version`, `token_usage`. The *served* model version is not observable in SAC 0.40.1 (`model_pin` unmet) and is recorded as `null`, not guessed |
| Same model ≠ independent | The editor summary reports `distinct_models`; two reviewers on the same model count as one model family and agreement between them is flagged as *correlated* |
| Tamper evidence | Report, outcome record and input tree are hashed; the summary lists the hashes |

A reviewer run that fails (timeout, invalid report, policy violation in the
outcome record) is recorded as `failed` and excluded from aggregation; it is
never silently replaced.

## 7. Review report (`scitex-agentic-journal.review-report` 1.0)

```json
{
  "schema": "scitex-agentic-journal.review-report",
  "schema_version": "1.0",
  "submission_id": "sha256:…",
  "review_id": "r1",
  "reviewer": {
    "kind": "agent",
    "id": "journal-reviewer-1",
    "model": {"provider": "…", "name": "…", "served_version": null},
    "orcid": null,
    "runtime": {"sac_version": "0.40.1", "spec_sha256": "…", "outcome_sha256": "…",
                "image_sha256": "…", "inputs_manifest_sha256": "…"},
    "prompt": {"id": "reviewer-v1", "sha256": "…"}
  },
  "claim_findings": [
    {
      "claim_id": "C3",
      "packet_state": "<the packet's state, copied by the journal>",
      "verdict": "supported | not-supported | unclear | not-assessed",
      "graph_nodes": ["<node id from the packet's claim graph>"],
      "severity": "none | minor | major | critical",
      "dimension": "scientific-validity | logical-structure | clarity",
      "comment": "…"
    }
  ],
  "general_findings": [
    {"location": "manuscript §2.1", "severity": "minor", "dimension": "clarity", "comment": "…"}
  ],
  "recommendation": "accept | minor-revision | major-revision | reject",
  "confidence": "low | medium | high",
  "summary": "…"
}
```

Rules checked at collection:

- every `claim_id` exists in the packet; every `graph_nodes` entry exists in
  that claim's graph in the evidence report (when the report omits the
  graph, node ids are recorded as unverified);
- `packet_state` is written by the journal from the packet, never taken from
  the reviewer, so the summary can show where a reviewer's `verdict` departs
  from the evidence state;
- packet claims a reviewer did not mention are recorded by the journal as
  `not-assessed` (never filled in);
- **untagged text gets no verdict** — it can only appear in
  `general_findings`, which carry severity but no claim assessment;
- for `kind: "human"`, `model` is null and `orcid` is required.

## 7a. Review ingestion (any source)

```
scitex-agentic-journal reviews ingest <submission-id> report.json source.json --channel <channel>
```

The same operation is available from the portal and, later, MCP. The report
follows §7. The `reviewer` block is replaced by a journal-verified **source**
block:

```json
"source": {
  "kind": "human | external-service | journal-panel",
  "reviewer_pseudonym": "r3",
  "identity": {"orcid": "0000-…", "service": "…", "service_version": "…",
               "model": {"provider": "…", "name": "…", "served_version": null}},
  "declared_independence": {"not_an_author": true, "saw_author_materials": false,
                            "conflicts": "none declared"},
  "attestation": "<how the identity was established: ORCID login | service API key id | signed payload>",
  "disclosure": "blind | model-family | open"
}
```

Rules:

- **Identity comes from the channel, not the payload.** A human is
  identified by their ORCID login. An external service is identified by the
  journal-issued key it called with. A free-text claim inside the report is
  stored but never trusted.
- **Validation** follows §7: claim ids and graph nodes are checked against
  the packet, `packet_state` is written by the journal, unmentioned claims
  are recorded as `not-assessed`, and untagged text gets general findings
  only.
- **Authors cannot review their own submission.** Any producer listed in
  the manifest (`produced_by`) is refused as a reviewer.
- **Findings become issues (§12).** Re-checks in later rounds come from the
  same source, identified by the same channel.
- **Undeclared independence is reported.** The editor summary shows
  `distinct_models` and, per source, its declared independence. Missing
  declarations are flagged, not assumed.

## 8. Editor summary and decision

`editor-summary.json` (+ a plain-text rendering) per submission:

- per claim: the packet's evidence `state` next to the K verdicts,
  agreement, and the union of graph nodes reviewers cited; claims whose
  verdicts split, or where a reviewer contradicts the evidence state, are
  listed first;
- recommendation tally; failed/excluded runs with reasons;
- independence block: reviewer ids, kinds, `distinct_models`, correlated
  pairs;
- hashes of every input and report;
- issue ledger per round (§12): opened / closed-resolved / re-opened / still
  open, by severity and by claim, with every unresolved `critical` or `major`
  issue listed by link.

The summary recommends, it does not decide. `panel decide` records the editor
(human ORCID or agent id + model), the decision and a reason referencing
summary items. Automatic decision rules can be added later as a
`rules/v2.yaml` *suggestion* over the summary.

## 9. Humans and agents

| Actor | Agent path | Human path |
|---|---|---|
| Author | `make submit` / `bundle submit` from the project (scitex-template target) | Django author portal upload of the same bundle |
| Reviewer | SAC sealed container, reads files or live-paper MCP tools, writes `review-report.json` | fills the same schema (or the portal form) → `reviews ingest`; reads `review.txt` / live-paper viewer |
| Editor | Agent reads `editor-summary.json`, calls `panel decide` | Reads `editor-summary.txt` / portal, calls `panel decide` |

Same schemas for both; only `reviewer.kind` and identity fields differ.

## 10. Phase-2 slice (re-scoped, §0)

1. `_contracts`:
   - vendored live-paper schemas (evidence report, review packet), pinned by
     commit, plus a hash test;
   - journal-owned schemas: submission, check record, preprint record,
     review report.
2. `_bundle`: `bundle validate|submit` for the submission bundle (§3):
   - manifest checks, file hashes, no unlisted files;
   - evidence-report schema, packet/report consistency;
   - licence and public-data declaration (§13.1b);
   - idempotent submission id and records.
3. `_admission`: the admission checks (§13.1). Each check writes a check
   record `{check, status: passed | failed | not-run, reason, tool, version,
   inputs/outputs hashes}`:
   - **ORCID**: reuses `_gate1/_orcid`.
   - **SciTeX form**: the scitex-dev research lint, run as a subprocess.
   - **Clew verify**: re-derives the evidence states from the snapshot and
     compares them with the submitted report.
   - **Executability and reproduction**: run behind an executor adapter.
     The default executor is `none`, which yields `not-run` with an explicit
     reason. Author code never runs on the journal host outside an isolated
     executor.

   All subprocesses get an explicit allowlisted environment.
4. `_preprint`: the snapshot record:
   - repo, tag, commit, bundle hash;
   - version, plus the internal ID from the existing `InternalIdMinter`;
   - DOI through the existing `IdMinter` adapters, later and optional;
   - the Live Paper input taken from the live-paper contract.
5. `_ingest`: review ingestion (§7a), with validation against the packet.
6. **Defect 1:** `decide` refuses review records that are not real (stub
   adapters, or none on record).
7. Issue tracking (§12) is designed but not shipped in 0.2.0. Ingested
   findings are kept in the `local` tracker records, and the GitHub adapter
   follows.
8. Tests use a real bundle built from the live-paper MNIST example, with
   opt-in markers for network and subprocess tools.
9. Release 0.2.0.

## 11. Open decisions

| id | Question | Recommendation |
|---|---|---|
| D1 | Option A (add beside legacy) or B (replace core)? (§2) | **Decided: A** |
| D2 | live-paper publishes `review-packet.schema.json` (packet is defined only in `_packet.py` today) | **Decided:** live-paper ships it next to the evidence-report schema, and the journal vendors it pinned by commit |
| D3 | *(applies to the future in-house panel)* SAC has no read-only input mount and no served-model pin (`readonly_packet`, `model_pin` unmet in 0.40.1) | Accept for the first slice with the manifest check and `served_version: null`; request both from SAC |
| D4 | *(moot, §0)* Default panel: K and model mix | K = 3 with at least two distinct model families when keys exist; the summary always states `distinct_models` |
| D5 | Who decides: human editor only, or agent editor allowed | Both allowed, recorded; rule-based v2 only as a suggestion |
| D6 | *(moot, §0)* Reviewer egress beyond the model endpoint (literature search for novelty) | Off in v1; novelty is out of scope of claim-level review |
| D7 | Reviewer disclosure on public issues (§12.5) | **Decided (default):** reviewers are pseudonymous by default; humans may opt in to disclosure; an AI review service and its model are always disclosed |
| D8 | Default issue venue (§12.6) | **Decided (default):** issues go to the author's repository; private submissions use a private journal-owned repository |
| D9 | GitHub credential type | **Decided:** a GitHub App (per-repo install, scoped `issues:write` + `metadata:read`) when hosted issue filing is built |
| D10 | Contract for the preprint admission lint (§13.1) | **Decided:** scitex-dev's machine-readable JSON (`linter validate-files --json`) together with the scitex-dev version, both recorded in the check record |
| D11 | Acceptance gate strictness: may claims that are `not_checkable` or have `no_evidence_graph` be accepted as editor-acknowledged exceptions? | **Open, for the user.** Recommendation: allow listed exceptions with reasons, shown on the article page |
| D12 | Should the review record get its own DOI? | **Open, for the user.** Recommendation: yes, once a DOI backend is configured |
| D13 | Reproduction tolerance (§13.1 check 4) | **Decided:** by default, the tolerance implied by the claim's declared precision, as in Clew's own claim checks |
| D14 | Certificate signing key and scheme (§13.2) | **Open, for the user** (together with the production policy for the Clew evidence-bundle signing key) |
| D15 | Corpus record licence and default publication conditions (§15) | **Open, for the user.** Recommendation: follow each claim's data and code licences, and export records only for accepted claims |
| D16 | Clew state lives in the authors' host store, not in the snapshot | **Decided:** a portable, signed, versioned Clew evidence-bundle exchange format (`.scitex/clew/evidence-bundle.json`) travels with the repository. The journal consumes it through a pinned schema and does not import clew. Signing is pluggable; the production key policy is open (D14) |
| D17 | Isolated executor for executability and reproduction | **Decided:** a SAC sealed run (no host access, empty or package-index-only egress allowlist, per-run reset, outcome record), or plain apptainer `--net none` if SAC cannot run a plain command. Inside the sandbox it runs clew's store-free rerun of the evidence bundle. **Shipped:** SAC 0.40.x seals only TUI agent panes (harness + model key required; scitex-agent-container#1793), so `--executor apptainer` (`_admission/_sandbox.py`, `_executor.py`) runs it under `--containall --cleanenv --no-home --no-eval`, offline phases also `--no-mount bind-paths,hostfs,cwd --net --network none`; dependencies are fetched as wheels before any author file is staged. Default `--executor none` keeps both checks `not-run` |
| D18 | Outbound fetches steered by a submission (server-side request forgery) | **Decided and shipped (0.3.0):** resolve-then-connect. Loopback, private, link-local, multicast, reserved and unspecified targets (including IPv4-mapped IPv6) are refused, and git is pinned to the vetted address with redirects disabled |

## 12. Review findings as hosted issues

Every finding becomes a ticket in the git host the authors already use, so
review, response and re-check happen where the code and manuscript live, and
the thread *is* the review record.

### 12.1 Roles and credentials

- **Reviewers never touch the host.** A sealed reviewer only writes
  `review-report.json` (§7) plus, from round 2, `recheck.json` (§12.4). The git
  host is not on its egress allowlist and it holds no host credential.
- **The journal files issues** with its own service credential (GitHub App
  installation token preferred, D9), read from the journal's secret store at
  call time, never logged, never passed to SAC specs or subprocesses.
- **Authors respond** with ordinary commits/PRs that reference the issue.

### 12.2 Mapping finding → issue

| Finding | Issue title | Anchor (part of the key) |
|---|---|---|
| per claim | `[C3] <reviewer verdict>: <first line of comment>` | `claim:C3` |
| per graph node | `[C3 › node n17] …` | `claim:C3/node:n17` |
| general (untagged text) | `[general] <location>` | `general:<normalised location>` |

Stable labels (created idempotently; values longer than the host limit are
truncated with a short hash suffix):

```
aj:review              aj:submission/<short lineage id>
aj:claim/C3            aj:state/not_supported      # packet evidence state; absent for general
aj:severity/major      aj:reviewer/r2              # pseudonymous slot (§12.5)
aj:model/<family>      aj:round/1  aj:round/2 …    # one label per round the issue was touched
```

The body carries the finding text, links to the claim's graph page and the
cited nodes, the evidence state, and a machine marker
`<!-- aj:finding-key=<key> -->`.

### 12.3 Idempotency

`finding-key = sha256(lineage_id, reviewer_slot, anchor)` — no round, no
wording. The lineage id is the first submission's id, carried by `supersedes`.

- The journal keeps `tracker.json` per lineage: `finding-key → issue ref`,
  written after each successful call (so a crash mid-batch resumes cleanly).
- Before creating, the adapter looks up the key in `tracker.json`, then falls
  back to searching the marker among `aj:submission/<id>` issues (recovers a
  lost ledger).
- Re-running a round therefore updates/comments on existing issues; it never
  duplicates them. Two findings from one reviewer with the same anchor are
  merged into one issue (one comment each).

### 12.4 Rounds

1. Round 1: `collect` validates reports → journal files issues (`aj:round/1`).
2. Author pushes fixes referencing issues (`Fixes #12`, or a PR linking them),
   replies in the thread, and resubmits; the new manifest's
   `repository.commit` must contain the linked commits.
3. Round 2 re-runs **the same reviewer slots**: same reviewer id, model, spec
   and prompt hash, new sealed container (fresh state; continuity is by
   identity and record, not by memory). Its input tree adds a read-only
   export of *its own* issues only: finding, author replies, linked commit
   diffs. It never sees other reviewers' issues.
4. The reviewer emits `recheck.json`:
   `{finding_key, outcome: resolved | not-resolved | withdrawn, comment}` per
   own open issue, plus new findings in a normal report.
5. The journal applies it: `resolved`/`withdrawn` → comment + close;
   `not-resolved` → comment + keep/re-open; adds `aj:round/2`. Issues closed by
   the *author* are re-opened if the reviewer says `not-resolved` — only the
   reviewer's re-check (or the editor) resolves a finding.
6. A reviewer slot that cannot be re-run (model retired) is recorded as
   `discontinued`; its open issues are flagged for the editor, not
   auto-closed.

### 12.5 Anonymity

Issues are filed by the journal's bot account, so the host never shows who
reviewed. Labels and bodies carry a per-submission pseudonym (`r1…rK`). The
mapping slot → identity/model lives in the journal's records, disclosed per
policy (D7):

- `blind`: pseudonym only (default for humans; ORCID stays private);
- `model-family`: pseudonym + model family label (default for agents — readers
  need it to judge correlated reviewers);
- `open`: full identity, opt-in per submission.

The editor summary is always complete; publication of the mapping after a
decision follows the same policy.

### 12.6 Venue and private repositories

- `author-repo` (default when the journal's App is installed on that repo):
  issues go to `repository.url`. The App install is the authors' explicit
  consent and works for private repos.
- `journal-repo` (fallback): a private journal-owned repo per lineage
  (`review-<lineage>`), authors invited as collaborators. Used when the author
  repo is not reachable, not on a supported host, or when the authors want
  review confidential until decision; it can be made public or transferred
  after the decision.
- `local`: no host; the same issue model lives in the journal's records and
  the portal. Always available; also used by tests.

Nothing from a private repository or a confidential review is ever written to
a public venue; the adapter checks repository visibility before filing and
refuses a mismatch with the venue policy.

### 12.7 Rate limits and failure

Filing is a journal-side queue, never done by reviewers: serialized per host,
honours `Retry-After` / `X-RateLimit-Reset` and the host's secondary limits on
content creation, with a per-round cap (default 50 issues per reviewer; the
overflow goes into one `[overflow] additional findings` issue). Any failure
leaves the queue resumable via `tracker.json`; a round's summary is not
produced until every finding is filed or explicitly recorded as `unfiled`
with the error.

### 12.8 Record

The hosted thread is the working surface; the authoritative record is the
journal's **mirror**: at each round close the journal snapshots every issue
(body, labels, comments, state, linked commits) with hashes into
`round-<n>/issues.json`. Later edits or deletions on the host are visible as
diffs against the mirror.

### 12.9 Adapter contract (hosting-neutral, no hard dependency)

```python
class IssueTracker(Protocol):
    host: str                                   # "github" | "gitlab" | "gitea" | "forgejo" | "local"
    def check_access(self, repo: RepoRef) -> AccessReport: ...   # reachable, visibility, can_write
    def ensure_labels(self, repo: RepoRef, labels: Sequence[Label]) -> None: ...
    def find_by_key(self, repo: RepoRef, key: str) -> IssueRef | None: ...
    def create(self, repo: RepoRef, issue: IssueDraft) -> IssueRef: ...
    def comment(self, ref: IssueRef, body: str) -> None: ...
    def set_state(self, ref: IssueRef, state: Literal["open", "closed"], reason: str) -> None: ...
    def add_labels(self, ref: IssueRef, labels: Sequence[Label]) -> None: ...
    def linked_changes(self, ref: IssueRef) -> list[ChangeRef]: ...      # PRs/commits referencing the issue
    def snapshot(self, ref: IssueRef) -> IssueSnapshot: ...
```

GitHub first, over its REST API with `requests` (already a dependency); no
host SDK is required. GitLab, Gitea and Forgejo adapters follow the same
contract (Gitea and Forgejo share an API). Adapters are selected by
`repository.host` and registered by name, like the existing reviewer-adapter
registry. A journal without any host adapter configured still works via
`local`.

## 13. Two stages: preprint, then journal

The venue has two stages over one research repository, each with its own
gate. Sections 3–12 describe the journal stage; the preprint stage reuses the
same bundle and records.

```
research project (git repo, own semver, e.g. v1.1.3)
   │  author tags a snapshot
   ▼
PREPRINT  snapshot v1.1.0 ── admission gate: "SciTeX format" ──▶ public preprint
   │      (Live Paper bundle: executable, UI over PDF, Clew graph; version DOI)
   │  author requests journal review of a preprint snapshot
   ▼
JOURNAL   review rounds as issues (§12), AI reviewers + other users
   │      ── acceptance gate: computational verification + editor decision ──▶
   ▼
PUBLICATION  v1.0.0 (own version line; article DOI)
```

### 13.1 Gates and checks

Preprint admission has three gates, all of which must pass. Each is checked by
the journal, not taken on the author's word:

| Gate | Passes when | Checked by |
|---|---|---|
| (i) Identity | The submitter's ORCID is linked and resolves | The existing Gate-1 ORCID check (`_gate1/_orcid`), against the ORCID the submitter logged in with |
| (ii) SciTeX standard form | The snapshot passes the SciTeX research lint (scitex-dev, `project-type: research`) | The journal re-runs the lint on the snapshot itself, in a sealed SAC run with a pinned scitex-dev version. An author-supplied report is not trusted. The lint output is pinned as a contract, like the live-paper schemas (D10) |
| (iii) Reproducibility by Clew graph | The evidence report validates (§3), and every main claim has a graph whose verification is `supported` | Mechanically, from the evidence report |

Admitted preprints then go through the automated checks, run by the journal
in sealed SAC runs. Each check produces a record:

1. **Format conformance**: the bundle and manuscript (§3), and Live Paper
   renderability.
2. **Clew verify**: the journal re-derives the evidence states on the
   snapshot and compares them with the submitted report. A mismatch is a
   finding.
3. **Code executability**: the project's entry points run in a clean
   container.
4. **Reproduction of main results**: the main claims' process nodes are
   re-executed, and the outputs are compared by hash or by declared
   tolerance. The result is `reproduced | differs | not-run (reason)`.

AI review (§6–§7, §12) then addresses **scientific validity, logical
structure and clarity**. Each finding carries a `dimension` field taking one
of those three values.

Journal acceptance requires both of the following:

- **Computational verification**: every registered claim in the accepted
  snapshot is `supported` with reproduction `reproduced`, or is listed as an
  editor-acknowledged exception with a reason (D11).
- **Review judgement**: the editor's decision is `accept` and no `critical`
  issue is open.

Admission is not acceptance: a preprint carries no claim of peer review, and
its page says so.

### 13.1a AI review is auxiliary at first

- **Humans confirm.** While the venue is in the `auxiliary` phase (a
  journal-level setting recorded in every decision), a decision needs at
  least one human reviewer, or a human editor confirming the AI findings
  issue by issue. Every AI finding is labelled `aj:source/ai`, and humans
  mark it `confirmed | disputed | irrelevant`.
- **Agreement is measured.** For each submission and each reviewer
  release, the journal computes:
  - per-claim verdict agreement between AI and human reviewers;
  - issues raised only by AI or only by humans (complementarity);
  - human confirmation rates by severity and dimension.

  Results are published in aggregate.
- **Reviewer releases are versioned.** Model, settings, prompt, SAC spec
  template and tool allowlist together form a reviewer release
  (`reviewer@1.2.0`), committed to this repo, with a changelog. Its run
  history (every outcome record and report) is indexed by release. A new
  release is evaluated against the previous one on held-out past
  submissions before use.
- **Ratings feed the next release.** Authors and researchers rate each AI
  finding (`useful | not useful` and `correct | incorrect`, with an optional
  reason) through the portal or CLI. Ratings are stored per finding key and
  are an input to the next release's evaluation. They never change a past
  decision.

### 13.1b Initial scope and policies

- **Public data only (v1).** The manifest declares each dataset with its
  source, licence and access URL. Admission refuses non-public or
  access-controlled data, and records the reason.
- **Policy documents** are deliverables of the venue, versioned under
  `docs/policies/`: submission rules, research ethics, data policy, and the
  reviewer-disclosure policy (D7). Every submission records the policy
  versions it was submitted under. These documents are not written yet.
- **Converting existing projects.** An agent may convert a project into
  SciTeX form (scitexification). The conversion is recorded as its own
  record: converting agent and model, source commit, resulting commit, and
  diff hash. Admission requires the author's explicit confirmation of that
  conversion, made while logged in with their ORCID. Without that
  confirmation, a converted project cannot pass gate (ii).

### 13.2 Versions, snapshots, DOIs

- **Project version** (`v1.1.3`): the authors' own; the journal only records
  it.
- **Preprint version** (`v1.1.0`): an immutable snapshot, meaning a tag plus a
  commit SHA, and the bundle hash (§3). Each revision during review is a new
  preprint snapshot (`v1.2.0`, …) linked by `supersedes`. Each snapshot gets a
  **version DOI** under one **concept DOI** for the preprint.
- **Publication version** (`v1.0.0`): the journal's own version line for the
  accepted article. Corrections are `v1.0.1`, … The record maps each
  publication version to the exact preprint snapshot it was accepted from.
- **Review record**: the round mirrors (§12.8), editor summaries and decision
  are published with the article. Optionally they get their own DOI, related
  to the article as a review of it.
- **Internal IDs first, DOI later.** On acceptance the existing
  `InternalIdMinter` assigns an internal persistent ID immediately. DOI
  registration (the company is the registrant) runs separately and may lag.
  When it completes, the DOI is recorded as an alias of the internal ID.
  Publication never waits on the DOI process.
- **Verified certificate.** Each accepted publication version gets
  `certificate.json`, plus a rendered page. It lists:
  - the snapshot commit and bundle hash;
  - the evidence-report hash;
  - each gate and automated-check result;
  - the reproduction results;
  - the reviewer provenance (§14);
  - the decision.

  It is signed by the journal's published key (detached signature; the key
  type is an open choice, D14), so anyone can verify it offline. It is
  published with the Live Paper.
- **DOI minting is an adapter.** It reuses the existing `IdMinter` protocol in
  `_publish` (Zenodo, JaLC and Crossref backends, plus a sandbox).
  - Backends are selected by configuration, and `none` is valid, so DOIs are
    not a hard dependency.
  - Minting happens only after the gate passes.
  - Metadata carries the relations: version of the concept DOI, preprint →
    publication, and review → article.
  - Credentials are held by the journal service only, as in §12.1.

## 14. Transparency as the answer to "predatory journal"

A predatory venue is opaque: unknown reviewers, no record, acceptance
uncorrelated with scrutiny. This venue makes every step inspectable:

1. **Public review threads.** Once the reviewed snapshot is a public
   preprint, its issues are public (§12.6). Confidential review is an explicit
   author choice and is recorded. The full thread is mirrored into the
   published record, including rejected and unresolved findings.
2. **Disclosed reviewer provenance.** Every article lists, per reviewer slot:
   - the kind (agent or human);
   - the model family under the D7 policy;
   - the SAC version, spec, prompt and outcome hashes;
   - which rounds the slot took part in.
   It also states `distinct_models` and any correlated pairs. The editor's
   identity and decision reason are published.
3. **Stated independence guarantees** (§6). Reviewers are sealed, blind to
   the authors' agents and to each other, and are not among the producers.
   Failures are recorded, never silently replaced.
4. **Two separate verdicts, never merged.** Each article page shows them
   side by side:
   - **Computational verification (Clew / evidence report).** For each
     registered claim, it checks whether the stated value follows from the
     recorded inputs and code by hash-checked provenance. It does not judge
     whether the method fits the question, whether the result generalises,
     or whether it matters.
   - **Scientific validity (review judgement).** Reviewers (AI or human)
     and the editor judge method, interpretation, scope and significance.
     These are opinions with reasons, attached to claims and graph nodes.

   A green verification is not an endorsement. A positive review does not
   repair a claim whose evidence is not supported. Text that is not a
   registered claim gets neither verdict.
5. **Decisions cite evidence.** Every decision references editor-summary
   items and issue links. Reviewer and editor records are append-only, with
   hashes.

The article, preprint and review pages render these records directly. There
is no separate "trust badge" that could drift from them.

## 15. Corpus export: one record per accepted claim

Every accepted claim also becomes a corpus record: a self-contained unit
that downstream users (search, meta-research, training data under licence)
can consume without the journal.

Schema `scitex-agentic-journal.claim-record` 1.0 (journal-owned, published in
the wheel under `_contracts/schemas/`), exported as JSON Lines per publication
version, and accumulated into a corpus index:

```json
{
  "schema": "scitex-agentic-journal.claim-record",
  "schema_version": "1.0",
  "record_id": "<publication id>#C3",
  "claim": {"claim_id": "C3", "type": "…", "stated_text": "…", "stated_value": "…",
            "location": {"file": "…", "line": 0, "label": "…"}},
  "source_data": [{"name": "…", "url": "…", "sha256": "…", "licence": "CC-BY-4.0"}],
  "code": {"repository": "…", "commit": "<sha>", "paths": ["…"], "licence": "…"},
  "execution_history": {"graph": {"nodes": [], "edges": []},
                        "journal_runs": [{"check": "reproduction", "sac_outcome_sha256": "…"}]},
  "verification": {"provider": {"name": "scitex-clew", "version": "…"},
                   "state": "supported", "evidence_report_sha256": "…"},
  "reproduction": {"result": "reproduced | differs | not-run", "tolerance": null, "detail": "…"},
  "review": {"verdicts": [{"reviewer_slot": "r1", "kind": "agent", "verdict": "supported"}],
             "issues": ["<issue urls>"]},
  "provenance": {
    "source": "<publication DOI or internal id>",
    "generation_route": "human-authored | agent-authored | agent-converted+author-confirmed",
    "producers": [{"kind": "agent", "id": "…", "model": "…"}],
    "policy_versions": {"submission": "…", "data": "…", "ethics": "…"}
  },
  "publication_conditions": {"licence": "…", "embargo_until": null,
                             "publication_version": "v1.0.0", "doi": null, "internal_id": "…"},
  "certificate_sha256": "…"
}
```

Rules:

- **Only accepted claims are exported.** Claims listed as acknowledged
  exceptions (D11) are exported with their real state and the editor's
  reason, never upgraded to `supported`.
- **Values are copied, not re-derived.** Every value comes from a record the
  journal already holds (evidence report, check records, review mirror,
  certificate), and each copy carries that record's hash.
- **Licences are respected.** The record's licence is the most restrictive
  of the claim's data and code licences. The exporter refuses a record whose
  licences are missing or incompatible (D15).
- **Export is a CLI, idempotent per publication version:**
  `scitex-agentic-journal corpus export <publication-id> --out claims.jsonl`.
- **Corrections publish a new version.** A correction (`v1.0.1`) produces new
  records that supersede the old ones. Old records stay available and are
  marked superseded.
