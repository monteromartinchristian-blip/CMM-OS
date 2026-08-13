# Phase 10.23 — Opposition Domain — Frozen Design

**Date:** 2026-08-13
**Phase:** 10.23 — Opposition Domain
**Canonical domain ID:** `domain:oppositions`
**Canonical operation prefix:** `opposition.`
**Target branch:** `feature/phase-10-domain-intelligence`
**Preflight baseline inspected:** `d49f35e`
**Status:** APPROVED DESIGN — FROZEN FOR IMPLEMENTATION AFTER REPOSITORY INTEGRATION CHECK

> This document is the contractual design for Phase 10.23.
> Do not implement from this file until its repository integration is confirmed and the dedicated implementation prompt/plan is issued.

---

## 1. Objective

Implement the canonical CMM OS Opposition Domain without creating a new kernel, cognitive engine, planner, workflow runtime, memory subsystem, permission system, source resolver, temporal engine, cross-domain engine, validation engine, model gateway, scheduler, or external connector.

The domain specializes CMM OS for:

- public competitive examinations / oppositions;
- public bodies and alternative bodies/routes;
- official calls;
- syllabi;
- topics and blocks;
- exam milestones;
- deadlines and requirements;
- merits;
- study plans;
- study progress;
- revision;
- mock exams;
- scores;
- workload and feasibility;
- risks;
- alternative routes;
- strategy review.

The domain must preserve one coherent system:

```text
Same Kernel
Same Cognitive Layer
Same Knowledge Model
Same Agent Runtime
Same Planner
Same Validation System
Same Memory
Same Domain Infrastructure
Same Permission / Approval Infrastructure
Same Cross-Domain Engine
        +
Opposition resources
Opposition profile binding
Opposition rules
Opposition operations
Opposition workflows
Opposition permissions
Opposition presentation
Opposition trace integration
```

---

## 2. Source Requirements

This design must satisfy the repository requirements already recorded for Phase 10.23.

Primary sources:

- `docs/roadmap/phase-10-domain-intelligence.md` — section `10.23 - Opposition Domain`;
- `docs/reference/domain-intelligence-requirements-matrix.md` — `DP-023` / `AT-DP-023`;
- `docs/roadmap/phase-8-cognitive-layer.md` — existing `OppositionProfile`;
- final hardened implementations of:
  - `cmm/domains/general/`;
  - `cmm/domains/health/`;
  - `cmm/domains/relationships/`;
  - `cmm/domains/university/`;
- frozen University design:
  - `docs/superpowers/specs/2026-08-09-university-domain-design.md`;
- University Independent Audit V18 as the current hardened semantic precedent.

`DP-023` requires, at minimum:

```text
versioned strategy and constraints
+
official-source verification
+
milestones and sequencing
+
trade-off analysis
+
realistic study planning
```

The requirements matrix explicitly records:

```text
shared domain infrastructure
external sources deferred
```

Therefore Phase 10.23 implements the domain semantics and the request/permission boundary for official verification. It does not implement a new web connector, scraper, scheduler, browser automation layer, or provider integration.

---

## 3. Repository-Grounded Preflight Decision

The Phase 10.23 preflight inspected the current repository and established:

1. The shared Domain Intelligence infrastructure already exists.
2. General, Health, Relationships, and University use a common 14-module specialized-domain boundary.
3. Domain resources, rules, operations, workflows, memory, permissions, presentation, trace, resolution, composition, validation, and registration already have common contracts and registries.
4. The shared permission architecture already supports:
   - `ExternalSourceRequirement`;
   - `OFFICIAL_ONLY`;
   - capability allow/deny;
   - approval-gated capabilities;
   - inbound/outbound cross-domain policy;
   - source/target domain constraints;
   - sensitivity;
   - scoped approvals.
5. The cross-domain engine already supports typed source-domain → target-domain transfers and permission-aware context construction.
6. University already demonstrates the hardened pattern for minimal authorized Health constraint projection.
7. No generic shared implementation equivalent to University's deep academic source-authority/deadline helpers was found outside University.
8. That does **not** justify pre-emptive extraction/refactoring. Opposition must first implement its own domain semantics on shared lower-level contracts.
9. No shared infrastructure blocker was found.

### Frozen preflight conclusion

```text
NO prerequisite shared-infrastructure refactor
NO University → Opposition implementation dependency
NO Health → Opposition implementation dependency
NO new cross-domain engine
NO new permission engine
NO new source engine
NO new temporal engine
NO new external connector

Implement only the specialized Opposition Domain Pack
plus tests/docs strictly required to register and validate it.
```

If implementation later proves a true shared abstraction is missing, the worker must stop and report the concrete duplication/gap before changing shared infrastructure.

---

## 4. Architecture Boundary

Create the specialized package:

```text
cmm/domains/oppositions/
├── __init__.py
├── bootstrap.py
├── catalog.py
├── definition.py
├── integration.py
├── memory.py
├── operations.py
├── permissions.py
├── presentation.py
├── profile.py
├── resources.py
├── rules.py
├── trace.py
└── workflows.py
```

This is the expected shared 14-module boundary.

A repository-grounded exception is allowed only when an existing final domain precedent demonstrates that a different boundary is required. Do not add files merely to make the package look richer.

### Responsibilities

`catalog.py`
- single canonical source of truth for identifiers and exact counts;
- deterministic ordering;
- no runtime side effects.

`definition.py`
- builds the `DomainDefinition`;
- declares canonical domain metadata and dependencies;
- does not register anything globally at import time.

`resources.py`
- builds the 11 resource definitions;
- reuses shared Resource contracts, adapters, provenance and temporal policy;
- creates no resource store.

`profile.py`
- binds `domain:oppositions` to the existing `OppositionProfile` semantics through shared profile contracts/registry;
- creates no cognitive engine.

`rules.py`
- implements exactly six Opposition reasoning rules;
- deterministic/pure where possible;
- no external access.

`operations.py`
- declares exactly ten canonical operation definitions and schemas;
- operations remain behind the shared execution/operation infrastructure.

`workflows.py`
- declares exactly seven canonical workflows;
- uses the shared Workflow Engine and gating/dependency semantics.

`permissions.py`
- declares the domain permission policy only;
- creates no resolver/gate/approval service.

`memory.py`
- supplies the Domain Memory view/policy;
- creates no independent memory store and writes nothing directly.

`presentation.py`
- preserves epistemic/temporal/source/decision distinctions;
- contains no business logic that changes conclusions.

`trace.py`
- integrates references into shared traces;
- creates no parallel trace store.

`integration.py`
- validates all pack components before mutation;
- registers atomically;
- restores exact previous registry state on failure.

`bootstrap.py`
- composes General + Oppositions using shared registries;
- performs explicit bootstrap only when called;
- no import-time registration.

`__init__.py`
- exposes the intentional public Opposition API only;
- does not trigger registration.

---

## 5. Canonical Counts

Phase 10.23 freezes these exact canonical counts:

```text
entities   = 14
resources  = 11
rules      = 6
operations = 10
workflows  = 7
```

These counts are contractual.

Roadmap concepts do not imply one Python class per entity/resource.

The entity list is semantic vocabulary. It must be represented through shared entity/knowledge/resource contracts rather than by introducing a parallel domain model hierarchy.

---

## 6. Canonical Entities

Exactly these 14 semantic entities:

```text
opposition
public_body
call
exam
syllabus
topic
block
mock_exam
score
study_session
deadline
requirement
merit
alternative_route
```

### Entity invariants

- identity must be explicit when identity matters to a conclusion;
- missing identity is not fabricated;
- malformed identity is not treated as absent;
- same-looking labels do not automatically prove same entity;
- entities are represented through shared Cognitive Layer knowledge/entity contracts;
- no Opposition-specific graph database or entity resolver exists;
- `alternative_route` is not equivalent to an adopted target change;
- `call` is temporally/version scoped;
- `syllabus` is version/scoped and may be superseded;
- `requirement` and `merit` must retain source and applicable call/regulation scope when decision-critical.

---

## 7. Canonical Resources

Exactly these 11 resource kinds:

```text
official_call
syllabus
regulation
study_plan
mock_exam
score_record
calendar_event
note
user_message
external_official_source
memory_entry
```

Canonical IDs should follow the current domain convention, e.g.:

```text
oppositions.official_call
oppositions.syllabus
...
```

unless the repository's current final catalog convention requires a mechanically different canonical form.

### Shared-resource principle

`calendar_event`, `note`, `user_message`, `memory_entry`, and external-source content reuse the shared resource/adaptor infrastructure.

Do not duplicate underlying resources merely because Oppositions interprets them differently.

For example:

```text
one calendar event resource
→ General interpretation
→ University interpretation when authorized
→ Oppositions interpretation when authorized
```

not:

```text
three independent calendar records
```

### Resource grounding

Every decision-relevant resource must preserve, where applicable:

- resource/source identity;
- provenance;
- source class;
- temporal scope/status;
- effective/retrieval/publication dates when available;
- applicable public body;
- applicable opposition;
- applicable call/exam;
- version;
- scope;
- supersession/replacement relation when grounded;
- sensitivity;
- permissions.

`provenance != truth`.

A caller-provided label such as `"official": true` must never be sufficient by itself to establish official authority.

---

## 8. Opposition Profile

`OppositionProfile` already exists conceptually in Phase 8 and belongs to the shared profile system.

Phase 10.23 must **bind/configure**, not recreate, that profile.

Required characteristics:

- planning;
- syllabus organization;
- call awareness;
- available workload;
- risks;
- scenarios;
- alternatives;
- review criteria;
- explicit temporal checking for changing official facts;
- source requirement for decision-critical call/regulation facts;
- no unsupported assumption of current requirements;
- preservation of uncertainty;
- bounded questions/gaps through shared Cognitive Layer mechanisms.

Do not implement:

```text
OppositionReasoningEngine
OppositionProfileRegistry
OppositionQuestionEngine
OppositionConfidenceEngine
OppositionContradictionEngine
```

The common Cognitive Layer owns those responsibilities.

General remains the fallback profile/domain when specialization is not justified.

---

## 9. Epistemic Hardening Baseline

Phase 10.23 starts from the hardened lessons of University Audit V18.

The following distinctions are mandatory throughout public helpers and canonical `Rule.evaluate(...)` paths:

```text
absent
!=
valid empty
!=
malformed
!=
unknown
!=
stale
!=
future
!=
conflicting
!=
grounded current
```

Also:

```text
Mapping instance
!=
semantically valid evidence
```

```text
truthy value
!=
authorized True
```

```text
provenance present
!=
fact confirmed
```

```text
newer
!=
more authoritative
```

```text
source claims official status
!=
official source grounded
```

```text
one high score
!=
performance trend
```

```text
time since study
!=
fact of forgetting
```

```text
alternative compared
!=
target abandoned
```

```text
plan proposed
!=
strategy adopted
```

Malformed public input must never widen:

- certainty;
- source authority;
- temporal validity;
- permissions;
- cross-domain access;
- operation availability;
- memory persistence;
- strategy adoption;
- external action.

Unknown/malformed decision-critical evidence fails closed for the affected conclusion/action.

---

## 10. OfficialCallPriorityRule

### Objective

Resolve the authority of opposition-related claims using grounded, attribute-specific, scope-aware evidence.

The rule prioritizes official calls and official sources **for the attributes they actually govern**.

### Attributes may include

- call status;
- application window;
- exam date;
- exam format;
- syllabus version;
- governing regulation;
- eligibility requirement;
- merit rules;
- number/type of exercises;
- scoring rules;
- public body;
- places/positions when relevant;
- official procedural requirements.

### Authority is attribute-specific

There is no naive global ranking that makes one source authoritative for every field.

Example:

```text
specific official call
→ may control its application deadline

current governing regulation
→ may control a general eligibility rule

specific official resolution/publication
→ may control an exam date

personal note
→ may preserve what the user remembers
→ may NOT override an incompatible grounded current official source
```

### Grounding requirements

An authoritative conclusion requires semantically valid evidence including, where relevant:

- usable source identity/reference;
- official source class established through trusted classification/contracts;
- provenance;
- temporal applicability;
- scope;
- supplied/covered attribute;
- value;
- relationship/supersession evidence if used.

A source descriptor missing the semantic fields required for the target attribute remains incomplete.

### Scope

Authority must respect:

- opposition;
- public body;
- call;
- exam;
- requirement;
- applicable period/jurisdiction when represented.

Malformed scope does not become global scope.

Absent scope and malformed scope remain distinct.

### Equal authority

```text
equal top authority + compatible same value
→ corroboration / non-conflicting support

equal top authority + incompatible values
→ unresolved authority conflict
→ preserve all sources
→ trigger verification/gap when material
```

Never choose an arbitrary winner based on input order.

### Supersession

A source may supersede another only when the supersession/replacement relation is grounded and compatible in scope.

A weak source cannot defeat a stronger official source merely by declaring `supersedes`.

Superseded/historical evidence remains traceable.

### Informal sources

Academy material, personal notes, messages, memory and unofficial summaries may:

- provide context;
- identify a question;
- preserve historical/user-reported information;
- suggest what needs verification.

They may not silently override a current grounded official fact.

---

## 11. OppositionTemporalValidityRule

### Objective

Determine whether changing opposition facts are usable for the current decision.

Mandatory temporal targets:

- current call;
- application deadline/window;
- exam date;
- syllabus;
- regulation;
- eligibility requirements;
- merit rules where time/version dependent.

### Temporal states

Implementation may map to current shared enums/contracts, but semantics must preserve at least:

```text
current / applicable
stale / expired / superseded
future / not-yet-applicable
unknown
conflicting
missing
malformed
```

### Invariants

- a bare date string is not automatically a confirmed official deadline;
- current status requires grounding, not caller assertion;
- unknown temporal ordering remains unknown;
- current scope cannot be inferred from recency alone;
- a newer informal note cannot replace a current official source;
- an explicitly expired official source remains historical, not current;
- a future rule cannot be applied as current unless the decision explicitly concerns its future scope;
- decision-critical missing/stale/conflicting/undergrounded facts produce a structured verification need/gap;
- no calendar event is created by this rule.

### Call monitoring semantics

Roadmap language requires monitoring of calls.

In Phase 10.23 this means:

```text
active opposition objective
+
call status/deadline/version is missing, stale, conflicting or due for review
→ structured monitoring / verification requirement
```

It does **not** mean:

- background scheduler;
- polling daemon;
- browser automation;
- push service;
- Phase 11 notification implementation.

Scheduled/continuous monitoring is deferred to Agent Runtime scheduling / Phase 11 integrations after explicit configuration.

---

## 12. SyllabusCoverageRule

### Objective

Evaluate study coverage without collapsing distinct dimensions into one misleading percentage.

The rule considers:

- topics studied;
- topics pending;
- block/topic identity;
- study depth;
- revision state;
- review recency;
- retention/forgetting risk;
- mock-exam evidence when traceably mapped to topics;
- unknown/malformed topic evidence.

### Coverage dimensions

The rule should preserve independent structured dimensions such as:

```text
exposure / studied state
depth
revision state
review due / retention risk
mock-linked evidence
unknown topics
pending topics
```

Exact field names may follow current project conventions.

### Invariants

- aggregate coverage cannot silently override contradictory topic-level evidence;
- duplicate topic identity must not double-count;
- identityless topic records cannot establish complete coverage;
- malformed topic collections remain malformed/unknown;
- a valid empty syllabus/topic list is not the same as absent/malformed input;
- time elapsed may indicate review risk, not prove forgetting;
- a mock score proves neither complete syllabus coverage nor topic mastery unless question/topic mapping supports that conclusion;
- unknown current syllabus version prevents definitive full-coverage claims when material;
- coverage output is analysis, not a promise of exam readiness.

---

## 13. StudyFeasibilityRule

### Objective

Evaluate whether a study strategy is realistic under known constraints and target dates.

Relates:

- time available;
- target date;
- study load;
- syllabus size/remaining work;
- review requirements;
- mock-exam workload;
- energy/functional capacity;
- Health-authorized functional constraints;
- University-authorized availability/load/deadline constraints;
- work/other commitments represented through authorized context;
- hard constraints;
- user preferences;
- scenarios.

### Pipeline

Canonical order:

```text
validate evidence
↓
resolve hard constraints
↓
resolve available capacity
↓
check target-date feasibility
↓
build valid scenarios
↓
compare trade-offs
↓
emit proposal / uncertainty / infeasibility
```

Hard constraints always precede preferences.

### Health → Oppositions

Default mode:

```text
minimal authorized functional constraint projection
```

Oppositions must never directly read/import Health storage or detailed clinical records.

Permitted semantic example:

```text
authorized = True
available study cap / reduced availability / relevant functional restriction
```

Not permitted by default:

- diagnosis;
- medication details;
- symptoms;
- clinical notes;
- clinician identity;
- unrelated health history.

Authorization is strict:

```text
authorized is True
```

not truthiness.

`"true"`, `"false"`, `1`, `0`, arbitrary objects or malformed values do not grant transfer.

### University → Oppositions

Default authorized projection may carry only what is needed for feasibility, such as:

- availability;
- academic workload;
- decision-relevant deadlines;
- fixed examination/attendance commitments;
- other minimal scheduling constraints.

It must not merge University and Opposition state or allow Oppositions to read University stores directly.

### Output semantics

The rule may emit:

- feasible scenario;
- infeasible scenario;
- unresolved feasibility;
- trade-offs;
- binding constraints;
- risks;
- proposal.

It never:

- adopts a study plan;
- changes the target opposition;
- changes a calendar;
- makes a medical conclusion;
- mutates University state;
- persists a decision directly.

---

## 14. MockExamInterpretationRule

### Objective

Interpret mock-exam evidence without confusing one observation with a stable trend or general capacity.

Must distinguish:

- point-in-time performance;
- trend;
- knowledge evidence;
- speed;
- format/process errors;
- unanswered items;
- scoring regime;
- comparability between mocks;
- uncertainty.

### Invariants

A single mock:

```text
→ observation
→ not a trend
```

Multiple mocks establish a trend only when enough evidence is comparable and temporally ordered.

Comparability may require:

- same or compatible format;
- compatible scoring rule;
- known denominator/penalty;
- valid chronology;
- comparable syllabus coverage/scope when material.

A raw score cannot be normalized when scoring rules are missing or malformed.

High/low mock performance must not be converted into:

- intelligence;
- fixed ability;
- guaranteed official-exam result;
- general personal capacity.

Speed and knowledge remain separate dimensions where evidence permits.

Format/process errors remain distinguishable from knowledge errors.

Order of input records must not change the semantic trend result.

---

## 15. AlternativeRouteRule

### Objective

Compare public bodies/opposition routes while preserving the user's current target and decision ownership.

The rule may compare:

- eligibility;
- syllabus overlap;
- exam format;
- deadlines;
- effort;
- expected study load;
- merits;
- geographic/organizational constraints when represented;
- current official-call availability;
- uncertainty;
- trade-offs;
- transition cost;
- compatibility with existing strategy.

### Fundamental invariant

```text
alternative considered
!=
alternative selected
!=
primary target abandoned
```

The current strategy remains in force until an explicit user decision adopts a change.

### Route-change semantics

A proposed route change must be:

- explicit;
- versioned;
- traceable to the decision;
- reversible at the planning-state level where possible;
- separated from source facts;
- never inferred solely from a better computed scenario.

The rule may recommend comparison/review. It may not silently alter:

- active goal;
- priority body;
- primary opposition;
- study strategy;
- registered external application.

Decision-critical route requirements must preserve official-source verification and temporal validity.

---

## 16. Versioned Opposition Strategy

`DP-023` requires versioned strategy and constraints.

Phase 10.23 therefore defines an internal conceptual boundary:

```text
Official Opposition State
!=
CMM Opposition Strategy State
!=
Personal Memory
```

### Official Opposition State

Facts grounded in external authoritative sources, for example:

- call;
- deadline;
- exam date;
- syllabus;
- regulation;
- requirements;
- merits.

### CMM Opposition Strategy State

Internal structured planning state, for example:

- current target;
- alternative routes under consideration;
- target date;
- plan version;
- milestones;
- sequencing;
- selected scenario after explicit adoption;
- constraints;
- study/revision strategy;
- review criteria;
- user-confirmed priorities.

This state is not an official fact.

### Personal Memory

Historical/user-context information retained under shared memory policy.

It may explain prior choices but cannot silently become current official opposition state or an adopted new strategy.

### Strategy versioning invariants

Every material strategy change must preserve:

- previous version;
- proposed change;
- reason;
- evidence/constraints;
- decision actor;
- decision time when adopted;
- relation to target/goal;
- uncertainty;
- trace reference.

A generated "best scenario" is a proposal until explicitly adopted through the shared decision/memory mechanisms.

No Opposition-local persistence layer is introduced.

---

## 17. Milestones and Sequencing

`DP-023` requires milestones and sequencing.

Milestones may include:

- call review;
- eligibility verification;
- syllabus baseline;
- block/topic coverage;
- first pass;
- revision cycles;
- mock milestones;
- application deadline;
- official exam;
- strategy review;
- alternative-route review.

Sequencing must respect dependencies.

Examples:

```text
unknown current syllabus
→ cannot claim complete syllabus division

decision-critical application deadline unresolved
→ affected registration planning remains blocked/conditional

revision plan
→ may depend on coverage state

exam readiness review
→ consumes coverage + mock evidence + temporal state + feasibility
```

Milestones are planning state, not external calendar mutations.

---

## 18. Trade-Off Analysis

Trade-off analysis is mandatory and structured.

Potential dimensions:

- time to target;
- syllabus overlap;
- remaining coverage;
- revision burden;
- mock performance evidence;
- workload;
- hard constraints;
- route requirements;
- uncertainty;
- switching cost;
- opportunity cost;
- schedule compatibility;
- user priority.

The system must not hide a trade-off by collapsing all dimensions into one opaque scalar unless a shared scoring policy explicitly defines and traces that aggregation.

Preferences cannot override hard constraints.

Unknown high-impact dimensions remain visible.

---

## 19. Canonical Operations

Exactly these ten operations:

```text
opposition.create_study_plan
opposition.divide_syllabus
opposition.track_progress
opposition.review_mock_exam
opposition.compare_bodies
opposition.review_call
opposition.generate_weekly_review
opposition.identify_risks
opposition.generate_revision_plan
opposition.update_progress
```

All definitions must use the current shared `DomainOperationDefinition` / schema / registry contracts.

### Operation boundaries

#### `opposition.create_study_plan`

Produces a structured study-plan proposal.

Must consider available grounded information and explicit constraints.

Never:
- registers for an exam;
- mutates calendar;
- changes target automatically;
- persists adoption by itself.

#### `opposition.divide_syllabus`

Structures the current known syllabus into blocks/topics/study units.

If syllabus identity/version is decision-critical and unresolved, output remains conditional and requests verification.

Does not invent missing official syllabus content.

#### `opposition.track_progress`

Analyses current internal progress evidence.

Does not directly write memory/state.

#### `opposition.review_mock_exam`

Runs `MockExamInterpretationRule` semantics and produces structured findings/recommendations.

No capacity/intelligence inference.

#### `opposition.compare_bodies`

Compares routes/bodies.

Produces trade-offs and proposals only.

Does not change the current target.

#### `opposition.review_call`

Analyses official-call evidence, authority, applicability, deadlines, requirements and gaps.

External verification request is read-only and `OFFICIAL_ONLY` under effective policy.

Does not register or submit.

#### `opposition.generate_weekly_review`

Synthesizes:

- call-monitoring state;
- milestones;
- progress;
- syllabus/revision state;
- mocks;
- workload;
- risks;
- unresolved gaps;
- next proposed actions.

Does not auto-adopt a new plan.

#### `opposition.identify_risks`

Produces structured risks such as:

- stale/unknown call;
- unresolved requirement;
- syllabus mismatch;
- insufficient time;
- revision deficit;
- poor comparability of mocks;
- deadline risk;
- dependency/blocker;
- route uncertainty.

Risk does not become certainty.

#### `opposition.generate_revision_plan`

Produces a revision proposal grounded in syllabus coverage and available time.

Time since study alone cannot prove forgetting.

#### `opposition.update_progress`

Produces a structured internal progress-update proposal.

It must never mutate:

- official public-body systems;
- registration;
- external records;
- calendar;
- memory/store directly.

Persistence/adoption, if any, remains a shared higher-layer responsibility.

### Operation schema rules

- strict structured schemas;
- required resources use current strict AND semantics and only name resources genuinely consumed;
- do not mechanically attach all domain resources to all operations;
- missing operation implementation is unavailable/fail-closed;
- malformed input is a structured validation failure, not permissive fallback;
- outputs distinguish proposal, observation, fact, inference, unknown and external-action status where applicable.

---

## 20. Canonical Workflows

Exactly these seven workflows:

```text
Opposition Setup
Weekly Study Review
Mock Exam Review
Call Analysis
Syllabus Revision
Alternative Route Comparison
Exam Readiness Review
```

Use the shared Workflow Engine.

No Opposition-specific workflow runtime/state machine.

### 20.1 Opposition Setup

Purpose:

```text
target/body
↓
known call state
↓
official verification needs
↓
syllabus baseline
↓
requirements
↓
constraints
↓
milestones
↓
initial strategy proposal
```

Must not require an active external call to create a study strategy when long-term preparation is reasonable, but uncertainty about the next/current call remains explicit.

### 20.2 Weekly Study Review

Purpose:

```text
monitoring state
+
progress
+
coverage/revision
+
mocks
+
capacity/constraints
+
risks
→ next-week proposal
```

Call monitoring is a required review concern when an opposition objective is active.

No scheduler is introduced.

### 20.3 Mock Exam Review

Purpose:

```text
mock evidence
→ normalize only if grounded
→ point performance
→ comparable history
→ trend if justified
→ knowledge/speed/format findings
→ revision recommendation
```

### 20.4 Call Analysis

Purpose:

```text
sources
→ authority by attribute/scope
→ temporal validity
→ requirements/deadlines
→ contradictions/gaps
→ official verification need
→ structured call summary
```

No registration/payment/submission.

### 20.5 Syllabus Revision

Purpose:

```text
current syllabus
→ coverage
→ review/retention risk
→ pending topics
→ available time
→ revision proposal
```

### 20.6 Alternative Route Comparison

Purpose:

```text
primary target
+
alternative(s)
→ grounded comparison
→ trade-offs
→ uncertainty
→ proposal
```

No implicit abandonment/change.

### 20.7 Exam Readiness Review

Consumes, where available:

- current call/exam temporal state;
- current syllabus identity;
- coverage;
- revision;
- mock evidence;
- feasibility;
- risks;
- unresolved requirements.

Output is a readiness assessment with explicit evidence and uncertainty.

It is not:

- a guarantee of passing;
- a capacity judgment;
- an automatic decision to sit/skip/change the exam.

---

## 21. External Official Verification

External verification is a shared capability boundary.

Phase 10.23 may request external verification when a decision-relevant fact is:

```text
missing
stale
conflicting
undergrounded
temporally unknown
materially scope-ambiguous
```

Canonical domain-triggered verification is:

```text
READ_ONLY
+
OFFICIAL_ONLY
```

under the effective permission/privacy policy.

### Suitable official-source categories

Do not hard-code one country's portals into domain logic.

Conceptually suitable sources may include:

- official gazette/publication;
- official public-body call/resolution;
- official public-body page/document;
- governing regulation;
- official examination publication.

The implementation must use existing source-class contracts where possible.

### Non-authoritative supporting material

Academies, forums, summaries, notes and memory may be useful as leads/context but are not promoted to official authority.

### No continuous external implementation

Do not implement:

- scraper;
- crawling;
- polling;
- RSS client;
- browser automation;
- CAPTCHA handling;
- credentials;
- remote provider;
- notification daemon.

Those remain adapter/integration concerns.

---

## 22. Permissions

Use current shared Domain Permission contracts.

### Allowed domain semantics

Subject to effective policy:

- authorized Opposition resource reads;
- analysis;
- planning;
- reversible proposal generation;
- internal structured progress analysis;
- shared memory reads according to policy;
- conditional official read-only verification.

### External verification

When initiated by the canonical domain:

```text
source requirement = OFFICIAL_ONLY
read-only
```

A missing/unknown source class is not trusted as official.

### Prohibited actions

Phase 10.23 must not autonomously:

- register for an opposition;
- submit an application;
- sign a filing;
- pay a fee;
- purchase services;
- upload formal documents to a public body;
- impersonate the user;
- withdraw an application;
- abandon a target;
- switch the primary route;
- make final user decisions;
- modify official records.

### Calendar / schedule

Planning may propose dates/sessions.

Actual shared calendar/schedule mutation requires exact scoped approval under the effective shared permission gate.

No `opposition.create_calendar_event` engine is introduced.

### Tasks

If the current shared capability supports persistent task creation, actual creation remains approval-gated.

The domain itself only proposes/requests it.

### Cross-domain

Oppositions must not receive autonomous broad cross-domain access.

Inbound transfer is:

```text
scoped
+
purpose-bound
+
minimum necessary
+
approval-gated where current policy requires
+
most-restrictive-policy wins
```

The supporting domain cannot widen Opposition permissions.

### Privacy

Any Phase 10 default privacy orientation is subordinate to the most restrictive effective combination of:

- global;
- user;
- session;
- resource;
- domain;
- workflow;
- operation;
- Knowledge Package;
- provider/model policy.

Oppositions does not select providers.

`LOCAL_ONLY` cannot be weakened.

---

## 23. Cross-Domain Contract

### 23.1 Health → Oppositions

Default:

```text
minimal functional constraint projection
```

No direct `cmm.domains.health` import from the Opposition package for data access.

No Health store/registry reads.

Detailed clinical information is denied by default.

### 23.2 University → Oppositions

Default:

```text
minimal availability/load/deadline projection
```

No direct University store/registry reads.

Do not merge academic state and Opposition strategy state.

### 23.3 Oppositions → University / Health

No automatic reverse transfer is required by Phase 10.23.

If future coordination needs it, use the existing cross-domain engine and explicit permission policies rather than direct imports.

### 23.4 General

General remains fallback/shared context, not a source of privileged authority over Opposition-specific official facts.

---

## 24. Memory

Use shared Domain Memory.

No:

```text
OppositionMemoryStore
OppositionKnowledgeStore
OppositionVectorStore
OppositionGraphStore
```

### Memory may preserve

- user-confirmed current target;
- versioned strategy decisions;
- prior strategy versions;
- study preferences;
- historical progress;
- historical mock summaries;
- user-reported constraints;
- prior alternative comparisons;
- review history.

### Memory may not silently establish

- current official call;
- current deadline;
- current syllabus;
- current regulation;
- current requirement;
- adopted strategy change.

Official state must remain grounded to current/scope-valid evidence.

Strategy adoption must remain an explicit decision.

### Memory updates

Use shared memory update proposal / confirmation mechanisms.

No direct persistence from a rule or operation.

---

## 25. Presentation

Presentation must preserve:

- official vs unofficial source status;
- provenance;
- temporal state;
- source scope;
- version;
- uncertainty;
- contradictions;
- information gaps;
- strategy version;
- proposal vs adopted decision;
- observed mock performance vs trend;
- coverage dimensions;
- feasibility constraints;
- risk;
- external-action/approval status.

### Recommended views

When relevant, present:

```text
target / body
call status
critical dates
requirements
syllabus version
coverage
revision
mock performance
trend confidence
workload / feasibility
risks
alternatives
strategy version
next review
verification needs
```

Presentation must not:

- turn a recommendation into a fact;
- hide unresolved source conflict;
- hide stale data;
- call a tentative strategy "decided";
- imply guaranteed success;
- imply that a compared alternative has replaced the primary route.

---

## 26. Traceability

Reuse the shared trace contracts and assembler.

Trace must reference, not duplicate:

- rule results;
- source/resource IDs;
- knowledge items;
- cross-domain transfer references;
- permission decisions;
- operation/workflow IDs;
- strategy/proposal references;
- memory proposals.

No hidden chain-of-thought persistence.

No Opposition-local trace database.

Invalid trace reference fails validation.

---

## 27. Integration and Registration

Follow the final University validation-first/rollback precedent.

Canonical flow:

```text
build pack components
↓
validate catalog consistency
↓
validate definitions
↓
validate profile
↓
validate resources
↓
validate rules
↓
validate operations + provided implementations
↓
validate workflows
↓
validate permissions/presentation/memory/trace
↓
validate duplicate IDs across target registries
↓
capture registry snapshots
↓
register
↓
if any mutation fails:
    restore every affected registry to exact snapshot parity
```

### Invariants

- no partial pack registration;
- no partial rollback;
- validation occurs before first registry mutation;
- nested/common registries are prevalidated where current architecture requires;
- missing implementation cannot be converted into availability;
- duplicate canonical ID is rejected;
- integration result is structured;
- registration order is deterministic.

---

## 28. Bootstrap

`bootstrap.py` composes:

```text
General
+
Oppositions
```

through existing shared registries/services.

General remains fallback.

Bootstrap must not instantiate duplicate infrastructure.

Supporting Health/University domains participate only through normal domain resolution/composition/cross-domain contracts when required and authorized.

No implicit direct multi-domain reads.

---

## 29. Import and Dependency Invariants

The Opposition package must not create reverse dependencies from shared infrastructure into the specialized domain except intentional public bootstrap/discovery mechanisms already used by final domain precedents.

Import invariants:

- no registration on import;
- no filesystem IO;
- no network IO;
- no external search;
- no clock-dependent mutation;
- no memory access;
- no model call;
- no environment mutation;
- no global registry mutation;
- no direct Health data access;
- no direct University data access.

Test clean import in a fresh interpreter.

---

## 30. Error / Unknown-State Policy

Unknown or invalid state must not become permission or certainty.

At minimum:

```text
unknown permission
→ deny / approval not satisfied

unknown external source class
→ not official

unknown call applicability
→ not current-confirmed

unknown deadline grounding
→ not confirmed

unknown syllabus version
→ do not claim complete current coverage

unknown temporal ordering
→ preserve unknown

unknown route requirement
→ comparison remains conditional

unknown mock comparability
→ no trend claim

unknown operation implementation
→ unavailable

unknown workflow
→ block

unknown approval
→ do not execute mutation

malformed cross-domain authorization
→ no transfer

invalid memory binding
→ reject

invalid trace reference
→ reject

partial registration
→ rollback
```

Do not use permissive defaults merely to make tests pass.

---

## 31. Missing and Incomplete Information

Canonical behavior:

```text
non-blocking gap
→ continue with explicit uncertainty

decision-critical blocking gap
→ request OFFICIAL_ONLY verification if permitted
   OR request the relevant user/resource input
   OR pause/block only the affected conclusion/action
```

Every material gap must expose:

- missing/invalid field;
- epistemic state;
- impact;
- confidence/uncertainty;
- affected conclusion;
- verification/question needed;
- action that must not proceed.

Do not silently fill current official facts from memory/general knowledge.

---

## 32. No Direct External Effects

Opposition rules and canonical operations are analysis/planning/state-proposal capabilities.

They must not directly:

- use HTTP;
- use a browser;
- call a government portal;
- register;
- pay;
- send;
- sign;
- submit;
- modify calendar/task storage;
- write memory;
- mutate official systems.

External side effects belong behind shared operations/integrations/approval gates.

---

## 33. Non-Goals

Phase 10.23 does **not** implement:

- public-administration portal connector;
- BOE/DOGC/BOP-specific scraper;
- automatic call crawler;
- automatic registration;
- application submission;
- fee payment;
- browser automation;
- email sending;
- calendar engine;
- task engine;
- notification center;
- continuous background monitoring;
- provider/model selection;
- Model Gateway;
- credentials store;
- OCR pipeline;
- custom search engine;
- own memory store;
- own knowledge graph;
- own vector store;
- own workflow engine;
- own resolver;
- own planner;
- own source authority engine shared globally;
- own temporal engine shared globally;
- Health clinical reasoning;
- University academic reasoning;
- employment/labor domain;
- legal advice engine;
- probabilistic pass predictor;
- intelligence/capacity assessment;
- autonomous target switching;
- Phase 11 UI/connectors.

Do not pre-build these now.

---

## 34. Catalog as Single Source of Truth

`catalog.py` must be the canonical source for exact Opposition identifiers.

Every other module derives/reconciles against it.

Tests must fail on:

- missing catalog item;
- extra item;
- duplicate item;
- count mismatch;
- wrong prefix;
- inconsistent domain ID;
- operation/workflow mismatch.

Do not maintain independent hand-copied identifier lists that can drift silently.

---

## 35. Testing Contract

Implementation depth must start at the **final hardened** Phase 10.22 standard, not University V1.

At minimum test:

- package audit;
- catalog reconciliation;
- definition;
- exact 14 entities;
- exact 11 resources;
- profile binding;
- all six reasoning rules;
- all ten operations;
- all seven workflows;
- permissions;
- permission gates/lifecycle;
- presentation;
- memory boundary;
- trace;
- integration;
- validation-first adversarial matrix;
- snapshot/rollback;
- resolver/bootstrap;
- public API;
- clean import in a fresh interpreter;
- official verification boundary;
- Health → Oppositions projection;
- University → Oppositions projection;
- malformed public payloads;
- strict booleans;
- order invariance;
- scope-aware source authority;
- temporal uncertainty;
- strategy versioning/decision preservation;
- full domain regressions.

Suggested files, following current repository style:

```text
tests/domains/test_oppositions_domain_audit.py
tests/domains/test_oppositions_domain_bootstrap.py
tests/domains/test_oppositions_domain_catalog_reconciliation.py
tests/domains/test_oppositions_domain_definition.py
tests/domains/test_oppositions_domain_resources.py
tests/domains/test_oppositions_domain_profile.py
tests/domains/test_oppositions_domain_rules.py
tests/domains/test_oppositions_domain_official_call_priority.py
tests/domains/test_oppositions_domain_temporal_validity.py
tests/domains/test_oppositions_domain_syllabus_coverage.py
tests/domains/test_oppositions_domain_study_feasibility.py
tests/domains/test_oppositions_domain_mock_exam.py
tests/domains/test_oppositions_domain_alternative_routes.py
tests/domains/test_oppositions_domain_strategy.py
tests/domains/test_oppositions_domain_operations.py
tests/domains/test_oppositions_domain_workflows.py
tests/domains/test_oppositions_domain_permissions.py
tests/domains/test_oppositions_domain_permission_gates.py
tests/domains/test_oppositions_domain_permission_lifecycle.py
tests/domains/test_oppositions_domain_health_projection.py
tests/domains/test_oppositions_domain_university_projection.py
tests/domains/test_oppositions_domain_memory.py
tests/domains/test_oppositions_domain_presentation.py
tests/domains/test_oppositions_domain_trace.py
tests/domains/test_oppositions_domain_integration.py
tests/domains/test_oppositions_domain_validation_first_matrix.py
tests/domains/test_oppositions_domain_rollback.py
tests/domains/test_oppositions_domain_resolution.py
tests/domains/test_oppositions_domain_public_api.py
tests/domains/test_oppositions_domain_safety.py
tests/domains/test_oppositions_domain_verification.py
```

The implementation worker may consolidate test files when repository style clearly favors consolidation, but must not drop coverage categories.

---

## 36. Official Source Authority Tests

At minimum:

1. current specific official call outranks an incompatible personal note for call-specific facts;
2. current specific official publication can control an exam date within its scope;
3. governing regulation controls a general requirement only within compatible scope;
4. recency alone does not override authority;
5. caller-provided `official=True` cannot create authority;
6. provenance alone does not create truth;
7. source without usable reference cannot confirm a decision-critical fact when traceable reference is required;
8. equal-authority agreeing evidence corroborates;
9. equal-authority incompatible evidence remains unresolved;
10. validated supersession works;
11. unvalidated self-declared supersession does not;
12. unknown temporality at higher authority can prevent a weaker source from becoming definitive when material;
13. expired history remains available but non-current;
14. malformed scope never becomes global;
15. input permutation does not change resolved authority/current value.

---

## 37. Temporal / Call Tests

At minimum:

- no call supplied;
- malformed call payload;
- call with missing identity;
- current grounded call;
- expired call;
- future call;
- conflicting call applicability;
- deadline with bare value only;
- grounded current deadline;
- stale deadline;
- future deadline;
- conflicting deadline;
- unknown ordering;
- current syllabus unresolved;
- current regulation unresolved;
- requirement version unresolved;
- decision-critical missing fact triggers verification need;
- non-critical gap can remain explicit without blocking unrelated analysis;
- active opposition objective + stale/unknown call state emits monitoring requirement;
- no rule auto-creates calendar events.

---

## 38. Syllabus Tests

At minimum:

- structured full coverage;
- pending topics;
- duplicate topic IDs not double-counted;
- identityless topic cannot establish complete coverage;
- malformed topic collection;
- valid empty collection remains distinct;
- unknown topic state;
- stale/unknown syllabus version blocks current-complete claim;
- review due does not equal forgotten;
- mock evidence without topic mapping does not establish topic mastery;
- aggregate percentage cannot override contradictory structured topic evidence;
- deterministic order-invariant result.

---

## 39. Feasibility Tests

At minimum:

- feasible scenario;
- infeasible hard constraint;
- unknown decision-critical constraint;
- preferences evaluated only after hard constraints;
- malformed numeric workload values do not raise;
- malformed scenario/member remains unresolved;
- target date missing;
- target date temporally invalid/unknown;
- Health authorized literal `True` constraint consumed;
- Health `"true"`, `"false"`, `1`, `0` not accepted as authorization;
- malformed authorized Health cap remains unknown, not permissive;
- no clinical details consumed/emitted;
- University minimal authorized projection consumed;
- unrelated University payload rejected/not consumed;
- supporting domain cannot widen permissions;
- no plan silently adopted.

---

## 40. Mock Exam Tests

At minimum:

- one mock = observation, not trend;
- multiple comparable mocks can establish trend;
- incompatible scoring regimes prevent naive trend;
- missing denominator/penalty prevents invalid normalization;
- malformed score does not raise/promote certainty;
- unknown chronology prevents temporal trend;
- duplicate mock identity does not double-count;
- order invariance;
- speed separate from knowledge;
- format errors separate from knowledge errors;
- no intelligence/capacity inference;
- no pass guarantee.

---

## 41. Alternative Route Tests

At minimum:

- compare primary + one alternative;
- multiple alternatives;
- missing official requirements leave affected comparison conditional;
- route with stale call data remains stale;
- better computed scenario does not change active target;
- comparison does not mark primary abandoned;
- explicit adopted change creates a new strategy version through higher-layer decision semantics;
- malformed route identity does not merge routes;
- trade-offs remain visible;
- hard constraint cannot be overridden by preference;
- input order does not change semantic comparison.

---

## 42. Strategy / DP-023 Tests

At minimum prove:

```text
versioned strategy
official verification
milestones
sequencing
constraints
trade-offs
realistic planning
```

Specific cases:

- current strategy has explicit version;
- proposed strategy update preserves prior strategy;
- proposal does not equal adoption;
- explicit adoption records actor/time/reason through shared mechanism;
- alternative-route recommendation does not mutate target;
- changing official facts do not silently rewrite strategy;
- changed official facts can create a strategy-review need;
- milestones preserve dependencies;
- infeasible study strategy is not presented as feasible;
- unresolved decision-critical constraints prevent definitive feasibility;
- personal memory cannot overwrite official state;
- official state cannot silently overwrite user-owned strategy decisions; instead it may invalidate assumptions and trigger review.

---

## 43. Cross-Domain Security Tests

### Health → Oppositions

Assert:

- no direct Health store import/read;
- only authorized minimal functional constraint consumed;
- detailed clinical resource kinds denied by default;
- strict boolean authorization;
- malformed authorization/cap fail closed;
- source domain cannot widen target permissions;
- most restrictive effective policy wins.

### University → Oppositions

Assert:

- no direct University store import/read;
- only authorized availability/load/deadline projection consumed;
- unrelated academic details are not transferred;
- University state is not merged with Opposition strategy state;
- malformed projection remains invalid;
- permission/approval scope is exact.

### General

Assert General fallback does not become a privileged bypass around official-source rules.

---

## 44. Operation / Workflow Tests

For all operations:

- canonical IDs exact;
- schemas reject malformed input;
- output schema enforced;
- required resources are minimal and use strict AND semantics;
- missing implementation fail-closed;
- no direct external side effect;
- proposal-only semantics preserved where relevant;
- operation registration validates before mutation.

For all workflows:

- canonical IDs/names exact;
- real dependency/gating semantics;
- cannot skip required review/verification gate;
- no direct registration/payment;
- no silent strategy adoption;
- pause/block behavior only affects decision-critical unresolved branches;
- shared Workflow Engine used;
- permission adapter behavior preserved.

---

## 45. Integration / Rollback Tests

At minimum:

- successful complete registration;
- duplicate resource/rule/operation/workflow rejected before mutation where possible;
- malformed component rejected before mutation;
- operation implementation mismatch rejected before mutation;
- injected registration failure restores all touched registries;
- rollback parity equals exact pre-call snapshots;
- no leaked partial registration;
- retry after rollback can succeed;
- deterministic integration result;
- clean package import leaves global registries untouched.

---

## 46. Public API and Safety Tests

Assert:

- intentional Opposition API exported;
- internal helpers not accidentally exported;
- no import-time side effects;
- no network/filesystem/model/memory operations on import;
- no direct Health/University data access;
- no custom permission resolver;
- no custom workflow engine;
- no custom memory store;
- no automatic registration/payment;
- no calendar mutation without shared approval;
- no route abandonment without explicit decision;
- no provider coupling;
- no user-specific opposition facts hard-coded.

---

## 47. Requirements-Matrix Coverage

Phase 10.23 must explicitly cover `DP-023` / `AT-DP-023`.

### Versioned strategy and constraints

Covered by:

- Opposition Strategy State boundary;
- strategy versioning;
- `create_study_plan`;
- weekly review;
- alternative comparison;
- explicit adoption semantics;
- shared memory/decision proposal mechanisms.

### Official-source verification

Covered by:

- `OfficialCallPriorityRule`;
- `OppositionTemporalValidityRule`;
- `review_call`;
- `Call Analysis`;
- `OFFICIAL_ONLY` read-only verification request;
- call-monitoring requirement.

### Milestones and sequencing

Covered by:

- Opposition Setup;
- study plan;
- syllabus division;
- weekly review;
- revision plan;
- workflow dependencies.

### Trade-offs

Covered by:

- `StudyFeasibilityRule`;
- `AlternativeRouteRule`;
- `compare_bodies`;
- Alternative Route Comparison;
- explicit hard-constraint-before-preference behavior.

### Realistic study planning

Covered by:

- `SyllabusCoverageRule`;
- `StudyFeasibilityRule`;
- mock interpretation;
- workload projections;
- `create_study_plan`;
- weekly/revision/readiness workflows.

### External sources deferred

Satisfied by implementing only:

- resource/source semantics;
- official verification requirement;
- permission request boundary;

while deferring actual connector/search/scheduling implementations.

The implementation must update the requirements matrix only to the state justified by completed implementation/verification. It must not mark independent audit completion prematurely.

---

## 48. Documentation Expectations

Implementation should add/update only documentation justified by completed production:

Expected domain reference:

```text
docs/reference/oppositions-domain.md
```

Expected matrix update:

```text
docs/reference/domain-intelligence-requirements-matrix.md
```

Expected roadmap status during implementation:

```text
Implemented, pending audit
```

not:

```text
Complete and audited
```

The frozen design file itself is:

```text
docs/superpowers/specs/2026-08-13-oppositions-domain-design.md
```

Independent audit/remediation documentation is a later closure workflow.

---

## 49. Self-Audit Requirements

Before claiming implementation ready for independent audit, inspect for:

- accidental University-specific semantics;
- accidental Health-specific semantics;
- user-specific hard-coded target/body/call facts;
- jurisdiction-specific assumptions embedded as universal logic;
- source authority based only on recency;
- caller-supplied `official` flags trusted;
- missing source reference promoted to confirmation;
- malformed scope becoming global;
- equal-authority order dependence;
- malformed Mapping accepted as semantic evidence;
- truthy strings/numbers accepted as booleans;
- unknown evidence silently dropped;
- stale source treated current;
- old call/academy/note/memory overriding current official evidence;
- syllabus aggregate bypass;
- duplicate topic counting;
- time-since-study treated as proven forgetting;
- one mock treated as trend;
- incomparable mocks combined;
- performance → intelligence/capacity inference;
- feasibility preferences before hard constraints;
- Health clinical-detail leakage;
- University detail leakage;
- alternative comparison causing silent target switch;
- plan proposal persisted as adopted strategy;
- call monitoring implemented as unauthorized continuous external activity;
- direct registration/payment/submission;
- direct calendar/task mutation;
- direct memory persistence;
- fake operation implementations;
- import-time side effects;
- partial registration;
- incomplete rollback;
- reverse dependency;
- unrelated shared refactoring.

Placeholder scan:

```bash
rg -n 'TBD|TODO|FIXME|PLACEHOLDER|XXX' \
  cmm/domains/oppositions \
  tests/domains/test_oppositions_domain_*.py \
  docs/reference/oppositions-domain.md \
  docs/superpowers/specs/2026-08-13-oppositions-domain-design.md || true
```

No required behavior may be postponed through a placeholder.

---

## 50. Verification Expectations

The implementation worker must inspect the actual repository at execution time and use current commands/counts rather than hard-coding historical totals.

Expected verification categories:

```text
focused Opposition tests
relevant General/Health/University regressions
all domain tests
global pytest suite
Ruff on changed/new Python
Ruff with py310 target when required by current workflow
compileall
dependency-direction tests
fresh-interpreter Opposition import
git diff --check
git diff --cached --check before commit
```

Fresh import expectation:

```bash
python - <<'PY'
import cmm.domains.oppositions
print("fresh_import=OK")
PY
```

Do not treat focal green tests as sufficient for completion.

Do not hard-code historical test counts as acceptance criteria.

---

## 51. Acceptance Criteria

Phase 10.23 implementation is acceptable when:

- `domain:oppositions` exists as a complete canonical Domain Pack;
- the package follows the shared 14-module boundary unless a demonstrated repository constraint requires otherwise;
- exactly 14 entity semantics exist;
- exactly 11 canonical resources exist;
- exactly 6 canonical reasoning rules exist;
- exactly 10 canonical operations exist;
- exactly 7 canonical workflows exist;
- `catalog.py` is the single source of truth;
- shared contracts/registries are reused;
- no parallel infrastructure exists;
- existing `OppositionProfile` semantics are reused/bound;
- source authority is grounded, attribute-specific and scope-aware;
- authority resolution is order-invariant;
- equal-authority agreement corroborates and equal-authority conflict remains unresolved;
- provenance does not automatically equal truth;
- malformed scope never becomes global;
- current official facts require temporal grounding;
- old/stale calls do not override current facts;
- academy/note/memory cannot silently override current official evidence;
- decision-critical unresolved official facts trigger verification/gap behavior;
- domain-triggered external verification is `OFFICIAL_ONLY` and read-only;
- mandatory call monitoring is represented semantically without building continuous external infrastructure;
- syllabus coverage preserves topic identity, pending/unknown state, depth, revision and retention risk;
- forgetting is not asserted solely from elapsed time;
- duplicate topics do not inflate coverage;
- study feasibility applies hard constraints before preferences;
- Health → Oppositions uses only minimal authorized functional projection;
- University → Oppositions uses only minimal authorized availability/load/deadline projection;
- no detailed Health/University store access exists;
- one mock is not a trend;
- incomparable mocks are not naively combined;
- mock performance is not converted into intelligence/capacity or pass certainty;
- alternative comparison never silently abandons/changes the primary target;
- strategy changes are proposals until explicitly adopted;
- strategy and constraints are versioned;
- milestones/sequencing/trade-offs are represented;
- all ten operations respect external-action boundaries;
- all seven workflows use the shared Workflow Engine;
- registration/payment/submission are absent;
- calendar/task mutation remains shared and approval-gated;
- memory reuses shared Domain Memory and no direct writes occur;
- trace is reference-only;
- presentation preserves source/temporal/uncertainty/proposal distinctions;
- missing operation implementation is fail-closed;
- General remains fallback;
- bootstrap composes General + Oppositions on shared registries;
- validation-first occurs before first mutation;
- rollback restores complete registry parity;
- clean import is verified;
- `DP-023` / `AT-DP-023` are demonstrably covered;
- focal/domain/global verification is green.

---

## 52. Future Considerations — Out of Scope

Record without implementing:

1. Phase 11 official-source connectors/search adapters.
2. Scheduled/continuous call monitoring through Agent Runtime scheduling and integrations.
3. Notification delivery for new calls/deadlines.
4. Portal/application automation after explicit future design and approvals.
5. Calendar/task connectors behind shared operations.
6. Provider/model routing through Phase 11 Model Gateway.
7. Richer employment/labor-career composition if a future domain boundary justifies it.
8. Life Plan ↔ Oppositions long-horizon composition.
9. Dedicated benchmark suites for opposition planning/source verification.
10. External artifact/document-generation workflows through shared artifact infrastructure.
11. Autonomous multi-route optimization.
12. Public-body-specific plugins.

Do not pre-build these now.

---

## 53. Final Hardened Precedent

Implementation must start from the **final** states of General, Health, Relationships and University, especially University V18.

Preserve these lessons from the beginning:

- General is fallback, never the specialized domain;
- compose through shared registries;
- one canonical catalog;
- no import-time registration;
- provenance does not equal truth;
- caller labels cannot create authority;
- semantic evidence validation matters beyond Python type shape;
- scope must be validated;
- malformed scope does not become global;
- temporal validity must be explicit;
- unknown order is not latest;
- equal authority must distinguish agreement from conflict;
- source resolution must be input-order invariant;
- traceable grounding requires usable references when material;
- absent != malformed;
- valid empty != malformed;
- strict booleans are strict;
- malformed evidence cannot disappear before canonical evaluation;
- hard constraints precede preferences;
- cross-domain transfer is minimal and authorized;
- supporting domains cannot widen permissions;
- external mutation requires exact permission/approval;
- memory proposal is not adoption;
- strategy proposal is not user decision;
- workflows need real dependency/gating semantics;
- missing implementation is fail-closed;
- validation-first precedes mutation;
- rollback restores exact state;
- public helpers and canonical rule paths must enforce the same hardening;
- green focal tests do not replace adversarial/domain/global verification.

---

## 54. Completion State

Successful implementation of this specification means:

```text
Opposition Domain implemented
+
full local verification green
+
self-audit complete
+
requirements matrix updated to justified implementation state
+
roadmap = Implemented, pending audit
+
ready for independent audit
```

It does **not** itself mean:

```text
Phase 10.23 Complete and audited
```

Official closure requires an independent audit/remediation cycle and its own closure documentation/commit.

The implementation worker must not preemptively close the milestone.

---

## 55. Design Freeze

This file freezes the following hard decisions:

1. Canonical ID is `domain:oppositions`.
2. Canonical operation prefix is `opposition.`.
3. Shared 14-module specialized-domain boundary.
4. Exactly 14 entities.
5. Exactly 11 resources.
6. Exactly 6 canonical rules.
7. Exactly 10 canonical operations.
8. Exactly 7 canonical workflows.
9. Existing shared profile/cognitive infrastructure is reused.
10. Existing shared permission/cross-domain/operation/workflow/memory/trace infrastructure is reused.
11. No prerequisite shared-infrastructure refactor.
12. Official source authority is grounded, attribute-specific, scope-aware and order-invariant.
13. Temporal validity is explicit; missing/malformed/stale/future/conflicting/current remain distinct.
14. Decision-critical changing official facts trigger read-only `OFFICIAL_ONLY` verification when permitted.
15. Mandatory call monitoring is semantic in 10.23; continuous scheduler/connectors are deferred.
16. Syllabus coverage is multidimensional and topic-grounded.
17. Elapsed time alone does not prove forgetting.
18. Study feasibility applies hard constraints before preferences.
19. Health → Oppositions defaults to minimal authorized functional projection.
20. University → Oppositions defaults to minimal authorized availability/load/deadline projection.
21. No detailed Health/University store access.
22. One mock does not establish trend.
23. Mock performance does not establish intelligence/capacity or guaranteed exam success.
24. Alternative comparison does not abandon/change the current target.
25. Strategy and constraints are versioned.
26. Plan/scenario/recommendation does not equal adopted user decision.
27. No automatic registration, submission, payment or official-system mutation.
28. Calendar/task mutation only through shared approval-gated capabilities.
29. No direct memory write.
30. General remains fallback.
31. Integration is validation-first and rollback-capable.
32. Clean import has no side effects.
33. `DP-023` / `AT-DP-023` must be explicitly covered.
34. Implementation ends at `Implemented, pending audit`, not `Complete and audited`.

Any implementation change to these decisions requires explicit design revision rather than silent divergence.

---

## 56. Next Step After Repository Integration

After this frozen spec is committed and its integration is verified, prepare the dedicated Phase 10.23 implementation prompt/plan.

That prompt must:

1. inspect the repository again before editing;
2. establish current test baseline;
3. use TDD;
4. implement only frozen scope;
5. reuse final hardened patterns;
6. run focal → domain → global verification;
7. self-audit against this document;
8. commit implementation only after verification;
9. leave Phase 10.23 as `Implemented, pending audit`;
10. stop before independent audit/closure.

No production implementation belongs in the spec-integration step.
