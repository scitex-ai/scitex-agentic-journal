"""ApptainerSandbox configuration errors (always on; no container is started)."""

from __future__ import annotations

import pytest
from scitex_agentic_journal._admission import ApptainerSandbox, SandboxError


def test_missing_image_is_refused_before_anything_runs(tmp_path):
    # Arrange
    image = tmp_path / "no-such-image.sif"
    # Act
    call = lambda: ApptainerSandbox(image, run_root=tmp_path)
    # Assert
    with pytest.raises(SandboxError):
        call()
