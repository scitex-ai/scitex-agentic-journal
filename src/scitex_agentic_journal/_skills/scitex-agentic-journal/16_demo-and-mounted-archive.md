---
description: |
  [TOPIC] Demo records and mounted archive
  [DETAILS] Interpret the shared MNIST example honestly and diagnose the mounted archive without confusing header context with stored submission scope.
tags: [scitex-agentic-journal-demo-and-mounted-archive]
---

# Demo records and mounted archive

The mounted app uses the canonical SDK header and project picker. Its Django
`AppConfig` must have a source-certifiable SDK base and literal app name/label;
from 0.1.0a3 it uses the required SDK directly rather than a conditional Django
fallback. A host's plugin discovery may refuse an unprovable registered owner,
so diagnose the actual source/installed version before treating a missing tile
as a navigation problem.

`_django/_examples.py:load_example_project` reads the shared example's real
Journal `bundle.yaml`, then **constructs** a Gate-1-shaped record, demo accept
decision and reserved `doi:10.5555/example-project-mnist`. It does not execute
ORCID validation, repository validation, Clew verification, review or a DOI
provider. The records carry `example: true` and explicit demo notes; the fixed
submission ID is `example-project-mnist`. Loading again replaces that fixed
demo record. Preserve any unexpected existing content instead of treating its
name as proof it is disposable.

The example path can be supplied through
`SCITEX_AGENTIC_JOURNAL_EXAMPLE_BUNDLE`; otherwise the loader checks process-home
and documented fleet/container corpus locations. A LivePaper render bundle
(directory with PDF and claims) differs from the Journal submission manifest.
Do not substitute one format for the other just because they share a project
name. Placeholder ORCID and registered/demo claims are not scientific evidence.

Mounted `app_page` reads the authenticated user's archive through the generic
host user-home provider; standalone mode retains the explicit journal-home
setting. The app is user-scoped, so its project picker does not filter the
archive or change the host's selected project. See
[30_django-and-hub.md](30_django-and-hub.md) for resolution and fail-closed errors.
A LivePaper port provider or translator does not prove the Journal portal embeds
that viewer.

For GUI verification, use the actual mounted page and installed leaf version,
inspect the SDK header/picker, and distinguish existing user submissions from
labeled demo fixtures. Keep example and UI evidence separate from real gate,
review, claim-verification or publication receipts.
