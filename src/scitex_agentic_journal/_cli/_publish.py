"""`scitex-agentic-journal publish` command — M5 hand-off wiring.

Factored out of `_cli/__init__.py` so the main CLI module stays under
the harness's per-file ceiling AND so the test mirror under
`tests/scitex_agentic_journal/_cli/test__publish.py` has a one-to-one
src counterpart (PS-204 / PS-205). Wired into the root group via
:func:`register_publish_command` — mirrors `_cli._submit` and
`_cli._review`.

The verb is a mutating one (it writes a bundle to disk and contacts
the live-paper port) so it supports the canonical ``--dry-run`` and
``--yes / -y`` flags (audit §6).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click


_PORT_CHOICES = ("local-filesystem", "remote-stub")


def _resolve_home() -> Path:
    """Mirror the home-resolution in `_publish._load_records`."""
    explicit = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".scitex" / "agentic-journal"


def register_publish_command(main_group: click.Group) -> None:
    """Attach the ``publish`` subcommand to ``main_group``."""

    @main_group.command(name="publish")
    @click.argument("submission_id")
    @click.option(
        "--dry-run/--no-dry-run",
        default=False,
        show_default=True,
        help=(
            "Compute the publish bundle and print it without handing "
            "off to scitex-live-paper. Mutating verbs MUST support "
            "--dry-run (audit §6)."
        ),
    )
    @click.option(
        "--yes",
        "-y",
        "assume_yes",
        is_flag=True,
        default=False,
        help=(
            "Assume yes to confirmation prompts. Mutating verbs MUST "
            "support --yes / -y for non-interactive callers (audit §6)."
        ),
    )
    @click.option(
        "--port",
        "port_name",
        type=click.Choice(_PORT_CHOICES, case_sensitive=False),
        default="local-filesystem",
        show_default=True,
        help=(
            "Live-paper port to use. 'local-filesystem' writes the "
            "bundle envelope under "
            "$SCITEX_AGENTIC_JOURNAL_HOME/published/<id>/bundle.json "
            "and is the M5 default. 'remote-stub' wires the "
            "placeholder for the future HTTP / MCP port and raises a "
            "clean NotImplementedError until that transport lands."
        ),
    )
    def publish(
        submission_id: str,
        dry_run: bool,
        assume_yes: bool,
        port_name: str,
    ) -> None:
        """Hand off an accepted submission to scitex-live-paper.

        Loads ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/``:
        ``gate1.json`` (manuscript bundle path), ``review.json``
        (content_hash → review_record_id), ``decision.json`` (verdict
        must be ``accept``; content_hash → decision_record_id), and
        ``persistent_id.json`` (the M4-minted id). Packages them into
        a :class:`LivePaperBundle` and hands it to the selected port.

        Example:

          $ scitex-agentic-journal publish sub_2026_06_13_abc123 --dry-run
          $ scitex-agentic-journal publish sub_2026_06_13_abc123 --yes
        """
        # `assume_yes` is currently informational — `publish` is fully
        # non-interactive — but the flag is mandatory for §6 audit
        # parity AND lets future revisions add a confirmation prompt
        # without breaking callers.
        del assume_yes

        # Deferred imports — keep the help epilog cheap.
        from scitex_agentic_journal._publish import (
            LocalFilesystemLivePaperPort,
            PublishLoadError,
            RemoteLivePaperPortStub,
            build_bundle,
            load_submission_records,
            publish_submission,
        )

        home = _resolve_home()

        try:
            records = load_submission_records(submission_id, home=home)
        except PublishLoadError as e:
            raise click.ClickException(str(e)) from e

        if dry_run:
            bundle = build_bundle(records)
            click.echo(
                "DRY-RUN publish "
                f"submission_id={records.submission_id} "
                f"persistent_id={records.persistent_id} "
                f"port={port_name.lower()}"
            )
            click.echo(
                json.dumps(
                    {
                        "submission_id": bundle.submission_id,
                        "persistent_id": bundle.persistent_id,
                        "manuscript_dir": str(bundle.manuscript_dir),
                        "review_record_id": bundle.review_record_id,
                        "decision_record_id": bundle.decision_record_id,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return

        port_name_lc = port_name.lower()
        if port_name_lc == "remote-stub":
            port = RemoteLivePaperPortStub()
        else:
            port = LocalFilesystemLivePaperPort(home=home)

        try:
            receipt = publish_submission(
                submission_id, port=port, home=home
            )
        except PublishLoadError as e:
            # Defensive: load_submission_records already ran above, but
            # publish_submission re-runs it. If a record was deleted in
            # between, surface it as a clean ClickException.
            raise click.ClickException(str(e)) from e
        except NotImplementedError as e:
            raise click.ClickException(str(e)) from e

        click.echo(
            "PUBLISHED "
            f"submission_id={records.submission_id} "
            f"viewer_url={receipt.viewer_url} "
            f"persistent_id={receipt.persistent_id}"
        )


__all__ = ["register_publish_command"]
