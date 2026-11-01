"""SDK-backed Django AppConfig with a source-certifiable identity.

Hub validates plugin identities before Django imports application code, so
name, label, and SDK inheritance must be statically provable declarations.
Django and scitex-sdk are required dependencies; a broken SDK install must
fail explicitly instead of silently disabling its host contracts.
"""

from __future__ import annotations

from scitex_sdk import app as _sdk_app

from scitex_agentic_journal._django._manifest import load_manifest


class SciTeXAgenticJournalConfig(_sdk_app.embed.ScitexAppConfig):
    """Embedded Journal app with stable URL and registry identity."""

    name = "scitex_agentic_journal._django"
    label = "scitex_agentic_journal"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "SciTeX Agentic Journal"

    def ready(self) -> None:
        """Validate the leaf manifest and run required SDK startup hooks."""
        load_manifest()
        super().ready()
