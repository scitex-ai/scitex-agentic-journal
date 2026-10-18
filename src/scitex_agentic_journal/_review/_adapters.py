"""Pluggable reviewer-adapter registry — `select_adapter(name)`.

The M2 acceptance criterion is "provider-pluggable behind the SciTeX
provider abstraction (Spartan / Qwen / local)". This module is the
single boundary where the CLI / MCP entry point picks one of the
implementations without learning their import paths.

Add a new adapter by registering it in :data:`ADAPTER_REGISTRY`.
Aliases are deliberately verbose so a typo is caught at command
invocation time instead of silently selecting the wrong provider.
"""

from __future__ import annotations

from typing import Callable

from scitex_agentic_journal._review._local_adapter import LocalDeterministicAdapter
from scitex_agentic_journal._review._qwen_adapter import QwenAdapterStub
from scitex_agentic_journal._review._types import ReviewerAdapter


# Each value is a zero-arg factory so the heavy adapters (Qwen
# session, HTTP client) construct lazily — `select_adapter("qwen")`
# pays the import cost only when actually invoked.
ADAPTER_REGISTRY: dict[str, Callable[[], ReviewerAdapter]] = {
    "local": LocalDeterministicAdapter,
    "local-deterministic": LocalDeterministicAdapter,
    "qwen": QwenAdapterStub,
    "qwen-stub": QwenAdapterStub,
    "qwen-self-hosted": QwenAdapterStub,
}


class UnknownAdapterError(ValueError):
    """Caller named an adapter that is not in :data:`ADAPTER_REGISTRY`."""


def list_adapter_names() -> tuple[str, ...]:
    """Return every registered name in sorted order."""
    return tuple(sorted(ADAPTER_REGISTRY))


def select_adapter(name: str) -> ReviewerAdapter:
    """Return a fresh :class:`ReviewerAdapter` instance for the given name.

    Parameters
    ----------
    name :
        Registered adapter name. Case-sensitive — the registry uses
        kebab-case and provider-shorthand aliases.

    Raises
    ------
    UnknownAdapterError
        Names the caller passed alongside the sorted list of known
        names so they can correct a typo or update their config.
    """
    factory = ADAPTER_REGISTRY.get(name)
    if factory is None:
        raise UnknownAdapterError(
            f"unknown reviewer adapter {name!r}; "
            f"available: {', '.join(list_adapter_names())}"
        )
    return factory()
