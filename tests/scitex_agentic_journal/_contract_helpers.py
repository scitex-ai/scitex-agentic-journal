"""Shared helpers for the contract-based path tests.

* The reference bundle under ``tests/scitex_agentic_journal/fixtures/bundle-reference``
  is real producer output (see ``fixtures/make_reference_bundle.py`` there).
* ``make_research_repo`` builds a real git repository holding a small
  SciTeX research project; ``point_bundle_at`` rewrites a bundle copy's
  manifest to it (the manifest is not part of ``files``, so the bundle stays
  valid).
* ``OrcidServer`` serves the ORCID fixture records over real local HTTP,
  as the Gate-1 tests do.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_TESTS = Path(__file__).resolve().parents[1]
REFERENCE_BUNDLE = REPO_TESTS / "scitex_agentic_journal" / "fixtures" / "bundle-reference"
ORCID_FIXTURES = REPO_TESTS / "scitex_agentic_journal" / "_gate1" / "_fixtures"
TEST_ORCID = "0000-0002-1825-0097"

GIT_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/nonexistent",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}

SCRIPT = '''"""Compute the area under the curve for the reference results."""


def main():
    """Print a constant AUC (the fixture's stand-in computation)."""
    print(0.91)


if __name__ == "__main__":
    main()
'''


def copy_reference_bundle(dest: Path) -> Path:
    shutil.copytree(REFERENCE_BUNDLE, dest)
    return dest


def read_manifest(bundle: Path) -> dict:
    return json.loads((bundle / "submission.json").read_text())


def write_manifest(bundle: Path, manifest: dict) -> None:
    (bundle / "submission.json").write_text(json.dumps(manifest, indent=1) + "\n")


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def make_research_repo(root: Path, *, research: bool = True) -> tuple[str, str]:
    """A real git repo with a small research project; returns (url, commit)."""
    (root / "scripts" / "metrics").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "config").mkdir()
    (root / "data" / ".gitkeep").write_text("")
    (root / "config" / "PATH.yaml").write_text("DATA: ./data\n")
    (root / "scripts" / "metrics" / "calc_auc.py").write_text(SCRIPT)
    if research:
        (root / ".scitex" / "dev").mkdir(parents=True)
        (root / ".scitex" / "dev" / "config.yaml").write_text(
            "project-type: research\n"
        )
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture project")
    return str(root), _git(root, "rev-parse", "HEAD")


def point_bundle_at(bundle: Path, url: str, commit: str, **changes) -> None:
    manifest = read_manifest(bundle)
    manifest["repository"] = {
        "host": "local",
        "url": url,
        "commit": commit,
        "tag": None,
        "project_version": "1.1.3",
    }
    manifest.update(changes)
    write_manifest(bundle, manifest)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        orcid = self.path.strip("/").split("/")[1] if self.path.count("/") >= 2 else ""
        fixture = ORCID_FIXTURES / f"orcid_{orcid}_record.json"
        if not fixture.is_file():
            self.send_response(404)
            self.end_headers()
            return
        body = fixture.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


class OrcidServer:
    """Real local HTTP server serving ``/v3.0/<orcid>/record`` from fixtures."""

    def __enter__(self) -> str:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._server.server_address[1]}/v3.0"

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2.0)
