"""`scitex-agentic-journal review` command — M2 wiring.

The package's main CLI module (`_cli.py`) hosts the entry-point group
and the M1 submit orchestrator; the M2 review verb lives here so the
two halves stay independently sized under the harness's 512-line
per-file ceiling. Wired into the root group via
:func:`register_review_command` — exactly mirrors the
`_cli_skills.register_skills_commands` pattern.
"""

from __future__ import annotations

import click


def register_review_command(main_group: click.Group) -> None:
    """Attach the ``review`` subcommand to ``main_group``."""

    @main_group.command(name="review")
    @click.argument("submission_id")
    @click.option(
        "--adapter",
        "adapter_name",
        default="local",
        show_default=True,
        help=(
            "Reviewer-agent adapter to use. See "
            "`scitex_agentic_journal._review.list_adapter_names()` for "
            "the registered set."
        ),
    )
    @click.option(
        "--prompts-version",
        "prompts_version",
        default="v1",
        show_default=True,
        help="Prompt-set version threaded into the adapter and recorded.",
    )
    def review(
        submission_id: str,
        adapter_name: str,
        prompts_version: str,
    ) -> None:
        """Run a single reviewer-agent against a persisted submission.

        Loads ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/gate1.json``
        (written by M1 / ``submit``), builds the typed inputs the
        reviewer agent expects, runs the selected adapter through
        every sub-report of the ARA rubric, hashes the result, and
        writes ``review.json`` next to the Gate-1 record. On success
        prints ``REVIEW DONE submission_id=... adapter=...
        content_hash=...`` so a downstream caller can pin the exact
        review by hash.

        Example:

          $ scitex-agentic-journal review sub_2026_06_13_abc123
          $ scitex-agentic-journal review sub_... --adapter local
        """
        # Imports are deferred so the help epilog renders without
        # the (currently large) `_review` subpackage import cost.
        from scitex_agentic_journal._review import (
            ReviewLoadError,
            ReviewRunner,
            UnknownAdapterError,
            load_submission_inputs,
            persist_review,
            select_adapter,
        )

        try:
            adapter = select_adapter(adapter_name)
        except UnknownAdapterError as e:
            raise click.ClickException(str(e)) from e
        try:
            inputs = load_submission_inputs(submission_id)
        except ReviewLoadError as e:
            raise click.ClickException(str(e)) from e
        try:
            record = ReviewRunner(
                adapter, prompts_version=prompts_version
            ).run(inputs)
        except NotImplementedError as e:
            # `QwenAdapterStub` raises NotImplementedError until the
            # live endpoint is wired; surface that as a clean
            # ClickException so the operator sees one structured line
            # instead of a Python traceback.
            raise click.ClickException(str(e)) from e
        persisted = persist_review(record)
        click.echo(
            f"REVIEW DONE submission_id={persisted.submission_id} "
            f"adapter={adapter.adapter_name} "
            f"content_hash={persisted.content_hash}"
        )


__all__ = ["register_review_command"]
