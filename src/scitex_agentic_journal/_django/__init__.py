"""Embedded Django app for the agentic journal.

The standalone package owns the logic + templates; the cloud-side
wrapper (`scitex-cloud / apps/workspace/agentic_journal_app/`) is the
thin shim that registers this app into the SciTeX Hub deployment.

Importing this package itself does **not** require Django to be
installed at the top level; only :func:`scitex_agentic_journal.
_django.apps.get_default_app_config` and the URL / view modules pull
Django in. Tests that don't need a running ORM can therefore exercise
the manifest + URL surface without spinning up Django.

The Django ``default_app_config`` magic is deprecated; Django >=3.2
auto-discovers ``AppConfig`` subclasses. We still expose ``app_label``
through the AppConfig so other Django sites can ``INSTALLED_APPS +=
["scitex_agentic_journal._django"]`` and have URL reverses work
unambiguously.
"""

from __future__ import annotations

from scitex_agentic_journal._django._manifest import (
    APP_LABEL,
    APP_MANIFEST_PATH,
    APP_NAME,
    load_manifest,
)

default_app_config = "scitex_agentic_journal._django.apps.SciTeXAgenticJournalConfig"
"""Legacy hook for very old Django setups; Django >=3.2 doesn't need it."""

__all__ = [
    "APP_LABEL",
    "APP_MANIFEST_PATH",
    "APP_NAME",
    "default_app_config",
    "load_manifest",
]
