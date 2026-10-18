"""Tests for :func:`derive_wrapper_manifest` — upstream ⇒ hub-schema.

Each test pins one mapping the proj-scitex-hub 2026-06-13 agreement
(msg 2a286d5d) calls out, so a future drift on either side surfaces
here first.

One assertion per body (PA-307 §3 STX-TQ001). No mocks.
"""

from __future__ import annotations

from scitex_agentic_journal._hub_app_publisher._derive_wrapper_manifest import (
    DEFAULT_HUB_SCHEMA_VERSION,
    _drop_version_spec,
    _split_description,
    derive_wrapper_manifest,
)
from scitex_agentic_journal._hub_app_publisher._manifest import (
    HUB_APP_MANIFEST,
)


# ---------------------------------------------------------------------------
# Top-level shape
# ---------------------------------------------------------------------------


def test_derive_returns_a_dict() -> None:
    # Arrange
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert isinstance(out, dict)


def test_derive_embeds_default_schema_version_when_not_overridden() -> None:
    # Arrange
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["$schema_version"] == DEFAULT_HUB_SCHEMA_VERSION


def test_derive_honours_explicit_schema_version_override() -> None:
    # Arrange
    expected = "3.0.0-rc1"
    # Act
    out = derive_wrapper_manifest(schema_version=expected)
    # Assert
    assert out["$schema_version"] == expected


def test_derive_name_passes_through_upstream_manifest_name() -> None:
    """``name`` is the hub-server slug — must match upstream verbatim
    so ``_apply_app_suffix`` lands on the right wrapper."""
    # Arrange
    expected = HUB_APP_MANIFEST["name"]
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["name"] == expected


# ---------------------------------------------------------------------------
# display_name → label
# ---------------------------------------------------------------------------


def test_derive_label_defaults_to_upstream_display_name() -> None:
    # Arrange
    expected = HUB_APP_MANIFEST["display_name"]
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["label"] == expected


def test_derive_label_honours_explicit_override() -> None:
    """Wrapper can override the label without forking
    :data:`HUB_APP_MANIFEST` (useful for tenant-branded variants)."""
    # Arrange
    expected = "Journal (Acme branded)"
    # Act
    out = derive_wrapper_manifest(label=expected)
    # Assert
    assert out["label"] == expected


# ---------------------------------------------------------------------------
# description → subtitle + about + description
# ---------------------------------------------------------------------------


def test_derive_description_carries_full_text_into_description() -> None:
    """``description`` field on hub side carries the same full text as
    the upstream — only ``subtitle`` is a derived summary."""
    # Arrange
    expected = HUB_APP_MANIFEST["description"]
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["description"] == expected


def test_derive_about_carries_full_text_too() -> None:
    """``about`` mirrors ``description`` for the workspace dashboard
    long-form panel."""
    # Arrange
    expected = HUB_APP_MANIFEST["description"]
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["about"] == expected


def test_derive_subtitle_defaults_to_first_sentence_of_description() -> None:
    """The first sentence of the upstream description becomes the
    workspace ``subtitle`` — a short blurb suitable for the app card.
    """
    # Arrange
    first_sentence, _ = _split_description(HUB_APP_MANIFEST["description"])
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["subtitle"] == first_sentence


def test_derive_subtitle_honours_explicit_override() -> None:
    # Arrange
    expected = "Custom one-liner for this tenant"
    # Act
    out = derive_wrapper_manifest(subtitle=expected)
    # Assert
    assert out["subtitle"] == expected


def test_split_description_picks_up_to_first_terminator() -> None:
    """The split helper trims through the first ``.``/``!``/``?`` and
    leaves the rest untouched."""
    # Arrange
    text = "Short summary. Longer body sentence two."
    # Act
    first, _ = _split_description(text)
    # Assert
    assert first == "Short summary."


def test_split_description_returns_whole_text_when_no_terminator() -> None:
    # Arrange
    text = "no terminator here"
    # Act
    first, _ = _split_description(text)
    # Assert
    assert first == text


# ---------------------------------------------------------------------------
# python_requires + requires[] → dependencies.python[]
# ---------------------------------------------------------------------------


def test_derive_dependencies_python_first_entry_is_python_constraint() -> None:
    """``dependencies.python[0]`` is the runtime constraint
    (``python>=3.10``-style) so the hub installer pins the right
    interpreter."""
    # Arrange
    expected = "python" + HUB_APP_MANIFEST["python_requires"]
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["dependencies"]["python"][0] == expected


def test_derive_dependencies_python_includes_all_upstream_requires() -> None:
    """Every PEP 508 entry in upstream ``requires[]`` MUST appear in
    the derived ``dependencies.python[]`` — version specs dropped."""
    # Arrange
    expected_packages = {
        _drop_version_spec(r) for r in HUB_APP_MANIFEST.get("requires", [])
    }
    # Act
    out = derive_wrapper_manifest()
    derived = set(out["dependencies"]["python"])
    # Assert: every upstream package name appears in the derived set.
    assert expected_packages.issubset(derived)


def test_derive_strips_version_specs_from_pep508_requires() -> None:
    """``scitex-live-paper>=0.1.0a0`` becomes ``scitex-live-paper``."""
    # Arrange
    # Act
    out = derive_wrapper_manifest()
    packages = out["dependencies"]["python"]
    # Assert: no ``>=`` / ``<=`` / ``==`` characters remain.
    assert not any(any(c in pkg for c in "<>=!~") for pkg in packages[1:])


def test_drop_version_spec_strips_geq() -> None:
    # Arrange
    requirement = "scitex-live-paper>=0.1.0a0"
    # Act
    out = _drop_version_spec(requirement)
    # Assert
    assert out == "scitex-live-paper"


def test_drop_version_spec_passes_bare_name_through() -> None:
    # Arrange
    requirement = "scitex-clew"
    # Act
    out = _drop_version_spec(requirement)
    # Assert
    assert out == "scitex-clew"


# ---------------------------------------------------------------------------
# permissions → privileges
# ---------------------------------------------------------------------------


def test_derive_privileges_mirror_upstream_permissions() -> None:
    """``privileges`` is the hub-side name for our upstream
    ``permissions`` list — same values, same order."""
    # Arrange
    expected = list(HUB_APP_MANIFEST.get("permissions", []))
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert out["privileges"] == expected


# ---------------------------------------------------------------------------
# upstream / category drops (upstream-only metadata)
# ---------------------------------------------------------------------------


def test_derive_does_not_emit_upstream_block() -> None:
    """The hub workspace schema has no ``upstream`` slot — our block
    stays purely upstream-side for pip-package discovery and MUST
    NOT leak into the wrapper's manifest.json."""
    # Arrange
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert "upstream" not in out


def test_derive_does_not_emit_category_field() -> None:
    """``category="app"`` is upstream-only metadata; hub handles the
    ``_app`` suffix at the server side (PR #274's
    ``_apply_app_suffix``), so the output dict carries no
    ``category`` slot."""
    # Arrange
    # Act
    out = derive_wrapper_manifest()
    # Assert
    assert "category" not in out
