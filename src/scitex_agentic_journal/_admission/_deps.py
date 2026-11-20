"""The dependencies a project declares, reduced to plain package-index requirements.

The sandbox fetches dependencies from the package index BEFORE any author file
is in the run, so a requirement must never be able to steer that fetch:
options (``--index-url``, ``-e``, ``-r``, ``--hash``), URLs, VCS and local paths
are refused, never passed on. Every requirement is parsed with
``packaging.requirements.Requirement`` and written back canonically; control
characters (a newline would smuggle an option line) and direct references are
refused. Sources, in order: every ``requirements*.txt`` at the project
root, then ``[project].dependencies`` of ``pyproject.toml``. The project itself
is not installed (its build backend would be author code run with egress).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

if sys.version_info >= (3, 11):  # noqa: UP036 - the package supports 3.10
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 only
    import tomli as tomllib

#: Any C0 control character or DEL: a newline would split one declared
#: dependency into a requirement AND a pip option line.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


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


def canonical_requirement(line: str) -> str | None:
    """``str(Requirement(line))`` for a plain name/specifier/marker requirement, else None.

    Refused: control characters (including newlines), anything
    :class:`packaging.requirements.Requirement` cannot parse (options such as
    ``--no-binary``, ``-e``, ``-r``, paths), and direct references (``name @ url``).
    The canonical form is what is written to the sandbox's requirements file,
    one per line, so nothing the author wrote reaches pip verbatim.
    """
    if _CONTROL.search(line):
        return None
    try:
        req = Requirement(line)
    except InvalidRequirement:
        return None
    if req.url is not None:
        return None
    canonical = str(req)
    if _CONTROL.search(canonical) or canonical.lstrip().startswith("-"):
        return None
    return canonical


def is_plain_requirement(line: str) -> bool:
    """True when :func:`canonical_requirement` accepts ``line``."""
    return canonical_requirement(line) is not None


def _requirement_lines(text: str) -> list[str]:
    joined = re.sub(r"\\\n", " ", text)
    lines = []
    for raw in joined.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw).strip()
        if line:
            lines.append(line)
    return lines


def _add(deps: DeclaredDependencies, source: str, line: str) -> None:
    canonical = canonical_requirement(line)
    if canonical is None:
        deps.refused.append({"source": source, "line": line})
    elif canonical not in deps.requirements:
        deps.requirements.append(canonical)


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
            _add(deps, "pyproject.toml", item if isinstance(item, str) else repr(item))
    return deps
