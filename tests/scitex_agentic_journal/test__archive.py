"""The public read port does not require Django initialization or mutate storage."""

import subprocess
import sys


def test_public_read_is_django_free(tmp_path):
    # Arrange
    code = """import sys
from pathlib import Path
from scitex_agentic_journal import get_submission
result = get_submission("missing", home=Path(sys.argv[1]))
assert result == {"submission_id": "missing", "found": False}
assert not any(name in sys.modules for name in ("django", "fastmcp", "mcp"))
assert not Path(sys.argv[1]).exists()
"""
    # Act
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )
    # Assert
    assert result.returncode == 0, result.stderr
