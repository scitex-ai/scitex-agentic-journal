"""CLI for the contract-based path: bundle, admission, preprint, reviews.

The stages before review (design 01 §0, §10):

    bundle seal DIR         hash every file into submission.json (files map)
    bundle validate DIR     check a submission bundle, print every finding
    bundle submit DIR       record a valid bundle, print its submission id
    admission evaluate ID   run the admission checks, record the outcome
    admission show ID       print the latest admission record
    preprint create ID V    snapshot an admitted submission as preprint V
    preprint show ID        print the preprint record
    reviews ingest ID R S   ingest a review R from source S (any reviewer)
    reviews list ID         list ingested reviews

Every command accepts ``--json`` for machine-readable output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click


def _emit(payload: Any, as_json: bool, line: str) -> None:
    if as_json:
        click.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        click.echo(line)


def _fail(exc: Exception) -> click.ClickException:
    return click.ClickException(str(exc))


_json_opt = click.option(
    "--json", "as_json", is_flag=True, help="Print machine-readable JSON."
)


def register_contract_commands(main_group: click.Group) -> None:
    """Attach the ``bundle``, ``admission``, ``preprint`` and ``reviews`` groups."""

    @main_group.group(name="bundle")
    def bundle() -> None:
        """Validate and submit contract-based submission bundles."""

    @bundle.command(name="validate")
    @click.argument("bundle_dir", type=click.Path(path_type=Path))
    @_json_opt
    def bundle_validate(bundle_dir: Path, as_json: bool) -> None:
        """Check BUNDLE_DIR against the submission contract; exit 1 on findings.

        Example:

          $ scitex-agentic-journal bundle validate ./submission
        """
        from scitex_agentic_journal._bundle import validate_bundle

        v = validate_bundle(bundle_dir)
        payload = {
            "ok": v.ok,
            "submission_id": v.submission_id,
            "findings": [f.as_dict() for f in v.findings],
        }
        lines = [
            f"BUNDLE {'VALID' if v.ok else 'INVALID'} submission_id={v.submission_id}"
        ]
        lines += [f"  [{f.code}] {f.message}" for f in v.findings]
        _emit(payload, as_json, "\n".join(lines))
        if not v.ok:
            raise SystemExit(1)

    @bundle.command(name="seal")
    @click.argument("bundle_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
    @_json_opt
    def bundle_seal(bundle_dir: Path, as_json: bool) -> None:
        """Hash every file of BUNDLE_DIR into submission.json's files map.

        Only the files map is rewritten; validate afterwards.

        Example:

          $ scitex-agentic-journal bundle seal ./submission
        """
        from scitex_agentic_journal._bundle import seal_bundle

        try:
            files = seal_bundle(bundle_dir)
        except (ValueError, OSError) as e:
            raise _fail(e) from e
        _emit({"files": files}, as_json, f"SEALED {bundle_dir} files={len(files)}")

    @bundle.command(name="submit")
    @click.argument("bundle_dir", type=click.Path(path_type=Path))
    @_json_opt
    def bundle_submit(bundle_dir: Path, as_json: bool) -> None:
        """Record a valid BUNDLE_DIR in the journal (idempotent).

        Example:

          $ scitex-agentic-journal bundle submit ./submission
        """
        from scitex_agentic_journal._bundle import BundleInvalidError, submit_bundle
        from scitex_agentic_journal._records import RecordError

        try:
            receipt = submit_bundle(bundle_dir)
        except (BundleInvalidError, RecordError) as e:
            raise _fail(e) from e
        payload = {
            "submission_id": receipt.submission_id,
            "record_dir": str(receipt.record_dir),
            "created": receipt.created,
        }
        _emit(
            payload,
            as_json,
            f"SUBMITTED submission_id={receipt.submission_id} created={receipt.created}",
        )

    @main_group.group(name="admission")
    def admission() -> None:
        """Run and inspect admission checks (identity, SciTeX form, evidence)."""

    @admission.command(name="evaluate")
    @click.argument("submission_id")
    @click.option(
        "--allow-local-repositories",
        is_flag=True,
        help="Accept non-https repository URLs (operator-run local journals only).",
    )
    @_json_opt
    def admission_evaluate(submission_id: str, allow_local_repositories: bool, as_json: bool) -> None:
        """Run every admission check for SUBMISSION_ID; exit 1 if not admitted.

        Contacts the ORCID registry, clones the declared repository and runs
        scitex-dev's lint on it. Author code is not executed.

        Example:

          $ scitex-agentic-journal admission evaluate aj-0123456789abcdef
        """
        from scitex_agentic_journal._admission import run_admission
        from scitex_agentic_journal._records import RecordError

        try:
            rec = run_admission(
                submission_id, allow_local_repositories=allow_local_repositories
            )
        except RecordError as e:
            raise _fail(e) from e
        lines = [f"ADMISSION submission_id={submission_id} admitted={rec['admitted']}"]
        lines += [
            f"  {c['status']:8} {c['check']}: {c['reason']}" for c in rec["checks"]
        ]
        _emit(rec, as_json, "\n".join(lines))
        if not rec["admitted"]:
            raise SystemExit(1)

    @admission.command(name="show")
    @click.argument("submission_id")
    @_json_opt
    def admission_show(submission_id: str, as_json: bool) -> None:
        """Print the latest admission record of SUBMISSION_ID.

        Example:

          $ scitex-agentic-journal admission show aj-0123456789abcdef --json
        """
        from scitex_agentic_journal._admission import load_admission
        from scitex_agentic_journal._records import RecordError

        try:
            rec = load_admission(submission_id)
        except RecordError as e:
            raise _fail(e) from e
        lines = [f"ADMISSION submission_id={submission_id} admitted={rec['admitted']}"]
        lines += [
            f"  {c['status']:8} {c['check']}: {c['reason']}" for c in rec["checks"]
        ]
        _emit(rec, as_json, "\n".join(lines))

    @main_group.group(name="preprint")
    def preprint() -> None:
        """Snapshot admitted submissions as preprints."""

    @preprint.command(name="create")
    @click.argument("submission_id")
    @click.argument("version")
    @click.option("--dry-run", is_flag=True, help="Show the record without writing it.")
    @click.option("--yes", "-y", "assume_yes", is_flag=True, help="Do not ask for confirmation.")
    @_json_opt
    def preprint_create(
        submission_id: str, version: str, dry_run: bool, assume_yes: bool, as_json: bool
    ) -> None:
        """Snapshot admitted SUBMISSION_ID as preprint VERSION (e.g. v1.1.0).

        A preprint record is immutable; use --dry-run to inspect it first.

        Example:

          $ scitex-agentic-journal preprint create aj-0123456789abcdef v1.1.0 --dry-run
          $ scitex-agentic-journal preprint create aj-0123456789abcdef v1.1.0 --yes
        """
        from scitex_agentic_journal._preprint import (
            PreprintRefusedError,
            create_preprint,
        )
        from scitex_agentic_journal._records import RecordError

        if not dry_run and not assume_yes:
            raise click.ClickException(
                f"refusing to create immutable preprint {version} of {submission_id} "
                "without --yes; inspect it first with --dry-run"
            )
        try:
            rec = create_preprint(submission_id, version, dry_run=dry_run)
        except (PreprintRefusedError, RecordError) as e:
            raise _fail(e) from e
        _emit(
            rec,
            as_json,
            f"{'PLAN ' if dry_run else ''}PREPRINT submission_id={submission_id} "
            f"version={rec['preprint_version']} "
            f"internal_id={rec['internal_id']} doi_status={rec['doi_status']}",
        )

    @preprint.command(name="show")
    @click.argument("submission_id")
    @_json_opt
    def preprint_show(submission_id: str, as_json: bool) -> None:
        """Print the preprint record of SUBMISSION_ID.

        Example:

          $ scitex-agentic-journal preprint show aj-0123456789abcdef
        """
        from scitex_agentic_journal._preprint import load_preprint
        from scitex_agentic_journal._records import RecordError

        try:
            rec = load_preprint(submission_id)
        except RecordError as e:
            raise _fail(e) from e
        _emit(
            rec,
            as_json,
            f"PREPRINT submission_id={submission_id} version={rec['preprint_version']} "
            f"internal_id={rec['internal_id']} doi_status={rec['doi_status']}",
        )

    @main_group.group(name="reviews")
    def reviews() -> None:
        """Ingest reviews from any source (external services, humans, users)."""

    @reviews.command(name="ingest")
    @click.argument("submission_id")
    @click.argument(
        "report_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
    )
    @click.argument(
        "source_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
    )
    @click.option(
        "--channel",
        default="operator-cli",
        show_default=True,
        type=click.Choice(
            ["orcid-login", "service-key", "operator-cli", "self-declared"]
        ),
        help="How the reviewer's identity reached the journal.",
    )
    @_json_opt
    def reviews_ingest(
        submission_id: str,
        report_path: Path,
        source_path: Path,
        channel: str,
        as_json: bool,
    ) -> None:
        """File the review REPORT_PATH from SOURCE_PATH against SUBMISSION_ID.

        REPORT_PATH follows the review-report schema; SOURCE_PATH follows the
        review-source schema. Both ship in the wheel under _contracts/schemas/.

        Example:

          $ scitex-agentic-journal reviews ingest aj-0123456789abcdef report.json source.json
        """
        from scitex_agentic_journal._ingest import ReviewRejectedError, file_review
        from scitex_agentic_journal._records import RecordError

        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            source = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise _fail(e) from e
        try:
            rec = file_review(submission_id, report, source, channel=channel)
        except (ReviewRejectedError, RecordError) as e:
            raise _fail(e) from e
        _emit(
            rec,
            as_json,
            f"REVIEW FILED submission_id={submission_id} review_id={rec['review_id']} "
            f"reviewer={rec['reviewer_pseudonym']} recommendation={rec['recommendation']}",
        )

    @reviews.command(name="list")
    @click.argument("submission_id")
    @_json_opt
    def reviews_list(submission_id: str, as_json: bool) -> None:
        """List the reviews ingested for SUBMISSION_ID.

        Example:

          $ scitex-agentic-journal reviews list aj-0123456789abcdef
        """
        from scitex_agentic_journal._ingest import list_reviews

        recs = list_reviews(submission_id)
        lines = [f"REVIEWS submission_id={submission_id} count={len(recs)}"]
        lines += [
            f"  {r['review_id']} {r['reviewer_pseudonym']} round={r['round']} "
            f"{r['source']['kind']} {r['recommendation']}"
            for r in recs
        ]
        _emit(recs, as_json, "\n".join(lines))


__all__ = ["register_contract_commands"]
