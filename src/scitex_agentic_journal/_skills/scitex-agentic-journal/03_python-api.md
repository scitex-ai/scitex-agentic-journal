---
description: |
  [TOPIC] Public Python API
  [DETAILS] Entry points exported by `scitex_agentic_journal` and its `_gate1` / `_orcid` / `_publish` / `_review` / `_ports` / `_django` subpackages.
tags: [scitex-agentic-journal-python-api]
---

# Python API

Stable entry points users (and downstream packages) import from
`scitex_agentic_journal`. Names starting with `_` are internal and
may change without a deprecation cycle; everything below is part of
the public contract.

## Top-level

```python
import scitex_agentic_journal as saj

saj.__version__
```

## Gate-1 (`scitex_agentic_journal._gate1`)

The structural-check surface. No AI in this layer — only HTTP,
subprocess, and shape checks.

```python
from scitex_agentic_journal._gate1 import (
    # Errors
    GateFailure,
    # ORCID resolvability (issue #2 / M1.1)
    verify_orcid, OrcidRecord, ORCID_PUB_API_BASE,
    # Code-repo cloneability (issue #3 / M1.2)
    clone_code_repo, cloned_code_repo, ClonedRepo,
    DEFAULT_CLONE_DEPTH, DEFAULT_CLONE_TIMEOUT_S,
    # Clew DAG verification (issue #4 / M1.3)
    verify_clew_dag, ClewVerification,
    CLEW_MARKER_DIR, DEFAULT_VERIFY_TIMEOUT_S,
)
```

`GateFailure` is the single structured exception every Gate-1 check
raises. Catch it in the orchestrator and print `str(fail)` to give
the operator an actionable message without a Python traceback.

See [12_gate1-checks.md](12_gate1-checks.md) for the contract
satisfied by each function (input shapes, error paths,
no-mock guarantees).

## ORCID utilities (`scitex_agentic_journal._orcid`)

Pure-Python link / URL / parsing helpers — no network unless
explicitly called.

```python
from scitex_agentic_journal._orcid import (
    OrcidClient,
    OrcidLink,
    orcid_url,
)
```

## Ports (`scitex_agentic_journal._ports`)

Protocol surfaces — `Protocol` classes that loosely couple
agentic-journal to its peers. Implementers fulfil one or more of
these to plug a custom Clew / Hub / scheduler / writer / UI into
the pipeline.

```python
from scitex_agentic_journal._ports import (
    ClewPort, ClewClaim, ClewDagSnapshot, ClewVerificationStatus,
    HubPort, HubNotification,
    LivePaperPort, LivePaperBundle,
    PublishReceipt,
    SchedulerPort, ReviewJob,
    UiPort, ManuscriptBundle, SubmissionStatus,
)
```

## Review (`scitex_agentic_journal._review`)

Gate-2 reviewer-agent engine — the ARA rubric, sub-report types,
the in-memory runner, and the Qwen-class adapter stub.

```python
from scitex_agentic_journal._review import (
    ARA_RUBRIC_VERSION, AraRubric, Criticism, Severity,
    ReviewRunner, ReviewRecord, ReviewerAdapter, ReviewSubReport,
    SubReportKind, SubmissionInputs,
    ClaimVerifyReport, MethodologyReport, NoveltyReport,
    QwenAdapterStub, ReproducibilityReport,
)
```

## Publish (`scitex_agentic_journal._publish`)

Gate-4 persistent-ID minting backends (sandbox -> Zenodo -> JaLC)
plus the live-paper hand-off proxy.

```python
from scitex_agentic_journal._publish import (
    PersistentId, MintInput, UnknownBackendError, select_minter,
    InternalIdMinter, CrossrefStub, JalcStub,
    ZenodoStub, ZenodoSandboxStub,
    LivePaperProxy,
)
```

## Django (`scitex_agentic_journal._django`)

Mountable Django app — apps.py / urls.py / views / templates that
plug into `scitex-hub` via `apps/workspace/agentic_journal_app/`.

```python
from scitex_agentic_journal._django import (
    APP_NAME, APP_LABEL, APP_MANIFEST_PATH,
    load_manifest,
)
```

See [30_django-and-hub.md](30_django-and-hub.md) for the manifest
contract and the URL include shape.

## MCP (`scitex_agentic_journal._mcp`)

```python
from scitex_agentic_journal._mcp import (
    AGENT_SCOPES, ALL_SCOPES,
    READ_ONLY_TOOLS, WRITE_TOOLS,
    AuditEntry, AuditLog,
    ScopeDeniedError, TokenScope, ToolKind,
    tool_catalogue,
)
```

The `fastmcp` server itself is a post-MVP target (see issue #6).
The exports above are the introspection surface used by
`scitex-agentic-journal mcp list-tools` today.
