"""Request-local user archive binding; CLI/home environment remains untouched."""

from __future__ import annotations

from functools import wraps
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils.module_loading import import_string


class JournalAuthenticationRequired(PermissionError):
    """An authenticated request is required for mounted per-user storage."""


class JournalStorageUnavailable(RuntimeError):
    """The configured host storage capability cannot safely resolve this user."""


def request_home(request) -> Path:
    """Resolve the authenticated host user's journal root, or standalone home.

    A configured host provider is authoritative. Failure never falls back to a
    shared service home or global environment override. Discovery creates no
    directory. The provider owns identity/jail validation; this consumer also
    rejects symlink escapes under the returned home.
    """
    cached = getattr(request, "scitex_journal_home", None)
    if cached is not None:
        return cached
    provider = getattr(settings, "SCITEX_USER_HOME_PROVIDER", "")
    mounted = (
        bool(provider)
        or getattr(settings, "SCITEX_APP_MODE", "standalone") != "standalone"
    )
    if mounted:
        if not getattr(getattr(request, "user", None), "is_authenticated", False):
            raise JournalAuthenticationRequired(
                "Sign in to access your journal archive"
            )
        if not provider:
            raise JournalStorageUnavailable("Host user storage provider is required")
        try:
            value = import_string(provider)(request)
        except (
            PermissionDenied,
            ImportError,
            AttributeError,
            OSError,
            ValueError,
            RuntimeError,
            TypeError,
        ) as exc:
            raise JournalStorageUnavailable(
                "Host user storage provider failed"
            ) from exc
        if value is None:
            raise JournalStorageUnavailable(
                "Host user storage provider returned no home"
            )
        try:
            user_home = Path(value)
        except TypeError as exc:
            raise JournalStorageUnavailable(
                "Host provider returned an invalid home"
            ) from exc
        if not user_home.is_absolute() or user_home.resolve() != user_home:
            raise JournalStorageUnavailable(
                "Host user storage provider must return a canonical absolute home"
            )
        home = user_home / ".scitex/agentic-journal"
        if not home.resolve().is_relative_to(user_home):
            raise JournalStorageUnavailable(
                "Journal archive escaped the host user home"
            )
    else:
        from ._leaf import _submission_home

        home = _submission_home()
    request.scitex_journal_home = home
    return home


def journal_request(view):
    """Bind storage once per request and return explicit, fail-closed errors."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            request_home(request)
            return view(request, *args, **kwargs)
        except JournalAuthenticationRequired:
            return JsonResponse({"error": "authentication-required"}, status=403)
        except (JournalStorageUnavailable, OSError):
            return JsonResponse({"error": "journal-storage-unavailable"}, status=503)

    return wrapped
