"""Structured failures for gate-1 checks.

`GateFailure` is intentionally an exception (not a result type) so that
callers in the submission pipeline can `raise` it on any structural
problem and the orchestrating CLI prints `reason` + `detail` to the
operator without a Python traceback. No silent fallbacks.

Implementation note: ``GateFailure`` is a ``@dataclass`` but is **not**
``frozen``. CPython sets ``__traceback__`` on every exception during
``raise`` / ``contextlib`` exit; a ``frozen=True`` dataclass-exception
trips ``FrozenInstanceError`` inside ``__exit__``. We rely on discipline
(no field reassignment in production) instead of enforced immutability.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=True)
class GateFailure(Exception):
    """A structural gate-1 check failed.

    Parameters
    ----------
    check :
        Short machine-readable check name, e.g. ``"orcid"``,
        ``"code_repo"``, ``"clew_dag"``.
    reason :
        Short human-readable reason, e.g. ``"orcid not resolvable"``.
    detail :
        Longer actionable detail (URL, status code, response excerpt)
        suitable for printing in the CLI.
    """

    check: str
    reason: str
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        head = f"GATE-1 FAIL [{self.check}]: {self.reason}"
        if self.detail:
            return f"{head} -- {self.detail}"
        return head
