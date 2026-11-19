"""Regenerate ``tests/scitex_agentic_journal/fixtures/bundle-reference/`` from real producers.

The fixture is NOT hand-written: the project, its evidence report and its
review packet are produced by scitex-live-paper's own reference evidence
provider and packet builder, at the pinned version. The journal's test suite
then reads the static files and never imports scitex-live-paper.

Run in an environment with scitex-live-paper installed from commit
``LIVE_PAPER_COMMIT`` (the commit the vendored schemas are pinned to)::

    python tests/scitex_agentic_journal/fixtures/make_reference_bundle.py \
        --provider-dir <dir holding _reference_provider.py from that commit,
                        tests/scitex_live_paper/evidence/> \
        --pdf <that commit: tests/scitex_live_paper/fixtures/bundle-min/manuscript.pdf> \
        --workdir <scratch dir> \
        --out tests/scitex_agentic_journal/fixtures/bundle-reference
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

LIVE_PAPER_COMMIT = "963de44fa4f7204326149ab141eb52217b32b229"  # develop, PR #106

BIB = """@misc{scitex_live_paper_2026,
  title        = {scitex-live-paper: executable, evidence-linked papers},
  author       = {Watanabe, Yusuke},
  year         = {2026},
  howpublished = {\\url{https://github.com/scitex-ai/scitex-live-paper}},
  note         = {Version 0.5.0.dev0}
}
"""


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--provider-dir", type=Path, required=True)
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    sys.path.insert(0, str(args.provider_dir))
    from _reference_provider import ReferenceProvider, build_project
    from scitex_live_paper.evidence import build_review_packet, review_text

    project = args.workdir / "project"
    if project.exists():
        shutil.rmtree(project)
    build_project(project)
    report = ReferenceProvider().evidence_report(str(project), None, {})
    packet = build_review_packet(report)

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    (out / "manuscript").mkdir(parents=True)
    (out / "review-packet").mkdir()
    shutil.copyfile(project / "paper" / "paper.tex", out / "manuscript" / "paper.tex")
    shutil.copyfile(args.pdf, out / "manuscript" / "manuscript.pdf")
    (out / "evidence-report.json").write_text(json.dumps(report, indent=1) + "\n")
    (out / "review-packet" / "review.json").write_text(
        json.dumps(packet, indent=1) + "\n"
    )
    (out / "review-packet" / "review.txt").write_text(review_text(packet))
    (out / "references.bib").write_text(BIB)

    files = {
        p.relative_to(out).as_posix(): _sha(p)
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }
    manifest = {
        "schema": "scitex-agentic-journal.submission",
        "schema_version": "1.0",
        "title": "Reference project exercising the evidence contract",
        "authors": [
            {
                "name": "Josiah Carberry",
                "orcid": "0000-0002-1825-0097",
                "corresponding": True,
            }
        ],
        "submitter_orcid": "0000-0002-1825-0097",
        "repository": {
            "host": "github",
            "url": "https://github.com/scitex-ai/scitex-live-paper",
            "commit": LIVE_PAPER_COMMIT,
            "tag": None,
            "project_version": "0.5.0.dev0",
        },
        "licence": {"manuscript": "CC-BY-4.0", "code": "AGPL-3.0-only"},
        "data": [],
        "produced_by": [
            {
                "kind": "agent",
                "id": "scitex-live-paper-reference-provider",
                "model": None,
            }
        ],
        "main_claims": ["auc"],
        "contracts": {
            "evidence_report": "scitex-live-paper.evidence-report@1",
            "review_packet": "scitex-live-paper.review-packet@1",
        },
        "files": files,
        "supersedes": None,
    }
    (out / "submission.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"wrote {out} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
