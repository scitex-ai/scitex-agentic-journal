"""Tests for the user-published wrapper-app manifest.

The manifest is the source of truth for the user-published
``scitex_agentic_journal_hub_app``'s shape. The fields must match
what ``scitex-hub app submit`` expects per proj-scitex-hub's spec
(ADR-0002 + ``src/scitex_hub/appmaker/_publish.py`` payload). We
pin every field individually so a future shape drift on the hub side
surfaces here as a real test failure.

One assertion per body (PA-307 §3 STX-TQ001). No mocks.
"""

from __future__ import annotations

from scitex_agentic_journal._hub_app_publisher import (
    HUB_APP_MANIFEST,
    HUB_APP_NAME,
    HUB_APP_VERSION,
    HUB_WRAPPER_MODULE,
)


def test_hub_app_name_is_the_upstream_pip_distribution_name() -> None:
    """Convention agreed with proj-scitex-live-paper (msg fcffcdaa,
    2026-06-13): ``HUB_APP_NAME`` is the upstream pip distribution
    name (with hyphens), NOT the wrapper module name. Invariant
    ``HUB_APP_NAME == HUB_APP_MANIFEST["name"]`` keeps it locked.
    """
    # Arrange
    expected = "scitex-agentic-journal"
    # Act
    name = HUB_APP_NAME
    # Assert
    assert name == expected


def test_manifest_name_equals_hub_app_name_invariant() -> None:
    """The invariant the canonical convention preserves — the manifest
    ``name`` field is the same string as ``HUB_APP_NAME`` so a single
    bump rolls through both."""
    # Arrange
    constant = HUB_APP_NAME
    # Act
    manifest_name = HUB_APP_MANIFEST["name"]
    # Assert
    assert manifest_name == constant


def test_hub_wrapper_module_is_python_safe_form_of_pip_name() -> None:
    """The wrapper's importable Python module name. Derived from the
    pip name with hyphens collapsed to underscores plus the
    ``_hub_app`` suffix per ADR-0002. Kept as its own constant
    because Python module references in entry-points cannot carry
    hyphens, so we can't reuse ``HUB_APP_NAME`` directly."""
    # Arrange
    expected = "scitex_agentic_journal_hub_app"
    # Act
    module = HUB_WRAPPER_MODULE
    # Assert
    assert module == expected


def test_manifest_version_reuses_hub_app_version_constant() -> None:
    # Arrange
    constant = HUB_APP_VERSION
    # Act
    manifest_version = HUB_APP_MANIFEST["version"]
    # Assert
    assert manifest_version == constant


def test_manifest_category_is_app_for_user_published_app_suffix() -> None:
    """``category = 'app'`` triggers ``_apply_app_suffix`` on the hub
    server (per PR #274) so the published wrapper carries the ``_app``
    suffix in its mount slug."""
    # Arrange
    expected = "app"
    # Act
    category = HUB_APP_MANIFEST["category"]
    # Assert
    assert category == expected


def test_manifest_python_requires_mirrors_upstream_constraint() -> None:
    """The wrapper resolves to the same Python range as the upstream
    journal package, so ``pip install`` from the registry never
    drifts on Python version."""
    # Arrange
    expected = ">=3.10"
    # Act
    python_requires = HUB_APP_MANIFEST["python_requires"]
    # Assert
    assert python_requires == expected


def test_manifest_entry_points_points_at_wrapper_url_patterns() -> None:
    """Bare ``module:attr`` target (no leading ``name=`` prefix —
    parity with live-paper PR #44, msg fcffcdaa)."""
    # Arrange
    expected = f"{HUB_WRAPPER_MODULE}.urls:urlpatterns"
    # Act
    entry = HUB_APP_MANIFEST["entry_points"]["scitex_hub.apps"]
    # Assert
    assert entry == expected


def test_manifest_entry_points_exposes_app_config_for_signals_hook() -> None:
    """``scitex_hub.app_config`` is the orthogonal EP key
    proj-scitex-hub confirmed honours an upstream Django ``AppConfig``
    (2026-06-13 EP-shape Q&A relayed via proj-scitex-live-paper
    msg 9102ba02). Bare ``module:attr`` target on the upstream
    module path so the wrapper does not have to redeclare the
    AppConfig.
    """
    # Arrange
    expected = (
        "scitex_agentic_journal._django.apps:SciTeXAgenticJournalConfig"
    )
    # Act
    entry = HUB_APP_MANIFEST["entry_points"]["scitex_hub.app_config"]
    # Assert
    assert entry == expected


def test_manifest_requires_lists_upstream_agentic_journal_package() -> None:
    """The wrapper depends on the upstream journal package so the
    registry installer pulls it in alongside the wrapper."""
    # Arrange
    requires = HUB_APP_MANIFEST["requires"]
    # Act
    has_upstream = any(
        r.startswith("scitex-agentic-journal") for r in requires
    )
    # Assert
    assert has_upstream


def test_manifest_requires_lists_live_paper_dependency() -> None:
    """The wrapper imports live-paper's ``mount`` + ``BundleContext`` so
    the registry installer needs to fetch it too."""
    # Arrange
    requires = HUB_APP_MANIFEST["requires"]
    # Act
    has_live_paper = any(r.startswith("scitex-live-paper") for r in requires)
    # Assert
    assert has_live_paper


def test_manifest_upstream_block_points_at_agentic_journal_package() -> None:
    """``upstream.package`` is the registry dashboard link back to the
    upstream pip-name; MUST match the canonical package name."""
    # Arrange
    expected = "scitex-agentic-journal"
    # Act
    upstream_package = HUB_APP_MANIFEST["upstream"]["package"]
    # Assert
    assert upstream_package == expected


def test_manifest_upstream_module_points_at_hub_app_publisher_module() -> None:
    """``upstream.module`` is the importable path the registry uses
    to surface the upstream helper module in the dashboard."""
    # Arrange
    expected = "scitex_agentic_journal._hub_app_publisher"
    # Act
    upstream_module = HUB_APP_MANIFEST["upstream"]["module"]
    # Assert
    assert upstream_module == expected


def test_manifest_permissions_mirrors_existing_django_app_roles() -> None:
    """Permission list MUST match the existing
    ``_django/manifest.json`` so the dashboard's role gating stays
    consistent between the embedded app and the user-published one."""
    # Arrange
    expected = ["submitter", "reviewer-agent", "editor", "admin"]
    # Act
    permissions = list(HUB_APP_MANIFEST["permissions"])
    # Assert
    assert permissions == expected


def test_manifest_display_name_is_operator_facing_label() -> None:
    # Arrange
    expected = "SciTeX Agentic Journal"
    # Act
    display_name = HUB_APP_MANIFEST["display_name"]
    # Assert
    assert display_name == expected
