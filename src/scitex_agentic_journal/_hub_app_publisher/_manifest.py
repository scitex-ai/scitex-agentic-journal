"""Manifest metadata the user-published wrapper hands to ``scitex-hub app submit``.

Per proj-scitex-hub's spec (ADR-0002 + the publishing flow on
``scitex-hub`` develop, see ``src/scitex_hub/_cli/_app/_scaffold.py``
and ``apps_app/views/api_registry.py::api_submit_jwt``), an upstream
Django app published to the hub registry carries the following
manifest shape. We co-locate it here so the published wrapper
(``scitex_agentic_journal_hub_app``) does not invent its own
version-coupled metadata.

The constants are the SOURCE OF TRUTH for the published-app shape; if
the wrapper publishes a different name / version / mount path, those
need updating here too.
"""

from __future__ import annotations

from typing import Any, Final


HUB_APP_NAME: Final[str] = "scitex-agentic-journal"
"""The upstream pip distribution name. Locked to
``HUB_APP_MANIFEST["name"]`` so the constant matches what
``pip install <name>`` resolves and what the hub registry shows in
its app card. Convention agreed cross-package with
``scitex-live-paper`` (msg fcffcdaa, 2026-06-13)."""

HUB_WRAPPER_MODULE: Final[str] = "scitex_agentic_journal_hub_app"
"""The Python module name of the user-published wrapper. Derives
trivially from the pip name (`-` → `_` + ``_hub_app`` suffix). Used
to construct entry-point targets without coupling them to the pip
name's hyphen shape (Python module references cannot contain ``-``)."""

HUB_APP_VERSION: Final[str] = "0.1.0-alpha"
"""Wrapper-app version — bumped independently of the upstream
``scitex-agentic-journal`` Python distribution. Same alpha grade as
the underlying journal package while the M4 contract beds in."""

HUB_APP_DISPLAY_NAME: Final[str] = "SciTeX Agentic Journal"
"""Operator-facing display label shown in the hub app dashboard."""

HUB_APP_DESCRIPTION: Final[str] = (
    "ARA-native AI-reviewed open publishing — reviewer dashboard + "
    "M4 paper-level re-review badge served into scitex-live-paper."
)

HUB_APP_CATEGORY: Final[str] = "app"
"""``scitex-hub app submit --category`` choice. ``app`` is what
ADR-0002 expects for user-published Django apps; it triggers the
``_apply_app_suffix`` helper on the server (per PR #274) so the
mounted slug carries the ``_app`` suffix."""

HUB_APP_PYTHON_REQUIRES: Final[str] = ">=3.10"
"""Mirrors the upstream ``scitex-agentic-journal`` constraint so
``pip install`` from the registry resolves without environment
drift."""


HUB_APP_MANIFEST: Final[dict[str, Any]] = {
    "name": HUB_APP_NAME,
    "version": HUB_APP_VERSION,
    "display_name": HUB_APP_DISPLAY_NAME,
    "description": HUB_APP_DESCRIPTION,
    "category": HUB_APP_CATEGORY,
    "python_requires": HUB_APP_PYTHON_REQUIRES,
    "entry_points": {
        # ``scitex_hub.apps`` is the discovery point the hub uses to
        # find an app's Django URLConf. The target is the wrapper's
        # ``urls`` module — bare ``module:attr`` shape (no leading
        # ``name=`` prefix; the entry-point name is the dict key).
        # parity with live-paper PR #44 (msg fcffcdaa, 2026-06-13).
        "scitex_hub.apps": (
            f"{HUB_WRAPPER_MODULE}.urls:urlpatterns"
        ),
        # ``scitex_hub.app_config`` is the orthogonal EP key —
        # exposes the upstream Django ``AppConfig`` so the hub server
        # can register signals / app-ready hooks without going through
        # the wrapper's URL surface. Lives on the upstream module path
        # (``scitex_agentic_journal._django.apps``) so the wrapper
        # never has to redeclare it.
        "scitex_hub.app_config": (
            "scitex_agentic_journal._django.apps:SciTeXAgenticJournalConfig"
        ),
    },
    "requires": [
        # The wrapper depends on the upstream journal package + on
        # live-paper (for ``mount`` + ``BundleContext``). Both are
        # version-pinned to the alpha line for now.
        "scitex-agentic-journal>=0.1.0a0",
        "scitex-live-paper>=0.1.0a0",
    ],
    "upstream": {
        # Pointer back at the agentic-journal package the wrapper
        # imports. The hub uses this to surface "this user-app is
        # backed by upstream X" links in the dashboard.
        "package": "scitex-agentic-journal",
        "module": "scitex_agentic_journal._hub_app_publisher",
    },
    "permissions": [
        "submitter",
        "reviewer-agent",
        "editor",
        "admin",
    ],
}
"""The manifest payload the user-published wrapper hands to
``scitex-hub app submit``. The wrapper either imports this dict
literally or copies its fields into a JSON file — either way the
canonical values live here so a bump on the upstream side flows
through naturally."""
