"""Django AppConfig for the agentic-journal embedded app.

Subclasses :class:`scitex_sdk.app.embed.ScitexAppConfig` when the SDK
is installed (manifest validation, app_version-from-dist, locale
checks); falls back to plain Django ``AppConfig`` where it isn't, so
the leaf stays hub-mountable without the SDK. The fallback never
silently loses validation: :meth:`ready` always runs our own
:func:`load_manifest`, which mirrors the SDK's required-keys +
version-forbidden + scope-enum rules.
"""

from __future__ import annotations

import warnings

from scitex_agentic_journal._django._manifest import (
    APP_LABEL,
    APP_NAME,
    load_manifest,
)

try:
    from scitex_sdk.app.embed import ScitexAppConfig as _BaseConfig
except ImportError:
    from django.apps import AppConfig as _BaseConfig


class SciTeXAgenticJournalConfig(_BaseConfig):
    """Embedded Django app registered as ``scitex_agentic_journal``.

    The label is fixed at :data:`APP_LABEL` so URL reverses
    (``reverse('scitex_agentic_journal:submission-detail', args=[1])``)
    work regardless of how the host project chooses to mount the
    package.
    """

    name = APP_NAME
    label = APP_LABEL
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "SciTeX Agentic Journal"

    def ready(self) -> None:
        """Eager manifest validation — fail loud at process start.

        If the manifest is malformed we want Django to refuse to boot
        rather than serve an empty dashboard later. The base
        ``ready()`` (locale-check registration on the SDK base, no-op
        otherwise) runs guarded: a skewed SDK install must not take
        down the host's whole URLconf (measured 2026-08-23 on the
        scholar cutover).
        """
        load_manifest()
        try:
            super().ready()
        except Exception as exc:  # noqa: BLE001 — boot must survive SDK skew
            warnings.warn(
                f"{APP_NAME}: base AppConfig.ready() failed ({exc!r}); "
                "continuing with leaf manifest validation only.",
                RuntimeWarning,
                stacklevel=2,
            )
