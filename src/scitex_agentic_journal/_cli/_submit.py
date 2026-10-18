"""`scitex-agentic-journal submit` command — M1 orchestrator wiring.

Factored out of `_cli/__init__.py` so the main CLI module stays
under the harness's per-file line ceiling AND so the test mirror
under `tests/scitex_agentic_journal/_cli/test__submit.py` has a
one-to-one src counterpart (PS-204 / PS-205 compliance).

Wired into the root group via :func:`register_submit_command`.
"""

from __future__ import annotations

import click


def register_submit_command(main_group: click.Group) -> None:
    """Attach the ``submit`` subcommand to ``main_group``."""

    @main_group.command(name="submit")
    @click.argument(
        "bundle_dir",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
    )
    def submit(bundle_dir: str) -> None:
        """Submit a manuscript bundle through Gate-1.

        Loads ``<bundle>/bundle.yaml``, runs the three structural
        checks (ORCID #2, code-repo #3, Clew DAG #4) in declared
        order, persists the verdict under
        ``$SCITEX_AGENTIC_JOURNAL_HOME/submissions/<id>/``, and
        prints ``GATE-1 PASS submission_id=...`` on success.

        On any structural failure prints a single-line ``GATE-1 FAIL
        [<check>]: <reason> -- <detail>`` and exits non-zero, with no
        Python traceback.

        Example:

          $ scitex-agentic-journal submit ./paper/
          GATE-1 PASS submission_id=sub_2026_06_13_abc123
        """
        from scitex_agentic_journal._submit import (
            Gate1Failure,
            SubmissionLoadError,
            load_submission,
            persist_verdict,
            run_gate1,
        )

        try:
            submission = load_submission(bundle_dir)
        except SubmissionLoadError as e:
            raise click.ClickException(str(e)) from e
        try:
            verdict = run_gate1(submission)
        except Gate1Failure as f:
            # `GateFailure.__str__` already produces the canonical
            # `GATE-1 FAIL [<check>]: <reason> -- <detail>` line.
            raise click.ClickException(str(f.wrapped)) from f
        persisted = persist_verdict(verdict)
        click.echo(f"GATE-1 PASS submission_id={persisted.submission_id}")


__all__ = ["register_submit_command"]
