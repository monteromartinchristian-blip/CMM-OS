# Phase 10.22 — University Domain Design

**Status:** Approved design
**Date:** 2026-08-09

## 1. Purpose

The University Domain specializes CMM OS for structured reasoning and planning about university academic life.

It covers:

- degrees;
- universities;
- academic years;
- semesters;
- subjects;
- assignments;
- examinations;
- exam attempts and reassessments;
- grades;
- deadlines;
- professors;
- adaptations/accommodations as academic facts or constraints;
- credits and ECTS;
- academic requirements;
- subject status;
- study planning;
- workload;
- observed academic performance;
- degree completion;
- TFG planning;
- formal-procedure preparation;
- official-source verification when academic facts are time-sensitive or decision-critical.

The domain exists to help the user organize, understand, compare, prepare and plan academic work while preserving authority, provenance, temporality, uncertainty, user control and academic-integrity constraints.

Canonical identity:

```text
domain_id = domain:university
kind = personal
```

The University Domain MUST NOT:

- create a second academic memory system;
- create a second workflow engine;
- create a second calendar or task engine;
- send emails or messages;
- submit university forms, appeals, recognition requests, accommodation requests or other formal procedures;
- modify the official university record;
- treat an inferred or remembered deadline as confirmed without grounding;
- silently resolve material conflicts between equivalent authoritative sources;
- confuse observed academic performance with intellectual or potential capacity;
- adopt an academic decision on behalf of the user;
- convert a planning proposal into a commitment without confirmation;
- weaken a more restrictive privacy, permission, approval or cross-domain policy;
- select or invoke a model provider directly.

---

## 2. Architectural Principle

University is the fourth canonical complete specialized Domain Pack after General, Health and Relationships.

It must reuse the shared architecture already implemented by CMM OS:

- `Resource`;
- `ResourceProvenance`;
- `TemporalScope`;
- shared sensitivity and permission contracts;
- `Entity`;
- `KnowledgeItem`;
- `KnowledgeRelation`;
- Cognitive Layer;
- shared Knowledge Store and Knowledge Graph;
- Domain Profiles;
- Reasoning Rules;
- Agent Runtime;
- shared approvals;
- `DomainDefinition`;
- `DomainResourceDefinition`;
- `DomainProfileDefinition`;
- `DomainOperationDefinition`;
- `DomainWorkflowDefinition`;
- Domain permissions;
- Domain presentation;
- Domain Memory integration;
- Domain Trace;
- common registries;
- the existing domain resolver;
- the existing cross-domain engine;
- the common Workflow Engine;
- snapshot/rollback and validation-first infrastructure.

University MUST NOT introduce:

- `UniversityEntity` persistent class hierarchy;
- `UniversityEntityStore`;
- `UniversityKnowledgeStore`;
- `UniversityKnowledgeGraph`;
- `UniversityMemory`;
- `UniversityTrace`;
- `UniversityResolver`;
- `UniversityRuntime`;
- `UniversityPlanner`;
- `UniversityWorkflowEngine`;
- `UniversityReasoningEngine`;
- `UniversityCalendarService`;
- `UniversityTaskService`;
- `UniversityEmailService`;
- parallel registries;
- separate persistent academic database.

Shared data exists once and may receive University domain bindings.

A calendar event, email, note, memory item or other shared resource must not be copied merely because University consumes it.

General remains the fallback domain.

Health may participate as a supporting domain only through explicit cross-domain composition and effective permissions.

---

## 3. Canonical Package Boundary

The intended production package is:

```text
cmm/domains/university/
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

Exactly 14 production modules are expected unless implementation proves a genuine architectural necessity that cannot be represented by the established General/Health/Relationships precedent.

Responsibilities:

### `catalog.py`

Single source of truth for the canonical University catalog.

It must expose one canonical ordered set for:

- entity semantics;
- resources;
- reasoning rules;
- operations;
- workflows;
- profile identity;
- domain identity;
- canonical presentation section IDs where the current repository pattern stores them in the package catalog.

No duplicated tuple/list catalog may become a second source of truth.

### `definition.py`

Builds the canonical `DomainDefinition` using existing public contracts.

### `profile.py`

Builds the canonical `DomainProfileDefinition` for `UniversityProfile`.

### `resources.py`

Builds and validates the 12 canonical `DomainResourceDefinition` instances.

### `rules.py`

Defines the 10 canonical `ReasoningRule` definitions and pure deterministic academic helpers where justified.

### `operations.py`

Defines the 11 canonical `DomainOperationDefinition` declarations and integrates only genuine implementations that satisfy existing validators.

### `workflows.py`

Defines the 7 canonical `DomainWorkflowDefinition` declarations using the existing shared Workflow Engine.

### `permissions.py`

Expresses University policy through the existing shared permission contracts.

### `presentation.py`

Defines the structured University presentation policy without altering epistemic content.

### `memory.py`

Uses existing Domain Memory views, proposals and bindings only.

### `trace.py`

Uses existing reference-only Domain Trace integration.

### `integration.py`

Performs complete validation-first atomic registration.

### `bootstrap.py`

Builds the standard composed General + University bootstrap over shared registries.

### `__init__.py`

Provides an explicit, side-effect-free public API.

---

## 4. Canonical Entity Semantics

Exactly 14 semantic entity types:

1. `degree`
2. `university`
3. `academic_year`
4. `semester`
5. `subject`
6. `assignment`
7. `examination`
8. `exam_attempt`
9. `grade`
10. `deadline`
11. `professor`
12. `adaptation`
13. `credit`
14. `academic_requirement`

These are semantic entity types over canonical shared entity/knowledge contracts.

They are NOT new persistent entity classes.

No University-specific entity store is introduced.

Entity references must preserve, where applicable:

- provenance;
- temporal scope;
- version;
- academic year/semester context;
- source authority context;
- relationship to canonical source resources.

An `exam_attempt` is semantically distinct from an `examination`.

A `grade` is semantically distinct from observed performance analysis.

An `adaptation` represents an academic accommodation/adaptation fact or requirement when authorized. It must not import detailed medical history by default.

A `credit` represents academic credit/ECTS state, not workload-hours by itself.

---

## 5. Canonical Resources

Exactly 12 canonical University resources:

1. `university.academic_record`
2. `university.subject_guide`
3. `university.university_calendar`
4. `university.examination_schedule`
5. `university.assignment`
6. `university.grade`
7. `university.email`
8. `university.note`
9. `university.study_session`
10. `university.user_message`
11. `university.regulation`
12. `university.memory_entry`

All resources reuse shared identity, provenance, temporal, reliability, sensitivity and permission contracts.

A shared underlying resource must not be duplicated merely because it has a University binding.

Examples:

```text
one email resource
    -> University interpretation binding
    -> possibly General interpretation binding

one calendar event
    -> University interpretation binding
    -> possibly Health/Oppositions interpretation binding
```

### Academic-state-capable resources

When authorized and sufficiently grounded, the following kinds may support updates to structured Academic State:

- `university.academic_record`;
- `university.grade`;
- official enrollment/credit facts represented through authorized resources;
- official examination/attempt facts;
- official subject status facts.

### Personal-memory resources

`university.memory_entry` does not override Academic State.

It is suitable for contextual items such as:

- preferences;
- study strategies;
- personal interpretations;
- perceived difficulty;
- desired priorities;
- planning preferences;
- conclusions about what has or has not worked;
- user-confirmed long-lived academic preferences.

These remain subject to Domain Memory policies and confirmation where required.

---

## 6. Contextual Academic Source Authority

University does not use one simplistic global source ranking for every fact.

Authority is attribute-specific.

Canonical source-authority semantics:

### Regulations and requirements

Prefer, when applicable:

```text
current official regulation
    > specific official act/resolution
    > other contextual references
```

The exact relation may depend on legal/academic competence and scope.

A later informal source does not supersede an authoritative regulation merely because it is newer.

### Grades, credits, enrollment and official record

Prefer:

```text
official academic record
    > official grade publication / official institutional record
    > other references
```

User recollection may be useful as a lead but must not silently replace a contradictory official record.

### Subject evaluation system

Prefer:

```text
current official subject guide / teaching plan
    > later official professor instruction when authorized to concretize it
    > institutional email/context
    > personal notes
```

The implementation must not hard-code assumptions about whether a professor can override a particular rule. It must preserve source scope and authority.

### Examination date or specific call

Prefer:

```text
specific current official examination/call publication
    > general academic calendar
```

A generic calendar cannot silently override a more specific valid official call.

### Assignment deadline

Prefer:

```text
official subject platform/publication or specific institutional instruction
    > current subject guide
    > personal reminder/note
```

### Study progress

For facts belonging to the user's own activity, primary evidence may be:

- study-session records;
- user notes;
- user messages;
- user-confirmed progress records.

The university is not authoritative over whether the user studied for three hours on a given day.

### Same-level priority

Within the same authority level, evaluate:

```text
validity
+
specificity
+
provenance
+
scope
```

Recency alone is insufficient.

A newer source does not automatically win when it lacks authority to alter the relevant fact.

No caller-supplied boolean such as `official=True` may by itself create authority.

Official status must be grounded in resource/source metadata validated through existing contracts.

---

## 7. Contradiction and Temporal Resolution

A material academic contradiction must never be silently discarded.

University must preserve:

- both or all conflicting claims/references;
- provenance;
- temporal scope;
- source class/authority where represented by current contracts;
- specificity;
- reason for any resolution;
- unresolved status when resolution is not justified.

Canonical principle:

```text
conflicting sources
!=
permission to choose arbitrarily
```

If one source can be shown to supersede another due to valid scope, temporality and authority, the system may resolve the current value while preserving history.

If equivalent authoritative sources conflict:

```text
conflict = unresolved
```

until sufficient evidence is obtained.

Example:

```text
institutional email -> exam on 18th
academic calendar   -> exam on 17th
specific later official call -> exam on 18th
```

A justified resolution toward the 18th is possible only because the specific official call has the relevant authority/specificity and temporal relationship.

If two equivalent official publications conflict, do not invent.

For decision-critical unresolved conflicts, University should:

1. trigger conditional official-source verification when policy permits;
2. otherwise expose the conflict and request confirmation/resource;
3. block decisions/actions that require the unresolved fact.

Historical truth must remain distinguishable from current truth.

A superseded date, grade, requirement or subject state remains part of history when relevant.

---

## 8. Academic State vs Personal Memory

This separation is a hard contractual decision.

```text
Academic State
!=
Personal Memory
```

### Academic State

Structured, objective academic state may be updated when sufficiently grounded and authorized.

Examples:

- enrolled subject;
- passed subject;
- failed subject;
- official grade;
- recognized credit;
- pending credit;
- exam attempt;
- reassessment status;
- degree requirement;
- official deadline;
- subject status.

Academic State should preserve:

- source references;
- temporal validity;
- version/history;
- contradictions;
- confidence/grounding status where applicable.

### Personal Memory

Interpretive or preference-like information is proposal-only under the shared memory policy.

Examples:

- "I prefer to study one subject at a time";
- perceived difficulty;
- predicted result;
- preferred study technique;
- interpretation of why an exam went badly;
- strategy preference;
- conclusion that a subject is "easy" or "hard";
- preferred workload distribution.

These must not silently become durable memory merely because an academic workflow inferred them.

### No substitution

A memory item saying "subject X passed" does not automatically override an official academic record saying otherwise.

Memory can point the resolver toward relevant evidence.

It is not an authority shortcut.

---

## 9. Pure Deterministic Academic Helpers

The domain uses:

```text
declarative domain
+
pure deterministic helpers
```

It does not introduce a University reasoning engine.

Conceptual helpers may include:

```text
classify_academic_source_authority()
resolve_academic_conflict()
classify_deadline_grounding()
calculate_ects_state()
classify_exam_attempt()
evaluate_academic_dependencies()
evaluate_workload_feasibility()
compare_academic_options()
classify_academic_integrity_constraint()
separate_performance_from_capacity()
```

Exact signatures must follow real repository conventions discovered during implementation.

Helpers must:

- be pure;
- be deterministic;
- perform no IO;
- perform no model calls;
- perform no external search;
- perform no registry mutation;
- perform no memory persistence;
- perform no calendar/task mutation;
- use no hidden clock;
- accept temporal reference explicitly where needed;
- preserve relevant source/provenance references;
- return structured results;
- reject malformed/unknown state fail-closed.

If an existing shared helper already represents the same semantics, reuse it rather than creating a University duplicate.

---

## 10. Deadline Grounding and Temporal Validity

A deadline/date may be represented in several epistemic states, conceptually including:

```text
confirmed_official
reported
remembered
inferred
calculated
conflicting
unknown
```

Use actual repository enums/contracts if they already represent this distinction.

The design requirement is semantic, not a mandate to invent a new enum.

`AcademicDeadlineRule` must ensure that:

- a confirmed deadline has an authorized grounding source;
- a recalled deadline is not silently promoted to confirmed;
- an inferred deadline remains an inference;
- a conflicting deadline remains visibly conflicting until resolved;
- historical deadlines are not treated as current;
- academic year/semester context is preserved;
- timezone is explicit when time-of-day matters;
- a decision-critical stale date can trigger conditional verification.

A missing temporal reference must not cause an expired item to become current by default.

Unknown relative ordering must remain unknown.

---

## 11. ECTS Consistency

`ECTSConsistencyRule` validates and reasons about:

- completed credits;
- recognized credits;
- enrolled credits;
- pending credits;
- required credits;
- optional/elective requirements where represented;
- prerequisite relationships;
- degree-completion totals;
- duplicate credit counting;
- incompatibilities;
- state changes over time.

The rule must not:

- double-count the same canonical credit;
- treat enrolled credits as completed;
- treat a planned recognition as already granted;
- fabricate missing curriculum requirements;
- silently resolve contradictory official credit records.

Where information is incomplete, output must preserve the gap and indicate which completion calculations are conditional.

Example:

```text
Known completed = 210 ECTS
Pending subject = 6 ECTS
TFG = 6 ECTS
Unknown recognition request = 6 ECTS
```

The system may produce scenarios.

It must not state a definitive completion total that assumes the unresolved recognition request is granted.

---

## 12. Exam Attempts and Reassessment

`ExamAttemptRule` distinguishes, when applicable:

- ordinary examination/call;
- reassessment/re-evaluation;
- separate exam attempts;
- exhausted or remaining attempts only when grounded;
- regulatory changes;
- annulled/cancelled/waived attempts if represented by authoritative sources;
- historical attempt status from current attempt status.

Do not infer institutional attempt consumption from a failed grade alone unless the relevant rule/source establishes it.

Do not treat reassessment as a new ordinary call unless the applicable academic rules establish that semantics.

When the applicable rules are missing or changing, the result must remain conditional and may trigger official verification.

---

## 13. Academic Workload

`AcademicWorkloadRule` evaluates feasibility using grounded constraints and explicit assumptions.

Possible inputs include:

- subjects;
- deadlines;
- exam dates;
- assignment requirements;
- ECTS/load;
- observed study time;
- available time;
- other academic dependencies;
- user-defined priorities;
- authorized minimal functional constraints imported from Health;
- other explicitly authorized goals/constraints through cross-domain composition.

Canonical decision order:

```text
1. hard constraints
2. feasibility
3. explicit user preferences
4. trade-offs
5. scenarios
```

Hard constraints may include:

- impossible date ordering;
- prerequisite not satisfied;
- insufficient available time under an explicit minimum assumption;
- mutually incompatible obligations;
- authorized health-related availability/load constraints;
- institutional requirements.

Only after infeasible options are eliminated should University rank/compare remaining options using explicit user preferences such as:

- speed;
- expected grade priority;
- effort;
- risk;
- cost;
- schedule preference;
- reversibility;
- completion timing.

The system may classify a plan as fragile or infeasible when the evidence supports that conclusion.

It must expose assumptions and uncertainty.

---

## 14. Academic Dependencies

`AcademicDependencyRule` detects and represents:

- prerequisites;
- co-requisites when applicable;
- subject dependencies;
- credits needed before TFG or other requirements;
- administrative/academic conditions for degree closure;
- dependencies between assignments/exams/subject status;
- sequencing constraints;
- unresolved dependency facts.

Dependency edges must be grounded.

Do not invent a prerequisite because a subject "looks advanced".

A planning workflow must not schedule a dependent academic step as feasible when a blocking prerequisite is unresolved or known unsatisfied.

---

## 15. Observed Performance vs Capacity

`ObservedPerformanceCapacityRule` is a hard epistemic boundary.

University may analyze:

- grades;
- exam outcomes;
- completion rate;
- study sessions;
- missed deadlines;
- trends;
- error patterns;
- preparation indicators;
- observed progress.

University may cautiously estimate:

- current risk of missing a deadline;
- current risk of failing an exam;
- likely workload pressure;
- plan fragility;
- progress against an explicit target.

Such estimates must preserve factors and uncertainty.

University MUST NOT infer from academic performance alone:

- intelligence;
- intellectual capacity;
- giftedness;
- lack of ability;
- general potential;
- stable personal worth;
- neurodevelopmental diagnosis.

Forbidden promotion:

```text
observed low grade
-> low intellectual capacity
```

Forbidden:

```text
one failed exam
-> incapable of subject/domain
```

Allowed:

```text
Observed result: 4.2/10.
Current evidence suggests preparation was incomplete in X and Y areas.
This does not establish underlying intellectual capacity.
```

---

## 16. Academic Integrity — Approved Mode C

This is a hard contractual decision.

University uses a permissive-by-default assistance policy grounded in known rules.

Canonical semantics:

```text
no accredited restriction
-> assistance allowed by default
```

The system must not treat ambiguous wording as proof of misconduct.

If no explicit sufficiently grounded restriction on AI/assistance is known, University may help produce academic work, including substantial drafting and problem solving, subject to general platform policy.

It may optionally flag that course-specific rules were not verified when that uncertainty materially matters.

If an explicit, sufficiently grounded academic rule restricts AI or external assistance:

- respect that concrete restriction;
- distinguish what is prohibited from what remains allowed;
- continue to teach, explain, review, quiz, outline or otherwise assist within the permitted scope;
- preserve the source and temporal validity of the restriction.

A caller cannot create an integrity prohibition merely by setting a boolean without grounding.

A remembered prohibition is not automatically equivalent to a current official prohibition.

A later official rule may supersede an earlier one if authority, scope and temporality justify it.

University must not invent a moral/disciplinary rule that is not in the authorized evidence or platform policy.

---

## 17. Academic Decision Preservation

`AcademicDecisionPreservationRule` ensures that University supports decisions without adopting them.

University may:

- enumerate options;
- eliminate demonstrably infeasible options;
- identify explicit user criteria;
- compare feasible options against those criteria;
- calculate trade-offs;
- identify risk and uncertainty;
- show which option best matches explicit criteria;
- preserve alternative routes.

University must NOT:

- mark a scenario as the user's chosen decision without confirmation;
- persist a proposed route as decided;
- enroll/withdraw/register anything;
- communicate a choice to the university;
- treat recommendation as commitment;
- infer that the user abandoned another academic goal.

Allowed output:

> Scenario B satisfies all hard constraints and best matches the priority you explicitly gave to finishing in January.

Not allowed:

> You have decided to take Scenario B.

An academic decision becomes explicit only after user confirmation or an authoritative external record showing the decision was already made.

---

## 18. Canonical Reasoning Rules

Exactly 10 canonical University rules:

1. `AcademicSourceAuthorityRule`
2. `AcademicContradictionRule`
3. `AcademicDeadlineRule`
4. `ECTSConsistencyRule`
5. `ExamAttemptRule`
6. `AcademicWorkloadRule`
7. `AcademicDependencyRule`
8. `ObservedPerformanceCapacityRule`
9. `AcademicIntegrityRule`
10. `AcademicDecisionPreservationRule`

### 1. `AcademicSourceAuthorityRule`

Evaluates authority according to attribute, source class, provenance, temporal validity, specificity and scope.

It absorbs the relevant temporal-authority semantics previously described by the roadmap's `AcademicTemporalValidityRule` without losing those requirements.

### 2. `AcademicContradictionRule`

Preserves incompatible academic claims and resolves only when sufficient authority/temporal/scope evidence exists.

Otherwise remains unresolved.

### 3. `AcademicDeadlineRule`

Checks dates, calls and deadlines with explicit grounding and temporal state.

### 4. `ECTSConsistencyRule`

Checks credits, requirements, completion totals, incompatibilities and double counting.

### 5. `ExamAttemptRule`

Distinguishes attempts, ordinary calls, reassessment and applicable regulatory constraints.

### 6. `AcademicWorkloadRule`

Evaluates workload and feasibility using hard constraints before preferences.

It incorporates authorized minimal functional constraints from Health without importing full clinical detail by default.

### 7. `AcademicDependencyRule`

Represents prerequisites, dependencies and degree-completion sequencing.

### 8. `ObservedPerformanceCapacityRule`

Keeps observed performance distinct from intellectual/potential capacity.

### 9. `AcademicIntegrityRule`

Implements Approved Mode C: permissive by default, restricted only by sufficiently grounded applicable rules.

### 10. `AcademicDecisionPreservationRule`

Ensures comparison/recommendation does not become an adopted user decision.

Rule IDs must follow actual CMM OS naming conventions discovered from the repository.

`catalog.py` remains the single source of truth.

No second rule catalog.

---

## 19. University Profile

`UniversityProfile` is a normal `DomainProfileDefinition`.

It does not introduce a specialized reasoning engine.

Profile characteristics:

- prioritize verifiable academic data;
- explicit provenance;
- explicit temporal validity;
- preserve contradictions;
- distinguish current from historical academic state;
- preserve unknowns and gaps;
- hard constraints before preferences;
- observed performance distinct from capacity;
- decision support without delegated decision-making;
- academic-integrity Mode C;
- ask only when a missing fact materially affects analysis or a decision/action cannot safely proceed;
- continue under non-blocking uncertainty with visible assumptions;
- controlled memory;
- no automatic external communication;
- no automatic formal procedure;
- external official verification only under the approved conditional policy.

The profile must remain compatible with Phase 8's University profile semantics:

```text
verifiable academic data
+ temporal exam/assessment context
+ objectives
+ workload
+ constraints
+ dependencies
+ observed performance != capacity
```

---

## 20. Canonical Operations

Exactly 11 operations:

1. `university.plan_semester`
2. `university.create_study_plan`
3. `university.review_academic_record`
4. `university.compare_semesters`
5. `university.prepare_exam`
6. `university.prepare_assignment`
7. `university.track_deadlines`
8. `university.analyse_performance`
9. `university.generate_academic_summary`
10. `university.update_subject_status`
11. `university.review_degree_completion`

### `university.plan_semester`

Purpose:

- build feasible semester scenarios;
- load subjects, requirements, dates, dependencies and available capacity;
- reject infeasible scenarios when grounded;
- compare remaining scenarios using explicit preferences;
- produce a plan/proposal only.

Must not create calendar events or tasks directly.

### `university.create_study_plan`

Purpose:

- create a structured study plan from academic objectives, deadlines, available time, dependencies and constraints;
- preserve assumptions and uncertainty;
- produce proposal data suitable for later shared task/calendar actions.

No direct scheduling mutation.

### `university.review_academic_record`

Purpose:

- inspect authorized academic-record facts;
- identify completed/pending credits;
- identify subject status;
- detect contradictions/gaps;
- preserve source/version/temporality.

It does not modify the official record.

### `university.compare_semesters`

Purpose:

- compare academic periods using comparable grounded dimensions;
- distinguish observed change from causal interpretation;
- preserve differences in subject mix, workload and constraints.

### `university.prepare_exam`

Purpose:

- structure exam requirements;
- evaluation format;
- scope/content;
- materials;
- available time;
- preparation plan;
- open questions.

It may adjust planning using observed progress.

It does not infer capacity from predicted or observed performance.

### `university.prepare_assignment`

Purpose:

- interpret the assignment;
- identify requirements;
- identify deadline and source grounding;
- organize sources/material;
- create work structure;
- assist with production under Academic Integrity Mode C.

It must respect explicit sufficiently grounded course restrictions.

### `university.track_deadlines`

Purpose:

- collect;
- normalize;
- order;
- verify;
- classify grounding;
- detect conflicts/staleness;
- identify upcoming academic dates.

It may output a proposal for later calendar/task creation.

It does not mutate calendar/task systems itself.

### `university.analyse_performance`

Purpose:

- analyze observed results and progress;
- identify trends/factors supported by inputs;
- estimate risk cautiously;
- preserve uncertainty.

It must never infer intellectual capacity from performance.

### `university.generate_academic_summary`

Purpose:

- produce structured summary of academic state, dates, requirements, workload, risks, progress, contradictions and open questions.

It does not persist decisions automatically.

### `university.update_subject_status`

Purpose:

- update INTERNAL Academic State only;
- use sufficiently grounded academic evidence;
- preserve history/provenance;
- distinguish statuses using actual repository contracts.

Conceptual statuses may include:

```text
enrolled
in_progress
passed
failed
withdrawn
pending
unknown
```

Use actual existing types if available.

This operation NEVER modifies a university system or official academic record.

### `university.review_degree_completion`

Purpose:

- calculate/compare completion scenarios;
- evaluate ECTS;
- requirements;
- dependencies;
- pending subjects;
- attempts;
- TFG dependencies;
- timing.

It may compare routes.

It never adopts the route as the user's decision.

### Hard operation boundary

None of the 11 operations may:

- send an email;
- send a message;
- create an external calendar event directly;
- create a persistent task directly through a duplicate University implementation;
- file an appeal;
- submit an accommodation request;
- submit credit recognition;
- register/enroll/withdraw;
- make payment;
- modify official grades;
- modify the university record;
- adopt a final academic decision.

---

## 21. Operation Execution Model

Canonical invariant:

```text
operation definition != implementation
```

A missing implementation means:

```text
UNAVAILABLE / fail-closed
```

No fake delegates.

No production lambda/stub that returns success without real semantics.

Injected implementations must pass the existing canonical public operation-implementation validator before the first registry mutation.

Operation schemas must:

- be closed according to current shared conventions;
- be semantically distinct;
- define actual required fields;
- use meaningful canonical resource requirements;
- avoid one generic schema copied across all operations;
- preserve provenance/temporality references where relevant;
- not expose narrative/PII through metadata where reference-only contracts are expected.

Hard distinctions:

```text
PLAN != TASK/CALENDAR MUTATION
PREPARATION != COMMUNICATION
ANALYSIS != DECISION
PROPOSAL != MUTATION
ACADEMIC STATE != OFFICIAL UNIVERSITY RECORD
```

---

## 22. Academic State Mutation Boundary

`university.update_subject_status` is the only canonical operation whose name implies a persistent state update.

Its boundary is deliberately narrow.

It may update CMM OS's internal Academic State only through existing authorized state/memory/knowledge mechanisms.

It must preserve:

- source;
- prior version;
- temporal scope;
- reason for update;
- trace references;
- conflict state when unresolved.

It must not:

- write to university infrastructure;
- overwrite source documents;
- delete historical status silently;
- convert a prediction into status;
- treat a proposed grade as official;
- treat an unverified user recollection as stronger than an official contradictory record.

If the existing architecture does not yet expose a direct persistent Academic State writer at this phase boundary, the implementation must use the existing authorized proposal/update path rather than invent a store.

---

## 23. Canonical Workflows

Exactly 7 canonical workflows:

1. `university.semester_planning`
2. `university.exam_preparation`
3. `university.academic_review`
4. `university.reassessment_planning`
5. `university.assignment_preparation`
6. `university.degree_completion_review`
7. `university.tfg_planning`

These correspond to the roadmap workflows:

- Semester Planning;
- Exam Preparation;
- Academic Review;
- Reassessment Planning;
- Assignment Preparation;
- Degree Completion Review;
- TFG Planning.

No additional University workflow is canonical in Phase 10.22.

---

## 24. Workflow Safety Structure

All University workflows reuse the shared Workflow Engine.

Conceptual common ordering:

```text
load authorized academic resources
        ↓
resolve relevant source authority / temporal state
        ↓
apply University profile
        ↓
apply relevant University rules
        ↓
detect contradictions / gaps
        ↓
conditional official verification when permitted and required
        ↓
apply hard constraints
        ↓
perform domain analysis/planning
        ↓
compare scenarios using explicit user preferences
        ↓
validate
        ↓
optional proposal(s)
        ↓
optional memory proposal
        ↓
complete / wait / request approval / pause
```

No workflow may bypass the source-authority, contradiction, integrity or decision-preservation path relevant to its output.

A blocked required rule must not silently reach normal completion.

Memory proposal is OPTIONAL.

External action is not a mandatory terminal step.

Workflows must use actual supported shared nodes/operations discovered in the repository.

Do not invent a second set of workflow node semantics.

---

## 25. Semester Planning

Canonical ID:

```text
university.semester_planning
```

Purpose:

- load academic record;
- load subjects;
- load relevant dates;
- load academic requirements;
- load dependencies;
- load available time/capacity;
- load authorized minimal constraints from supporting domains when applicable;
- evaluate workload;
- detect conflicts;
- generate scenarios;
- discard infeasible scenarios when grounded;
- compare feasible scenarios using explicit preferences;
- generate a semester plan proposal.

Conceptual flow:

```text
Load Academic State
→ Load Subjects
→ Load Deadlines
→ Load Academic Constraints
→ Load Authorized Capacity Constraints
→ Apply Source/Temporal Rules
→ Detect Contradictions
→ Evaluate Workload
→ Detect Dependencies
→ Generate Scenarios
→ Reject Grounded Infeasible Scenarios
→ Compare Remaining Scenarios
→ Validate
→ Produce Plan Proposal
→ Optional Task/Calendar Proposals
→ Complete
```

Creating actual tasks or calendar events belongs to shared external-action capabilities and is approval-gated.

The workflow never enrolls the user in subjects.

---

## 26. Exam Preparation

Canonical ID:

```text
university.exam_preparation
```

Purpose:

- load subject/evaluation requirements;
- identify exam date and grounding;
- identify exam format;
- identify scope/material;
- calculate available preparation period;
- incorporate observed study progress;
- identify gaps;
- create/update preparation plan;
- preserve uncertainty.

Conceptual flow:

```text
Load Subject Guide / Exam Sources
→ Verify Exam Date when needed
→ Resolve Evaluation Requirements
→ Load Available Time
→ Load Study Progress
→ Apply University Rules
→ Detect Gaps / Conflicts
→ Build Preparation Plan
→ Evaluate Feasibility
→ Validate
→ Optional Schedule Proposal
→ Complete
```

A risk estimate may be produced.

It must not become a statement about intellectual capacity.

---

## 27. Academic Review

Canonical ID:

```text
university.academic_review
```

Purpose:

produce a structured snapshot of:

- credits;
- passed/pending subjects;
- current subject status;
- official grades where available;
- observed performance;
- workload;
- deadlines;
- academic requirements;
- risks;
- contradictions;
- gaps;
- progress;
- next academic actions/questions.

This workflow is primarily analytical.

It may serve as input to:

- semester planning;
- degree-completion review;
- reassessment planning;
- exam preparation.

It does not require a persistent memory write to complete.

---

## 28. Reassessment Planning

Canonical ID:

```text
university.reassessment_planning
```

Purpose:

- identify reassessment/re-evaluation eligibility;
- distinguish attempt semantics;
- verify dates/rules when needed;
- identify pending requirements;
- compare reassessment workload against other subjects;
- model opportunity cost;
- produce a preparation/decision-support plan.

Conceptual flow:

```text
Load Exam / Attempt History
→ Load Reassessment Rules
→ Verify Current Rule/Date when needed
→ Apply ExamAttemptRule
→ Detect Dependencies
→ Load Competing Academic Load
→ Evaluate Feasibility
→ Generate Scenarios
→ Compare Against Explicit Priorities
→ Validate
→ Complete
```

It must not conflate:

- reassessment;
- ordinary attempt;
- new enrollment;
- regulatory attempt exhaustion.

If the governing rule is unknown, preserve the gap.

---

## 29. Assignment Preparation

Canonical ID:

```text
university.assignment_preparation
```

Purpose:

- load assignment instructions;
- identify requirements;
- identify deadline;
- identify sources/material;
- identify evaluation criteria when known;
- determine applicable integrity restrictions;
- break work into stages;
- assist with production under Approved Mode C;
- validate that no known accredited restriction is violated.

Conceptual flow:

```text
Load Assignment Resource
→ Load Relevant Subject Guide / Rules
→ Resolve Deadline
→ Resolve Integrity Constraints
→ Detect Missing Requirements
→ Build Work Structure
→ Assist with Preparation / Production
→ Validate Against Known Constraints
→ Optional Task Proposal
→ Complete
```

If no explicit sufficiently grounded restriction exists, assistance remains permissive by default.

---

## 30. Degree Completion Review

Canonical ID:

```text
university.degree_completion_review
```

Purpose:

- calculate current grounded ECTS state;
- identify pending credits/subjects;
- identify degree requirements;
- identify dependencies;
- identify attempt/reassessment constraints;
- identify TFG dependencies;
- identify timeline constraints;
- build completion scenarios;
- compare viable routes;
- expose uncertainties.

Conceptual flow:

```text
Load Academic Record
→ Load Degree Requirements
→ Apply ECTSConsistencyRule
→ Apply AcademicDependencyRule
→ Load Attempts / Deadlines
→ Detect Conflicts / Gaps
→ Build Completion Scenarios
→ Reject Infeasible Scenarios
→ Compare Feasible Routes
→ Validate
→ Complete
```

The workflow never marks a route as adopted without user confirmation.

---

## 31. TFG Planning

Canonical ID:

```text
university.tfg_planning
```

TFG remains inside University Domain.

No TFG subdomain is created.

Purpose:

- identify TFG eligibility requirements;
- tutor/advisor milestones when available;
- proposal/research/writing milestones;
- submission requirements;
- defense requirements;
- dependencies on credits/subjects;
- relevant dates;
- available time;
- risks/gaps;
- completion relation to the degree.

The workflow reuses existing University rules and operations.

Conceptual flow:

```text
Load TFG / Degree Requirements
→ Load Academic State
→ Detect Eligibility Dependencies
→ Load Dates / Milestones
→ Verify Decision-Critical Current Rules when needed
→ Build Milestone Plan
→ Evaluate Workload
→ Detect Risks / Gaps
→ Validate
→ Optional Task/Calendar Proposals
→ Complete
```

It does not submit a TFG proposal, registration, document or defense request.

---

## 32. Conditional External Verification — Official Read-Only

This is a hard contractual decision.

University may perform or request external verification only when effective policy permits and an academic fact is:

```text
missing
or
stale
or
conflicting
or
decision-critical and insufficiently grounded
```

The preferred source class is:

```text
OFFICIAL_ONLY
```

Use the current Phase 10.15 source-class permission contracts.

Verification may target, for example:

- current regulations;
- official calls;
- academic calendar;
- examination schedule;
- subject guide;
- official deadline;
- enrollment requirement;
- reassessment rule;
- TFG requirement.

Verification is read-only.

It must preserve:

- source reference;
- retrieval date/time;
- source class;
- provenance;
- temporal scope;
- relation to the unresolved fact;
- trace decision.

It must NOT:

- continuously monitor all university data;
- contact the university;
- submit a request;
- log in with credentials unless a separately authorized integration exists in a later layer;
- perform an external mutation;
- widen permissions because the fact is important.

No monitoring loop is introduced in 10.22.

Continuous monitoring belongs to agents/automations/integrations when separately designed and authorized.

---

## 33. Cross-Domain Health → University Projection

The approved mode is hybrid with minimum projection by default.

Canonical principle:

```text
Health detailed context
    --X--> University by default

Authorized minimal functional constraint
    -----> University when relevant and permitted
```

University normally needs constraints such as:

- temporarily unavailable on a date;
- reduced available workload/capacity;
- cannot attend a particular activity;
- schedule restriction;
- authorized adaptation/accommodation fact.

It normally does NOT need:

- diagnosis details;
- medication lists;
- test results;
- clinical narrative;
- specialist notes;
- complete medical history.

Detailed clinical information may enter University only through explicit effective authorization and scoped cross-domain transfer.

Supporting-domain participation must not widen University permissions.

The most restrictive effective policy wins.

`AcademicWorkloadRule` consumes the authorized constraint projection; it does not fetch Health records directly.

No direct `health` store access from the University package.

---

## 34. External Actions Boundary

University specializes academic reasoning and preparation.

It does not duplicate shared action capabilities.

### Calendar

University may:

- detect dates;
- generate structured calendar proposals;
- identify schedule conflicts;
- request a common calendar action.

Actual calendar mutation is:

```text
shared capability
+
explicit approval
+
post-action verification when required by platform policy
```

No `university.create_calendar_event` operation is introduced.

### Tasks

University may:

- propose tasks;
- structure study tasks;
- propose due dates;
- request a common task-creation action.

Persistent task creation is approval-gated according to effective policy.

No duplicate University task engine.

### Email / academic communication

University is PREPARATION ONLY.

It may:

- draft an email;
- prepare arguments/questions;
- review wording;
- prepare supporting facts;
- identify recipient role when already known.

It must NEVER send the email/message in Phase 10.22.

Even if a shared communication capability exists elsewhere, University's canonical operations/workflows do not directly execute it.

### Formal academic procedures

Formal procedures are PREPARATION ONLY.

Examples:

- grade review;
- reassessment request;
- complaint/appeal;
- credit recognition;
- adaptation/accommodation request;
- enrollment exception;
- administrative request;
- TFG registration/defense procedure.

University may:

1. identify the possible route;
2. verify current official requirements/deadlines;
3. collect authorized relevant documents;
4. structure factual grounds;
5. draft text;
6. produce checklist;
7. expose legal/academic uncertainty.

University must NOT:

- submit;
- register;
- sign;
- send;
- pay;
- impersonate the user;
- create a final legal/administrative act.

---

## 35. Missing and Incomplete Information

University uses prudent continuation rather than automatic blocking for every gap.

Canonical behavior:

```text
non-blocking gap
-> continue with explicit assumption/uncertainty

blocking decision-critical gap
-> verify official source if permitted
   OR ask for confirmation/resource
   OR pause/block affected decision/action
```

Every materially incomplete result must expose:

- what is missing;
- what assumption, if any, was used;
- impact of the gap;
- confidence/uncertainty;
- which conclusion remains conditional;
- which action/decision must not proceed without resolution.

Do not silently fill missing official academic facts with general knowledge or memory.

---

## 36. Permissions

Use current shared Domain Permission contracts.

University baseline semantics:

- authorized academic resource reads allowed according to effective policy;
- authorized memory read according to effective policy;
- structured academic analysis allowed;
- planning allowed;
- reversible plan/proposal generation allowed;
- external official read-only verification allowed conditionally and only under effective policy/source class;
- calendar/task mutations require explicit approval through shared capabilities;
- email/communication is preparation-only in the canonical University domain;
- formal procedures are preparation-only;
- no automatic registration/enrollment;
- no official-record modification;
- no payment;
- no final academic decision;
- cross-domain transfer requires scoped permission;
- Health detailed information is denied by default absent explicit scoped authorization;
- supporting domain cannot widen permissions;
- memory persistence follows Academic State vs Personal Memory rules and shared approval/confirmation requirements.

### Privacy

Phase 10's initial University privacy orientation may be `REMOTE_ALLOWED`, but this does NOT grant remote processing by itself.

Effective privacy remains the most restrictive intersection of:

- global policy;
- user policy;
- session policy;
- resource policy;
- Knowledge Package policy;
- domain policy;
- workflow policy;
- operation policy;
- model/provider policy.

University cannot weaken `LOCAL_ONLY` or more restrictive resources.

University cannot select a provider directly.

### Source search

External search does not mean arbitrary web search.

When this domain initiates verification under its canonical policy, it requests `OFFICIAL_ONLY` source class unless a higher-level explicit policy says otherwise.

### Approval scope

An approval is scoped.

A one-shot calendar approval does not create a permanent grant.

Task approval does not authorize communication.

Read permission does not imply mutation permission.

Proposal permission does not imply apply permission.

---

## 37. Presentation

Canonical University presentation separates these 10 conceptual sections:

1. `subjects`
2. `states`
3. `dates`
4. `dependencies`
5. `workload`
6. `risks`
7. `scenarios`
8. `plan`
9. `progress`
10. `next_review`

These names may be adapted to actual `DomainPresentationPolicy` conventions while preserving the same semantics.

Presentation must preserve:

- provenance where required;
- source authority distinctions;
- temporal validity;
- unresolved contradictions;
- uncertainty;
- gaps;
- assumptions;
- approval requirements;
- decision/proposal status;
- integrity restrictions when relevant.

Presentation must not transform:

```text
remembered date
-> confirmed deadline
```

```text
prediction
-> grade fact
```

```text
observed performance
-> intellectual capacity
```

```text
best-matching scenario
-> adopted decision
```

```text
plan proposal
-> external task/calendar mutation
```

```text
email draft
-> communication sent
```

`warning_position`, uncertainty, provenance and other generic presentation semantics must reuse the current shared Domain Presentation implementation.

No University renderer may rewrite epistemic status.

---

## 38. Memory

Reuse Phase 10 Domain Memory contracts.

No `UniversityMemory` store.

University may:

- request authorized memory views;
- build update proposals;
- bind proposals using current public Domain Memory APIs;
- request confirmation where required.

University must distinguish:

### Objective durable academic state

When authorized and grounded, factual state may be updated through the canonical state/knowledge path.

Examples:

- official grade;
- subject passed;
- recognized credits;
- enrollment state;
- confirmed deadline;
- attempt status.

### Interpretive/personal memory

Requires proposal/confirmation according to current policy.

Examples:

- preferred study strategy;
- perceived difficulty;
- inferred risk tendency;
- preferred exam preparation style;
- conclusions about personal performance;
- preferred semester configuration.

University must NOT:

- directly persist through a new store;
- silently convert a prediction to fact;
- overwrite history;
- remove provenance;
- store an inferred academic decision as confirmed;
- store detailed Health information merely because it was used as a temporary constraint.

Use only current PUBLIC memory digest/binding helpers.

Do not import private `_...` helpers.

---

## 39. Trace

Reuse Domain Trace.

No `UniversityTrace`.

Trace remains reference-only.

It may reference:

- domain resolution;
- resources;
- profile;
- rules;
- operations;
- workflows;
- source-authority decisions;
- contradiction decisions;
- external-verification decisions;
- permission decisions;
- cross-domain transfer decisions;
- approvals;
- memory views/proposals;
- result;
- academic safety/integrity reason codes where current contracts support them.

Never fabricate IDs.

Never store chain-of-thought.

Never store hidden prompts or secrets.

Do not copy academic record payload or other sensitive narrative into reference-only trace metadata.

---

## 40. Standard Bootstrap

The standard University bootstrap must follow the FINAL hardened precedents of General, Health and Relationships.

It composes:

```text
General
+
University
```

over the SAME registries.

General remains:

```text
fallback_domain = domain:general
```

University is a specialized candidate.

Do NOT configure University as fallback.

Do NOT create a `UniversityResolver`.

Required semantics:

- generic input may resolve General;
- valid University signal may resolve University;
- specialized University beats General when eligible;
- denied/unavailable/unauthorized/disabled University cannot silently fall through to General when global fallback-blocking policy requires `BLOCKED`;
- a University-like request must not become permitted via General when University would deny the requested action;
- fresh standard bootstraps are deterministic/equivalent;
- General and University share registries;
- no import-time registration.

If the repository now exposes a broader standard bootstrap introduced after Relationships, integrate into that canonical path instead of creating a second incompatible standard builder.

---

## 41. Validation-First Atomic Registration

`register_university_domain()` must incorporate the final lessons from General, Health and Relationships from its FIRST implementation.

All deterministic conflicts that normal `register()` can reject, and that are observable through public APIs, must be prevalidated BEFORE the first mutation.

At minimum:

### Domain

- duplicate Domain definition.

### Profile

- duplicate profile ID;
- existing profile for `domain:university`.

### Resources

- canonical resource collisions.

### Rules

- canonical reasoning-rule collisions.

### Operations

- local `DomainOperation` collision;
- nested common Agent Operation collision where that is the current architecture;
- unknown implementation ID;
- `implementation.definition` mismatch;
- invalid execute signature;
- invalid implementation according to the canonical public validator.

### Workflows

- local Domain Workflow collision;
- nested common Workflow collision;
- invalid workflow definition where deterministically testable;
- unsupported node/operation references where current public APIs expose validation.

### Permissions

- policy collision.

### Presentation / Memory / Trace / other registries

- any deterministic conflict a later public `register()` would reject.

Use PUBLIC registry APIs.

Do not inspect private registry internals.

Do not duplicate canonical validators.

Validation-first invariant:

```text
predictable deterministic error
-> zero first-registry mutations
```

Use a counting registry spy in tests to prove this property.

---

## 42. Snapshot and Rollback

Validation-first is the primary defense against deterministic conflicts.

Snapshot/rollback is the secondary transactional defense.

Before the first mutation, capture the complete relevant registration state using established public/supported mechanisms.

On an unexpected failure after mutation:

- restore domain registry;
- restore profile registry;
- restore resource registry;
- restore rule registry;
- restore operation registry;
- restore nested common operation registry if part of the transaction;
- restore workflow registry;
- restore nested common workflow registry if part of the transaction;
- restore permission registry;
- restore presentation registry/other affected registries;
- restore implementation availability/registration parity where applicable.

No partial University registration may remain.

Unexpected exceptions from registries must not be converted into false success.

Do not catch broad exceptions merely to hide failures.

After rollback, registration parity must equal the pre-registration snapshot.

---

## 43. Resolver and Fallback Semantics

University uses the existing default/canonical domain resolver.

Do not create a specialized resolver.

Expected signals may include, using actual repository signal conventions:

- university;
- degree;
- semester;
- subject;
- exam;
- reassessment;
- assignment;
- grade;
- ECTS/credits;
- TFG;
- academic record;
- university deadline;
- subject guide;
- academic planning.

Do not hard-code user-specific subjects or university names into the Domain Pack.

Resolver behavior must preserve:

- explicit-domain priority under current policy;
- session continuity when relevant;
- specialized-domain priority;
- fallback safety;
- ambiguity handling;
- permission constraints;
- deterministic ranking;
- no permission widening through fallback.

A generic request must not become University merely because University is installed.

---

## 44. Public API and Import Safety

`cmm.domains.university` must expose only the public University API justified by current repository conventions.

Expected concepts include builders/accessors for:

- canonical definition;
- profile;
- resources;
- rules;
- operations;
- workflows;
- permission policy;
- presentation policy;
- registration;
- standard bootstrap;
- approved pure helper types/functions if part of the public contract.

Root `cmm.domains` exports should be extended only if that is the established pattern used by General/Health/Relationships.

Import invariants:

- no registration on import;
- no filesystem IO;
- no network IO;
- no external search;
- no clock-dependent mutation;
- no memory access;
- no model call;
- no environment mutation;
- no global registry mutation.

Test clean import in a fresh interpreter.

---

## 45. Academic Requirements-Matrix Coverage

Phase 10.22 must explicitly satisfy these recorded requirements.

### `REQ-DP22-001`

Coordinate subjects, TFG, scholarship/other academic obligations when represented by authorized resources, representation/academic commitments when represented, and cognitive/available workload as a system of priorities under limited resources.

Core reusable mechanisms:

- `AcademicWorkloadRule`;
- `AcademicDependencyRule`;
- semester planning;
- degree-completion review;
- TFG planning;
- explicit user priorities;
- cross-domain constraints only through authorized projection.

The implementation must not hard-code a particular current personal semester into the Domain Pack.

### `REQ-DP22-002`

Verify deadlines and changing academic rules; distinguish source authority and own elaboration; protect academic integrity.

Covered by:

- `AcademicSourceAuthorityRule`;
- `AcademicContradictionRule`;
- `AcademicDeadlineRule`;
- conditional `OFFICIAL_ONLY` verification;
- provenance;
- Academic Integrity Mode C;
- preparation-only formal procedures.

General legal/jurisprudential source distinctions, when relevant to a Law assignment, remain resource/source semantics and must not turn University into a legal-domain engine.

### `REQ-DP22-003`

Implement concrete workflows for:

- semester planning;
- exam preparation;
- reassessment;
- TFG;
- degree completion;
- prioritization under limited capacity.

Covered by the seven canonical workflows and University operations.

---

## 46. Testing Contract

Phase 10.22 must have implementation depth at least equivalent to the FINAL hardened Relationships Domain and must preserve all reusable lessons from General and Health audits.

Implementation test coverage must include:

- package audit;
- canonical catalog reconciliation;
- definition;
- 14 entity semantics;
- 12 resources;
- University profile;
- pure deterministic helpers;
- all 10 reasoning rules;
- all 11 operations;
- all 7 workflows;
- permissions;
- presentation;
- Academic State boundary;
- memory;
- trace;
- integration;
- validation-first adversarial matrix;
- snapshot/rollback;
- resolver;
- bootstrap;
- public API;
- fresh-process clean import;
- external-verification permission boundary;
- cross-domain Health projection;
- E2E canonical academic behavior.

### Source authority tests

At minimum:

- official academic record outranks informal note for record facts;
- specific valid official exam publication can outrank generic calendar for that exam date;
- recency alone does not override scope/authority;
- caller boolean cannot fabricate official status;
- provenance alone does not guarantee truth;
- equivalent authoritative conflict remains unresolved;
- superseded history remains available.

### Deadline tests

- confirmed deadline requires grounding;
- remembered deadline remains non-confirmed;
- stale deadline not treated current;
- conflicting deadline preserved;
- decision-critical unresolved deadline triggers verification/request/pause according to policy;
- unknown temporal ordering stays unknown.

### ECTS tests

- passed/completed differs from enrolled;
- no duplicate counting;
- unresolved recognition creates scenario/uncertainty, not definitive completion;
- degree total uses grounded requirements;
- conflicting record does not silently resolve.

### Exam attempt tests

- ordinary vs reassessment preserved;
- attempts not inferred solely from a failed grade;
- changing regulation can trigger official verification;
- missing rule remains a gap.

### Workload tests

- hard constraints evaluated before preferences;
- infeasible scenario can be eliminated only with grounded constraints;
- explicit user preferences rank remaining feasible scenarios;
- imported Health constraint is minimal/scoped;
- no detailed Health payload required by University helper.

### Performance tests

- observed grade/trend remains performance;
- risk estimate is qualified;
- performance never becomes capacity/intelligence inference.

### Academic integrity tests

- no grounded restriction -> assistance permitted by default;
- ambiguous wording does not become prohibition;
- grounded explicit restriction limits only prohibited scope;
- allowed teaching/review assistance remains available;
- stale/superseded rule handled temporally;
- caller flag alone cannot create restriction.

### Decision tests

- hard-infeasible options removed when justified;
- remaining options compared against explicit criteria;
- best-match may be identified;
- no option becomes adopted decision without confirmation;
- alternative route remains available unless explicitly rejected.

### External action tests

- semester/study planning does not mutate calendar/tasks;
- deadline tracking may create a proposal only;
- calendar mutation requires shared approval path;
- task mutation requires shared approval path;
- email preparation cannot send;
- formal-procedure preparation cannot submit/register;
- no University-specific duplicate calendar/task/email operation exists.

### Academic State tests

- grounded official grade/status may update internal state through authorized path;
- prediction cannot update state;
- history/provenance preserved;
- no official university system mutation;
- personal memory does not silently override authoritative state.

### Cross-domain tests

- Health constraint projection works when explicitly authorized;
- detailed Health resource denied by default;
- supporting Health cannot widen University permissions;
- unrelated health content is not transferred;
- same shared resource is not duplicated.

### External verification tests

- missing/stale/conflicting/decision-critical fact can request verification;
- source class is `OFFICIAL_ONLY` under canonical University policy;
- verification is read-only;
- no continuous monitoring loop;
- no external mutation;
- denied external search fails closed.

### Bootstrap tests

- General + University share registries;
- General remains fallback;
- generic request remains General when appropriate;
- University-like request can resolve University;
- blocked University action does not become permitted via General fallback;
- fresh bootstraps equivalent;
- import has no side effects.

### Validation-first tests

Use counting registry spies and prove zero first-registry mutations for every deterministic collision class exposed by public APIs.

### Rollback tests

Inject failures after each meaningful registration stage and prove exact state restoration/parity.

### Contract tests

Follow current strict CMM OS standards:

- immutable/frozen where applicable;
- deep immutability;
- exact enums;
- no implicit coercion;
- unknown-field rejection;
- JSON-safe values;
- finite numbers;
- deterministic ordering;
- deterministic IDs/digests where used;
- strict round-trip;
- sanitized contractual errors;
- no accidental `KeyError`/`AttributeError`/`TypeError` leaks from malformed public payloads.

Do not invent new contracts merely to satisfy these standards if existing contracts already cover University.

---

## 47. Canonical E2E Scenarios

At minimum, test complete canonical behavior for these scenarios.

### Scenario A — Semester planning with hard constraints

Inputs:

- several subjects;
- known dates;
- limited available time;
- one explicit user preference.

Expected:

- hard constraints first;
- infeasible scenario excluded with reason;
- feasible scenarios compared;
- no external mutation;
- no adopted decision.

### Scenario B — Conflicting exam date

Inputs:

- generic official calendar says one date;
- more specific official valid call says another.

Expected:

- both preserved;
- resolution uses authority/specificity/temporality;
- provenance visible;
- selected current date justified.

Variant:

- two equivalent official sources conflict.

Expected:

- unresolved conflict;
- no arbitrary date;
- verify/request resource before decision-critical action.

### Scenario C — Reassessment

Inputs:

- failed assessment;
- reassessment source;
- competing assignment deadline.

Expected:

- reassessment distinguished from ordinary attempt;
- workload/opportunity cost analyzed;
- plan proposal only.

### Scenario D — Academic integrity

Inputs:

- assignment with no verified AI restriction.

Expected:

- production assistance allowed.

Variant:

- current official subject rule explicitly prohibits generated final text.

Expected:

- restriction enforced only to that scope;
- explanation/review/study assistance remains available.

### Scenario E — Health constraint projection

Inputs:

- University planning request;
- Health has authorized minimal constraint "unavailable on date X";
- full clinical data exists but is not authorized for transfer.

Expected:

- only minimal constraint transferred;
- full clinical data excluded;
- plan adapts;
- trace records scoped transfer.

### Scenario F — Degree completion

Inputs:

- official record;
- pending subject;
- TFG requirement;
- unresolved credit recognition.

Expected:

- completion scenarios;
- unresolved recognition not assumed;
- ECTS totals conditional where needed;
- no route adopted.

### Scenario G — Performance

Inputs:

- multiple grades and study sessions.

Expected:

- observed trend;
- factors/gaps;
- cautious risk estimate if justified;
- no capacity/intelligence inference.

### Scenario H — Email/formal procedure

Inputs:

- user asks University workflow to prepare a grade-review request.

Expected:

- requirements/deadline verification when needed;
- draft/checklist;
- no send/submit/register.

---

## 48. Security, Privacy and Fail-Closed Rules

Unknown or invalid state must not become permission.

At minimum:

```text
unknown permission
-> deny

unknown external source class
-> do not trust as official

unknown deadline status
-> do not treat as confirmed

unknown temporal ordering
-> preserve unknown

unknown academic rule applicability
-> do not fabricate applicability

unknown operation implementation
-> unavailable

unknown workflow
-> block

unknown approval
-> do not execute mutation

invalid memory binding
-> reject

invalid trace reference
-> reject

partial registration
-> rollback
```

Do not use permissive defaults merely to make tests pass.

Academic Integrity Mode C is permissive only with respect to assistance when no applicable restriction is grounded.

It does NOT create broad permission to external actions, memory writes, provider egress or cross-domain access.

---

## 49. Non-Goals

Phase 10.22 does NOT implement:

- university portal connector;
- automatic enrollment;
- automatic subject registration;
- automatic reassessment registration;
- automatic formal appeal submission;
- automatic credit-recognition submission;
- automatic accommodation/adaptation submission;
- email sending;
- messaging;
- calendar engine;
- task engine;
- payment;
- legal representation;
- plagiarism detector;
- surveillance/proctoring;
- browser automation for university portals;
- credentials store;
- scholarship decision engine;
- TFG subdomain;
- academic-capacity/intelligence assessment;
- own memory store;
- own graph database;
- own vector store;
- own workflow engine;
- own resolver;
- model/provider selection;
- continuous external monitoring;
- Phase 11 connectors/UI.

Future connectors must remain behind shared operations/integrations and current permission/approval contracts.

---

## 50. Acceptance Criteria

Phase 10.22 is acceptable when:

- `domain:university` exists as a complete canonical Domain Pack;
- the package follows the approved shared 14-module boundary unless a repository-grounded exception is documented;
- exactly 14 entity semantics exist;
- exactly 12 canonical resources exist;
- exactly 10 canonical reasoning rules exist;
- exactly 11 canonical operations exist;
- exactly 7 canonical workflows exist;
- `catalog.py` is the single source of truth;
- shared contracts are reused;
- no parallel infrastructure exists;
- source authority is attribute-specific and grounded;
- contradictions are fail-closed when unresolved;
- recency alone cannot override authority/scope;
- provenance does not automatically equal truth;
- Academic State is separated from Personal Memory;
- dates/deadlines preserve grounding and temporal status;
- ECTS calculations do not double count or assume unresolved credit;
- exam attempts/reassessment are distinguished;
- workload applies hard constraints before preferences;
- academic dependencies are grounded;
- observed performance never becomes capacity/intelligence inference;
- Academic Integrity Mode C is implemented exactly;
- academic decisions remain proposals until confirmed;
- all 11 operations respect external-action boundaries;
- `update_subject_status` cannot mutate university systems;
- all 7 workflows reuse the shared Workflow Engine;
- conditional official verification is `OFFICIAL_ONLY`, read-only and non-continuous;
- Health→University defaults to minimal constraint projection;
- detailed Health data requires explicit scoped authorization;
- calendar/task execution remains shared and approval-gated;
- communication remains preparation-only;
- formal procedures remain preparation-only;
- presentation preserves provenance, temporality, uncertainty, contradictions and decision status;
- memory reuses shared Domain Memory;
- trace is reference-only;
- missing operation implementation is fail-closed;
- General remains fallback;
- bootstrap composes General + University on shared registries;
- validation-first occurs before first mutation;
- nested common registries are prevalidated where current architecture uses them;
- rollback restores full registration parity;
- clean import is verified in a fresh interpreter;
- `REQ-DP22-001` is covered;
- `REQ-DP22-002` is covered;
- `REQ-DP22-003` is covered;
- focal/domain/global regressions remain green.

---

## 51. Future Considerations — Out of Scope

Record without implementing:

1. Phase 11 university portal/calendar/task/email connectors behind shared operations and approvals.
2. Scheduled deadline monitoring through Agent Runtime/automations after explicit configuration.
3. Richer scholarship/financial-aid workflows if a future domain boundary justifies them.
4. Cross-domain University ↔ Oppositions coordination once Opposition Domain is canonical.
5. University ↔ Life Plan composition for medium/long-term education decisions.
6. Dedicated benchmark expansion for planning, dates, workload, constraints and progress.
7. Provider/model routing through Phase 11 Model Gateway only.
8. Optional external document-generation/export workflows through the shared artifact system, not the University core.

Do not pre-build these now.

---

## 52. Final Hardened Precedent

The implementation must start from the FINAL hardened states of General, Health and Relationships, not copy their historical defects.

Explicitly preserve these lessons:

- General is fallback, never the specialized domain;
- compose General + specialized domain on shared registries;
- one canonical catalog per domain;
- no import-time registration;
- provenance does not equal epistemic truth;
- source labels supplied by callers cannot bypass grounding;
- temporal validity must be explicit;
- unknown order is not latest;
- sensitive confirmation cannot be caller-disabled;
- external mutation requires exact permission/approval;
- workflows need real dependency/gating semantics;
- memory proposal is optional, not a forced workflow terminal;
- `PREPARATION != EXTERNAL COMMUNICATION`;
- `PROPOSAL != MUTATION`;
- `proposal_only != requires_approval`;
- required resources must be meaningful;
- operation definitions are not fake implementations;
- missing implementation fails closed;
- deterministic helpers preserve state distinctions;
- validation-first must have adversarial matrix coverage;
- predictable conflicts cause zero first-registry mutations;
- rollback restores registration parity after unexpected failure;
- permission-registry unexpected exceptions propagate;
- use public memory digest/binding APIs;
- reference-only trace/memory metadata must not carry narrative payload or PII;
- clean import must be tested in a fresh interpreter;
- no supporting domain can widen permissions;
- no fallback can bypass a specialized-domain denial;
- strict contract serialization/immutability standards from hardened Phase 10 infrastructure remain applicable;
- no unrelated refactoring.

University adds these domain-specific hard lessons from the approved design:

- source authority is attribute-specific;
- same-level authority depends on validity + specificity + provenance + scope;
- equivalent authoritative conflict remains unresolved;
- Academic State is not Personal Memory;
- hard constraints precede preferences;
- assistance is permissive by default under Integrity Mode C;
- observed performance is not capacity;
- Health context is projected minimally by default;
- external verification is conditional, official-only and read-only;
- calendar/task execution stays shared/approval-gated;
- email and formal procedures stay preparation-only.

---

## 53. Canonical Counts

The following counts are contractual:

```text
entities   = 14
resources  = 12
rules      = 10
operations = 11
workflows  = 7
```

Canonical entity semantics:

```text
degree
university
academic_year
semester
subject
assignment
examination
exam_attempt
grade
deadline
professor
adaptation
credit
academic_requirement
```

Canonical resource IDs:

```text
university.academic_record
university.subject_guide
university.university_calendar
university.examination_schedule
university.assignment
university.grade
university.email
university.note
university.study_session
university.user_message
university.regulation
university.memory_entry
```

Canonical rules:

```text
AcademicSourceAuthorityRule
AcademicContradictionRule
AcademicDeadlineRule
ECTSConsistencyRule
ExamAttemptRule
AcademicWorkloadRule
AcademicDependencyRule
ObservedPerformanceCapacityRule
AcademicIntegrityRule
AcademicDecisionPreservationRule
```

Canonical operations:

```text
university.plan_semester
university.create_study_plan
university.review_academic_record
university.compare_semesters
university.prepare_exam
university.prepare_assignment
university.track_deadlines
university.analyse_performance
university.generate_academic_summary
university.update_subject_status
university.review_degree_completion
```

Canonical workflows:

```text
university.semester_planning
university.exam_preparation
university.academic_review
university.reassessment_planning
university.assignment_preparation
university.degree_completion_review
university.tfg_planning
```

No alias may appear as a second independent catalog item.

If implementation discovers a pre-existing public ID representing the same semantics, reconcile through the same compatibility discipline used in prior domains; do not maintain two contradictory canonical catalogs.

---

## 54. Implementation Self-Audit Requirements

Before claiming Phase 10.22 ready for independent audit, implementation must self-review for:

- accidental Health-specific semantics;
- accidental Relationships-specific semantics;
- accidental user-specific hard-coded academic facts;
- hidden assumption that one specific university's regulation is universal;
- duplicate catalog items;
- missing roadmap requirements;
- missing `REQ-DP22-001/002/003` coverage;
- source authority based only on recency;
- provenance incorrectly treated as truth;
- unresolved contradiction silently collapsed;
- ungrounded deadline promoted to confirmed;
- ECTS double counting;
- attempt/reassessment conflation;
- workload preference evaluated before hard constraints;
- Health detail leakage;
- performance→capacity inference;
- academic-integrity policy made more restrictive than Approved Mode C;
- best scenario silently persisted as decision;
- calendar/task direct mutation;
- communication sending;
- formal-procedure submission;
- University-specific duplicate action infrastructure;
- direct memory persistence;
- private memory helper imports;
- fake operation implementations;
- import-time side effects;
- incomplete rollback;
- reverse dependencies;
- unrelated refactoring.

Run a placeholder scan on all new University production/tests/docs:

```bash
rg -n 'TBD|TODO|FIXME|PLACEHOLDER|XXX' \
  cmm/domains/university \
  tests/domains \
  docs/reference \
  docs/superpowers/specs/2026-08-09-university-domain-design.md || true
```

Any intentional TODO outside this phase must not be introduced merely to postpone a required 10.22 behavior.

---

## 55. Verification Expectations

The future implementation task must inspect the actual repository first and then run the strongest current verification commands supported by the repository.

Expected baseline categories:

```text
focused University tests
relevant General/Health/Relationships regression tests
all domain tests
global pytest suite
Ruff on changed/new Python
Ruff with Python 3.10 target when used by current project workflow
compileall
dependency-direction tests
git diff --check
staged diff check before commit
fresh-interpreter import test
```

Do not hard-code a historical test count as a pass criterion.

The current repository state at implementation time is authoritative for exact counts and commands.

A phase is not "complete" merely because focal tests pass.

---

## 56. Completion State

Successful implementation of this specification means:

```text
University Domain implemented
+
full local verification green
+
self-audit complete
+
ready for independent audit
```

It does NOT itself mean:

```text
Phase 10.22 officially closed and audited
```

Official closure occurs only after independent audit/remediation and the corresponding roadmap update/commit.

The implementation worker must not preemptively mark 10.22 as complete and audited.

---

## 57. Design Freeze

This file is the approved contractual design for Phase 10.22.

Implementation must not silently rewrite these hard decisions:

1. 14 entities.
2. 12 resources.
3. Attribute-specific source authority.
4. Material contradiction fail-closed when unresolved.
5. Academic State distinct from Personal Memory.
6. Exactly 10 canonical rules.
7. Exactly 11 canonical operations.
8. Exactly 7 canonical workflows.
9. Hard constraints before user preferences.
10. Observed performance distinct from capacity.
11. Academic Integrity Approved Mode C.
12. Decision support does not adopt decisions.
13. Conditional official read-only external verification.
14. Health→University minimum constraint projection by default.
15. Calendar/task mutation only through shared approval-gated capabilities.
16. Emails are preparation-only.
17. Formal academic procedures are preparation-only.
18. No parallel University infrastructure.
19. General remains fallback.
20. Shared memory/trace/workflow/operation/permission architecture is reused.

If implementation evidence demonstrates a genuine incompatibility with an existing public contract, the worker must stop and report the exact conflict rather than silently changing this specification.
