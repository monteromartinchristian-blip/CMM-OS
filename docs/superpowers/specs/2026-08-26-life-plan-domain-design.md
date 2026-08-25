# Phase 10.29 — Life Plan Domain Design

**Status:** Frozen design — approved for implementation planning
**Phase:** 10.29 — Domain Intelligence
**Domain ID:** `domain:life-plan`
**Profile:** `LifePlanProfile`
**Baseline:** `da83b50` — `docs(sport): close phase 10.28 independent audit`
**Branch:** `feature/phase-10-domain-intelligence`

---

## 1. Purpose

The Life Plan Domain specializes CMM OS for coordinating medium- and long-term goals, scenarios, dependencies, resources, constraints, risks, decisions, milestones, and plan drift.

Life Plan is a **cross-domain coordinating domain**. It does not replace the specialized semantics owned by Health, University, Oppositions, Parenthood, Project, or other Domain Packs.

Its responsibility is to combine authorized, purpose-minimized contributions from supporting domains into coherent long-horizon planning while preserving epistemic status, decision status, permissions, uncertainty, approval requirements, memory controls, and traceability.

---

## 2. Architectural constraints

Phase 10.29 must reuse the existing shared Phase 10 infrastructure.

It must not introduce a Life Plan-specific:

- reasoning engine;
- planner;
- workflow engine;
- permission engine;
- approval engine;
- memory store;
- trace engine;
- cross-domain engine;
- registry implementation;
- persistence subsystem.

The package follows the established Domain Pack pattern used by Languages, Parenthood, and Sport.

Canonical production package:

```text
cmm/domains/life_plan/
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

Exactly **14 production modules**.

No `state.py`, `models.py`, custom planner, custom repository, or parallel runtime is introduced unless implementation inspection proves an unavoidable shared-contract gap. Any such gap must be fixed in the shared infrastructure rather than duplicated in Life Plan.

---

## 3. Canonical identity

```text
domain:life-plan
LifePlanProfile
```

Expected versioned identifiers should follow the same naming conventions used by recent Domain Packs, for example:

```text
LIFE_PLAN_DOMAIN_ID = "domain:life-plan"
LIFE_PLAN_DOMAIN_VERSION = "1.0.0"
LIFE_PLAN_MANIFEST_ID = "manifest:life-plan:1.0.0"
LIFE_PLAN_PROFILE_ID = "life-plan.profile"
LIFE_PLAN_PROFILE_NAME = "LifePlanProfile"
```

Exact symbol spelling must remain consistent with existing shared contracts and registry conventions.

---

## 4. Canonical counts

The frozen Phase 10.29 canon is:

```text
13 entities
12 resources
8 rules
10 operations
7 workflows
14 production modules
```

These counts are closure invariants.

No additional canonical rule or workflow may be introduced merely to satisfy a secondary requirement if that requirement can be expressed through one of the frozen canonical items.

---

## 5. Entities — 13

```text
life_goal
milestone
scenario
dependency
constraint
risk
decision
financial_resource
career_path
education_path
housing_goal
family_goal
timeline
```

Entity definitions are declarative Domain Pack metadata. They must not create a competing persistent state model.

---

## 6. Resources — 12

```text
life_plan
financial_plan
academic_plan
opposition_plan
health_constraints
family_plan
housing_plan
goal
decision
calendar_event
memory_entry
user_message
```

Resource IDs must use the established domain-scoped naming convention, for example:

```text
life_plan.resource.life_plan
life_plan.resource.financial_plan
...
```

Where a resource represents data originating from another domain, the resource must contain only the authorized and purpose-minimized contribution needed by Life Plan.

It must not silently ingest complete specialized dossiers.

---

## 7. Rules — 8

### 7.1 GoalDependencyRule

Purpose:

- represent prerequisites and dependencies between goals;
- distinguish hard prerequisites from soft dependencies;
- reject circular or internally contradictory dependency structures where detectable;
- avoid converting correlation or preference into obligation.

Required invariant:

```text
related != prerequisite
preference != dependency
```

### 7.2 ScenarioConsistencyRule

Purpose:

- validate internal scenario coherence;
- detect incompatible assumptions, milestones, constraints, or resources;
- preserve uncertainty.

Required invariant:

```text
scenario viability != decision
scenario viability != commitment
```

### 7.3 ResourceConstraintRule

Purpose:

Evaluate separately:

```text
time
money
energy
available capacity
```

Requirements:

- missing values do not silently become zero;
- malformed values fail closed or produce structured uncertainty;
- resources from supporting domains require authorized provenance;
- feasibility claims must remain evidence-calibrated.

### 7.4 DecisionStatusRule

Decision status is explicit and non-collapsible:

```text
idea
preference
goal
scenario
decision
commitment
```

Required invariants:

```text
preference != decision
scenario != decision
decision != commitment
inference != confirmed decision
```

A closed decision must not be reopened or replaced without explicit new evidence, explicit user action, or a valid state transition.

The earlier Phase 10 requirement `life_plan.closed_decision_reopening` is implemented through this canonical rule rather than by creating a ninth rule.

### 7.5 LongTermTemporalRule

Purpose:

- validate dates, ordering, milestones, windows, dependencies, and long-term temporal compatibility;
- preserve uncertain dates as uncertain;
- reject impossible or incoherent sequencing;
- avoid fabricating missing chronology.

### 7.6 AlternativeRouteRule

Purpose:

- preserve alternative routes toward the same or related goals;
- distinguish fallback, contingency, exploration, and abandonment.

Required invariant:

```text
alternative route != failure
alternative route != automatic abandonment
```

### 7.7 CrossDomainImpactRule

Purpose:

- evaluate authorized impacts across supporting domains;
- ensure that specialized semantics remain owned by the source domain;
- consume only purpose-minimized contributions.

Relevant supporting domains include:

```text
domain:health
domain:university
domain:oppositions
domain:parenthood
domain:project
```

and any other domain explicitly authorized by shared composition policy.

Required invariant:

```text
raw external payload != authorized supporting-domain contribution
```

### 7.8 PlanDriftRule

Purpose:

Compare:

```text
planned state
confirmed decisions
actual current state
```

Requirements:

- detect material drift;
- distinguish expected evolution from contradiction;
- never infer abandonment merely because the current state differs from an old scenario;
- preserve provenance for each compared state.

---

## 8. Operations — 10

Canonical operations:

```text
life_plan.build_timeline
life_plan.compare_scenarios
life_plan.review_goals
life_plan.detect_dependencies
life_plan.identify_risks
life_plan.update_plan
life_plan.create_milestones
life_plan.generate_periodic_review
life_plan.evaluate_feasibility
life_plan.track_decisions
```

Each operation must:

- be registered in the shared operation catalog/registry;
- expose a deterministic schema;
- return structured results;
- preserve decision and epistemic status;
- avoid hidden persistence;
- obey shared permission and approval infrastructure;
- reject forged authorization evidence;
- remain side-effect free unless explicitly routed through an approved shared side-effect path.

### Sensitive operation semantics

`life_plan.update_plan` and `life_plan.track_decisions` must never convert:

```text
preference
hypothesis
scenario
inference
```

into:

```text
decision
commitment
```

without explicit confirmation or valid shared-runtime evidence.

---

## 9. Workflows — exactly 7

The frozen workflow set is:

```text
life_plan.life_plan_setup
life_plan.quarterly_life_review
life_plan.scenario_comparison
life_plan.goal_dependency_review
life_plan.cross_domain_impact_review
life_plan.plan_drift_review
life_plan.annual_life_plan_update
```

Public display names:

```text
Life Plan Setup
Quarterly Life Review
Scenario Comparison
Goal Dependency Review
Major Decision Support
Plan Drift Review
Annual Life Plan Update
```

### 9.1 Resolution of the 10.15 workflow requirement

The pre-existing infrastructure requirement:

```text
life_plan.cross_domain_impact_review
```

is implemented as the canonical workflow ID behind the public workflow:

```text
Major Decision Support
```

This does **not** create an eighth workflow.

This follows the established Phase 10 precedent that required infrastructure IDs are integrated into the frozen Domain Pack canon rather than increasing canonical counts.

### 9.2 Shared workflow runtime

Workflows must execute through the existing shared workflow registry/resolution/execution infrastructure.

AT-DP-029 must not simulate successful workflow execution by calling Life Plan helpers directly when a shared workflow runtime path exists.

---

## 10. LifePlanProfile

`LifePlanProfile` must be registered through the existing profile registry.

The profile should configure Life Plan-specific:

- resource priorities;
- reasoning rules;
- workflow availability;
- operation availability;
- permission requirements;
- presentation requirements;
- memory boundaries;
- supporting-domain expectations.

It must not alter shared Cognitive Layer behavior.

Life Plan is a coordinator, not an owner of all specialized facts.

---

## 11. Cross-domain architecture

Canonical direction:

```text
Life Plan need
↓
CrossDomainPermissionRequest
↓
shared permission resolution
↓
DomainPermissionGate / canonical authorization evidence
↓
authorized purpose-minimized supporting-domain result
↓
Life Plan rule / operation / workflow
```

Forbidden shortcut:

```text
raw mapping
arbitrary authorization ID
caller boolean
duck-typed object
unverified domain-result ID
↓
trusted Life Plan state mutation
```

### 11.1 Trust boundary

Untrusted inputs include:

- caller-provided mappings;
- raw IDs;
- booleans such as `is_authorized=True`;
- arbitrary dataclass instances;
- values claiming to be permission or approval results;
- unverified cross-domain payloads.

Trusted evidence is service/runtime-owned evidence validated through canonical shared infrastructure.

The Domain Pack does not attempt to defend against an actor that already has arbitrary Python execution inside the trusted process. Process isolation and capability security are platform-level concerns, not Phase 10.29 requirements.

---

## 12. Specialized domain ownership

Life Plan must not reinterpret complete specialized records.

Examples:

### Health

Allowed:

```text
authorized functional constraint
authorized availability/capacity impact
authorized time-bounded health constraint
```

Not owned by Life Plan:

```text
diagnosis
treatment
clinical interpretation
complete medical dossier
```

### University

Allowed:

```text
authorized workload
authorized milestone/deadline
authorized academic compatibility contribution
```

University retains ownership of academic rules, formal requirements, and official-source semantics.

### Oppositions

Allowed:

```text
authorized workload
authorized progress
authorized strategy/milestone contribution
```

Oppositions retains ownership of opposition-specific strategy and official-source verification.

### Parenthood

Allowed:

```text
authorized family goal
authorized dependency
authorized financial/timeline impact
```

Parenthood retains legal, medical, ethical, child, and journey semantics.

### Project

Allowed:

```text
authorized project status
authorized dependency
authorized resource/timeline impact
```

Project retains project-specific execution semantics.

---

## 13. Permission policy

Life Plan has explicit multidomain access only.

Required principles:

```text
explicit authorization
purpose minimization
most restrictive permission wins
sensitive inference limited
memory write reinforced
external commitments supervised
payments prohibited without explicit approved external-action path
```

Life Plan must not use presence of a supporting domain as implicit authorization.

The effective permission result must be produced by shared composition/permission infrastructure.

---

## 14. External actions and approvals

Life Plan may propose actions but must not silently execute external commitments.

Always supervised or prohibited without canonical approval evidence:

- payments;
- financial commitments;
- applications;
- registrations;
- contracts;
- external communications;
- calendar actions where approval policy requires it;
- abandonment of a confirmed major goal;
- conversion of scenario into commitment.

Approval trust must be service-owned.

An arbitrary approval ID, boolean, mapping, or forged object is not sufficient approval evidence.

---

## 15. Memory integration

Life Plan must reuse:

- shared memory view request;
- memory proposal;
- memory binding;
- memory validation.

Expected Life Plan package functions should mirror the stabilized pattern of recent Domain Packs:

```text
build_life_plan_memory_view_request
build_life_plan_memory_proposal
build_life_plan_memory_view
build_life_plan_memory_binding
validate_life_plan_memory_binding
```

Exact signatures must follow shared contracts.

### Memory invariants

No implicit persistence.

The following must not become durable confirmed memory merely because they appeared in reasoning:

```text
preference
scenario
inference
hypothesis
unconfirmed decision
unconfirmed commitment
```

Memory writes must fail closed when:

- required confirmation is absent;
- binding provenance is invalid;
- permission evidence is invalid;
- content violates Life Plan memory policy.

---

## 16. Trace integration

Life Plan must reuse shared Domain Trace contracts and validators.

Expected pattern:

```text
build_life_plan_trace_reference
build_life_plan_trace_contribution
build_supporting_trace_contribution
assemble_life_plan_trace
validate_life_plan_trace
```

### Independent trace inventory

AT-DP-029 must build its trace inventory independently from the final trace object.

It must not:

1. assemble the final trace;
2. inspect that trace;
3. derive the inventory from it;
4. validate the trace against its own reconstructed content.

The inventory must be assembled from authoritative runtime artifacts produced during the connected acceptance lifecycle before final trace assembly.

Trace validation must reject:

- orphan references;
- mismatched domain ownership;
- forged permission/approval references;
- missing workflow or operation evidence where required;
- tampered domain-result references;
- inconsistent primary/supporting domain composition.

---

## 17. Atomic integration

`register_life_plan_domain(...)` must follow the established validation-first, snapshot, register, rollback pattern.

It must atomically register the complete Life Plan pack into the shared registries.

On failure:

- every affected registry returns to the exact prior state;
- no partial Life Plan registration remains;
- General remains intact;
- rollback failure is explicit rather than silently ignored.

AT-DP-029 must prove exact snapshot parity after forced failure.

---

## 18. Bootstrap and General fallback

The canonical bootstrap must:

1. build the standard General Domain registries;
2. register Life Plan into the same registry objects;
3. expose both General and Life Plan;
4. preserve General fallback.

No bootstrap-local replacement registry is permitted.

If Life Plan does not resolve for a request, normal shared resolution/fallback behavior must remain available.

---

## 19. Presentation

Life Plan presentation may adapt:

- headings;
- scenario comparisons;
- timelines;
- explicit decision labels;
- risk summaries;
- resource-constraint summaries;
- drift summaries;
- alternative-route presentation.

Presentation must not:

- convert uncertainty into certainty;
- hide decision status;
- convert scenarios into commitments;
- soften approval requirements;
- suppress cross-domain provenance;
- create new conclusions.

---

## 20. AT-DP-029 connected acceptance

AT-DP-029 is designed from the start as a state-linked connected lifecycle.

Target: approximately 45 checkpoints.
The implementation plan will freeze the exact number before coding.

Minimum connected proof:

```text
resolver
→ LifePlanProfile
→ exact catalog counts
→ Life Plan state/resources
→ goals
→ dependencies
→ resource constraints
→ scenario comparison
→ explicit decision-status preservation
→ temporal compatibility
→ alternative routes
→ real CrossDomainPermissionRequest
→ canonical permission decision
→ authorized supporting-domain contribution
→ unauthorized/raw contribution rejection
→ life_plan.cross_domain_impact_review through shared workflow runtime
→ cross-domain impact
→ feasibility evaluation
→ timeline
→ milestones
→ plan drift
→ decision tracking
→ external-action approval boundary
→ memory proposal
→ memory view/binding
→ memory validation
→ real DomainResult
→ independent trace inventory
→ final trace assembly
→ trace validation
→ tamper rejection
→ atomic registration
→ rollback
→ General fallback
```

The acceptance test is candidate-side implementation evidence only.

It must not mark independent audit closure by itself.

---

## 21. Permanent adversarial closure gate

Phase 10.29 must include adversarial tests from the first implementation candidate rather than waiting for independent audit findings.

Required attack classes:

```text
PREFERENCE_NOT_DECISION
SCENARIO_NOT_DECISION
SCENARIO_NOT_COMMITMENT
INFERENCE_NOT_CONFIRMED_FACT
CLOSED_DECISION_NOT_REOPENED_WITHOUT_EVIDENCE
ALTERNATIVE_NOT_ABANDONMENT
RAW_CROSS_DOMAIN_REJECTED
FORGED_PERMISSION_REJECTED
UNAUTHORIZED_SUPPORTING_DOMAIN_REJECTED
SUPPORTING_DOMAIN_PURPOSE_MINIMIZED
MOST_RESTRICTIVE_PERMISSION_WINS
MALFORMED_RESOURCE_CONSTRAINT_FAILS_CLOSED
NO_AUTOMATIC_GOAL_ABANDONMENT
NO_EXTERNAL_COMMITMENT_WITHOUT_APPROVAL
NO_PAYMENT_WITHOUT_APPROVED_EXTERNAL_PATH
FORGED_APPROVAL_REJECTED
MEMORY_WRITE_FAILS_CLOSED
MEMORY_DOES_NOT_PROMOTE_INFERENCE
TRACE_INVENTORY_INDEPENDENT
TRACE_TAMPER_REJECTED
ATOMIC_REGISTRATION_ROLLBACK
GENERAL_FALLBACK_PRESERVED
```

Tests must reproduce attacks without relying on production helper functions to manufacture trusted evidence whenever that would make the test circular.

---

## 22. DP-029 lifecycle

Initial and implementation-candidate state:

```text
DP_029=REQUIRES_PHASE_INSPECTION
```

Implementation may establish:

```text
PHASE10_29_IMPLEMENTATION=COMPLETE
AT_DP_029=PASS
DP_029=REQUIRES_PHASE_INSPECTION
```

or equivalent repository wording that clearly preserves the independent-audit boundary.

It must **not** set:

```text
DP_029=VERIFIED_EXISTING
```

before a successful independent closure audit.

Only the independent auditor may authorize the final transition to:

```text
PHASE10_29=COMPLETE
FINAL_INDEPENDENT_CLOSURE_AUDIT=PASS
DP_029=VERIFIED_EXISTING
AT_DP_029=PASS
```

---

## 23. Documentation

Implementation must add/update the minimum canonical documentation:

```text
docs/reference/life-plan-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
```

Before independent audit, documentation must say only that implementation is complete/candidate and audit is pending.

Historical or unrelated documentation debt in other Domain Packs must not be opportunistically modified during 10.29 unless it directly blocks correctness.

---

## 24. Testing strategy

### Focused tests

Expected Life Plan test families:

```text
test_life_plan_domain_catalog.py
test_life_plan_domain_definition.py
test_life_plan_domain_profile.py
test_life_plan_domain_resources.py
test_life_plan_domain_rules.py
test_life_plan_domain_operations.py
test_life_plan_domain_workflows.py
test_life_plan_domain_permissions.py
test_life_plan_domain_memory.py
test_life_plan_domain_trace.py
test_life_plan_domain_cross_domain.py
test_life_plan_domain_integration.py
test_life_plan_domain_bootstrap.py
test_life_plan_domain_public_api.py
test_life_plan_domain_safety.py
test_life_plan_domain_dp029_acceptance.py
test_life_plan_domain_closure_adversarial.py
```

Exact file decomposition may be adjusted to existing repository conventions while preserving coverage.

### Required gates

Before audit candidate creation:

```text
focused Life Plan tests
domain tests
global pytest suite
Ruff check
Ruff format/check formatting according to repository convention
compileall / syntax validation
git diff --check
```

No unrelated test failure may be hidden.

---

## 25. Audit bundle and closure

Independent auditor: ChatGPT in the CMM OS project.

Mandatory sequence:

```text
implementation
→ focused tests
→ domain tests
→ global tests
→ Ruff / format / compile
→ docs
→ commits
→ versioned-HEAD audit TAR.GZ
→ independent audit
→ remediation only if required
→ fresh audit bundle
→ final closure audit
→ closure commit
```

Audit bundle must be created from versioned HEAD:

```bash
git archive --format=tar.gz --output=<bundle>.tar.gz HEAD
```

The audit bundle remains untracked external evidence.

No raw working-directory tarball is accepted as the canonical audit candidate.

---

## 26. Scope exclusions

Phase 10.29 does not implement:

- financial transaction execution;
- autonomous purchase or payment;
- autonomous legal commitment;
- autonomous goal abandonment;
- medical reasoning beyond authorized supporting-domain constraints;
- University/Oppositions/Parenthood/Project domain logic;
- new shared memory infrastructure;
- new shared permission infrastructure;
- new shared trace infrastructure;
- cryptographic capability security inside the Python process;
- Phase 10.30 Project Domain;
- Phase 11 platform orchestration.

---

## 27. Definition of done — implementation candidate

10.29 is ready for independent audit only when:

```text
[ ] cmm/domains/life_plan exists
[ ] exactly 14 production modules
[ ] 13 entities
[ ] 12 resources
[ ] 8 rules
[ ] 10 operations
[ ] 7 workflows
[ ] LifePlanProfile registered
[ ] shared registries reused
[ ] shared workflow runtime reused
[ ] real cross-domain permission path used
[ ] supporting-domain data purpose-minimized
[ ] preference != decision enforced
[ ] scenario != commitment enforced
[ ] inference != confirmed fact enforced
[ ] alternatives do not imply abandonment
[ ] no automatic goal abandonment
[ ] external commitments require canonical approval
[ ] payments cannot occur through an unapproved Life Plan path
[ ] memory writes fail closed
[ ] trace inventory independent
[ ] trace validation fail closed
[ ] atomic registration
[ ] exact rollback
[ ] General fallback preserved
[ ] connected AT-DP-029 PASS
[ ] permanent adversarial gate PASS
[ ] focused tests PASS
[ ] domains tests PASS
[ ] global tests PASS
[ ] Ruff/format/compile gates PASS
[ ] docs say pending independent audit
[ ] DP-029 remains REQUIRES_PHASE_INSPECTION
[ ] no push
[ ] no merge
```

---

## 28. Frozen design decision

Approved implementation strategy:

**Standard 14-module Life Plan Domain Pack on existing shared Phase 10 infrastructure.**

Rejected:

1. adding a Life Plan-specific persistent state/model subsystem;
2. increasing the canonical workflow count to eight;
3. creating duplicated reasoning, memory, permission, approval, workflow, trace, or cross-domain infrastructure.

The required `life_plan.cross_domain_impact_review` workflow is the canonical workflow ID for the public **Major Decision Support** workflow and remains within the frozen seven-workflow canon.

This design is frozen for implementation planning. Any material architectural change requires explicit review before implementation.
