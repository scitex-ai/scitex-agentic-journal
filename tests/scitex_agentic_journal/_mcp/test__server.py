"""Real persistence and in-memory MCP calls; no external workflow execution."""

import asyncio
import hashlib

import pytest
from fastmcp import Client

from scitex_agentic_journal import get_submission
from scitex_agentic_journal._gate1 import ClewVerification, OrcidRecord
from scitex_agentic_journal._mcp._server import build_fastmcp_server
from scitex_agentic_journal._submit import Gate1Verdict, Submission, persist_verdict


@pytest.fixture
def persisted(tmp_path):
    """Persist a synthetic verdict through the real producer, without probes."""
    bundle = tmp_path / "bundle"
    verdict = Gate1Verdict(
        submission=Submission(
            bundle_dir=bundle,
            orcid_id="0000-0000-0000-0000",
            code_repo_url="https://example.invalid/synthetic",
            clew_project_dir=bundle,
        ),
        orcid_record=OrcidRecord(
            orcid_id="0000-0000-0000-0000",
            given_name="Synthetic",
            family_name="Fixture",
            credit_name="Synthetic Fixture",
        ),
        code_repo_head_commit="a" * 40,
        code_repo_head_subject="Owned fixture",
        clew_verification=ClewVerification(
            project_dir=bundle,
            green_claims=(),
            red_claims=(),
            total_claims=0,
            raw_stdout="[]",
        ),
    )
    return persist_verdict(verdict, home=tmp_path / "archive")


def _call(server, name, args):
    async def invoke():
        async with Client(server) as client:
            return await client.call_tool(name, args)

    return asyncio.run(invoke())


def _snapshot(root):
    return {
        str(p.relative_to(root)): (
            hashlib.sha256(p.read_bytes()).hexdigest(),
            p.stat().st_mtime_ns,
        )
        for p in root.rglob("*")
        if p.is_file()
    }


def test_get_returns_same_persisted_detail_as_web(persisted):
    # Arrange
    from scitex_agentic_journal._django._leaf import get_submission_summary

    home = persisted.record_dir.parent.parent
    expected = {
        **get_submission_summary(persisted.submission_id, home),
        "found": True,
        "placeholder": False,
    }
    # Act
    actual = get_submission(persisted.submission_id, home=home)
    # Assert
    assert actual == expected


def test_not_found_does_not_create_archive(tmp_path):
    # Arrange
    home = tmp_path / "absent"
    # Act
    result = get_submission("missing", home=home)
    # Assert
    assert (result, home.exists()) == (
        {"submission_id": "missing", "found": False},
        False,
    )


@pytest.mark.parametrize(
    "value", ["../other", "/etc/passwd", "", "a/b", ".", "x" * 129]
)
def test_invalid_identifier_is_refused(tmp_path, value):
    # Arrange
    home = tmp_path / "absent"
    # Act
    # Assert
    with pytest.raises(ValueError, match="Invalid journal submission identifier"):
        get_submission(value, home=home)


def test_symlinked_submission_is_not_followed(tmp_path, persisted):
    # Arrange
    home = tmp_path / "other"
    (home / "submissions").mkdir(parents=True)
    (home / "submissions" / "alias").symlink_to(
        persisted.record_dir, target_is_directory=True
    )
    # Act
    actual = get_submission("alias", home=home)
    # Assert
    assert actual == {"submission_id": "alias", "found": False}


def test_actual_mcp_lists_only_identifier_parameter(tmp_path):
    # Arrange
    server = build_fastmcp_server(home=tmp_path)

    async def discover():
        async with Client(server) as client:
            return await client.list_tools()

    # Act
    tool = next(t for t in asyncio.run(discover()) if t.name == "aj_get_submission")
    # Assert
    assert (
        set(tool.model_dump(by_alias=True)["inputSchema"]["properties"]),
        tool.model_dump(by_alias=True)["inputSchema"]["required"],
        tool.annotations.model_dump(by_alias=True)["readOnlyHint"],
    ) == ({"submission_id"}, ["submission_id"], True)


def test_actual_mcp_reads_persisted_record(persisted):
    # Arrange
    server = build_fastmcp_server(home=persisted.record_dir.parent.parent)
    # Act
    result = _call(
        server, "aj_get_submission", {"submission_id": persisted.submission_id}
    )
    # Assert
    assert result.data["has_gate1"] is True


def test_actual_mcp_does_not_modify_persistence(persisted):
    # Arrange
    home = persisted.record_dir.parent.parent
    server = build_fastmcp_server(home=home)
    before = _snapshot(home)
    # Act
    _call(server, "aj_get_submission", {"submission_id": persisted.submission_id})
    # Assert
    assert _snapshot(home) == before


def test_unimplemented_tools_are_not_advertised(tmp_path):
    # Arrange
    server = build_fastmcp_server(home=tmp_path)

    async def discover():
        async with Client(server) as client:
            return await client.list_tools()

    # Act
    names = [tool.name for tool in asyncio.run(discover())]
    # Assert
    assert names == ["aj_get_submission"]


def test_actual_mcp_not_found_does_not_create_home(tmp_path):
    # Arrange
    home = tmp_path / "absent"
    server = build_fastmcp_server(home=home)
    # Act
    result = _call(server, "aj_get_submission", {"submission_id": "missing"})
    # Assert
    assert (result.data, home.exists()) == (
        {"submission_id": "missing", "found": False},
        False,
    )


def test_actual_mcp_rejects_path_identifier(tmp_path):
    # Arrange
    from fastmcp.exceptions import ToolError

    server = build_fastmcp_server(home=tmp_path)
    # Act
    # Assert
    with pytest.raises(ToolError, match="Invalid journal submission identifier"):
        _call(server, "aj_get_submission", {"submission_id": "../other"})


def test_actual_mcp_cannot_override_operator_home(tmp_path):
    # Arrange
    from fastmcp.exceptions import ToolError

    server = build_fastmcp_server(home=tmp_path / "bound")
    # Act
    # Assert
    with pytest.raises(ToolError):
        _call(
            server,
            "aj_get_submission",
            {"submission_id": "missing", "home": str(tmp_path)},
        )


def test_planned_catalogue_stays_explicitly_unavailable():
    # Arrange
    from scitex_agentic_journal._mcp import tool_catalogue

    # Act
    states = [(tool.name, tool.available) for tool in tool_catalogue()]
    # Assert
    assert (len(states), [name for name, available in states if available]) == (
        15,
        ["aj_get_submission"],
    )
