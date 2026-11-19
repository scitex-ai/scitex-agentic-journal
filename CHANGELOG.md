# Changelog

All notable changes to `scitex-agentic-journal` are documented in this file.

## [Unreleased]

### Added

- Isolated executor for the `executability` and `reproduction` admission
  checks (design §11 D17): `admission evaluate --executor apptainer
  --sandbox-image SIF --clew-requirement 'scitex-clew==X'` runs scitex-clew's
  store-free `clew bundle rerun` in a sealed apptainer container
  (`--containall --cleanenv --no-home --no-eval`, offline phases also
  `--no-mount bind-paths,hostfs,cwd --net --network none`). Declared
  dependencies (`requirements*.txt`, `[project].dependencies`; options, URLs
  and paths refused) are fetched as wheels only from the package index
  BEFORE any author file is in the run, then installed offline. Each run is
  fresh and leaves only `out/outcome.json` (image sha256, apptainer version,
  flags, env names, per-phase argv/egress/timing/exit/output hashes); the
  check records cite it by hash. The default stays `--executor none`; both
  checks remain non-blocking for admission (§13.1). SAC 0.40.x cannot be
  used for this yet: its sealed runs require a TUI agent harness and a model
  key.

### Security

- Outbound-network policy for fetches a submission can steer (D18): the
  repository host is resolved once, and any loopback, private, link-local,
  multicast, reserved or unspecified answer (including IPv4-mapped IPv6) is
  refused. git is then pinned to the vetted address with
  `http.curloptResolve` and redirects are disabled, so DNS rebinding and
  redirects cannot reach internal hosts.

### Changed

- Design doc records the operator decisions D7-D10, D13 and D16-D18, and lists
  D11, D12, D14 and D15 as open for the user.

## [0.2.0] - 2026-11-19

Contract-based path for the stages before review (design:
`docs/design/01_contract-submission-and-independent-review.md`). It sits
alongside the legacy intake, which keeps working.

### Added

- `bundle seal|validate|submit`: `seal` writes every file's hash into
  the manifest (for `make submit`-style tooling). A submission bundle (`submission.json` manifest,
  manuscript, scitex-live-paper evidence report and review packet,
  bibliography) is validated against **vendored, version-pinned**
  scitex-live-paper schemas (evidence-report and review-packet 1.2.0, pinned
  at commit 963de44). Every file is hashed, unlisted files and symlinks are
  refused, and the packet must agree with the report claim by claim. v1
  accepts public data only, and an agent conversion of a project must be
  confirmed by the author. The submission id is derived from the manifest
  hash, so resubmitting identical bytes is idempotent.
- `admission evaluate|show`: admission checks with explicit records:
  - ORCID resolves and belongs to an author;
  - the declared repository commit checks out without credentials (only
    `https://` URLs; local paths need the operator flag
    `--allow-local-repositories`, and a URL is never parsed as a git option);
  - scitex-dev's research lint passes with zero errors and every rule run;
  - every declared main claim is `supported` with an evidence graph.

  Clew re-verification, executability and reproduction are recorded as
  `not-run`, with the reason. Author code is never run on the journal host,
  and child processes get an explicit minimal environment.
- `preprint create|show`: an admitted submission becomes a preprint record:
  - an internal persistent ID, with the DOI `unregistered` until a minter
    runs;
  - hashes of the manifest, evidence report, review packet and admission
    record;
  - an explicit "not peer reviewed" notice.
- `reviews ingest|list`: review ingestion from any source (external AI review
  services, human researchers, other users). The report and source are
  validated against the journal's published schemas. The journal adds each
  claim's evidence state and records unmentioned claims as `not-assessed`.
  It refuses unknown claims and graph nodes, and refuses authors or
  producers as reviewers. The channel the identity arrived by is recorded (CLI channels are recorded as unverified; verified ORCID-login/service-key channels need an authenticated surface). Authors are refused by ORCID, by name and as listed producers. Reviewers get
  per-submission pseudonyms. Findings are added to a local ledger keyed by
  reviewer, anchor and dimension; re-filing never duplicates, and each round
  recomputes a finding's severity and open/noted status.
- Journal-owned JSON Schemas (`submission`, `review-report`,
  `review-source`) are published in the wheel under `_contracts/schemas/`.

### Fixed

- A placeholder review can no longer produce an editorial decision. Review
  records carry `adapter_mode`, and `decide` refuses anything that is not
  `live`, including the `local-deterministic` adapter and legacy records
  without a mode. Previously a Gate-1-passing bundle reached
  `default_accept` without any real review.

## [0.1.0a4] - 2026-11-01

### Added

- Original author portal with preparation, intake, personal archive, review/revision and publication guidance using SDK-owned chrome.
- Authenticated request-local archive resolution through the generic host user-home provider; mounted failures do not fall back to a shared service home.
- Real per-user review/decision reads and safe single-component record identifiers.
- Register installed documentation/skills with the shared Dev dispatcher so discovery does not depend on a central package registry entry.
- Document demo receipts, mounted archive scope and the source-certifiable SDK AppConfig boundary; repair missing README branding links with verified canonical assets.

### Fixed

- Require SDK >=0.3.17 and explicitly declare the Journal header's request-local
  user scope, preserving the host's remembered project while showing All projects.

- Preserve uploaded inputs in independently checked durable snapshots before intake staging is removed; immutable retries retain subsequent reviews and decisions.
- Stop returning fabricated passing validator checks, protect unexpected example content and record aliases, and remove the retired scitex-ui runtime dependency.
- Use the full SciTeX Agentic Journal in-app label and square content cards/notices; keep the short launcher and browser labels.
- Replace obsolete CLI-stub descriptions with implemented workflow contracts and executable help examples.

## 0.1.0a3 — 2026-11-01

- Declare literal Journal AppConfig identity and explicit required SDK inheritance so Hub can certify the plugin before Django startup.
- Keep manifest and SDK startup errors visible instead of silently falling back to a plain Django app.
- Load the shared SDK header stylesheet so the canonical row renders consistently on mounted pages.

## [0.1.0a2] - 2026-11-01

### Fixed
- Require `scitex-sdk>=0.3.16`: the project-scope app header needs the
  tolerant `scitex_project_picker` (renders the leaf local-folder
  fallback with no host provider); 0.3.14/0.3.15 raise
  `ImproperlyConfigured` and red the pytest matrix (PR #58).
- `gui` is now the canonical group `gui {open,serve,status,stop}`
  (doctrine 19_gui-commands.md §12; scholar-modeled Django + SDK-embed
  wiring) instead of a bare leaf: `serve` stays foreground headless
  with `--force` orphan-reclaim, `open` auto-serves detached then opens
  the browser. Migration: `... gui --port N` → `... gui serve --port N`.

## [0.1.0a1] - 2026-10-19

### Fixed
- Release pipeline: promote write scope (#51), explicit tag to promote
  (org #99 pin, #53), publish via `pypi` environment — trusted-publisher
  parity with storage (#55).

## [0.1.0-alpha] - 2026-10-18

### Added
- Demo `docs/demo/monday-mock.html` (#44): single-file zero-dependency
  visual mock of the submit → Clew gate → AI review + DOI → Live Paper
  publish loop (ticket review, repo-per-paper, Clew hover graph).
  Visual only — no package code touched.
- Canonical CI caller + tag-driven release caller workflows (#43).
- `scitex-agentic-journal gui` standalone launcher (SDK-canonical
  `serve_gui` + `run_standalone` over `scitex_agentic_journal._django`,
  same shape `scitex-sdk app init` scaffolds): binds exactly `--port`
  or fails loud, `--force` reclaims only this app's own GUI.
  Tests: `tests/scitex_agentic_journal/_cli/test__gui.py` (6 tests).
- Leaf `_django` demo surface (aj-leaf-django): `_django/_leaf.py`
  (Django-free helpers: real-FS archive list, deterministic mock
  validator panel, browse/share payloads, HTML payload via the
  live-paper ports contract — no core fork) + `dashboard/` route
  (`decision_dashboard()` verdict→badge-status rows + counts for
  the Monday demo). Placeholder/503 contracts kept. Tests:
  `tests/scitex_agentic_journal/_django/test__leaf.py` (10 tests).
- M5 publish hand-off (#9 → PR #27): `_publish.publish_submission`,
  `_publish.LocalFilesystemLivePaperPort` (default in-process port that
  writes the Live Paper bundle envelope to
  `<home>/published/<submission_id>/bundle.json`),
  `_publish.RemoteLivePaperPortStub` (NotImplementedError stub for the
  future HTTP/MCP port), `_publish.load_submission_records` +
  `PublishLoadError` (refuses to publish unless gate1/review/decision/
  persistent_id are all on disk and the decision verdict is `accept`).
  CLI: `scitex-agentic-journal publish <submission-id>` with the
  audit-§6 mutating-verb flags `--dry-run` / `--yes`. Prints
  `PUBLISHED submission_id=... viewer_url=... persistent_id=...` on
  success.
- M4 persistent-ID minting (#8 → PR #26): `_publish.mint_for_submission`
  + `MintLoadError` (orchestrates a mint over a persisted Gate-1
  record), `_publish.persist_persistent_id` + `PersistedPersistentId`
  (drops `persistent_id.json` next to `gate1.json` / `review.json` /
  `decision.json`). `_publish._zenodo.ZenodoSandboxStub` now mints
  against the real `sandbox.zenodo.org` REST API over real HTTP — token
  from `SCITEX_AJ_ZENODO_SANDBOX_TOKEN`. `ZenodoStub` (production)
  shares the same HTTP code path against `zenodo.org` when
  `SCITEX_AJ_ZENODO_TOKEN` is set; both raise loud `RuntimeError` on
  missing token or non-2xx response (no silent fallback). The opt-in
  network test exercises the sandbox round-trip when
  `SCITEX_RUN_NETWORK_TESTS=1` + `SCITEX_AJ_ZENODO_SANDBOX_TOKEN` are
  both present.
- M3 editorial decision engine (#7 → PR #28): `_decide.DecisionEngine`
  produces `accept | revise | reject` over the immutable
  `ReviewRecord` from M2. Rules-set is versioned + auditable
  (`_decide/rules/v1.yaml`, bundled via
  `[tool.setuptools.package-data]`) — no silent thresholds in code.
  Every rule emits a `RuleHit` (both pass and fail) so the persisted
  `decision.json` proves which rules passed alongside which failed.
  Verdict precedence: first failing reject rule wins reject; otherwise
  first failing revise rule wins revise; otherwise accept.
  `_decide.persist_decision` + `PersistedDecision` drop
  `decision.json` next to `gate1.json` / `review.json`. CLI:
  `scitex-agentic-journal decide <submission-id>` prints
  `DECISION submission_id=... verdict=... rules_version=... content_hash=...`.
- M2 reviewer-agent harness (#6 → PR #25): `_review.ReviewRunner` runs
  all four ARA sub-reports (reproducibility, claim verify, novelty,
  methodology) against one submission in rubric order via a pluggable
  `ReviewerAdapter` protocol. Ships `LocalDeterministicAdapter` (the
  in-memory dev/test adapter) and `QwenAdapterStub` (NotImplementedError
  placeholder until the live endpoint is wired). `_review.persist_review`
  + `PersistedReview` write `review.json` (sha256 content_hash +
  `written_at_utc`) next to `gate1.json`. CLI:
  `scitex-agentic-journal review <submission-id> [--adapter local]
  [--prompts-version v1]` prints `REVIEW DONE submission_id=...
  adapter=... content_hash=...`.
- M1 CLI orchestrator (#5 → PR #24): `_submit.run_gate1` runs the three
  Gate-1 checks (ORCID → code-repo → Clew DAG) in declared order and
  short-circuits on the first failure with a structured `Gate1Failure`
  wrapping the underlying `GateFailure`. `_submit.persist_verdict` +
  `PersistedSubmission` mint a sortable, opaque submission id
  (`sub_YYYY_MM_DD_<6-hex>`) and drop `gate1.json` under
  `$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/`. CLI:
  `scitex-agentic-journal submit <bundle-dir>` prints
  `GATE-1 PASS submission_id=...` on success and one structured
  `GATE-1 FAIL [<check>]: <reason> -- <detail>` line on failure.
- M1.3 Clew-DAG verification (#4 → PR #21): `_gate1.verify_clew_dag`
  shells out to the real `clew claim verify` binary against the
  bundled DAG and returns a `ClewVerification` recording the green /
  red claim ids and total claim count. Loud `GateFailure` when no
  green claim is present, when `clew` is missing from PATH, or when
  the DAG directory is malformed. Opt-in real test gated on
  `SCITEX_RUN_CLEW_TESTS=1` + `clew` on PATH.

- `_gate1.clone_code_repo(repo_url, destination, *, depth=1, ref=None,
  timeout_s=60.0)` — second slice of the M1 submission gate. Shells out
  to the real system `git` binary to shallow-clone the author's code
  repository. Loud structured `GateFailure` on empty URL, missing `git`
  binary, pre-existing destination, clone failure (exit code + stderr
  excerpt), or timeout. On any failure the partially-populated
  destination is removed.

### Fixed
- Leaf `_django/manifest.json`: added the `dependencies` object
  (`python` / `system` / `node` / `r` / `other`, all empty) required
  by scitex-sdk 0.3.6 (`scitex-sdk app validate` now passes; was
  `manifest.json missing 'dependencies' field`). No behaviour change —
  the leaf carries no extra system/node/r deps.
- `_gate1.cloned_code_repo(repo_url, ...)` — context-manager helper that
  clones into a tempdir and cleans up on exit, so the CLI orchestrator
  (issue #5) does not have to manage tempdirs itself.
- `_gate1.ClonedRepo` dataclass exposing `repo_url`, `path`,
  `head_commit`, `head_subject` so downstream gates can identify what
  was reviewed without re-cloning.
- `tests/test_gate1_code_repo.py` — hermetic test suite that builds a
  real local bare git repo with one real commit and clones via a
  `file://` URL. Real `git` binary, real subprocess, real disk; no
  `subprocess` patching, no respx/responses replay (STX-NM001-003 /
  PA-306 compliant). One opt-in `@pytest.mark.network` test clones
  `github.com/octocat/Hello-World` when `SCITEX_RUN_NETWORK_TESTS=1`.
- `scitex_agentic_journal._gate1` package — first slice of the M1 submission
  gate. Public surface: `GateFailure` (structured failure exception),
  `verify_orcid(orcid_id, *, session=None, base_url=...)`, `OrcidRecord`,
  and `ORCID_PUB_API_BASE` constant.
- `verify_orcid` resolves an ORCID iD against the public ORCID v3.0 API
  via real HTTP (`requests`). Accepts bare iDs and any `orcid.org` /
  `sandbox.orcid.org` URL form. Verifies the ISO 7064 MOD 11-2 check
  digit before any network call. Loud, structured `GateFailure` on
  malformed iD / bad checksum / 404 / non-2xx / non-JSON body /
  unfamiliar record shape / network unreachable. No silent fallbacks,
  no mocks.
- `tests/test_gate1_orcid.py` — hermetic test suite that spins up a real
  local stdlib `http.server` on an ephemeral port and exercises
  `verify_orcid` over real TCP via the `base_url` config seam (no
  monkey-patching, no respx/responses replay library — STX-NM001-003 /
  PA-306 compliant). One opt-in `@pytest.mark.network` test hits the
  real `pub.orcid.org` when `SCITEX_RUN_NETWORK_TESTS=1`.
- `pyproject.toml`: register the `network` pytest marker.
- README "What it is" section spelling out the AI-agent-driven peer-review /
  copy-edit / publication-readiness role, and an explicit "MVP loop"
  (submit → agent review → decision → publish) section that maps to the
  initial GitHub issues.
- README "Full pipeline (design target)" section with a 4-gate flow
  (structural gate → AI review → editorial decision → persistent ID) so the
  MVP loop and the long-term target are no longer collapsed.
- Roadmap expanded from 5 to 7 milestones (M1–M7) with an explicit editorial
  decision engine (M3), persistent ID stage (M4), Live Paper hand-off (M5),
  reviewer dashboard (M6) and MCP server (M7).
- `scitex-scholar` added to the dependency direction diagram as the source of
  novelty / literature triangulation.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) running `pytest` on
  Python 3.10 / 3.11 / 3.12 for `push` and `pull_request` against `main` and
  `develop`.
- `pyproject.toml`: `license-files`, extra keywords (`agentic-review`,
  `peer-review`, `reproducibility`), extra classifiers
  (`Framework :: Django`, information analysis, LaTeX), and a `Changelog`
  project URL.

### Fixed
- M1.3 Clew-DAG check vs `scitex-clew` 0.21.0: verify via
  `clew dag --claims --json` (the every-claim JSON entry point),
  accept the current `.scitex/clew/` project marker (legacy `.clew/`
  still accepted), and fail loud with an actionable
  store-not-provisioned error when clew's PostgreSQL store is missing
  instead of reporting unparseable output. Opt-in tests no longer call
  the removed `clew init`; full-pass fixtures run a real
  `clew.session()` step so a tracked run produces the claimed source,
  and are gated on the new `SCITEX_RUN_CLEW_STORE_TESTS=1`
  (provisioned store required). The unprovisioned-premise store test
  runs only where the store is not provisioned (lead decision (a)) —
  where `STORE_TESTS` is set its premise cannot occur, so it skips.
  Full-pass fixtures pin the run (`session_id` into `clew.session`),
  link it explicitly (`--source-session` + stable `--claim-id`), and
  validate the seed with per-claim `verify` before the gate runs.
- CLI audit dict review-verb + AAA test style (#42).

## [0.1.0-alpha] — 2026-06-12

### Added
- Initial scaffold with purpose + 5-milestone roadmap.
- README pipeline diagram (submit -> ORCID+code+DAG gate -> AI review -> persistent ID -> Live Paper).
- Dependency direction documented: consumer of `scitex-clew` (claim model owner), emits to `scitex-live-paper`.
- `pyproject.toml` with `scitex-dev`, `scitex-ui`, `django`, `click`, `requests`, `pyyaml` runtime deps.
- Package skeleton at `src/scitex_agentic_journal/` with version export.
- Smoke test.
