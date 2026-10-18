"""`scitex-agentic-journal decide` command — M3 wiring.

Hosts the M3 decision-engine verb. Factored out of `_cli/__init__.py`
so the main CLI module stays under the harness's per-file line ceiling
and so the test mirror under `tests/scitex_agentic_journal/_cli/test__decide.py`
has a one-to-one src counterpart (PS-204 / PS-205 compliance).

Wired into the root group via :func:`register_decide_command`,
mirroring `_cli._submit.register_submit_command` and
`_cli._review.register_review_command`.
"""

from __future__ import annotations

import click


def register_decide_command(main_group: click.Group) -> None:
    """Attach the ``decide`` subcommand to ``main_group``."""

    @main_group.command(name="decide")
    @click.argument("submission_id")
    def decide(submission_id: str) -> None:
        """Apply the editorial decision engine to a review record.

        Loads ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/review.json``
        (written by M2 / ``review``), runs the bundled rule set
        (versioned YAML — see ``_decide/rules/v1.yaml``), and writes
        ``decision.json`` next to the review record. On success prints
        ``DECISION submission_id=... verdict=... rules_version=...
        content_hash=...`` so a downstream caller can pin the exact
        decision by hash.

        On load / engine errors raises a single-line ``click.ClickException``
        (no traceback) — mirrors the ``review`` and ``submit`` shape.

        Example:

          $ scitex-agentic-journal decide sub_2026_06_13_abc123
        """
        # Imports are deferred so the help epilog renders without
        # paying the `_decide` subpackage import cost.
        from scitex_agentic_journal._decide import (
            DecisionEngine,
            DecisionLoadError,
            RulesLoadError,
            load_review_record,
            persist_decision,
        )

        try:
            record = load_review_record(submission_id)
        except DecisionLoadError as e:
            raise click.ClickException(str(e)) from e
        try:
            engine = DecisionEngine()
        except RulesLoadError as e:
            raise click.ClickException(str(e)) from e
        decision = engine.decide(record)
        persisted = persist_decision(decision)
        click.echo(
            f"DECISION submission_id={persisted.submission_id} "
            f"verdict={decision.verdict} "
            f"rules_version={decision.rules_version} "
            f"content_hash={persisted.content_hash}"
        )


__all__ = ["register_decide_command"]
