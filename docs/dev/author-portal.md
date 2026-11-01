# Author portal contract

The leaf owns the author guidance, templates, request handlers and filesystem
records. It uses the SDK header, scope picker and content tabs. The host supplies
authentication, CSRF and a generic `SCITEX_USER_HOME_PROVIDER` callable; the leaf
has no Hub-model dependency or retired `scitex_ui` runtime dependency.

The original guidance covers research criteria, manuscript/evidence preparation,
data access, declarations, intake, review/revision and publication. Its navigation
was informed by [Nature For Authors](https://www.nature.com/nature/for-authors)
and [initial submission](https://www.nature.com/nature/for-authors/initial-submission),
with data-access prompts informed by [PLOS data availability](https://journals.plos.org/plosone/s/data-availability)
and a staged workflow informed by [eLife submission guidance](https://elifesciences.org/about/submit-your-research).
This is original SciTeX guidance, not those publishers' policies, eligibility,
fees, service guarantees or branding.

## Implemented boundaries

- The portal defaults to For authors. The remaining sections are Prepare,
  Submit, Your submissions, Review & revision, and Publication.
- The app is user-scoped. A view does not remember a project or change the host's
  global profile. SDK >=0.3.17 receives the explicit request-local
  `view_scope="user"` picker declaration: a stale global project does not
  become the Journal's selected scope. All projects represents this user's
  archive; individual project options remain disabled by its user-only
  capabilities. Mounted records live below the authenticated host user's home,
  in `.scitex/agentic-journal`. CLI/standalone mode retains its existing explicit
  journal-home override and process-home default.
- A configured provider is authoritative. Missing/invalid/denied mounted storage
  fails closed (503), anonymous mounted requests fail 403, and no shared-home
  fallback or directory creation occurs during discovery.
- Review and decision views read actual persisted records. Missing records return
  404; the portal does not manufacture passing checks. Local deterministic and
  synthetic example records are identified as such.
- Web intake accepts YAML and UTF-8 text only, at most 2 MiB total. The explicit
  action contacts ORCID/Git and invokes Clew. It does not run a reviewer, revise
  a manuscript, mint a DOI or publish a paper. Binary bundles remain a CLI path.
- Passing web intake snapshots assets durably, verifies both copies, rebases all
  recorded paths, and atomically writes Gate-1. Content-derived IDs plus a
  process lock make retries immutable while preserving later assessments.
  Corrupt or changed stored assets cause a conflict, not an overwrite.
- Interrupted persistence may retain an orphan snapshot. There is no automatic
  snapshot cleanup. Revision and publishing remain separately configured CLI /
  operator workflows, not buttons that pretend to complete them.

Source: `_django/_request_home.py`, `_django/_uploads.py`, `_django/views.py`,
`_django/handlers.py`, `_django/_leaf.py` and `_submit/_persist.py`.

## Verification

The temporary-filesystem tests cover authenticated user separation, anonymous
and provider failures, path traversal and aliases, original record reads,
intake cleanup, immutable retries, asset corruption and actual process locking.
Network tests are opt-in and are not required to render or verify this portal.
No real submissions, paid reviews or identifier registrations are used for UI
verification.
