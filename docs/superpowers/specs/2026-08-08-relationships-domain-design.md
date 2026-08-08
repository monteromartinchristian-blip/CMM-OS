# Phase 10.21 — Relationships Domain Design

**Status:** Approved design
**Date:** 2026-08-08

## 1. Purpose

The Relationships Domain specializes CMM OS for analysing and organizing:

- relationships;
- interactions;
- conversations;
- conflicts;
- relational events;
- emotional responses;
- needs;
- expectations;
- commitments;
- boundaries;
- ruptures;
- reconciliations;
- support events;
- relational patterns;
- open relational questions;
- possible courses of action.

Its purpose is to help the user understand relationships without converting interpretations into facts.

The domain must distinguish:

```text
observable behavior
from
interpretation
from
possible function
from
possible origin
from
system hypothesis
```

The Relationships Domain MUST NOT:

- attribute intentions to another person without direct evidence;
- diagnose psychological or psychiatric conditions in third parties;
- represent speculative psychological explanations as facts;
- collapse ambivalent feelings into one interpretation;
- automatically contact another person;
- automatically send messages;
- automatically end or resume relationships;
- automatically change a boundary;
- automatically adopt an important relational decision;
- persist sensitive relational inference without confirmation.

Canonical identity:

```text
domain_id = domain:relationships
kind = personal
sensitivity = high
```

---

## 2. Architectural Principle

Relationships is the third canonical complete Domain Pack after General and Health.

It must reuse the existing shared architecture:

- Resource;
- ResourceProvenance;
- TemporalScope;
- Sensitivity;
- Entity;
- KnowledgeItem;
- KnowledgeRelation;
- Cognitive Profiles;
- Reasoning Rules;
- Agent Runtime;
- approvals;
- DomainDefinition;
- DomainResourceDefinition;
- DomainProfileDefinition;
- DomainOperationDefinition;
- DomainWorkflowDefinition;
- Domain permissions;
- Domain presentation;
- Domain Memory;
- Domain Trace;
- common registries;
- DefaultDomainResolver;
- workflow engine;
- snapshot/rollback infrastructure.

Relationships MUST NOT introduce:

- `RelationshipEntity` class hierarchy;
- `RelationshipEntityStore`;
- `RelationshipKnowledgeStore`;
- `RelationshipMemory`;
- `RelationshipTrace`;
- `RelationshipResolver`;
- `RelationshipRuntime`;
- `RelationshipPlanner`;
- `RelationshipWorkflowEngine`;
- `RelationshipReasoningEngine`;
- parallel relationship registries;
- separate persistent relationship database.

Shared data exists once and may receive Relationships domain bindings.

---

## 3. Canonical Package Boundary

The intended production package is:

```text
cmm/domains/relationships/
    __init__.py
    bootstrap.py
    catalog.py
    definition.py
    integration.py
    memory.py
    operations.py
    permissions.py
    presentation.py
    profile.py
    resources.py
    rules.py
    trace.py
    workflows.py
```

Exactly 14 production modules are expected unless implementation proves a genuine architectural necessity.

Responsibilities:

### `catalog.py`

Single source of truth for the canonical Relationships catalog.

### `definition.py`

Builds the canonical `DomainDefinition`.

### `profile.py`

Builds the canonical `DomainProfileDefinition`.

### `resources.py`

Builds and validates `DomainResourceDefinition` instances.

### `rules.py`

Defines the eight canonical `ReasoningRule` definitions and pure deterministic relationship-analysis helpers.

### `operations.py`

Defines the ten canonical `DomainOperationDefinition` declarations.

### `workflows.py`

Defines the six canonical `DomainWorkflowDefinition` declarations.

### `permissions.py`

Expresses Relationships policy through the shared permission contracts.

### `presentation.py`

Defines the structured Relationships presentation policy.

### `memory.py`

Uses existing Domain Memory views, proposals and bindings only.

### `trace.py`

Uses existing reference-only Domain Trace integration.

### `integration.py`

Performs complete validation-first atomic registration.

### `bootstrap.py`

Builds the standard composed General + Relationships bootstrap.

### `__init__.py`

Provides an explicit, side-effect-free public API.

---

## 4. Canonical Entity Semantics

Exactly 13 semantic entity types:

1. `person`
2. `relationship`
3. `conversation`
4. `interaction`
5. `conflict`
6. `boundary`
7. `need`
8. `emotion`
9. `expectation`
10. `commitment`
11. `rupture`
12. `reconciliation`
13. `support_event`

These are semantic entity types over canonical `Entity` / `KnowledgeItem` contracts.

They are NOT new persistent entity classes.

No `RelationshipEntityStore` is introduced.

Entity references must preserve provenance and temporal scope where applicable.

---

## 5. Canonical Resources

Exactly 8 canonical Relationships resources:

1. `relationships.user_message`
2. `relationships.conversation`
3. `relationships.relationship_event`
4. `relationships.note`
5. `relationships.memory_entry`
6. `relationships.timeline`
7. `relationships.communication`
8. `relationships.personal_reflection`

All Relationships resources are sensitive/high-sensitivity according to the actual current shared `Sensitivity` contracts.

Resources must reuse:

- shared identity;
- provenance;
- temporal scope;
- reliability;
- permissions;
- sensitivity;
- entity bindings.

A resource shared across domains must not be duplicated merely because Relationships consumes it.

`relationships.communication` represents an existing communication or communication context. It does NOT authorize communication execution.

---

## 6. Epistemic Model

Relationships must preserve explicit epistemic distinctions.

### Observed fact

A behavior or event directly evidenced by an authorized resource.

Examples:

- a message was sent;
- a conversation occurred;
- the user reports that a cancellation occurred;
- a person said a quoted or recorded statement.

### Direct statement

Something a person explicitly said or wrote.

### User interpretation

The user's interpretation of a behavior or event.

### System hypothesis

A possible interpretation proposed by CMM OS.

### Possible function

A hypothesis about what function a behavior may serve.

### Possible origin

A hypothesis about why a pattern may exist.

### Unknown

Information not established by the available evidence.

The following promotions are forbidden:

```text
interpretation -> fact
hypothesis -> fact
possible function -> intention
possible origin -> diagnosis
repeated pattern -> certainty
confidence -> fact
user suspicion -> third-party psychological truth
```

Provenance identifies the origin of information.

The mere presence of provenance does NOT upgrade epistemic status.

---

## 7. Behavior / Function / Origin Separation

The implementation must preserve this analytical separation:

```text
observed behavior
        ↓
possible function
        ↓
possible origin
```

Only the first layer may be factual when supported by evidence.

Possible function is explicitly hypothetical unless directly stated by the relevant person/source.

Possible origin is explicitly hypothetical unless represented as a documented direct statement/source claim.

Example:

Observed:

> Person contacted the user three times immediately before requesting help.

Allowed pattern analysis:

> One possible pattern is contact clustered around requests.

Allowed hypothesis:

> A possible function of the contact may be seeking support or resources.

Not allowed as a system fact:

> They only contact the user to use them.

Not allowed:

> They are manipulative.

Not allowed:

> They behave this way because of narcissism, attachment pathology, trauma or a personality disorder.

Repetition across several relationships may increase evidence for a pattern of observations. It does not establish psychological cause.

---

## 8. Third-Party Safety

Hard invariants:

- no third-party psychological diagnosis;
- no psychiatric diagnosis;
- no personality-disorder attribution;
- no unsupported intention attribution;
- no mind-reading presented as fact;
- no autonomous relationship action;
- preserve ambivalence;
- controlled memory;
- no automatic communication.

If an authorized source explicitly contains a diagnosis or intention statement, the system may represent:

```text
source X states Y
```

with provenance.

It must not silently adopt that source statement as system-established fact.

---

## 9. Pure Deterministic Relationship Helpers

The domain uses:

```text
declarative domain
+
pure deterministic helpers
```

It does not introduce a Relationships reasoning engine.

Conceptual helpers:

```text
classify_relationship_statement()
classify_relationship_perspective()
detect_relationship_pattern()
evaluate_boundary_consistency()
separate_emotion_need_expectation()
preserve_relationship_ambivalence()
compare_relationship_options()
```

Exact signatures must follow real repository conventions during implementation.

Helpers must:

- be pure;
- be deterministic;
- perform no IO;
- perform no model calls;
- perform no registry mutation;
- perform no memory persistence;
- use no hidden clock;
- accept temporal context explicitly;
- preserve source references/provenance;
- return structured results;
- never generate psychological diagnoses.

---

## 10. Relationship Statement Classification

The classification layer must distinguish:

- `observed_fact`;
- `direct_statement`;
- `user_interpretation`;
- `system_hypothesis`;
- `possible_function`;
- `possible_origin`;
- `unknown`.

Precedence must ensure that provenance itself cannot upgrade epistemic status.

Example:

```text
"I think he only talks to me when he needs something."
```

must remain:

```text
user_interpretation
```

not:

```text
observed_fact
```

An AI-generated explanation carrying evidence references remains a `system_hypothesis` unless the factual component is separately represented.

---

## 11. Self / Other Perspective

`SelfOtherPerspectiveRule` must preserve:

### Self experience

- user's feeling;
- user's thought;
- user's need;
- user's interpretation.

### Other observable behavior

- directly observed/documented action;
- explicit statement.

### Possible other perspective

- inferred possibility;
- never fact without direct evidence.

### Unknown

- unavailable information.

The system should prefer:

> I cannot establish why they did this.

over fabricating a motivation.

---

## 12. Ambivalence

`AmbivalencePreservationRule` must allow simultaneous contradictory feelings.

Example:

- wants closeness;
- also wants distance;
- misses the person;
- also feels relief without contact.

The system must not force those states into:

> You really want to leave.

or:

> You actually want reconciliation.

unless the user explicitly decides that.

Ambivalence is structured information, not an inconsistency that CMM OS must automatically resolve.

---

## 13. Boundaries

`BoundaryConsistencyRule` analyzes:

- boundary expressed;
- boundary acknowledged;
- boundary applied;
- boundary violated;
- boundary changed;
- contradiction between stated and applied boundary;
- unresolved boundary.

The system may identify inconsistency.

It may not autonomously impose, communicate, withdraw or modify a boundary.

---

## 14. Pattern Detection

`PatternWithoutCertaintyRule` may detect repeated structures such as:

- repeated approach/distance cycles;
- conflict-repair cycles;
- repeated cancellation;
- repeated support asymmetry;
- frequency changes;
- recurring boundary conflict;
- repeated commitment/non-fulfilment.

Every pattern output must retain:

- supporting observation references;
- counterexamples where available;
- temporal range;
- uncertainty;
- hypothesis status.

Pattern detection MUST NOT become psychological profiling.

---

## 15. Canonical Reasoning Rules

Exactly 8 rules:

### 1. `SeparateRelationshipFactInterpretationRule`

Distinguishes:

- what happened;
- what each person said;
- what the user interpreted;
- what interpretation the system proposes.

### 2. `DoNotInferIntentRule`

Prevents unsupported intent attribution.

### 3. `RelationshipTimelineRule`

Orders:

- approaches;
- distancing;
- conflicts;
- repairs;
- frequency changes;
- commitments;
- boundaries.

### 4. `PatternWithoutCertaintyRule`

Allows pattern detection as hypotheses, never automatic fact or cause.

### 5. `EmotionNeedDistinctionRule`

Distinguishes:

- emotion;
- need;
- desire;
- expectation;
- interpretation;
- behavior.

### 6. `BoundaryConsistencyRule`

Analyzes:

- expressed boundaries;
- applied boundaries;
- violations;
- changes;
- contradictions.

### 7. `AmbivalencePreservationRule`

Preserves contradictory feelings and motivations without forcing one reading.

### 8. `SelfOtherPerspectiveRule`

Separates:

- personal experience;
- observable behavior of another person;
- possible other perspective;
- unknown information.

Rule IDs must follow actual CMM OS naming conventions discovered from the repository.

`catalog.py` remains the single source of truth.

---

## 16. Relationships Profile

`RelationshipsProfile` is a normal `DomainProfileDefinition`.

Conservative profile characteristics:

- high sensitivity;
- explicit provenance;
- explicit uncertainty;
- fact/interpretation separation;
- low tolerance for unsupported third-party inference;
- sensitive inference allowed only as visibly labelled hypothesis where policy permits;
- no third-party diagnosis;
- no autonomous personal decision;
- ask only when a missing fact materially changes the analysis;
- preserve ambivalence;
- controlled memory;
- no automatic communication.

No specialized reasoning engine is introduced.

---

## 17. Canonical Operations

Exactly 10 operations:

1. `relationships.build_timeline`
2. `relationships.compare_periods`
3. `relationships.extract_events`
4. `relationships.detect_patterns`
5. `relationships.separate_facts_interpretations`
6. `relationships.identify_needs`
7. `relationships.review_boundaries`
8. `relationships.prepare_conversation`
9. `relationships.generate_relationship_summary`
10. `relationships.track_open_questions`

### `relationships.build_timeline`

Constructs a traceable temporal relationship timeline.

### `relationships.compare_periods`

Compares two relationship periods without assigning psychological cause.

### `relationships.extract_events`

Extracts structured events from authorized resources while preserving provenance.

### `relationships.detect_patterns`

Identifies supported repeated patterns as hypotheses, with references and uncertainty.

### `relationships.separate_facts_interpretations`

Structures observed facts, statements, user interpretations and system hypotheses separately.

### `relationships.identify_needs`

Organizes explicitly reported or cautiously inferred needs. Inferred needs remain hypotheses.

### `relationships.review_boundaries`

Reviews expressed/applied/violated/changed boundaries and contradictions.

### `relationships.prepare_conversation`

Prepares goals, points, questions, boundaries and possible wording.

It NEVER sends the communication.

### `relationships.generate_relationship_summary`

Produces a structured summary preserving epistemic distinctions.

### `relationships.track_open_questions`

Identifies unresolved questions and missing information.

No operation may:

- send a message;
- contact a person;
- block or unblock a person;
- end or start a relationship;
- diagnose a third party;
- change a boundary;
- persist sensitive inference directly.

---

## 18. Operation Execution Model

Canonical invariant:

```text
operation definition != implementation
```

A missing implementation means:

```text
UNAVAILABLE / fail-closed
```

No fake delegates.

Injected implementations must pass the existing canonical public implementation validator before the first registry mutation.

Operation schemas must:

- be closed;
- be semantically distinct;
- define actual required fields;
- use meaningful canonical resources;
- avoid one generic schema copied across operations.

Hard distinctions:

```text
PREPARATION != COMMUNICATION
ANALYSIS != DECISION
PROPOSAL != MUTATION
```

---

## 19. Canonical Workflows

Exactly 6 workflows:

1. Relationship Timeline Analysis
2. Conflict Review
3. Boundary Review
4. Difficult Conversation Preparation
5. Pattern Evolution Review
6. Relationship Decision Support

Canonical IDs must follow repository naming conventions.

---

## 20. Workflow Safety Structure

Conceptual ordering:

```text
load authorized resources
        ↓
classify facts / statements / interpretations
        ↓
apply Relationships profile
        ↓
apply Relationships rules
        ↓
detect gaps / contradictions
        ↓
permitted analysis
        ↓
possible options / questions
        ↓
validation
        ↓
optional memory proposal
        ↓
completion
```

Every analytical operation must transitively depend on the relevant fact/interpretation safety path.

A blocked safety rule must not silently reach normal successful completion.

Memory proposal is OPTIONAL, not a forced terminal for every workflow.

---

## 21. Relationship Timeline Analysis

Purpose:

construct chronology of:

- interactions;
- contact frequency;
- approach;
- distance;
- conflict;
- repair;
- commitments;
- boundaries;
- changes.

Must preserve missing periods and uncertainty.

Must not infer reasons for changes solely from temporal sequence.

---

## 22. Conflict Review

Must separate:

- event;
- each person's explicit statements;
- user experience;
- observable behavior;
- interpretations;
- unresolved facts;
- needs;
- boundaries;
- hypotheses;
- possible next steps.

No automatic assignment of blame, intention or diagnosis.

---

## 23. Boundary Review

Analyzes:

- what boundary was expressed;
- when;
- to whom;
- whether acknowledged;
- observed compliance/non-compliance;
- later modifications;
- contradictions;
- user needs;
- possible actions.

It does not automatically communicate or enforce a boundary.

---

## 24. Difficult Conversation Preparation

May produce:

- objective;
- facts to mention;
- user feelings;
- needs;
- questions;
- boundary options;
- possible wording;
- risks/uncertainties;
- alternatives.

It is PREPARATION only.

It must never:

- send;
- schedule;
- notify;
- contact;
- impersonate the user;
- execute the conversation.

Any later communication operation belongs to another controlled execution layer and requires approval.

---

## 25. Pattern Evolution Review

May compare patterns across periods.

Must preserve:

- supporting observations;
- contradictions;
- counterexamples;
- changes over time;
- uncertainty.

Repeated behavior can strengthen confidence in an observational pattern.

It does NOT establish intent, personality or psychological cause.

---

## 26. Relationship Decision Support — Approved Mode A

This is a hard contractual decision.

Relationship Decision Support is SUPPORT FOR DECIDING.

It is NOT delegated decision-making.

The workflow may:

- enumerate options;
- identify explicit user criteria;
- compare options against those criteria;
- identify consequences and trade-offs;
- identify uncertainties;
- identify reversibility;
- show which option best matches the USER'S EXPLICIT criteria.

It must NOT:

- adopt an option as the user's decision;
- persist the option as decided;
- communicate it;
- execute it;
- represent recommendation as commitment;
- infer that ambivalence is resolved.

Allowed output:

> Option B currently matches 4/5 criteria you explicitly prioritized.

Not allowed:

> You have decided to end the relationship.

Not allowed:

> The correct decision is to end the relationship.

A relational decision becomes explicit only after user confirmation.

Any persistent memory representing the decision requires explicit confirmation.

Examples of relational decisions requiring confirmation:

- ending a relationship;
- resuming contact;
- distancing;
- reconciliation;
- changing a material boundary;
- initiating a difficult conversation;
- making a significant commitment;
- abandoning a relationship goal.

---

## 27. Permissions

Use current shared Domain Permission contracts.

Relationships baseline:

- high sensitivity;
- controlled memory read;
- memory proposal allowed only under current policy;
- memory persistence requires confirmation;
- external search denied by default unless separately authorized by global policy;
- external models denied by default for sensitive relational context;
- sensitive inference limited;
- cross-domain transfer restricted;
- no automatic communication;
- no autonomous relational action.

Hard forbidden semantics:

- third-party diagnosis;
- unsupported intent attribution;
- external communication without approval;
- automatic breakup/contact/reconciliation;
- unconfirmed sensitive-memory persistence;
- unauthorized sensitive cross-domain transfer.

Cross-domain composition:

Relationships may interact with Reflection/Concerns only through explicit scoped domain composition and permissions.

Do NOT create automatic cross-domain sharing.

A supporting domain must never widen the primary domain's permissions.

---

## 28. Presentation

Canonical presentation separates exactly these conceptual sections:

1. `facts`
2. `statements`
3. `emotions`
4. `needs`
5. `interpretations`
6. `hypotheses`
7. `patterns`
8. `contradictions`
9. `open_questions`
10. `possible_actions`

Presentation must preserve:

- provenance;
- temporality;
- uncertainty;
- epistemic category;
- unresolved ambiguity;
- approval requirements.

Presentation must not transform:

```text
possible interpretation
-> fact
```

```text
pattern hypothesis
-> psychological truth
```

```text
possible motive
-> intention
```

```text
possible action
-> decision
```

```text
user-reported statement
-> independently established fact
```

---

## 29. Memory

Reuse Phase 10 Domain Memory contracts.

No `RelationshipMemory` store.

Relationships may:

- request authorized memory views;
- build sensitive update proposals;
- bind proposals using canonical `DomainMemoryProposalBinding`;
- request confirmation.

Relationships must NOT:

- directly persist;
- apply;
- invalidate;
- delete;
- silently store psychological inference.

Important invariant:

An inferred pattern, possible function or possible origin must not be persisted as a stable fact.

If such inference is proposed for memory, it must:

- remain explicitly hypothetical;
- preserve source references;
- require user confirmation;
- remain subject to existing memory validation.

An explicit relational decision also requires user confirmation before memory persistence.

Use only current PUBLIC memory digest/binding helpers.

Do not import private `_...` helpers.

---

## 30. Trace

Reuse Domain Trace.

No `RelationshipTrace`.

Trace remains reference-only.

It may reference:

- domain;
- resources;
- profile;
- rules;
- operations;
- workflows;
- permission decisions;
- approvals;
- memory views;
- proposals;
- result;
- epistemic/safety reason codes where current contracts support them.

Never fabricate IDs.

Never store chain-of-thought.

Never store hidden prompts or secrets.

---

## 31. Standard Bootstrap

The standard Relationships bootstrap must follow the final hardened Health precedent.

It composes:

```text
General
+
Relationships
```

over the SAME registries.

General remains:

```text
fallback_domain = domain:general
```

Relationships is a specialized candidate.

Do NOT configure Relationships itself as fallback.

Do NOT create a `RelationshipResolver`.

Required semantics:

- generic input may resolve General;
- valid Relationships signal may resolve Relationships;
- specialized Relationships beats General when eligible;
- denied/unavailable/unauthorized/disabled Relationships cannot silently fall through to General when global fallback-blocking policy requires `BLOCKED`;
- fresh standard bootstraps are deterministic/equivalent.

---

## 32. Validation-First Atomic Registration

`register_relationships_domain()` must incorporate the final lessons from General 10.19 and Health 10.20 from its FIRST implementation.

All deterministic conflicts that normal `register()` can reject, and that are observable through public APIs, must be prevalidated BEFORE the first mutation.

At minimum:

### Domain

- duplicate Domain definition.

### Profile

- duplicate profile ID;
- existing profile for `domain:relationships`.

### Resources

- canonical resource collisions.

### Rules

- canonical reasoning-rule collisions.

### Operations

- local `DomainOperation` collision;
- nested common `AgentOperation` collision;
- unknown implementation ID;
- `implementation.definition` mismatch;
- invalid `execute` signature.

### Workflows

- local `DomainWorkflow` collision;
- nested common `Workflow` collision;
- invalid workflow definition where deterministically testable.

### Permissions

- policy collision.

### Presentation / other registries

- any deterministic conflict that a later `register()` would reject and that is publicly observable.

Use PUBLIC registry APIs.

Do not inspect private registry internals.

Do not duplicate canonical validators.

Validation-first invariant:

```text
predictable deterministic error
-> zero first-registry mutations
```

Snapshot/rollback remains secondary protection for unexpected runtime failures.

---

## 33. Rollback

After complete prevalidation:

```text
snapshot affected registries
        ↓
perform mutations
        ↓
restore all snapshots on unexpected failure
```

Test restoration across mutation boundaries.

Nested common operation/workflow registry state must also restore correctly.

Retry after failed registration must be clean.

Do not create a Relationships transaction manager.

---

## 34. Resolution

Reuse `DefaultDomainResolver`.

No Relationships-specific resolver.

Relationships resolution relies on declarative domain capabilities/signals consistent with the existing architecture.

Do not hard-code a large psychological keyword classifier into the generic resolver.

General fallback remains generic and domain-agnostic.

High sensitivity influences eligibility through existing global contracts, not through a second resolver.

---

## 35. Clean Public API

Importing:

```python
import cmm.domains.relationships
```

must:

- succeed;
- emit no stdout;
- emit no stderr;
- register nothing;
- mutate no global registry;
- perform no IO;
- perform no network calls;
- perform no model calls;
- perform no persistence;
- perform no bootstrap automatically.

The implementation must test clean import using a BRAND-NEW Python interpreter, following the hardened Health precedent.

---

## 36. Error Handling

Reuse existing typed domain/registry errors.

Do not create a Relationships-specific error hierarchy unless a genuinely new contract requires one.

Semantics:

```text
deterministic invalid registration
-> prevalidation error before mutation
```

```text
unexpected runtime failure
-> rollback
```

```text
epistemic uncertainty
-> structured uncertainty, not exception
```

```text
unsupported intention
-> blocked or hypothesis according to rule semantics
```

```text
third-party diagnosis attempt
-> blocked
```

```text
operation implementation missing
-> unavailable / fail-closed
```

```text
user decision not confirmed
-> candidate / possible action, never adopted decision
```

---

## 37. Testing Contract

Phase 10.21 must have implementation depth equivalent to the FINAL hardened Health Domain, not its initial pre-audit state.

Implementation must cover:

- package audit;
- catalog reconciliation;
- definition;
- resources;
- profile;
- pure relationship helpers;
- all 8 reasoning rules;
- all 10 operations;
- all 6 workflows;
- permissions;
- presentation;
- memory;
- trace;
- integration;
- validation-first adversarial matrix;
- rollback;
- resolver;
- bootstrap;
- public API;
- clean fresh-process import;
- E2E canonical domain behavior.

Required adversarial tests:

### Fact / interpretation

- user interpretation never becomes fact merely because provenance exists;
- system hypothesis never becomes fact through confidence;
- direct statement remains a statement unless independently evidenced.

### Intent

- no direct evidence means intention cannot be established;
- repeated behavior does not prove motive.

### Third-party diagnosis

Attempts to infer narcissism, personality disorder, attachment diagnosis, depression or similar clinical/psychological diagnoses about another person are blocked as system diagnoses.

### Pattern

- repeated events may form a pattern hypothesis;
- counterexamples are preserved;
- pattern does not imply psychological cause.

### Ambivalence

- contradictory feelings coexist;
- system does not force one relational objective.

### Boundary

- contradiction is detectable;
- system does not enforce or change the boundary.

### Decision support

- options are compared;
- explicit criteria are used;
- best-match may be identified;
- no option becomes adopted decision without user confirmation.

### Communication

- `prepare_conversation` may generate preparation;
- it cannot send/contact.

### Memory

- sensitive inference requires confirmation;
- explicit decision requires confirmation;
- no direct persistence.

### Bootstrap

- General + Relationships share registries;
- fallback is General;
- generic request cannot become Relationships through fallback.

### Validation-first

Use a counting `DomainRegistry` spy and prove zero first-registry mutations for every deterministic collision class.

---

## 38. Sensitive Inference

Relationships is explicitly covered by the Domain Permission invariant:

Sensitive inference may be permitted as a labelled hypothesis.

Sensitive inference is distinct from:

- persistence;
- export;
- cross-domain transfer;
- external-model egress.

Permission to ANALYZE does not imply permission to PERSIST, EXPORT or COMMUNICATE.

No third-party diagnosis.

No automatic communication.

No implicit persistence.

---

## 39. Non-Goals

Phase 10.21 does NOT implement:

- psychotherapy;
- clinical mental-health diagnosis;
- personality profiling engine;
- attachment-style diagnostic engine;
- social-network graph store;
- messaging connector;
- email/WhatsApp/Telegram sending;
- contact automation;
- breakup automation;
- reconciliation automation;
- autonomous boundary enforcement;
- relationship scoring or ranking of people;
- surveillance;
- external people search;
- sentiment model/provider;
- own vector store;
- own graph database;
- provider selection;
- UI;
- persistence backend;
- Phase 11 connectors.

---

## 40. Acceptance Criteria

Phase 10.21 is acceptable when:

- `domain:relationships` exists as a complete canonical Domain Pack;
- package contains exactly the approved 14 production modules;
- exactly 13 entity semantics exist;
- exactly 8 resources exist;
- exactly 8 reasoning rules exist;
- exactly 10 operations exist;
- exactly 6 workflows exist;
- `catalog.py` is the single source of truth;
- shared contracts are reused;
- no parallel infrastructure exists;
- fact/interpretation separation is enforced;
- intention is not inferred as fact;
- third-party diagnosis is blocked;
- possible function/origin remains hypothetical;
- ambivalence is preserved;
- patterns preserve uncertainty and evidence;
- boundaries can be reviewed but not autonomously acted upon;
- decision support never adopts a decision;
- relational decisions require confirmation;
- no automatic communication exists;
- sensitive memory is proposal-only plus confirmation;
- trace is reference-only;
- missing operation implementation is fail-closed;
- General remains fallback;
- bootstrap composes General + Relationships on shared registries;
- validation-first occurs before first mutation;
- nested common registries are prevalidated;
- rollback restores full state;
- clean import is verified in a new interpreter;
- focal/domain/global regressions remain green.

---

## 41. Future Considerations — Out of Scope

Record without implementing:

1. Whether some Relationships epistemic helpers should become generic person/claim epistemic helpers after multiple domains demonstrate the same need.
2. Cross-domain Relationships ↔ Reflection / Concerns composition once those domains exist.
3. Phase 11 communications/connectors for approved prepared conversations.
4. Optional model/provider policies for sensitive relationship analysis in Phase 11.

Do not pre-build them now.

---

## 42. Final Hardened Precedent

The implementation must start from the FINAL hardened state of Health, not copy historical Health defects.

Preserve these lessons from the first implementation:

- General is fallback, never the specialized domain;
- compose General + specialized domain on shared registries;
- provenance is not epistemic truth;
- an input boolean alone must never bypass grounding;
- sensitive confirmation cannot be caller-disabled;
- workflows need real dependency/gating semantics;
- memory proposal must not be forced into every workflow;
- PREPARATION is not EXTERNAL communication;
- `proposal_only` is not equivalent to `requires_approval`;
- `required_resources` must be meaningful;
- deterministic helpers must preserve state distinctions;
- validation-first requires adversarial matrix coverage;
- unexpected permission-registry exceptions must propagate;
- use public memory digest APIs;
- clean import must be tested in a fresh interpreter.

---

## 43. Canonical Counts

These counts are contractual:

```text
entities = 13
resources = 8
rules = 8
operations = 10
workflows = 6
```

Any implementation that changes these counts requires an explicit design change before implementation.

---

## 44. Implementation Gate

This document is the canonical Phase 10.21 implementation specification.

Implementation may refine exact Python names, signatures and adapters only where required to match existing repository contracts.

Such refinement MUST NOT change:

- canonical counts;
- domain safety boundaries;
- epistemic distinctions;
- Decision Support Mode A;
- no-third-party-diagnosis rule;
- no-intent-as-fact rule;
- no-automatic-communication rule;
- proposal-only sensitive memory;
- General fallback;
- validation-first atomicity;
- no-parallel-infrastructure constraint.

If implementation discovers a conflict requiring one of those guarantees to change, implementation must stop and request an explicit design decision rather than silently modifying this specification.
