"""SciTeX Agentic Journal — ARA-native AI-reviewed open publishing on top of Clew.

Pipeline: submit -> ORCID+code+DAG gate -> AI review (Spartan Qwen) -> internal
persistent ID -> Live Paper.

Status: pre-alpha scaffold. M1 (submission gate) implementation pending.

See README.md for the dependency graph and roadmap.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("scitex-agentic-journal")
except PackageNotFoundError:  # pragma: no cover - source-tree fallback
    # PEP 440 local-segment fallback for in-tree / editable installs that
    # are not yet registered with importlib.metadata. Audit rule PA-203.
    __version__ = "0.0.0+local"


# M4 paper-level re-review badge — agentic-journal → live-paper contract.
# Re-exported at the package top so a hub-side resolver writes
# ``from scitex_agentic_journal import resolve_badge_for_paper`` instead
# of digging into the underscored submodule.
from scitex_agentic_journal._re_review_badge import (
    ReReviewBadge,
    ReReviewStatus,
    resolve_badge_for_paper,
    verdict_to_status,
)

# B-path hub-app-publisher helpers — surfaced at the package top so the
# user-published ``scitex_agentic_journal_hub_app`` wrapper writes
# ``from scitex_agentic_journal import build_hub_resolver, HUB_APP_MANIFEST,
# derive_wrapper_manifest`` instead of digging into the underscored submodule.
from scitex_agentic_journal._hub_app_publisher import (
    HUB_APP_MANIFEST,
    HUB_APP_NAME,
    HUB_APP_VERSION,
    build_hub_resolver,
    derive_wrapper_manifest,
)

__all__ = [
    "HUB_APP_MANIFEST",
    "HUB_APP_NAME",
    "HUB_APP_VERSION",
    "ReReviewBadge",
    "ReReviewStatus",
    "__version__",
    "build_hub_resolver",
    "derive_wrapper_manifest",
    "resolve_badge_for_paper",
    "verdict_to_status",
]
