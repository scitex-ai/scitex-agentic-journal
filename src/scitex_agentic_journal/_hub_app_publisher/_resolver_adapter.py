"""Adapter that turns :func:`resolve_badge_for_paper` into a
``mount(resolver=...)`` callable.

live-paper's ``mount(resolver=...)`` (PR #38, _django/_mount.py)
expects a callable with signature::

    (request, paper_id, **url_kwargs) -> BundleContext

The user-published wrapper imports
:func:`build_hub_resolver(load_paper, hub_log_url_template)` and gets
that callable back — no Django code in agentic-journal beyond the
Python adapter shape itself.

Boundary
--------

* We **never** import :mod:`scitex_live_paper` here. The wrapper
  package imports it (it depends on live-paper); we stay pure-Python.
  The :class:`BundleContextFactory` Protocol lets the caller hand the
  ``BundleContext`` factory in as a parameter, so the adapter never
  has to look one up.
* We **do** call :func:`resolve_badge_for_paper` from
  :mod:`scitex_agentic_journal._re_review_badge`; that already returns
  ``Optional[ReReviewBadge]`` without raising.

This module deliberately has zero side effects at import time so the
wrapper can pull it in from any startup path.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol, runtime_checkable

from scitex_agentic_journal._re_review_badge import resolve_badge_for_paper


@runtime_checkable
class PaperLoader(Protocol):
    """The host-supplied "given a paper id, give me the paper bundle"
    callable.

    Typically a closure over the hub's storage / project authz layer.
    The adapter only needs the call shape; the host returns whatever
    its live-paper ``BundleSource.from_resolver`` accepts.
    """

    def __call__(self, paper_id: str, request: Any) -> Any: ...


@runtime_checkable
class BundleContextFactory(Protocol):
    """The live-paper-side ``BundleContext`` constructor the wrapper
    passes in.

    Always the wrapper's bound ``BundleContext`` (from
    ``from scitex_live_paper import BundleContext``). Kept as a
    Protocol parameter so this module has zero live-paper imports.
    The factory MUST accept ``re_review_badge`` as a keyword arg —
    that is the field PR #38 added.
    """

    def __call__(
        self,
        *,
        source: Any,
        paper_state: Any,
        api_base: str,
        options: Any,
        re_review_badge: Any,
    ) -> Any: ...


HubResolver = Callable[..., Any]
"""The shape live-paper's ``mount(resolver=...)`` expects."""


def build_hub_resolver(
    *,
    load_paper: PaperLoader,
    bundle_context_factory: BundleContextFactory,
    bundle_source_factory: Callable[[Callable[[], Any]], Any],
    paper_state_factory: Callable[[str], Any],
    renderer_options_factory: Callable[[], Any],
    hub_log_url_template: str = "/aj/{paper_id}/log/",
) -> HubResolver:
    """Return a ``mount(resolver=...)``-shape callable.

    Parameters
    ----------
    load_paper :
        Host-supplied ``(paper_id, request) -> bundle`` callable. The
        wrapper closes over its project / authz context here. The
        return value is whatever ``BundleSource.from_resolver`` takes.
    bundle_context_factory :
        ``scitex_live_paper.BundleContext`` constructor. Passed in so
        this module stays free of any live-paper import.
    bundle_source_factory :
        ``scitex_live_paper.BundleSource.from_resolver`` callable.
        Same reason as above.
    paper_state_factory :
        Host-supplied ``paper_id -> PaperState`` lookup (typically a
        ``PaperState.from_db`` bound method).
    renderer_options_factory :
        Zero-arg factory for the wrapper's ``RendererOptions``.
        Defaults to ``embed_mode=True`` shape on the hub side, but the
        wrapper decides.
    hub_log_url_template :
        Format string used to build the ``log_url`` passed into the
        badge resolver. The single ``{paper_id}`` slot is replaced
        with the live-paper paper id. Default points at the
        agentic-journal log surface mounted under ``/aj/``.

    Returns
    -------
    A callable ``(request, paper_id, **url_kwargs) -> BundleContext``
    suitable for live-paper's ``mount(resolver=...)``.
    """

    def resolver(request: Any, paper_id: str, **url_kwargs: Any) -> Any:
        # Build the badge first — falsy ``None`` is the contract for
        # "hide the chip", so we never default to a placeholder. The
        # log url template is operator-controlled at wrapper-build
        # time so we don't hard-code a hub URL here.
        log_url: Optional[str] = (
            hub_log_url_template.format(paper_id=paper_id)
            if hub_log_url_template
            else None
        )
        badge = resolve_badge_for_paper(paper_id, log_url=log_url)

        # url_kwargs are forwarded so a resolver that routes on the
        # endpoint can use it; we deliberately discard ours so we do
        # not silently shadow the host's keys.
        del url_kwargs

        return bundle_context_factory(
            source=bundle_source_factory(lambda: load_paper(paper_id, request)),
            paper_state=paper_state_factory(paper_id),
            api_base=request.path.rsplit("/", 1)[0] + "/",
            options=renderer_options_factory(),
            re_review_badge=badge,
        )

    resolver.__name__ = "scitex_aj_hub_resolver"
    resolver.__doc__ = (
        "Resolver returned by "
        "scitex_agentic_journal._hub_app_publisher.build_hub_resolver. "
        "Plug into live-paper mount(resolver=...)."
    )
    return resolver
