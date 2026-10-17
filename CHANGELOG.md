# Changelog

All notable changes to `scitex-agentic-journal` are documented in this file.

## [Unreleased]

### Added
- Demo `docs/demo/monday-mock.html` (#44): single-file zero-dependency
  visual mock of the submit → Clew gate → AI review + DOI → Live Paper
  publish loop (ticket review, repo-per-paper, Clew hover graph).
  Visual only — no package code touched.
- Canonical CI caller + tag-driven release caller workflows (#43).
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
  (provisioned store required).
- CLI audit dict review-verb + AAA test style (#42).

## [0.1.0-alpha] — 2026-06-12

### Added
- Initial scaffold with purpose + 5-milestone roadmap.
- README pipeline diagram (submit -> ORCID+code+DAG gate -> AI review -> persistent ID -> Live Paper).
- Dependency direction documented: consumer of `scitex-clew` (claim model owner), emits to `scitex-live-paper`.
- `pyproject.toml` with `scitex-dev`, `scitex-ui`, `django`, `click`, `requests`, `pyyaml` runtime deps.
- Package skeleton at `src/scitex_agentic_journal/` with version export.
- Smoke test.
