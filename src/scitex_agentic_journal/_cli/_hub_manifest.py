"""``scitex-agentic-journal hub-manifest`` command — emit wrapper manifest JSON.

Mirrors :mod:`scitex_live_paper._cli`'s ``hub-manifest`` subcommand
(live-paper PR #45) verbatim — same verb, same flags, same JSON
shape — so the scitex-hub scaffolder can shell-out uniformly to
both upstream packages instead of special-casing journal.

Wired into the root CLI group via :func:`register_hub_manifest_command`,
matching the pattern of the sibling ``_cli/_submit``, ``_cli/_review``,
``_cli/_decide``, ``_cli/_publish`` subcommands.

The output is the hub workspace-UI shape — derived from
:data:`scitex_agentic_journal.HUB_APP_MANIFEST` via
:func:`scitex_agentic_journal.derive_wrapper_manifest`. Default
formatting is ``indent=2`` + ``sort_keys=True`` so successive runs
produce stable, review-friendly diffs; ``--compact`` switches to a
single-line JSON for inline embedding.
"""

from __future__ import annotations

import click


def register_hub_manifest_command(main_group: click.Group) -> None:
    """Attach the ``hub-manifest`` subcommand to ``main_group``."""

    @main_group.command(name="hub-manifest")
    @click.option(
        "--label",
        default=None,
        help=(
            "Override workspace tile title (default: HUB_APP_MANIFEST "
            "display_name)."
        ),
    )
    @click.option(
        "--subtitle",
        default=None,
        help=(
            "Override short tagline (default: first sentence of "
            "description)."
        ),
    )
    @click.option(
        "--schema-version",
        default="2.0.0",
        show_default=True,
        help="Hub manifest schema_version to declare.",
    )
    @click.option(
        "--compact",
        is_flag=True,
        default=False,
        help=(
            "Emit single-line JSON (default: indented + sorted for "
            "stable VCS diffs)."
        ),
    )
    def hub_manifest_cmd(
        label: str | None,
        subtitle: str | None,
        schema_version: str,
        compact: bool,
    ) -> None:
        """Print the scitex-hub workspace manifest as JSON.

        Hub-side wrapper apps regenerate ``manifest.json`` via this
        verb so the upstream pip package stays the single source of
        truth (cross-package mirror of ``scitex-live-paper
        hub-manifest`` from live-paper PR #45).

        The output is the v2.0.0 hub workspace UI shape — derived
        from :data:`scitex_agentic_journal.HUB_APP_MANIFEST` via
        :func:`scitex_agentic_journal.derive_wrapper_manifest`.
        Default formatting is indented + ``sort_keys=True`` so
        successive runs produce stable, review-friendly diffs.

        Example:

        \b
            $ scitex-agentic-journal hub-manifest > manifest.json
            $ scitex-agentic-journal hub-manifest --label "Agentic Journal" \\
                --subtitle "ARA-native AI-reviewed open publishing"
            $ scitex-agentic-journal hub-manifest --compact
        """
        import json as _json

        from scitex_agentic_journal import derive_wrapper_manifest

        manifest = derive_wrapper_manifest(
            label=label,
            subtitle=subtitle,
            schema_version=schema_version,
        )

        if compact:
            click.echo(_json.dumps(manifest, sort_keys=True))
        else:
            click.echo(_json.dumps(manifest, sort_keys=True, indent=2))


__all__ = ["register_hub_manifest_command"]
