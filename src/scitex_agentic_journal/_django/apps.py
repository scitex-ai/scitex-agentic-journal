"""Django AppConfig for the agentic-journal embedded app."""

from __future__ import annotations

from django.apps import AppConfig

from scitex_agentic_journal._django._manifest import (
    APP_LABEL,
    APP_NAME,
    load_manifest,
)


class SciTeXAgenticJournalConfig(AppConfig):
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
        rather than serve an empty dashboard later.
        """
        load_manifest()
