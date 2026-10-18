---
description: |
  [TOPIC] Django reviewer dashboard + scitex-hub integration
  [DETAILS] How `_django` is mounted into scitex-hub via apps/workspace/agentic_journal_app, manifest contract, and URL include.
tags: [scitex-agentic-journal-django-and-hub]
---

# 07 · Django app + scitex-hub integration

`scitex-agentic-journal` ships an **embedded Django app** (`scitex_agentic_journal._django`) that is mounted into the SciTeX Hub deployment via a thin wrapper at `apps/workspace/agentic_journal_app/` in `scitex-cloud` (the hub repo).

This is the same `_django` pattern used by `scitex-writer`, `scitex-figrecipe`, and `scitex-todo`: the **standalone package owns the logic + templates**, and the hub repo holds a minimal wrapper that registers it.

> **Status:** planned (M6 — `aj-django` + `aj-cloud-thin-wrap` board cards). Not yet implemented.

## Why `_django` lives in the standalone package, not in scitex-cloud

| Principle | Consequence |
|-----------|-------------|
| `scitex` package = single source of truth | Backend logic lives in the standalone repo, not in Django |
| Django is a thin wrapper | The cloud-side wrapper is `apps.py`-only + URL forwarding |
| Self-hostable everywhere | The reviewer dashboard works in any Django project, not just scitex-cloud |
| One canonical migration history | Migrations live with the standalone package; the hub wrapper only re-exports them |

A user who installs `scitex-agentic-journal` outside scitex-cloud (e.g. into a research-group Django site) gets the same reviewer dashboard with zero extra wiring.

## `_django` sub-package layout (planned)

```
src/scitex_agentic_journal/_django/
├── __init__.py
├── apps.py                  # SciTeXAgenticJournalConfig (default_auto_field, name, label)
├── urls.py                  # /aj/, /aj/<submission_id>/, /aj/<submission_id>/review/
├── views.py                 # Submission detail, review record, decision record (read-only views)
├── handlers.py              # POST /aj/submit (create), POST /aj/<id>/decide (admin-only)
├── manifest.json            # SciTeX Hub app-store manifest (icon, label, mount-point, permissions)
├── models.py                # Submission, ReviewRecord, DecisionRecord, PersistentId
├── migrations/
│   └── 0001_initial.py
├── templates/scitex_agentic_journal/
│   ├── base.html
│   ├── submission_detail.html
│   ├── review_record.html
│   └── decision_record.html
└── static/scitex_agentic_journal/
    └── aj.css
```

## scitex-cloud wrapper (planned, aj-cloud-thin-wrap card)

`apps/workspace/agentic_journal_app/` in scitex-cloud is intentionally small:

```
apps/workspace/agentic_journal_app/
├── __init__.py
├── apps.py                  # AgenticJournalAppConfig — wraps SciTeXAgenticJournalConfig
├── urls.py                  # path("", include("scitex_agentic_journal._django.urls"))
└── tests/
    └── test_mount.py        # smoke: import works, reverse('aj:submission-detail', args=[1]) returns a URL
```

The wrapper exists so the hub's `apps/workspace/__init__.py` registration list stays uniform, so the hub's URL routing knows the mount-point, and so deployment can disable the journal app (e.g. for a hub deploy that doesn't host journal traffic) by simply not registering the wrapper.

The wrapper MUST NOT contain business logic. If it grows beyond URL include + apps.py, that's a smell — push the logic back into `_django` upstream.

## Reviewer dashboard

The dashboard is **read-mostly**:

| Page | Audience | What it shows |
|------|----------|---------------|
| `/aj/` | submitters | Their submissions + status (`gate1-pending`, `under-review`, `decided-accept`, `decided-revise`, `decided-reject`, `published`) |
| `/aj/<id>/` | submitters + public (once published) | Submission detail, current gate, current review status |
| `/aj/<id>/review/` | public (once published) | Full review record (sub-reports, prompts version, adapter version) — transparency |
| `/aj/<id>/decision/` | public (once published) | Full decision record (rules version, firing branch, outcome) — auditability |
| `/aj/admin/` | hub admins | Operator-decision panel (manual override only on `agent-wait` blockers — NOT on accept/reject) |

There is **no** "edit review" page. Reviews are immutable once written; if a reviewer agent run was buggy, the fix is a new prompt version, not editing the record.

## Auth + permissions

- Submission: ORCID-bound; the corresponding-author ORCID is the immutable owner.
- Review: written by the reviewer adapter (no user identity); readable by the submitter and (once published) the public.
- Decision: written by the rules engine; same visibility as review.
- Admin: scitex-hub admin role (re-uses hub auth).

## Why a dashboard at all (vs. CLI-only)

For machine-driven submission this would be unnecessary. The dashboard exists so **human readers** of accepted papers can see the AI review and decision records — which is the whole point of "transparent AI-driven editorial". A black-box journal would defeat the design.
