"""POST handlers — placeholders until M1+ ship.

The handlers are kept separate from :mod:`views` so the auth /
permissions layer can wrap them without touching the read-only
surface. M1 implements ``submit`` only; the rest sit on
:data:`PENDING_HANDLERS` so the URL config can register them and
return a typed 503 (``"not yet implemented"``) instead of 404.
"""

from __future__ import annotations

from typing import Final

from django.http import HttpRequest, JsonResponse

PENDING_HANDLERS: Final[tuple[str, ...]] = (
    "submit",
    "start_review",
    "submit_review",
    "apply_decision",
    "mint_id",
    "publish",
)
"""Names of POST handlers reserved for M1–M5 implementations.

Listed here so docs / dashboards can show "wired but not yet
implemented" rather than 404 / silently 200.
"""


def submit(request: HttpRequest) -> JsonResponse:
    """POST /aj/submit — create a submission record (placeholder).

    Returns HTTP 503 (Service Unavailable) with a typed body until the
    M1 gate-1 plumbing lands. Explicit 503 + reason avoids the silent-
    fallback trap of a 200 with an empty body.
    """
    return JsonResponse(
        {
            "ok": False,
            "reason": "M1 submission gate not yet implemented; track aj-checks / aj-django.",
        },
        status=503,
    )
