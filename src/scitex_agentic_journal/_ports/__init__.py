"""Adapter ports — :class:`typing.Protocol` boundaries to loosely-coupled neighbours.

`scitex-agentic-journal` deliberately avoids importing the neighbour
packages it integrates with (`scitex-writer`, `scitex-clew`,
`scitex-hub`, `scitex-live-paper`, `scitex-ui`) at runtime. Instead each
neighbour is reached through a :class:`typing.Protocol` declared here.
Two consequences:

* Tests inject in-memory implementations — no network, no Django, no
  Clew sub-process.
* A deployment that disables an integration (e.g. a hub without
  Live-Paper output) simply doesn't wire the corresponding port.

No silent fallback: a port method that needs to fail does so by
raising; it does not return ``None`` to silently pass over an error.
"""

from __future__ import annotations

from scitex_agentic_journal._ports._clew import (
    ClewClaim,
    ClewDagSnapshot,
    ClewPort,
    ClewVerificationStatus,
)
from scitex_agentic_journal._ports._hub import (
    HubNotification,
    HubPort,
)
from scitex_agentic_journal._ports._live_paper import (
    LivePaperBundle,
    LivePaperPort,
    PublishReceipt,
)
from scitex_agentic_journal._ports._scheduler import (
    ReviewJob,
    SchedulerPort,
)
from scitex_agentic_journal._ports._ui import (
    SubmissionStatus,
    UiPort,
)
from scitex_agentic_journal._ports._writer import (
    ManuscriptBundle,
    WriterPort,
)

__all__ = [
    "ClewClaim",
    "ClewDagSnapshot",
    "ClewPort",
    "ClewVerificationStatus",
    "HubNotification",
    "HubPort",
    "LivePaperBundle",
    "LivePaperPort",
    "ManuscriptBundle",
    "PublishReceipt",
    "ReviewJob",
    "SchedulerPort",
    "SubmissionStatus",
    "UiPort",
    "WriterPort",
]
