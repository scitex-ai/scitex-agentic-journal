# Design 01 — Contract-based submission and independent review panel

Status: **proposal, awaiting an operator decision on §2** (2026-11-19).
Scope: the smallest implementable design for
submission → review assignment → review → decision, in which reviewers
are independent of the authors' agents and every verdict points at a
registered claim.

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

## 2. Direction conflict (decision needed)

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

Every transition writes one immutable JSON record into
`$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/` (existing layout; no
database). A revision is a new submission linked by `supersedes`.

CLI (Phase 2):

```
scitex-agentic-journal bundle validate <dir>
scitex-agentic-journal bundle submit   <dir>                 # → submission id
scitex-agentic-journal panel assign    <id> --reviewers reviewers.yaml
scitex-agentic-journal panel run       <id>                  # launches SAC reviewers
scitex-agentic-journal panel collect   <id>                  # validates reports + outcomes
scitex-agentic-journal panel summary   <id>                  # editor summary (json + txt)
scitex-agentic-journal panel decide    <id> --editor <who> --decision <d> --reason …
scitex-agentic-journal review template <id>                  # human reviewer form
scitex-agentic-journal review file     <id> report.json      # human reviewer submit
```

## 6. Reviewer independence

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
      "comment": "…"
    }
  ],
  "general_findings": [
    {"location": "manuscript §2.1", "severity": "minor", "comment": "…"}
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

## 8. Editor summary and decision

`editor-summary.json` (+ a plain-text rendering) per submission:

- per claim: the packet's evidence `state` next to the K verdicts,
  agreement, and the union of graph nodes reviewers cited; claims whose
  verdicts split, or where a reviewer contradicts the evidence state, are
  listed first;
- recommendation tally; failed/excluded runs with reasons;
- independence block: reviewer ids, kinds, `distinct_models`, correlated
  pairs;
- hashes of every input and report.

The summary recommends, it does not decide. `panel decide` records the editor
(human ORCID or agent id + model), the decision and a reason referencing
summary items. Automatic decision rules can be added later as a
`rules/v2.yaml` *suggestion* over the summary.

## 9. Humans and agents

| Actor | Agent path | Human path |
|---|---|---|
| Author | `make submit` / `bundle submit` from the project (scitex-template target) | Django author portal upload of the same bundle |
| Reviewer | SAC sealed container, reads files or live-paper MCP tools, writes `review-report.json` | `review template` → fills the same schema (or the portal form) → `review file`; reads `review.txt` / live-paper viewer |
| Editor | Agent reads `editor-summary.json`, calls `panel decide` | Reads `editor-summary.txt` / portal, calls `panel decide` |

Same schemas for both; only `reviewer.kind` and identity fields differ.

## 10. Phase-2 slice (Option A)

1. `_contracts`: vendored live-paper schemas + journal schemas + hash test.
2. `_bundle`: validate + submit (idempotent id), records.
3. `_panel`: reviewer spec template (SAC `scitex-agent-container/v3`,
   sealed `sandbox` block, prompt asks for `review-report.json` then `DONE`),
   assign, run via the `sac agents start|stop|delete` CLI (subprocess with an
   explicit allowlisted env, never `os.environ`), wait on `outcome.json`
   `status: finalized` with a deadline, collect outcome + egress logs. Reuses
   the staging/lock lessons from paper-scitex-clew's `scripts/_sac_runner`
   (spec-repo lock, input manifest check) rather than importing it.
4. `_report` + `_editor`: report validation against the packet, summary.
5. `decide` refuses stub-adapter records (defect 1).
6. Tests: real bundle fixtures produced by live-paper; real `sac` runs behind
   the opt-in marker `SCITEX_RUN_SAC_TESTS=1`.
7. Release 0.2.0.

## 11. Open decisions

| id | Question | Recommendation |
|---|---|---|
| D1 | Option A (add beside legacy) or B (replace core)? (§2) | A |
| D2 | live-paper publishes `review-packet.schema.json` (packet is defined only in `_packet.py` today) | Ask live-paper to ship it in the wheel next to the evidence-report schema; the journal vendors it when released |
| D3 | SAC has no read-only input mount and no served-model pin (`readonly_packet`, `model_pin` unmet in 0.40.1) | Accept for the first slice with the manifest check and `served_version: null`; request both from SAC |
| D4 | Default panel: K and model mix | K = 3 with at least two distinct model families when keys exist; the summary always states `distinct_models` |
| D5 | Who decides: human editor only, or agent editor allowed | Both allowed, recorded; rule-based v2 only as a suggestion |
| D6 | Reviewer egress beyond the model endpoint (literature search for novelty) | Off in v1; novelty is out of scope of claim-level review |
