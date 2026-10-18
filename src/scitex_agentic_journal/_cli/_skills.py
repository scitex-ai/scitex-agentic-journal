"""`scitex-agentic-journal skills` command group — §1a compliance.

The package ships a bundled ``_skills/scitex-agentic-journal/`` tree;
the audit's §1a rule requires a ``<pkg> skills {list, get, install}``
Click sub-group so operators (and agents) can discover and
materialise the bundle without having to learn ``scitex-dev skills
get``.

All three subcommands resolve the bundle via :mod:`importlib.resources`
so they work identically from a checked-out repo and from a
pip-installed wheel. No network, no fetch — everything ships with
the distribution.

Split out of :mod:`scitex_agentic_journal._cli` to keep the main CLI
module under the harness's 512-line per-file ceiling.
:func:`register_skills_commands` is the single entry point — call it
once on the root Click group.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

import click

_OWN_PACKAGE = "scitex_agentic_journal"
_BUNDLE_RELATIVE = ("_skills", "scitex-agentic-journal")


def _skills_bundle_files():
    """Return the importlib.resources Traversable for the bundle.

    Wrapped in a function so the import + lookup happen lazily and
    failures show up at command-invocation time (with a clean
    :class:`click.ClickException`) rather than at module-import time.

    The bundle directory's basename contains a hyphen
    (``scitex-agentic-journal``) so it cannot be addressed as a
    Python sub-package; we resolve it as a child of the own package's
    Traversable instead, which works identically for both an
    editable checkout and a wheel install.
    """
    from importlib import resources

    root = resources.files(_OWN_PACKAGE)
    for part in _BUNDLE_RELATIVE:
        root = root / part
    return root


def _skills_bundle_leaves() -> list[str]:
    """Return the sorted list of ``.md`` leaf filenames in the bundle."""
    root = _skills_bundle_files()
    return sorted(
        entry.name
        for entry in root.iterdir()
        if entry.is_file() and entry.name.endswith(".md")
    )


def _resolve_install_destination(explicit: str | None) -> Path:
    """Pick the install destination per the (explicit → env → default) chain."""
    if explicit is not None:
        return Path(explicit)
    env_dest = os.environ.get("SCITEX_AGENTIC_JOURNAL_SKILLS_DEST")
    if env_dest:
        return Path(env_dest).expanduser().resolve()
    return Path.home() / ".claude" / "skills" / "scitex-agentic-journal"


def _copy_bundle_to(destination: Path, leaves: Iterable[str]) -> int:
    """Copy each leaf from the importlib-resources bundle to ``destination``.

    Returns the number of leaves written. Uses :mod:`shutil` via the
    text round-trip so the on-disk encoding is deterministic UTF-8
    regardless of the source distribution's filesystem origin.
    """
    root = _skills_bundle_files()
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for leaf in leaves:
        source_text = (root / leaf).read_text(encoding="utf-8")
        (destination / leaf).write_text(source_text, encoding="utf-8")
        count += 1
    return count


def register_skills_commands(main_group: click.Group) -> None:
    """Attach the ``skills {list, get, install}`` sub-group to ``main_group``.

    Idempotent — calling twice on the same group raises a Click
    ``CommandError`` (Click's standard behaviour). Tests should
    instantiate a fresh root group rather than calling this twice.
    """

    @main_group.group(name="skills", invoke_without_command=True)
    @click.pass_context
    def skills(ctx: click.Context) -> None:
        """List, fetch, or materialise the bundled scitex-agentic-journal skills.

        The bundle lives under ``_skills/scitex-agentic-journal/``
        inside the installed distribution. Each ``.md`` leaf is a
        self-contained section of the skill index; ``SKILL.md`` is
        the entry point.

        Example:

          $ scitex-agentic-journal skills list
          $ scitex-agentic-journal skills get 01_overview
          $ scitex-agentic-journal skills install --dest ~/.claude/skills
        """
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @skills.command("list")
    @click.option(
        "--json",
        "as_json_local",
        is_flag=True,
        default=False,
        help="Emit the leaf list as JSON.",
    )
    def skills_list(as_json_local: bool) -> None:
        """List every ``.md`` leaf shipped under ``_skills/scitex-agentic-journal/``.

        Example:

          $ scitex-agentic-journal skills list
          $ scitex-agentic-journal skills list --json
        """
        try:
            leaves = _skills_bundle_leaves()
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise click.ClickException(
                "scitex-agentic-journal skills bundle not importable "
                f"({exc!r}) — reinstall with `pip install -e .` from a "
                "checkout, or `pip install scitex-agentic-journal` from "
                "a wheel."
            ) from exc
        if as_json_local:
            click.echo(json.dumps({"skills": leaves}, indent=2))
            return
        if not leaves:
            click.echo("(no skills bundled)")
            return
        for leaf in leaves:
            click.echo(leaf)

    @skills.command("get")
    @click.argument("name", required=True)
    @click.option(
        "--json",
        "as_json_local",
        is_flag=True,
        default=False,
        help="Emit the skill content as a JSON envelope.",
    )
    def skills_get(name: str, as_json_local: bool) -> None:
        """Print the content of one bundled skill leaf.

        NAME may be given with or without the ``.md`` suffix. Pass
        ``SKILL`` (or ``SKILL.md``) to retrieve the index. Use
        ``scitex-agentic-journal skills list`` to enumerate available
        names.

        Example:

          $ scitex-agentic-journal skills get SKILL
          $ scitex-agentic-journal skills get 01_overview
          $ scitex-agentic-journal skills get 03_gate1-checks --json
        """
        leaf_name = name if name.endswith(".md") else f"{name}.md"
        try:
            root = _skills_bundle_files()
            leaf = root / leaf_name
            if not leaf.is_file():
                raise FileNotFoundError(leaf_name)
            content = leaf.read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            # Surface available leaves so the operator can correct a
            # typo without having to remember exact filenames.
            try:
                leaves = _skills_bundle_leaves()
            except Exception:
                leaves = []
            hint = f" available: {', '.join(leaves)}" if leaves else ""
            raise click.ClickException(
                f"skill {leaf_name!r} not found in the bundle.{hint}"
            ) from exc
        if as_json_local:
            click.echo(
                json.dumps(
                    {
                        "package": "scitex-agentic-journal",
                        "name": leaf_name,
                        "content": content,
                    },
                    indent=2,
                )
            )
            return
        click.echo(content)

    @skills.command("install")
    @click.option(
        "--dest",
        "dest",
        type=click.Path(file_okay=False, dir_okay=True, resolve_path=True),
        default=None,
        help=(
            "Directory to copy the bundle into. Defaults to "
            "`$SCITEX_AGENTIC_JOURNAL_SKILLS_DEST` if set, else "
            "`~/.claude/skills/scitex-agentic-journal/`."
        ),
    )
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Overwrite the destination if it already exists.",
    )
    @click.option(
        "--dry-run/--no-dry-run",
        default=False,
        show_default=True,
        help="List the files that would be copied without writing anything.",
    )
    @click.option(
        "--yes",
        "-y",
        "assume_yes",
        is_flag=True,
        default=False,
        help="Assume yes to confirmation prompts (skip interactive prompt).",
    )
    def skills_install(
        dest: str | None, force: bool, dry_run: bool, assume_yes: bool
    ) -> None:
        """Materialise the bundled ``_skills/scitex-agentic-journal/`` tree to disk.

        Example:

          $ scitex-agentic-journal skills install --dest ~/.claude/skills
          $ scitex-agentic-journal skills install --dry-run
          $ scitex-agentic-journal skills install --force
        """
        destination = _resolve_install_destination(dest)
        try:
            leaves = _skills_bundle_leaves()
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise click.ClickException(
                f"scitex-agentic-journal skills bundle not importable "
                f"({exc!r})."
            ) from exc

        if dry_run:
            click.echo(f"would create: {destination}")
            for leaf in leaves:
                click.echo(f"would copy: {leaf} -> {destination / leaf}")
            return

        if destination.exists() and any(destination.iterdir()):
            if not force and not assume_yes:
                raise click.ClickException(
                    f"destination {destination} is not empty — pass "
                    "`--force` (overwrite skill leaves only, preserve "
                    "unrelated files) or `--yes/-y` to acknowledge "
                    "and proceed."
                )

        count = _copy_bundle_to(destination, leaves)
        click.echo(f"installed {count} skill leaf/leaves to {destination}")


__all__ = ["register_skills_commands"]
