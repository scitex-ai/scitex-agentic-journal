"""Typed Submission descriptor — loaded from ``<bundle>/bundle.yaml``.

A submission bundle is a directory containing:

* ``bundle.yaml`` — the manifest read into :class:`Submission`.
* the manuscript and its assets (LaTeX, figures, code, …) — opaque
  to Gate-1 today; M2 reviewer-agent will read them.
* optionally an in-bundle Clew project rooted at the path the
  manifest names (defaulting to the bundle root).

Gate-1 is intentionally schema-strict — every field below is
required so an under-specified bundle fails loudly at load time
instead of silently producing a useless gate result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Submission:
    """Typed view of one ``<bundle>/bundle.yaml`` manifest.

    Attributes
    ----------
    bundle_dir :
        Absolute path to the bundle directory the manifest was loaded
        from. Resolved before storage so downstream callers do not
        need to re-anchor relative paths against cwd.
    orcid_id :
        The author's ORCID id, in bare ``0000-0000-0000-0000`` form
        or any URL form ``verify_orcid`` accepts.
    code_repo_url :
        Anything ``git clone`` accepts — ``https://``, ``ssh://``,
        ``git@``, ``file://``, or a bare local path.
    clew_project_dir :
        Absolute path to the Clew project inside the bundle. When the
        manifest omits ``clew_project_path`` we default to
        ``bundle_dir`` itself (i.e. the bundle root *is* the Clew
        project).
    """

    bundle_dir: Path
    orcid_id: str
    code_repo_url: str
    clew_project_dir: Path
