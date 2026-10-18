"""B-path scaffold for the user-published ``scitex_agentic_journal_hub_app``.

This subpackage is the agentic-journal-side helper layer the
user-published Django wrapper (``scitex_agentic_journal_hub_app``)
imports. It exists because:

* live-paper's M4 ``mount(resolver=...)`` contract (PR #38) needs a
  resolver callable on every request — that callable belongs to
  agentic-journal (we own the verdict), so the published wrapper
  cannot ship it itself.
* The 2026-06-12 user-published-apps reframe forbids hub-side built-in
  wrappers (PR #257 → #266). Hosts publish per-user apps that mount
  upstream packages; agentic-journal stays the upstream.

We therefore expose two thin helpers here that the published wrapper
can import without copy-pasting agentic-journal code:

* :func:`build_hub_resolver(load_paper, hub_log_url_template)` — wraps
  :func:`scitex_agentic_journal.resolve_badge_for_paper` into the
  shape ``mount(resolver=...)`` expects:
  ``Callable[[HttpRequest, str, ...], BundleContext]``. The published
  wrapper drops it in verbatim.
* :data:`HUB_APP_MANIFEST` — the canonical manifest payload
  ``scitex-hub app submit`` expects. The published wrapper either
  imports this dict or copies its values; either way the upstream
  package keeps the source of truth.

Both helpers are deliberately **lightweight** — no Django imports at
module load (the published wrapper imports Django itself). Tests
construct fakes for ``load_paper`` / ``request`` without touching the
real Django stack.

Status (2026-06-13): pre-alpha. Lands when the operator picks B/C on
the M4 reframe call; until then this module is a draft of the
agentic-journal-side contract. See ``docs/dev/`` for the B-path
manifest spec proj-scitex-hub published.
"""

from __future__ import annotations

from scitex_agentic_journal._hub_app_publisher._derive_wrapper_manifest import (
    DEFAULT_HUB_SCHEMA_VERSION,
    derive_wrapper_manifest,
)
from scitex_agentic_journal._hub_app_publisher._manifest import (
    HUB_APP_MANIFEST,
    HUB_APP_NAME,
    HUB_APP_VERSION,
    HUB_WRAPPER_MODULE,
)
from scitex_agentic_journal._hub_app_publisher._resolver_adapter import (
    BundleContextFactory,
    HubResolver,
    PaperLoader,
    build_hub_resolver,
)

__all__ = [
    "BundleContextFactory",
    "DEFAULT_HUB_SCHEMA_VERSION",
    "HUB_APP_MANIFEST",
    "HUB_APP_NAME",
    "HUB_APP_VERSION",
    "HUB_WRAPPER_MODULE",
    "HubResolver",
    "PaperLoader",
    "build_hub_resolver",
    "derive_wrapper_manifest",
]
