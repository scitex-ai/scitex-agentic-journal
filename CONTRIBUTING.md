# Contributing to `scitex-agentic-journal`

Thank you for your interest. This document is the short form. The
long form lives in the [SciTeX ecosystem guidelines](https://scitex.ai).

## Quick rules

1. **One task = one PR off `develop`.** Open the PR against `develop`,
   not `main`. CI must be green before merge.
2. **No mocks.** Production paths use real collaborators (real HTTP,
   real `git`, real subprocess). Hermetic CI is achieved with real
   local fixtures (stdlib `http.server`, real on-disk repos), never
   with `respx` / `responses` / `unittest.mock` replay libraries.
   See `STX-NM001-003` / `PA-306` in the SciTeX no-mocks discipline.
3. **No silent fallbacks.** Every failure path raises a structured
   `GateFailure` (or similar) with `reason` + `detail`.
4. **Sign the [CLA](CLA.md).** A bot will check on PR open.
5. **No `Co-Authored-By` trailer** from automated agents.
6. **No `--no-verify`, no force-push** to protected branches.

## Local development

```bash
git clone https://github.com/ywatanabe1989/scitex-agentic-journal.git
cd scitex-agentic-journal
pip install -e ".[dev]"
pytest tests/
```

To exercise the opt-in real-network tests:

```bash
SCITEX_RUN_NETWORK_TESTS=1 pytest tests/ -m network
```

## Submitting a change

1. Branch off `develop`: `git checkout -b feat/your-thing develop`.
2. Implement + add tests.
3. Update `CHANGELOG.md` under `## [Unreleased]`.
4. Push, open a PR against `develop`, wait for CI.
5. Self-merge (squash) once CI is green and the CLA bot is happy.

## What gets reviewed

- Architecture fit (consumes Clew, emits Live Paper; we do not invent
  new claim models here).
- No mocks in production paths.
- Real errors with guidance, not silent fallbacks.
- Tests describe behaviour, not implementation.

Questions: open an issue, or reach the maintainers via
`contact@scitex.ai`.
