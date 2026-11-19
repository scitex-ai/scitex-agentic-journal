"""The dependencies a project declares, reduced to plain package-index requirements.

The sandbox fetches dependencies from the package index BEFORE any author file
is in the run, so a requirement must never be able to steer that fetch:
options (``--index-url``, ``-e``, ``-r``, ``--hash``), URLs, VCS and local paths
are refused, never passed on. Only ``name[extras] <specifiers> ; <marker>``
lines are kept. Sources, in order: every ``requirements*.txt`` at the project
root, then ``[project].dependencies`` of ``pyproject.toml``. The project itself
is not installed (its build backend would be author code run with egress).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):  # noqa: UP036 - the package supports 3.10
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 only
    import tomli as tomllib

_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
_EXTRAS = r"(?:\s*\[\s*" + _NAME + r"(?:\s*,\s*" + _NAME + r")*\s*\])?"
_VERSION = r"[A-Za-z0-9.*+!_-]+"
_SPEC = r"(?:===|==|!=|~=|<=|>=|<|>)\s*" + _VERSION
_SPECS = r"(?:\s*\(?\s*" + _SPEC + r"(?:\s*,\s*" + _SPEC + r")*\s*\)?)?"
_MARKER = r"(?:\s*;\s*[A-Za-z0-9_.'\"<>=!~(),\s-]+)?"
REQUIREMENT_RE = re.compile(r"^" + _NAME + _EXTRAS + _SPECS + _MARKER + r"$")


@dataclass
class DeclaredDependencies:
    requirements: list[str] = field(default_factory=list)
    refused: list[dict[str, str]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirements": list(self.requirements),
            "refused": list(self.refused),
            "sources": list(self.sources),
        }


def is_plain_requirement(line: str) -> bool:
    """True for ``name[extras] specifiers ; marker`` with no option, URL or path."""
    if "://" in line or "@" in line or line.startswith(("-", ".", "/", "~")):
        return False
    return REQUIREMENT_RE.match(line) is not None


def _requirement_lines(text: str) -> list[str]:
    joined = re.sub(r"\\\n", " ", text)
    lines = []
    for raw in joined.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw).strip()
        if line:
            lines.append(line)
    return lines


def _add(deps: DeclaredDependencies, source: str, line: str) -> None:
    if is_plain_requirement(line):
        if line not in deps.requirements:
            deps.requirements.append(line)
    else:
        deps.refused.append({"source": source, "line": line})


def declared_dependencies(project: Path) -> DeclaredDependencies:
    """Collect the project's declared runtime dependencies (see module docstring)."""
    deps = DeclaredDependencies()
    for req_file in sorted(project.glob("requirements*.txt")):
        if not req_file.is_file() or req_file.is_symlink():
            deps.refused.append(
                {"source": req_file.name, "line": "<not a regular file>"}
            )
            continue
        deps.sources.append(req_file.name)
        for line in _requirement_lines(
            req_file.read_text(encoding="utf-8", errors="replace")
        ):
            _add(deps, req_file.name, line)
    pyproject = project / "pyproject.toml"
    if pyproject.is_file() and not pyproject.is_symlink():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
            deps.refused.append(
                {"source": "pyproject.toml", "line": f"<unparsable: {e}>"}
            )
            return deps
        declared = (data.get("project") or {}).get("dependencies") or []
        if declared:
            deps.sources.append("pyproject.toml")
        for item in declared:
            _add(deps, "pyproject.toml", str(item).strip())
    return deps
