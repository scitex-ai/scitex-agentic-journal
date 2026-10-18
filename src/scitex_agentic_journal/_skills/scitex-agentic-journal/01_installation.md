---
description: |
  [TOPIC] Installation
  [DETAILS] `pip install scitex-agentic-journal` (+ optional [mcp] / [dev] extras) and a smoke verify via `scitex-agentic-journal --version`.
tags: [scitex-agentic-journal-installation]
---

# Installation

## Basic install

```bash
pip install scitex-agentic-journal
```

Installs the CLI (`scitex-agentic-journal`) and the public Python
surface under `scitex_agentic_journal`. Network and filesystem
dependencies (`requests`, `pyyaml`, `click`, `django>=4.2`) are
pulled transitively — no manual chase.

## Recommended (faster) install via `uv`

```bash
uv pip install scitex-agentic-journal[all]
```

`uv`'s Rust resolver typically settles the SciTeX dep set in
1–3 min where vanilla `pip` can take 30+ min on the full extras.
The plain `pip install` still works and is what CI exercises.

## Optional extras

```bash
pip install 'scitex-agentic-journal[mcp]'   # + fastmcp for the MCP server
pip install 'scitex-agentic-journal[dev]'   # + pytest, pytest-cov, fastmcp
pip install 'scitex-agentic-journal[all]'   # everything above
```

| Extra   | Provides                                            |
|---------|-----------------------------------------------------|
| `mcp`   | `fastmcp>=2.0` — MCP server entry point (post-MVP)  |
| `dev`   | `pytest`, `pytest-cov`, `pytest-django`, `fastmcp`  |
| `all`   | `dev` + `mcp` (alias used by ecosystem CI template) |

## From source (contributors)

```bash
git clone https://github.com/ywatanabe1989/scitex-agentic-journal.git
cd scitex-agentic-journal
pip install -e .[dev]
pytest tests/
```

## Smoke verify

```bash
scitex-agentic-journal --version
scitex-agentic-journal --help
```

The `--version` output prints the installed version; the `--help`
output names the four pipeline subcommands (`submit`, `review`,
`decide`, `publish`) plus the `skills` sub-group introduced for
SciTeX-fleet audit compliance.

## Configuration

Optional environment variables (also documented in `.env.example`):

| Variable | Purpose |
|---|---|
| `SCITEX_AGENTIC_JOURNAL_CONFIG` | Path to an alternate YAML config; defaults to `./config.yaml` → `~/.scitex/agentic-journal/config.yaml`. |
| `SCITEX_AGENTIC_JOURNAL_SKILLS_DEST` | Default destination for `scitex-agentic-journal skills install` (overrides `~/.claude/skills/scitex-agentic-journal/`). |
