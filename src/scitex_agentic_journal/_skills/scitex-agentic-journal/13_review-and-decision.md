---
description: |
  [TOPIC] Gate-2 AI review + Gate-3 editorial decision
  [DETAILS] Reviewer agent surface (reproducibility re-run, claim verify, novelty triangulation, methodology critique) and the rule-based accept/revise/reject engine.
tags: [scitex-agentic-journal-review-and-decision]
---

# 04 · AI review (gate-2) + editorial decision (gate-3)

Gate-2 and gate-3 are the **AI-driven** part of the journal — the reason the package exists. Both are M2/M3 milestones, not yet implemented.

## Gate-2 — AI review

A bundle that passed gate-1 is queued for review by a **reviewer agent** (Spartan / Qwen-class LLM with tool access). The reviewer agent performs four sub-tasks against the bundle:

| Sub-task | What the agent does | Tools it uses |
|----------|---------------------|---------------|
| Reproducibility re-run | Clones the code repo, re-executes the entry-point script in a sandbox, verifies each claim's `VerificationStatus` re-derives green | sandboxed shell, Clew CLI |
| Claim verification | For each claim in `claims.yaml`, runs `clew claim verify <id>` and records the actual `Evidence` it observed vs. the manifest | Clew Python API |
| Novelty triangulation | Searches `scitex-scholar` for ≥ 10 nearest-neighbour papers per top-level claim, summarises overlap and lists prior art the manuscript missed | Scholar search MCP |
| Methodology critique | Reads `manuscript/main.tex`, lists methodological weaknesses (stats, controls, sample size, confound handling) with section/line references | LaTeX parser, structured prompt |

Each sub-task emits a typed `ReviewSubReport`. The four sub-reports are persisted as the **review record** under the submission's ID.

### Prompts

Reviewer agent prompts are versioned under `_review/prompts/v1/`:

```
_review/prompts/v1/
├── reproducibility.md
├── claim_verify.md
├── novelty.md
└── methodology.md
```

Prompt updates are immutable releases — `v1`, `v2`, ... — never edited in place. The review record records which prompt version was used so decisions are reproducible.

### Reviewer agent endpoint

Pluggable adapter pattern. M2 ships **one** adapter (Qwen via SciTeX's hosted endpoint); the interface is stable for swapping in Spartan / GPT-OSS / Claude / etc.:

```python
class ReviewerAdapter(Protocol):
    def run_review(self, bundle: Submission, prompts_version: str) -> ReviewRecord: ...
```

## Gate-3 — Editorial decision

Editorial decision is **rule-based** over the review record. No LLM "decides" the outcome — the rules are auditable code:

```
accept   ⇐ reproducibility.passed
       ∧  all top-level claims verified GREEN by the reviewer
       ∧  novelty.overlap_score < threshold
       ∧  methodology.criticisms.severity ≤ "minor"

revise   ⇐ accept-criteria not met
       ∧  at least one criticism is "major"
       ∧  no criticism is "fatal"

reject   ⇐ any criticism is "fatal"
       ∨  reproducibility.failed
       ∨  any top-level claim downgraded to RED
```

Thresholds + severity bands are stored in `_review/decision_rules.yaml` (versioned alongside prompts; bumping rules bumps a decision-rules version).

### Decision record

A `DecisionRecord` captures: which review record, which rules version, which branch of the rule tree fired, and the resulting `accept | revise | reject`. The record is read-only once written and forms the audit trail.

## What gate-2 + gate-3 do NOT do

- **No human reviewer override.** If the rules say `revise`, the system says `revise`. Authors can re-submit; reviewers cannot append opinions.
- **No reviewer identity.** The reviewer agent is a versioned adapter + prompt — not a person. The "reviewer name" in the record is `adapter@version+prompts@version`.
- **No DOI minting.** That's gate-4 ([05_publish-handoff.md](05_publish-handoff.md)).
- **No paper rendering.** That's `scitex-live-paper` ([05_publish-handoff.md](05_publish-handoff.md)).

## Why this design

| Design choice | Reason |
|---------------|--------|
| Four sub-tasks, not one mega-review | Each sub-task has a different prompt + tool set; mixing them produces vague critiques. Separating gives the LLM a tighter brief. |
| Rule-based decision, not LLM-as-editor | An LLM-as-editor turns the journal into a black box. Rule-based decisions over a structured review record are inspectable. |
| Versioned prompts + rules | Two submissions of the same bundle to two different `v` should yield deterministically-different decisions. No silent reviewer drift. |
| Pluggable reviewer adapter | LLM landscape moves fast; locking to one provider would kill the package. |
| Spartan/Qwen first | Open-weights, self-hostable; matches the SciTeX self-hosting principle. |
