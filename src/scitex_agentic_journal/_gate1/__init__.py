"""Gate-1: structural submission checks (ORCID, code repo, Clew DAG).

Gate-1 is the no-AI gate. It is a fast, deterministic, network-only check
that the submission bundle is well-formed and the author can be reached.

Public surface — only what we need today:

- :class:`GateFailure` — structured failure raised by any gate-1 check.
- :func:`verify_orcid` — resolve an ORCID iD against the public ORCID API.
- :func:`clone_code_repo` / :func:`cloned_code_repo` /
  :class:`ClonedRepo` — shallow-clone the author's code repository via
  the real system ``git`` binary.

The orchestrating CLI (``scitex-agentic-journal submit``) wires these
checks together; that wiring is tracked separately under issue #5 (M1 CLI).
"""

from scitex_agentic_journal._gate1._clew_dag import (
    CLEW_MARKER_DIR,
    CLEW_MARKER_DIRS,
    CLEW_STATE_DIR,
    DEFAULT_VERIFY_TIMEOUT_S,
    ClewVerification,
    verify_clew_dag,
)
from scitex_agentic_journal._gate1._code_repo import (
    DEFAULT_CLONE_DEPTH,
    DEFAULT_CLONE_TIMEOUT_S,
    ClonedRepo,
    clone_code_repo,
    cloned_code_repo,
)
from scitex_agentic_journal._gate1._errors import GateFailure
from scitex_agentic_journal._gate1._orcid import (
    ORCID_PUB_API_BASE,
    OrcidRecord,
    verify_orcid,
)

__all__ = [
    "CLEW_MARKER_DIR",
    "CLEW_MARKER_DIRS",
    "CLEW_STATE_DIR",
    "ClewVerification",
    "ClonedRepo",
    "DEFAULT_CLONE_DEPTH",
    "DEFAULT_CLONE_TIMEOUT_S",
    "DEFAULT_VERIFY_TIMEOUT_S",
    "GateFailure",
    "ORCID_PUB_API_BASE",
    "OrcidRecord",
    "clone_code_repo",
    "cloned_code_repo",
    "verify_clew_dag",
    "verify_orcid",
]
