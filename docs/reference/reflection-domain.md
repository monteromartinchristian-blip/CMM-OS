# Reflection Domain — Reference

## Domain ID

`domain:reflection`

## Status

Phase 10.24 — Implemented, pending independent audit V6.

This is the implementation-side status. Independent audit V1 findings were
remediated (V1-I1..V1-I9, V1-M1). Independent audit V2 findings were
remediated (V2-I1..V2-I5). Independent audit V3 findings were remediated
(V3-I1..V3-I4, V3-M1). Independent audit V4 findings were remediated
(V4-I1, V4-I2, V4-M1). Independent audit V5 identified two findings
(V5-I1, V5-I2); these have been remediated with normalized compositional
classifiers and permanently encoded in
`tests/domains/test_reflection_domain_audit_v5_closure.py`. Audit V6 closure
remains a separate lifecycle event and is not claimed here.

## Overview

The Reflection Domain specializes CMM OS for complex reflection, hypothesis
exploration, organization of ideas, longitudinal comparison, decision review,
and preservation of genuine ambivalence without forcing a single conclusion.

It is a declarative, composable layer over the existing Domain Intelligence
infrastructure. It does **not** create parallel engines, separate storage, or
direct runtime access. It reuses the canonical Entity, Resource, Rule,
Operation, Workflow, Permission, Trace, Memory, Presentation, Resolution, and
Integration contracts.

The phase-10.24 safety posture:

- **Distinct epistemic levels are preserved.** Observation, interpretation,
  belief, hypothesis, counter-hypothesis, uncertainty, and open question are
  never silently promoted: `observation != interpretation != belief != fact`,
  `hypothesis != fact`, `memory != current truth`, `repetition != proof`,
  `correlation != cause`.
- **Open-ended analysis is a valid success state.** A reflection is not
  incomplete because it has no conclusion: multiple hypotheses, ambivalence,
  open questions, conflicting evidence, partial timelines, and missing
  recommendations may all be present in a successful result.
- **Ambivalence is information, not a defect.** Simultaneous opposing
  emotions/needs/beliefs are preserved with their context/time distinctions.
- **Prudent hypotheses stay hypotheses.** Psychological hypotheses are never
  presented as diagnoses; identity hypotheses never become stable identity
  facts; no arbitrary winner is selected.
- **Interest mapping is source-grounded.** One mention is a candidate only;
  duplicates never inflate evidence; model summaries are never independent
  corroboration; interest is never identity or commitment.
- **Persistence is confirmation-gated.** A complete shared confirmation reference
  (traceable id plus a literal-`True` `approved` field) plus independent grounded
  provenance authorizes confirmed persistence; repetition/model inference/memory
  summaries never establish it, and a raw bare `True` is not a complete confirmation.
- **Proposal is never mutation.** `prepare_notion_entry` prepares content only
  (`PREPARATION != EXTERNAL COMMUNICATION`); `review_decision` analyzes only
  (`PROPOSAL != MUTATION`); no decision is ever adopted autonomously.

## Package boundary (14 modules)

Production package `cmm/domains/reflection/` contains exactly these 14 modules:

| Module | Purpose |
|---|---|
| `__init__.py` | public package surface only; no import-time registration |
| `bootstrap.py` | General + Reflection composition via the shared bootstrap |
| `catalog.py` | canonical entities/resources/rules/operations/workflows |
| `definition.py` | immutable `domain:reflection` `DomainDefinition` |
| `integration.py` | validation-first atomic registration with exact rollback |
| `memory.py` | proposal/reference-only memory integration; no store |
| `operations.py` | nine declarative `reflection.*` operations + pure result builders |
| `permissions.py` | high-sensitivity fail-closed permission policy |
| `presentation.py` | certainty-preserving user-facing projections |
| `profile.py` | conservative `ReflectionProfile` over shared cognition |
| `resources.py` | nine shared resource definitions |
| `rules.py` | six canonical rules + pure DP-024 semantic helpers |
| `trace.py` | reference-only trace composition |
| `workflows.py` | six shared-engine workflow definitions |

No Reflection-specific engine, store, registry, resolver, planner, workflow
runtime, memory store, trace store, or external connector exists.

## Catalog (11 entities / 9 resources / 6 rules / 9 operations / 6 workflows)

Entities: `reflection`, `belief`, `value`, `question`, `hypothesis`, `emotion`,
`need`, `conflict`, `identity_narrative`, `decision`, `uncertainty`.

Resources: `user_message`, `conversation`, `note`, `journal_entry`,
`memory_entry`, `relationship_event`, `life_event`, `goal`, `decision`.

Rules: `MultipleHypothesesRule`, `PreserveAmbivalenceRule`,
`BeliefEvidenceRule`, `OpenQuestionRule`, `ReflectionTemporalEvolutionRule`,
`NoForcedConclusionRule`.

Operations: `reflection.structure_reflection`, `reflection.extract_beliefs`,
`reflection.compare_versions`, `reflection.identify_open_questions`,
`reflection.generate_hypotheses`, `reflection.build_personal_timeline`,
`reflection.prepare_notion_entry`, `reflection.generate_summary`,
`reflection.review_decision`.

Workflows: `Structured Reflection`, `Belief Review`,
`Personal Question Exploration`, `Decision Reflection`,
`Identity Narrative Review`, `Longitudinal Reflection Review`.

## Rules and semantics

| Rule | Core guarantee |
|---|---|
| `MultipleHypothesesRule` | retains every plausible explanation; no arbitrary winner; evidence/counterevidence/unknowns preserved |
| `PreserveAmbivalenceRule` | keeps simultaneous conflicting states; no forced reduction; context/time distinctions retained |
| `BeliefEvidenceRule` | separates belief/evidence/counterevidence/experience/interpretation; blocks type promotion |
| `OpenQuestionRule` | keeps questions open when the basis is insufficient or conflicting; no invented answers |
| `ReflectionTemporalEvolutionRule` | compares versions only with grounded chronology; equal timestamps never evolve; input order never supplies time |
| `NoForcedConclusionRule` | permits successful unresolved completion; flags unsupported certainty phrasing |

The canonical reasoning projection is:

```text
source / evidence
  -> observation
  -> interpretation
  -> belief
  -> hypothesis
  -> counter-hypothesis
  -> uncertainty
  -> open question
```

Each level is preserved; nothing is silently promoted.

## Operations

All nine operations use the shared `DomainOperationDefinition` contract with the
`reflection.` namespace. Operations are registered **UNAVAILABLE** (fail-closed)
unless implementations are injected. Pure result builders define the semantic
core of each operation:

- `structure_reflection_result` — sections for observations/beliefs/values/
  emotions/needs/conflicts/hypotheses/uncertainties/open questions; never persists.
- `extract_beliefs_result` — explicit/inferred/uncertain/contradicted preserved;
  inferred beliefs never become facts.
- `compare_versions_result` — grounded chronology only; input order is never
  chronology.
- `identify_open_questions_result` — unresolved questions with explicit reasons;
  no invented answer.
- `generate_hypotheses_result` — multiple prudent hypotheses; no diagnosis;
  no forced winner.
- `build_personal_timeline_result` — timeline proposal; no invented dates;
  unusable dates are reported, never ordered; no timeline mutation.
- `prepare_notion_entry_result` — prepared content only; no connector call,
  no page write, no saved claim.
- `generate_summary_result` — summary preserves uncertainty/ambivalence/open
  questions; certainty is never increased.
- `review_decision_result` — analysis and proposal only; `decision_adopted=False`.

## DP-024 mapping

`AT-DP-024` covers all four DP-024 dimensions with direct executable tests in
`tests/domains/test_reflection_domain_dp024_acceptance.py`:

- **A. Open-ended analysis** — successful unresolved results, multiple
  hypotheses, retained open questions, preserved ambivalence, no forced
  conclusion.
- **B. Prudent hypotheses** — hypothesis != fact, alternatives and
  counterevidence retained, no diagnosis, no unsupported identity certainty.
- **C. Interest mapping grounded in sources** — source-backed candidates, one
  mention is never persistence, duplicates never inflate, contradiction
  retained, model inference never treated as source.
- **D. Confirmed persistence** — candidate != confirmed, memory proposal !=
  memory mutation, only a valid confirmation authorizes persistence, malformed/
  nonliteral authorization fails closed.

Implementation-side evidence is recorded here as candidate ATP-024 evidence;
independent audit closure is a separate lifecycle event.

## Permissions

Reflection is a high-sensitivity domain.

- Autonomous surface is read + memory-read + operation/workflow execution only.
- Denied by default: sensitive inference, sensitive-inference persistence,
  memory write, external search/models/communication, file modification, task
  creation, schedule modification, goal update, export, publication, external
  domain activation, irreversible change, knowledge deletion, permission
  modification, medical/legal/financial decisions/actions/spend.
- Identity inference is restricted: no personality/sexual/political/religious
  identity classification, no attachment/moral-character/fixed-motive labels, no
  mental-health diagnosis.
- Only the literal boolean `True` authorizes any boolean-gated field;
  strings, numerics, collections, and `None` never authorize.
- Most-restrictive permission wins under composition; unknown/malformed
  permission state denies.

## Memory boundary

Reflection uses the shared memory contracts only. It produces memory proposals,
persistence proposals, and references. It never writes semantic memory
silently; every proposal requires confirmation (`requires_confirmation=True`
and no override). A `memory_entry` input is provenance, never automatically
current truth.

## External-action boundary

Phase 10.24 implements no external connectors. `prepare_notion_entry` prepares
content only; it never calls Notion, creates/updates a page, or claims a write.
No calendar/task/message/email/form/purchase mutation occurs.

## Cross-domain boundary

`relationship_event` is consumed only through the existing shared cross-domain
mechanism as a minimal authorized projection (literal-`True` authorization);
no direct Relationships store/state import or merge occurs. Reflection composes
with General through the shared bootstrap; General remains the fallback.
Phase 10.25 Concerns does not exist yet; Reflection has no dependency on
`cmm.domains.concerns`.

## Known deferrals (Phase 11+)

- External Notion connector and write runtime.
- Communication-profile-aware presentation rendering.
- Concerns Domain composition (10.25).
- Interest recommendation engines.
- Any persistent semantic-memory mechanism beyond confirmation-gated proposals.

## Implementation status

Phase 10.24 — Implemented, pending independent audit V3.

Do not mark Complete or audited until an independent audit closes the phase.

## Audit V1 remediation note

Independent audit V1 raised ten findings (V1-I1..V1-I9, V1-M1), now remediated:

- **V1 duplicate/conflict hardening** — same-identity incompatible hypotheses and
  ambivalence records fail closed to unresolved/conflicting with no clean
  ranking; counterevidence is never bypassed by supporting-evidence count.
- **Temporal normalization** — equal-time subgroups stay temporally ambiguous
  (no directional change inside a tied instant); the personal timeline orders by
  normalized UTC instant, never raw ISO text.
- **Source-grounded interest hardening** — the grounded source-kind allowlist
  governs grounding; synthetic/model/memory-summary/unknown kinds and `memory_entry`
  fail closed to non-independent provenance; the top-level evidence state reflects
  actual grounded evidence only.
- **Shared-confirmation persistence** — a candidate pattern becomes confirmed only
  via a complete shared confirmation reference (traceable id + literal-`True`
  `approved`) plus independent grounded provenance; a raw `True` is no longer a
  complete confirmation; model/memory-summary-only provenance is never independent.
- **Strict presentation states** — persistence/decision booleans use literal-state
  normalization (never Python truthiness); `present_state` no longer maps a bare
  boolean to `confirmed`; interest-candidate fields and labels cannot contradict.
- **Diagnosis/certainty boundaries** — a narrow deterministic closed-vocabulary
  boundary flags diagnostic/identity-classifying wording as prohibited/unsafe
  (`no_diagnosis=False`, never presented verbatim); unsupported-certainty and
  forced-conclusion language (incl. multilingual) is detected structurally so
  unresolved reflection cannot be presented as resolved.
- **Shared executable workflow validation** — the shared runtime now evaluates a
  `VALIDATE` node's `wait_condition` fail-closed (true completes, false/unknown/
  missing/malformed fails), making safety gates executable rather than metadata.
- **Strict JSON / malformed-input hardening** — all public helpers/operations emit
  strict JSON (`json.dumps(..., allow_nan=False)`), collapse non-finite floats
  fail-closed, distinguish absent/valid-empty/malformed/grounded, and raise no
  accidental `TypeError` on malformed inputs.

The permanent regression suite is
`tests/domains/test_reflection_domain_audit_v1_closure.py`.