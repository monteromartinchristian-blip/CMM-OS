# Design — Phase 10 expansion: Mental Health and Neurodivergence domains

**Date:** 2026-08-26
**Status:** Approved design, pending repository application
**Scope:** CMM OS roadmap and Phase 10/11 specifications
**Canonical additions:** `domain:mental-health` and `domain:neurodivergence`

## 1. Decision

CMM OS will add two new canonical Domain Packs at the end of the existing Phase 10 sequence without renumbering any existing subphase:

- **10.52 — Mental Health Domain** → `domain:mental-health`
- **10.53 — Neurodivergence Domain** → `domain:neurodivergence`

`domain:health` remains an independent sibling domain focused on medical and clinical health. It is not the parent namespace or ownership boundary for the two new domains.

The three domains coordinate only through the existing Phase 10 cross-domain contracts, permission intersection, Domain Knowledge Packages, provenance, privacy policies, and shared Cognitive Layer / Agent Runtime infrastructure.

## 2. Why this change is needed

The original Phase 10 prompt reconciliation placed both mental-health and neurodivergence requirements under `domain:health`.

That decision is too broad for the current requirements:

- **Health** is primarily medical and clinical: diagnoses, symptoms, specialists, tests, treatment, medication, clinical documentation, risk and medical follow-up.
- **Mental Health** includes a substantial non-clinical interaction model: emotional support, natural conversation, therapy continuity, processing of therapy sessions, relationship/emotional context, and a warm conversational mode that must not turn every exchange into a clinical assessment.
- **Neurodivergence** has a distinct longitudinal and epistemic workload: TDAH, possible TEA/AACC/TERIA, dysgraphia, developmental history, executive functioning, sensory/social functioning, neuropsychological evaluation, differential reasoning, and explicit certainty states.

Keeping all three inside Health would either make Health excessively broad or force Mental Health and Neurodivergence to inherit clinical behavior where it is inappropriate.

## 3. Stable domain boundaries

### 3.1 Health

Canonical ID: `domain:health`

Owns:

- medical symptoms and diagnoses;
- specialists and appointments;
- laboratory, imaging and other clinical tests;
- treatment plans and medical interventions;
- medication and supplementation;
- clinical chronology;
- medical risk and red flags;
- medical documentation;
- preparation of medical consultations;
- structured clinical records and Notion health documentation.

Health remains authoritative for clinical interpretation, diagnosis status, medical treatment, medication changes, and medical safety boundaries.

### 3.2 Mental Health

Canonical ID: `domain:mental-health`
Canonical profile: `MentalHealthProfile`

Owns:

- emotional wellbeing;
- personal emotional conversation and support;
- therapy continuity;
- therapy-session transcription analysis;
- preparation before therapy;
- processing after therapy;
- emotional state and longitudinal psychological context;
- emotionally relevant decisions;
- emotional meaning of relationships and life events;
- distinguishing facts, interpretations, fears and intuitions;
- detecting loops or over-analysis without pathologizing ordinary conversation;
- conversational warmth and human accompaniment consistent with system safety.

Mental Health must not become a replacement for the Health domain's clinical authority.

It may consume authorized Health projections when psychiatric medication, formal diagnosis, clinical risk, or medical treatment is relevant.

### 3.3 Neurodivergence

Canonical ID: `domain:neurodivergence`
Canonical profile: `NeurodivergenceProfile`

Owns:

- confirmed TDAH information;
- possible / in-evaluation TEA;
- possible / in-evaluation high intellectual abilities;
- possible / in-evaluation ARFID/TERIA;
- dysgraphia and related written-output difficulties;
- developmental history;
- executive functioning;
- sensory functioning;
- academic and functional impact;
- social functioning when interpreted through a neurodevelopmental lens;
- neuropsychological assessments;
- longitudinal evidence and contradictions;
- differential reasoning between neurodevelopmental, emotional, medical and contextual explanations;
- explicit certainty hierarchy such as confirmed / in evaluation / hypothesis / unsupported or ruled out.

Neurodivergence must not diagnose conditions or silently promote hypotheses to facts.

It may consume authorized Health projections for medication, clinical diagnoses and medical data, and authorized Mental Health projections for emotional or therapy context when required.

## 4. Cross-domain ownership rules

No domain duplicates another domain's source of truth.

Examples:

```text
"Concerta seems to increase my anxiety"
Primary: neurodivergence
Supporting: health + mental-health
```

```text
"I want to prepare tomorrow's session with my psychologist"
Primary: mental-health
Supporting: relationships / neurodivergence / health when relevant
```

```text
"My psychiatrist changed my medication"
Primary: health
Supporting: neurodivergence or mental-health according to indication and effects
```

```text
"Could this social difficulty fit TEA or anxiety?"
Primary: neurodivergence
Supporting: mental-health
Health only when clinical documentation or medical treatment is required
```

Cross-domain transfer must always preserve:

- provenance;
- epistemic kind;
- temporal validity;
- uncertainty;
- sensitivity;
- permissions;
- purpose limitation;
- source-domain authority.

A supporting domain must receive only the minimum authorized projection required for the task.

## 5. Impact on Phases 0–9

### 5.1 Phases 0–7

**No implementation change and no reopening.**

These phases provide generic infrastructure: kernel, semantic execution, planning, execution, rollback, technical memory, transformations and validation.

The new domains do not introduce a new operation protocol, execution model, validation engine or persistence mechanism.

### 5.2 Phase 8 — Cognitive Layer

**No implementation change and no reopening.**

Phase 8 explicitly requires Phase 10 domains to provide resources, profiles, rules, permissions, operations and workflows without creating a different Knowledge Model or independent cognitive engine.

The new domains reuse:

- `KnowledgeItem`;
- epistemic kinds;
- provenance;
- temporal scope;
- contradiction detection;
- uncertainty preservation;
- reasoning profiles;
- gap analysis;
- question generation;
- cognitive sessions;
- memory update proposals;
- privacy and sensitivity controls.

No `MentalHealthKnowledgeModel` or `NeurodivergenceKnowledgeModel` may be created.

### 5.3 Phase 9 — Autonomous Agent Runtime

**No implementation change and no reopening.**

Phase 9 explicitly requires future domains to configure the shared Agent Runtime rather than create independent runtimes.

Both new domains must reuse:

- Agent Runtime;
- policy engine;
- approval system;
- action budgets;
- runtime state machine;
- planner adapter;
- registered operations;
- validation;
- recovery;
- checkpoints;
- goal and workflow persistence.

No domain-specific autonomous runtime may be introduced.

## 6. Phase 10 changes

### 6.1 Add 10.52 — Mental Health Domain

The Phase 10 specification must append a full new subphase after 10.51.

Minimum design requirements:

- canonical `DomainDefinition`;
- `MentalHealthProfile`;
- domain-specific entities/resources/rules/operations/workflows;
- explicit conversational behavior constraints;
- therapy-transcript resource handling;
- emotional-context chronology;
- preparation and post-session workflows;
- cross-domain coordination with Relationships, Reflection, Health, Neurodivergence and General;
- sensitive privacy policy;
- Domain Knowledge Package specialization;
- benchmark/evaluation suite;
- domain metrics;
- permission boundaries;
- memory proposal/binding behavior;
- domain trace coverage;
- AT-DP-052 acceptance test.

Mental Health must preserve a distinction between:

- ordinary emotional conversation;
- therapeutic reflection;
- clinical psychiatric information;
- actual immediate safety risk.

It must not medicalize normal emotional conversation by default.

### 6.2 Add 10.53 — Neurodivergence Domain

The Phase 10 specification must append a full new subphase after 10.52.

Minimum design requirements:

- canonical `DomainDefinition`;
- `NeurodivergenceProfile`;
- domain-specific entities/resources/rules/operations/workflows;
- certainty hierarchy;
- developmental and longitudinal chronology;
- assessment/document interpretation;
- differential-overlap analysis;
- medication/treatment chronology through Health-authorized projections;
- cross-domain coordination with Health, Mental Health, University, Relationships and General;
- sensitive privacy policy;
- Domain Knowledge Package specialization;
- benchmark/evaluation suite;
- domain metrics;
- permission boundaries;
- memory proposal/binding behavior;
- domain trace coverage;
- AT-DP-053 acceptance test.

Neurodivergence must never promote screening, self-report, isolated traits or model inference into a confirmed diagnosis.

### 6.3 Update shared Phase 10 catalog surfaces

Without renumbering existing sections, update shared Phase 10 documentation and canonical catalogs so both domains participate in:

- initial/canonical domain lists;
- domain registry examples;
- profile registry;
- domain resolution examples;
- multi-domain composition examples;
- cross-domain examples;
- resource policies;
- permission examples;
- benchmark suites;
- evaluation metrics;
- Knowledge Package specializations;
- privacy policy orientation;
- final completion criteria;
- requirements matrix / DP inventory;
- prompt-preflight mapping;
- closure checklist.

### 6.4 Privacy

Both domains default to:

```text
Mental Health     -> SENSITIVE
Neurodivergence   -> SENSITIVE
```

Remote processing, exports, cross-domain transfers and provider use remain subject to the most restrictive effective policy.

No new privacy engine is introduced.

## 7. Phase 11 impact

Phase 11 architecture remains valid. No new infrastructure layer is required.

The specification must be updated so that all generic platform capabilities recognize the two new canonical domains.

Affected integration surfaces:

- Domain Router;
- Context Resolver;
- domain configuration;
- domain enable/disable controls;
- per-domain privacy and autonomy settings;
- Timeline filters/views;
- Search filters/facets;
- Knowledge Explorer domain filters;
- Memory Workspace domain boundaries;
- Workflow templates and workflow routing;
- model-routing policies;
- model-evaluation suites;
- cost dashboards grouped by domain;
- provider evaluation scoped by domain;
- Knowledge Package export;
- audit records and traces;
- E2E domain-routing tests;
- cross-domain permission/isolation tests.

Existing generic contracts remain unchanged unless implementation proves a real generic contract gap.

### 7.1 Canonical naming cleanup

Phase 11 examples that use a generic or legacy domain name such as:

```text
domain="medical"
```

must use the canonical Health identifier when they mean the existing Health domain:

```text
domain="health"
```

This avoids ambiguity between medical Health and the new Mental Health domain.

This is a documentation/schema-example normalization, not a Phase 8 or Phase 10 compatibility break.

## 8. Public ROADMAP.md changes

The concise public roadmap must:

1. preserve the existing Phase 0–11 sequence;
2. preserve the status of already completed/audited phases;
3. update the Phase 10 domain list to include:
   - `mental-health`;
   - `neurodivergence`;
4. use `parenthood` as the current canonical name instead of the obsolete `nil` label wherever the roadmap still contains the old public list;
5. describe Mental Health and Neurodivergence as independent sibling domains of Health;
6. keep Phase 11 described as consuming Domain Intelligence generically rather than hard-coding the two domains into its architecture.

## 9. Compatibility and migration policy

No stored Health knowledge is automatically migrated to the new domains merely because the domains now exist.

Future migration or reclassification must be explicit, provenance-preserving and supervised.

Rules:

- existing Health records remain valid;
- source-domain history is preserved;
- no silent movement of knowledge;
- no silent change of epistemic kind;
- no silent duplication;
- reclassification creates auditable versions or bindings;
- cross-domain views may expose shared information without changing ownership.

This prevents a roadmap change from rewriting historical knowledge.

## 10. Documentation affected

Expected repository documentation changes:

```text
ROADMAP.md
docs/roadmap/phase-10-domain-intelligence.md
docs/roadmap/phase-11-stable-integrated-platform.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/audits/phase-10.15-prompts-preflight.md
```

Additional reference/acceptance documents may be added following the existing Phase 10 pattern for DP-052 / DP-053 and AT-DP-052 / AT-DP-053.

Phases 0–9 documentation should only be changed if a stale forward-reference names a fixed list of Phase 10 domains. Such a change is documentary only and must not change their closed implementation contracts.

## 11. Testing strategy

The roadmap/spec change itself must verify:

- no existing Phase 10 numbering changes;
- 10.52 and 10.53 are appended after 10.51;
- existing domain IDs remain unchanged;
- both new IDs are unique and canonical;
- Health remains independently addressable;
- public roadmap and detailed Phase 10 spec agree;
- Phase 11 references canonical domain IDs;
- `medical` is not used as a canonical domain ID;
- privacy defaults for both domains are `SENSITIVE`;
- cross-domain rules use explicit permission intersection;
- no Phase 8/9 duplicate engine/runtime is introduced.

Implementation of each new Domain Pack must later receive its own unit, integration, E2E, DP and independent closure audit following the established Phase 10 process.

## 12. Definition of done for this roadmap modification

This roadmap modification is complete when:

1. Phase 10 contains **10.52 Mental Health Domain** and **10.53 Neurodivergence Domain**.
2. No existing Phase 10 subphase has been renumbered.
3. ROADMAP.md lists both domains.
4. `parenthood` replaces stale `nil` references in the current public domain catalog.
5. Phase 11 recognizes both domains through generic routing/configuration/search/timeline/model-evaluation surfaces.
6. Legacy `medical` examples that mean Health are normalized to `health`.
7. Phases 0–9 remain closed and require no implementation changes.
8. Cross-domain ownership and privacy rules are explicit.
9. Documentation and requirements matrices are internally consistent.
10. The subsequent implementation plan treats 10.52 and 10.53 as two independently implementable and independently auditable Domain Packs.

## 13. Non-goals

This change does not:

- reopen Health 10.20;
- rewrite existing Health implementation;
- migrate existing user data;
- create a new Cognitive Layer;
- create a new Agent Runtime;
- change Phase 8 or Phase 9 public contracts;
- renumber Phase 10;
- merge Mental Health with Relationships or Reflection;
- merge Neurodivergence with Health;
- implement the two Domain Packs yet.

The next step after review of this design is a separate implementation plan for the roadmap/specification edits, followed by implementation and validation.
