# Design 01 — Contract-based submission and independent review panel

Status: **proposal, awaiting an operator decision on §2** (2026-11-19).
Scope: the smallest implementable design for
submission → review assignment → review → decision, in which reviewers
are independent of the authors' agents and every verdict points at a
registered claim. Findings are tracked as issues on the authors' git host
(§12).

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
6. `_tracker`: the issue-tracker contract (§12) with the `local` tracker
   (journal-owned records, no network) and the GitHub adapter; GitHub tests
   run against a throwaway repo behind `SCITEX_RUN_NETWORK_TESTS=1`.
7. Tests: real bundle fixtures produced by live-paper; real `sac` runs behind
   the opt-in marker `SCITEX_RUN_SAC_TESTS=1`.
8. Release 0.2.0.

## 11. Open decisions

| id | Question | Recommendation |
|---|---|---|
| D1 | Option A (add beside legacy) or B (replace core)? (§2) | A |
| D2 | live-paper publishes `review-packet.schema.json` (packet is defined only in `_packet.py` today) | Ask live-paper to ship it in the wheel next to the evidence-report schema; the journal vendors it when released |
| D3 | SAC has no read-only input mount and no served-model pin (`readonly_packet`, `model_pin` unmet in 0.40.1) | Accept for the first slice with the manifest check and `served_version: null`; request both from SAC |
| D4 | Default panel: K and model mix | K = 3 with at least two distinct model families when keys exist; the summary always states `distinct_models` |
| D5 | Who decides: human editor only, or agent editor allowed | Both allowed, recorded; rule-based v2 only as a suggestion |
| D6 | Reviewer egress beyond the model endpoint (literature search for novelty) | Off in v1; novelty is out of scope of claim-level review |
| D7 | Reviewer disclosure on public issues (§12.5) | `model-family` for agents, `blind` for humans; `open` per submission opt-in |
| D8 | Default issue venue (§12.6) | Author repo when the journal's app is installed there; otherwise a private journal-owned review repo |
| D9 | GitHub credential type | GitHub App (per-repo install, scoped `issues:write` + `metadata:read`) over a personal token |

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
