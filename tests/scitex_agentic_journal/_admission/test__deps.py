"""Declared dependencies: only plain package-index requirements reach the sandbox."""

from __future__ import annotations

import pytest
from scitex_agentic_journal._admission._deps import (
    canonical_requirement,
    declared_dependencies,
    is_plain_requirement,
)


@pytest.mark.parametrize(
    "line",
    [
        "numpy",
        "numpy==1.26.4",
        "pandas>=2.0,<3",
        "scitex-clew[io]~=0.34",
        "tomli>=2; python_version < '3.11'",
    ],
)
def test_plain_requirement_is_kept(line):
    # Arrange
    candidate = line
    # Act
    kept = is_plain_requirement(candidate)
    # Assert
    assert kept is True


@pytest.mark.parametrize(
    "line",
    [
        "--index-url https://evil.example/simple",
        "-e .",
        "-r other.txt",
        "pkg @ https://evil.example/pkg.whl",
        "git+https://github.com/x/y.git",
        "./local_pkg",
        "/abs/path.whl",
        "numpy==1.26 --hash=sha256:00",
    ],
)
def test_option_url_or_path_is_refused(line):
    # Arrange
    candidate = line
    # Act
    kept = is_plain_requirement(candidate)
    # Assert
    assert kept is False


def test_requirements_file_lines_are_collected_without_comments(tmp_path):
    # Arrange
    (tmp_path / "requirements.txt").write_text("# deps\nsix==1.16.0  # pinned\n\n")
    # Act
    deps = declared_dependencies(tmp_path)
    # Assert
    assert deps.requirements == ["six==1.16.0"]


def test_pyproject_dependencies_are_collected(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["numpy>=1.26"]\n'
    )
    # Act
    deps = declared_dependencies(tmp_path)
    # Assert
    assert deps.requirements == ["numpy>=1.26"]


def test_index_override_in_requirements_is_refused_with_its_source(tmp_path):
    # Arrange
    (tmp_path / "requirements-dev.txt").write_text("--extra-index-url https://x\n")
    # Act
    deps = declared_dependencies(tmp_path)
    # Assert
    assert deps.refused == [
        {"source": "requirements-dev.txt", "line": "--extra-index-url https://x"}
    ]


def test_newline_smuggling_a_pip_option_is_refused(tmp_path):
    # Arrange: a pyproject dependency whose string ends in an option line; if
    # written verbatim, --no-binary would make pip build the author's sdist
    # while the fetch phase has network.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n'
        "dependencies = [\"evilpkg ; os_name=='posix'\\n--no-binary=evilpkg\"]\n"
    )
    # Act
    deps = declared_dependencies(tmp_path)
    # Assert
    assert (deps.requirements, len(deps.refused)) == ([], 1)


@pytest.mark.parametrize("char", ["\r", "\t", "\x00", "\x1b", "\x7f"])
def test_control_characters_are_refused(char):
    # Arrange
    line = f"numpy{char}==1.26"
    # Act
    canonical = canonical_requirement(line)
    # Assert
    assert canonical is None


def test_requirement_is_written_back_canonically():
    # Arrange
    line = "Pandas >= 2.0 , < 3"
    # Act
    canonical = canonical_requirement(line)
    # Assert
    assert canonical == "Pandas<3,>=2.0"


def test_project_without_declarations_has_no_requirements(tmp_path):
    # Arrange
    project = tmp_path
    # Act
    deps = declared_dependencies(project)
    # Assert
    assert deps.as_dict() == {"requirements": [], "refused": [], "sources": []}
