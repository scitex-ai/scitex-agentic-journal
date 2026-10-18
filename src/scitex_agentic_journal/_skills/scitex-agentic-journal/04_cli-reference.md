---
description: |
  [TOPIC] CLI reference
  [DETAILS] Every top-level subcommand the `scitex-agentic-journal` console script exposes — submit / review / decide / publish + skills + mcp + info + shell-completion.
tags: [scitex-agentic-journal-cli-reference]
---

# CLI Reference

Authoritative list of commands shipped by the `scitex-agentic-journal`
entry point declared in `[project.scripts]`. Run `--help-recursive`
to print the full subcommand tree in one call.

## Global

```bash
scitex-agentic-journal --version          # vX.Y.Z token (PS-203)
scitex-agentic-journal --help             # top-level help epilog
scitex-agentic-journal --help-recursive   # every subcommand's help
scitex-agentic-journal --json <subcmd>    # machine-readable output
```

Configuration is read from `$SCITEX_AGENTIC_JOURNAL_CONFIG`, then
`./config.yaml`, then `~/.scitex/agentic-journal/config.yaml` — see
[20_env-vars.md](#) (post-MVP) for the full env-var inventory.

## Pipeline subcommands (stubs until M1+)

```bash
scitex-agentic-journal submit  ./paper/    # Gate-1 orchestrator (#5)
scitex-agentic-journal review  <bundle>    # Reviewer agent (#6, M2)
scitex-agentic-journal decide  <record>    # Decision engine (#7, M3)
scitex-agentic-journal publish <bundle> --dry-run / --yes
```

Today each subcommand raises a structured `click.ClickException`
naming its tracking issue rather than no-op'ing. The error message
tells the operator exactly which milestone unblocks the command.

## `skills` group (§1a)

```bash
scitex-agentic-journal skills list                    # list bundled .md leaves
scitex-agentic-journal skills list --json             # JSON envelope
scitex-agentic-journal skills get SKILL               # print SKILL.md
scitex-agentic-journal skills get 01_installation     # print one leaf
scitex-agentic-journal skills get 12_gate1-checks --json
scitex-agentic-journal skills install                 # copy bundle to ~/.claude/skills/scitex-agentic-journal/
scitex-agentic-journal skills install --dest /path    # custom destination
scitex-agentic-journal skills install --dry-run       # preview
scitex-agentic-journal skills install --force         # overwrite non-empty dest
```

`skills install` honours `$SCITEX_AGENTIC_JOURNAL_SKILLS_DEST` if
set. The bundle is resolved via `importlib.resources` so works
identically from a checkout (`pip install -e .`) and from a wheel.

## `mcp` group

```bash
scitex-agentic-journal mcp list-tools            # introspect MCP tool catalogue
scitex-agentic-journal mcp list-tools --json
```

The MCP server itself is a post-MVP target (#6). `list-tools` today
returns the registered names — empty for the alpha — without
requiring `fastmcp` to be installed.

## `info` group

```bash
scitex-agentic-journal info list-python-apis    # enumerates the public Python API
```

## Shell completion

```bash
scitex-agentic-journal install-shell-completion bash --dry-run
scitex-agentic-journal install-shell-completion zsh --yes
scitex-agentic-journal print-shell-completion fish
```

These wire through `scitex_dev._cli._completion.attach_shell_completion`
when `scitex-dev` is importable; otherwise they degrade to stubs
that keep the command surface present so agents introspecting the
CLI don't see commands disappear.

## Exit codes

| Code | Meaning |
|---|---|
| 0  | Success (or Gate-1 PASS) |
| 1  | Gate failure — see stderr for the structured `GateFailure` reason + detail |
| 2  | Click usage error (unknown flag, bad arg) |

See [11_submission-bundle.md](11_submission-bundle.md) for the
input shape, and [12_gate1-checks.md](12_gate1-checks.md) for the
per-check error vocabulary.
