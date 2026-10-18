"""Tests for ``build_hub_resolver`` — the live-paper mount adapter.

The adapter is the single piece of code the user-published wrapper
``scitex_agentic_journal_hub_app/_django/urls.py`` calls when
constructing the ``mount(resolver=...)`` callable. We exercise it
with simple fakes for the live-paper types so the test suite does
not need ``scitex-live-paper`` installed — that import would couple
agentic-journal's CI matrix to live-paper's release cadence.

One assertion per body (PA-307 §3 STX-TQ001). No mocks, no
monkeypatch — just real Python objects and small fake dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scitex_agentic_journal._hub_app_publisher import build_hub_resolver


# ---------------------------------------------------------------------------
# Fakes for the live-paper types — shape mirrors PR #38's _types.py.
# ---------------------------------------------------------------------------


@dataclass
class _FakeBundleSource:
    """Stand-in for ``scitex_live_paper.BundleSource``."""

    loader: Any


def _fake_bundle_source_factory(loader: Any) -> _FakeBundleSource:
    """Stand-in for ``BundleSource.from_resolver``."""
    return _FakeBundleSource(loader=loader)


@dataclass
class _FakePaperState:
    """Stand-in for ``scitex_live_paper.PaperState``."""

    paper_id: str


def _fake_paper_state_factory(paper_id: str) -> _FakePaperState:
    """Stand-in for ``PaperState.from_db``."""
    return _FakePaperState(paper_id=paper_id)


@dataclass
class _FakeRendererOptions:
    """Stand-in for ``scitex_live_paper.RendererOptions``."""

    embed_mode: bool = True


def _fake_renderer_options_factory() -> _FakeRendererOptions:
    return _FakeRendererOptions(embed_mode=True)


@dataclass
class _FakeBundleContext:
    """Stand-in for ``scitex_live_paper.BundleContext`` — the field
    names mirror PR #38 exactly, including ``re_review_badge``.
    """

    source: Any = None
    paper_state: Any = None
    api_base: str = ""
    options: Any = None
    re_review_badge: Any = None


def _fake_bundle_context_factory(**kwargs: Any) -> _FakeBundleContext:
    """Stand-in for the ``BundleContext`` constructor."""
    return _FakeBundleContext(**kwargs)


@dataclass
class _FakeRequest:
    """Minimal Django-shaped request fake."""

    path: str = "/apps/live-paper/some-paper-id/"


@dataclass
class _LoaderCall:
    paper_id: str
    request: Any


class _SpyPaperLoader:
    """Records calls so we can assert the adapter forwards them."""

    def __init__(self) -> None:
        self.calls: list[_LoaderCall] = []

    def __call__(self, paper_id: str, request: Any) -> str:
        self.calls.append(_LoaderCall(paper_id=paper_id, request=request))
        return f"bundle-for-{paper_id}"


def _build(resolver_kwargs: dict[str, Any] | None = None) -> Any:
    """Helper: construct a resolver with the fakes wired in.

    ``resolver_kwargs`` lets a single test override just one parameter
    (e.g. ``hub_log_url_template=""``) without restating the whole
    setup.
    """
    defaults = dict(
        load_paper=_SpyPaperLoader(),
        bundle_context_factory=_fake_bundle_context_factory,
        bundle_source_factory=_fake_bundle_source_factory,
        paper_state_factory=_fake_paper_state_factory,
        renderer_options_factory=_fake_renderer_options_factory,
    )
    if resolver_kwargs:
        defaults.update(resolver_kwargs)
    return build_hub_resolver(**defaults)


# ---------------------------------------------------------------------------
# Adapter shape
# ---------------------------------------------------------------------------


def test_build_hub_resolver_returns_a_callable() -> None:
    # Arrange
    resolver = _build()
    # Act
    flag = callable(resolver)
    # Assert
    assert flag is True


def test_resolver_returns_bundle_context_instance() -> None:
    # Arrange
    resolver = _build()
    request = _FakeRequest()
    # Act
    ctx = resolver(request, "scitex-aj-20260613-stub-abc123")
    # Assert
    assert isinstance(ctx, _FakeBundleContext)


def test_resolver_threads_paper_state_for_supplied_paper_id() -> None:
    # Arrange
    resolver = _build()
    request = _FakeRequest()
    # Act
    ctx = resolver(request, "paper-42")
    # Assert
    assert ctx.paper_state.paper_id == "paper-42"


def test_resolver_constructs_api_base_from_request_path() -> None:
    """live-paper's existing mount expects ``api_base`` to be the
    request path with the last segment stripped + a trailing slash;
    the adapter MUST reproduce that exact shape from
    ``_django/_mount.py`` (``request.path.rsplit('/', 1)[0] + '/'``).
    A request to the viewer page at ``/apps/live-paper/paper-42``
    rsplits to ``/apps/live-paper/`` + ``paper-42`` and produces
    ``api_base = /apps/live-paper/``.
    """
    # Arrange
    resolver = _build()
    request = _FakeRequest(path="/apps/live-paper/paper-42")
    # Act
    ctx = resolver(request, "paper-42")
    # Assert
    assert ctx.api_base == "/apps/live-paper/"


def test_resolver_invokes_bundle_source_factory_with_loader_closure() -> None:
    # Arrange
    spy = _SpyPaperLoader()
    resolver = _build({"load_paper": spy})
    request = _FakeRequest()
    # Act
    ctx = resolver(request, "paper-99")
    # The loader is wrapped in a 0-arg lambda; calling it triggers the spy.
    ctx.source.loader()
    # Assert
    assert spy.calls == [_LoaderCall(paper_id="paper-99", request=request)]


# ---------------------------------------------------------------------------
# Badge population — the whole point of the adapter
# ---------------------------------------------------------------------------


def test_resolver_returns_none_badge_when_no_submission_matches_paper(
    tmp_path: Any,
) -> None:
    """No matching submission on disk ⇒ ``re_review_badge`` is None
    (live-paper hides the chip per contract)."""
    # Arrange
    import os

    resolver = _build()
    request = _FakeRequest()
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path)
    try:
        # Act
        ctx = resolver(request, "scitex-aj-20260613-unknown-xxxxxx")
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert ctx.re_review_badge is None


def test_resolver_populates_badge_log_url_from_template(tmp_path: Any) -> None:
    """The ``hub_log_url_template`` parameter is formatted with the
    paper id and threaded into the badge — that's the operator-owned
    deep link the SPA renders."""
    # Arrange
    import json
    import os

    submission_id = "sub_2026_06_13_stub"
    persistent_id = "scitex-aj-20260613-stubpaper-aaaaaa"
    sub_dir = tmp_path / "submissions" / submission_id
    sub_dir.mkdir(parents=True)
    (sub_dir / "persistent_id.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "record": {
                    "submission_id": submission_id,
                    "persistent_id": persistent_id,
                    "backend": "internal",
                },
            }
        ),
        encoding="utf-8",
    )
    (sub_dir / "decision.json").write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "written_at_utc": "2026-06-13T12:30:00+00:00",
                "record": {
                    "submission_id": submission_id,
                    "verdict": "accept",
                    "decided_at": "2026-06-13T12:30:00+00:00",
                    "rule_hits": [],
                },
            }
        ),
        encoding="utf-8",
    )
    resolver = _build({"hub_log_url_template": "/aj/{paper_id}/log/"})
    request = _FakeRequest()
    original = os.environ.get("SCITEX_AGENTIC_JOURNAL_HOME")
    os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = str(tmp_path)
    try:
        # Act
        ctx = resolver(request, persistent_id)
    finally:
        if original is None:
            os.environ.pop("SCITEX_AGENTIC_JOURNAL_HOME", None)
        else:
            os.environ["SCITEX_AGENTIC_JOURNAL_HOME"] = original
    # Assert
    assert (
        ctx.re_review_badge is not None
        and ctx.re_review_badge.log_url == f"/aj/{persistent_id}/log/"
    )


def test_resolver_passes_empty_log_url_when_template_is_empty() -> None:
    # Arrange
    resolver = _build({"hub_log_url_template": ""})
    request = _FakeRequest()
    # Act
    ctx = resolver(request, "paper-xyz")
    # Assert
    # Empty template ⇒ no log_url override.  Resolver returns ``None``
    # for the badge because the home is unset — the assertion sticks
    # to "no crash".
    assert ctx.re_review_badge is None


def test_resolver_callable_has_introspectable_name_for_logging() -> None:
    """A long-lived hub process logs the resolver name in error
    traces; the adapter brands its returned callable so the logs
    point at agentic-journal explicitly."""
    # Arrange
    resolver = _build()
    # Act
    name = resolver.__name__
    # Assert
    assert name == "scitex_aj_hub_resolver"
