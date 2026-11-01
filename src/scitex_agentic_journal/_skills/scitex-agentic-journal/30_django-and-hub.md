---
description: |
  [TOPIC] Author portal and authenticated archive storage
  [DETAILS] Diagnose the leaf-owned portal, host user-home capability, real record reads and durable uploaded bundles.
tags: [scitex-agentic-journal-django-and-hub]
---

# Author portal and host integration

The package owns `_django/urls.py`, `views.py`, `handlers.py`, the template and
static assets. The host mounts that URL configuration and provides authentication,
CSRF middleware and the generic user-home capability. No Hub models are imported.
The SDK owns the header, scope picker and content-tab chrome.

The manifest is user-scoped (`user: true`, `project: false`). Viewing the portal
never changes the host's selected project. Its sections are For authors, Prepare,
Submit, Your submissions, Review & revision, and Publication. Guidance is not a
claim that a reviewer, DOI provider or publication service has run.

## Storage resolution

`_django/_request_home.py:request_home` is authoritative for every web handler:

- When `SCITEX_USER_HOME_PROVIDER` is configured, import that dotted callable and
  call it with the request. It must return the authenticated user's canonical
  absolute home. Store Journal records under `<home>/.scitex/agentic-journal`.
- A mounted request (`SCITEX_APP_MODE` other than `standalone`) requires the
  provider and authentication. Anonymous requests get 403; missing, denied or
  invalid storage gets 503. Do not fall back to the service account's home.
- In standalone mode without a provider, retain CLI-compatible resolution:
  `SCITEX_AGENTIC_JOURNAL_HOME`, then `~/.scitex/agentic-journal`.

The provider owns user identity/jail validation. The leaf additionally rejects
archive aliases that escape the supplied home and does not create directories
while discovering or listing an empty archive. Never set a process-wide home
from a request or accept a user-home path from browser parameters.

## Record reads

Relative to the mount root:

| Route | Behavior |
|---|---|
| `?section=archive` | This user's persisted submission summaries |
| `submissions/<id>/` | Existing Gate-1/review/decision/identifier availability |
| `submissions/<id>/review/` | Actual `review.json`, or 404 if absent |
| `submissions/<id>/decision/` | Actual `decision.json`, or 404 if absent |
| `submissions/<id>/validator/` | Recorded evidence; never synthetic passing checks |
| `submit/` (POST) | Explicit structural intake of YAML plus UTF-8 text files |
| `examples/example-project-mnist/load/` (POST) | Explicit labeled example records |

IDs are single bounded ASCII components; path traversal and symlinked submission
folders/record files are not followed. These endpoints do not make private
archives public just because a decision says accept. The admin endpoint exposes
no operator actions. Web review execution, revision submission, and publishing
are not implemented actions.

## Uploaded asset lifecycle

`handlers.submit` limits YAML/text uploads to 2 MiB total, stages them privately,
loads the manifest and runs the actual ORCID, Git and Clew checks. It does not
start a paid reviewer. A passing result goes through
`_uploads.persist_uploaded_verdict` before temporary intake is removed:

1. Lock a stable content-derived submission ID across processes.
2. Copy into a unique durable `bundles/` snapshot; independently hash source and
   copy, reject symlinks and changes during copying, and flush the files.
3. Rebase every persisted bundle/Clew path to the snapshot and atomically commit
   `submissions/<id>/gate1.json`.
4. Return an identical retry unchanged only if its fingerprint and stored asset
   checksum still match. Preserve prior review/decision records.

An interrupted record commit can leave an orphan snapshot; no automatic sweeper
is installed. Do not delete snapshots by age or assume they are disposable.
Conflicts return 409; unavailable storage returns 503. Check the archive before
retrying an ambiguous request. Explicit CLI `persist_verdict` keeps its existing
minting behavior; web immutability is enforced by the upload wrapper.

## Offline verification

Run `python -m pytest tests/scitex_agentic_journal/_django
 tests/scitex_agentic_journal/_submit -q` on one line. Tests use real temporary
files, authenticated request identities and locks; network tests remain opt-in.
Do not run real submissions or review providers to verify UI layout.
