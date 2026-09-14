# Phase 10.28 — Sport Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `domain:sport` as a production Domain Pack for training, physical activity, goals, progression, load, recovery, measurements, injury signals and controlled Health coordination.

**Architecture:** Reuse the established Phase 10 Domain Pack architecture and its shared registries, resolver, workflow engine, permission system, memory proposal/binding contracts, trace contracts and General fallback. `SportProfile` is already part of the shared profile surface and must be reused/bound rather than re-created as a parallel profile system. Sport owns athletic reasoning; Health remains authoritative for clinical interpretation, diagnosis and treatment.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing `cmm.domains`, Cognitive Layer, Agent Runtime, Workflow, Permission, Approval, Memory and Trace contracts.

**Spec:** `docs/roadmap/phase-10-domain-intelligence.md` — `10.28 - Sport Domain`

**Cross-domain requirement sources:**
- `docs/reference/domain-intelligence-requirements-matrix.md` — DP-028 / Sport row.
- `docs/audits/phase-10.15-prompts-preflight.md` — Sport → Health and `sport.return_to_training_with_health_constraints`.
- Existing Health Domain public contracts and permission boundaries.

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Required Phase 10.27 closed ancestor: `d6400676081a7e4cde42aacb016fbb24fbabccfc`.
- Canonical domain ID: `domain:sport`.
- Public display name: `Sport`.
- Canonical profile: `SportProfile`.
- Domain version: `1.0.0`.
- Canonical manifest ID: `manifest:sport:1.0.0`.
- Canonical permission policy ID: `domain-permission:sport:1.0.0`.
- Exact canonical counts: **11 entities / 9 resources / 6 rules / 8 operations / 5 workflows**.
- `catalog.py` is the single source of truth for those inventories.
- Sport may import from Health only an authorized, purpose-bounded `health_constraint` projection. A full medical report, diagnosis, medication/treatment plan or unrestricted Health memory is not a Sport input.
- Sport must not diagnose injuries.
- Sport must not modify treatment.
- Sport must not make high-risk medical recommendations.
- Calendar mutation requires the shared approval-gated path. `sport.schedule_sessions` may prepare/propose scheduling but must not bypass approval.
- Readiness, recovery and load are mutable state. A previous result must not become a permanent identity or timeless truth.
- A single body measurement or isolated performance point is not a trend.
- Measurement trends require comparable evidence and preserve punctual variation/outliers.
- Training progression must not encode a universal physiological percentage as unquestionable truth. Any threshold must come from explicit policy/configuration or remain unknown.
- Injury signals can require stop/check/escalation but are not diagnoses.
- No direct memory write. Use shared Domain Memory proposals/bindings.
- No import-time registration.
- No Sport-specific planner, runtime, workflow engine, permission engine, memory store, knowledge store, trace engine, clinical engine or scheduler.
- General remains resolver fallback.
- Shared production code may change only if a RED test proves a genuine generic contract gap; otherwise keep all implementation inside `cmm/domains/sport/` and Sport tests/docs.
- Existing untracked `phase-10.27-audit-v1.tar.gz` and `tmp/` are out of scope: do not edit, delete, stage or use them as production source.
- TDD: RED → verify RED reason → minimal GREEN → focused regression → commit.
- Do not weaken existing tests.
- Do not push.
- Do not merge.
- Implementation may mark DP-028 only as implemented/candidate/pending independent audit. Independent closure is a later read-only audit.

---

# Planned Package

Use the established 14-module internal Domain Pack boundary unless repository inspection proves the current canonical pattern differs:

```text
cmm/domains/sport/
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

Primary tests:

```text
tests/domains/test_sport_domain_catalog.py
tests/domains/test_sport_domain_definition.py
tests/domains/test_sport_domain_profile.py
tests/domains/test_sport_domain_permissions.py
tests/domains/test_sport_domain_resources.py
tests/domains/test_sport_domain_rules.py
tests/domains/test_sport_domain_operations.py
tests/domains/test_sport_domain_workflows.py
tests/domains/test_sport_domain_memory.py
tests/domains/test_sport_domain_presentation.py
tests/domains/test_sport_domain_trace.py
tests/domains/test_sport_domain_integration.py
tests/domains/test_sport_domain_bootstrap.py
tests/domains/test_sport_domain_public_api.py
tests/domains/test_sport_domain_cross_domain.py
tests/domains/test_sport_domain_safety.py
tests/domains/test_sport_domain_dp028_acceptance.py
```

---

# Canonical Inventory

## Entities — exactly 11

```text
sport.entity.exercise
sport.entity.workout
sport.entity.training_plan
sport.entity.metric
sport.entity.body_measurement
sport.entity.injury
sport.entity.recovery
sport.entity.sport_goal
sport.entity.equipment
sport.entity.session
sport.entity.performance_record
```

## Resources — exactly 9

```text
sport.resource.workout_log
sport.resource.health_resource
sport.resource.body_measurement
sport.resource.training_plan
sport.resource.calendar_event
sport.resource.user_message
sport.resource.note
sport.resource.wearable_data
sport.resource.memory_entry
```

`health_resource` is a catalog resource type, not permission to ingest arbitrary Health records. Effective cross-domain access is narrowed to authorized `health_constraint` fields by permission/composition rules.

## Rules — exactly 6

```text
sport.rule.training_load
sport.rule.progressive_overload
sport.rule.recovery
sport.rule.injury_signal
sport.rule.health_constraint
sport.rule.measurement_trend
```

Public rule names:

```text
TrainingLoadRule
ProgressiveOverloadRule
RecoveryRule
InjurySignalRule
HealthConstraintRule
MeasurementTrendRule
```

## Operations — exactly 8

```text
sport.create_training_plan
sport.review_progress
sport.adjust_training_load
sport.generate_workout
sport.track_measurements
sport.review_recovery
sport.identify_risks
sport.schedule_sessions
```

## Workflows — exactly 5

```text
sport.training_plan_setup
sport.weekly_training_review
sport.recovery_review
sport.progress_review
sport.return_to_training_with_health_constraints
```

The fifth ID is fixed by the Phase 10.15 cross-domain requirement. Its display name remains **Return to Training**.

---

# Core Semantic Invariants

## 1. Sport / Health boundary

Allowed cross-domain projection:

```text
Health
  ↓ explicit authorization + purpose/scope
health_constraint
  ↓ restrictive intersection
Sport
```

Allowed Sport fields should be minimal functional constraints, for example when present in the shared projection contract:

```text
constraint_id
status
effective_from
effective_until
activity_limits
load_limits
movement_limits
return_to_activity_conditions
source_reference
provenance
authorization_reference
```

The implementation must inspect the actual shared cross-domain projection contract and use its real field names. Do not invent a new Health data store.

Denied:

```text
full medical report
diagnostic history
diagnosis inference
medication list unless represented only as an authorized functional constraint
treatment plan
raw Health memory
unrelated sensitive Health claims
```

## 2. Readiness is mutable

A readiness/recovery result is time-bound evidence:

```text
observations at t1 → readiness(t1)
new observations at t2 → readiness(t2)
```

Do not persist `ready`, `limited`, `hold`, fatigue or pain as stable identity traits.

## 3. Injury signal != diagnosis

Sport may produce:

```text
continue
reduce_load
hold
stop_and_check
request_health_review
insufficient_information
```

It must not produce a clinical diagnosis.

## 4. Training load

Training load evaluation must keep volume, intensity and frequency distinguishable. A useful implementation may calculate derived load only when the inputs are comparable and sufficiently specified.

Missing values remain unknown rather than silently zero.

## 5. Progressive overload

A plan can be compared with prior load. The rule must preserve:
- baseline;
- proposed change;
- policy threshold if one exists;
- missing/unknown threshold;
- warnings;
- rationale.

Do not hard-code “10%” or any other universal progression rule as the domain truth.

## 6. Measurement trend

Trend inference requires:
- at least two temporally ordered observations, and preferably the repository’s established minimum if shared contracts define one;
- comparable metric/unit/method;
- preserved timestamps;
- no Boolean-as-number coercion;
- no NaN/Inf decision-driving evidence;
- isolated outliers remain visible.

## 7. Scheduling

`sport.schedule_sessions` creates a proposed schedule/operation request. Real calendar mutation is performed only through the shared approval-gated external operation path.

## 8. Memory

Sport may propose persistence of:
- explicit training plans;
- workout/session records;
- explicit goals;
- measurements;
- derived trend/readiness snapshots with timestamp/provenance.

It must not silently persist:
- inferred injury diagnosis;
- unrestricted Health context;
- treatment advice;
- temporary readiness as a stable trait.

---

# Task 1 — Canonical Catalog and Immutable Definition

**Files**
- Create: `cmm/domains/sport/catalog.py`
- Create: `cmm/domains/sport/definition.py`
- Test: `tests/domains/test_sport_domain_catalog.py`
- Test: `tests/domains/test_sport_domain_definition.py`

**Interfaces**
- Produces constants for all later Sport modules.
- Produces `build_sport_domain_definition()` using current `DomainDefinition` contracts.

- [ ] **Step 1: Inspect current sibling APIs**

Read:

```text
cmm/domains/languages/catalog.py
cmm/domains/languages/definition.py
cmm/domains/parenthood/catalog.py
cmm/domains/parenthood/definition.py
```

Use actual constructors and metadata fields from the repository.

- [ ] **Step 2: RED identity and count tests**

At minimum:

```python
def test_sport_domain_identity_contract() -> None:
    definition = build_sport_domain_definition()
    assert str(definition.id) == "domain:sport"
    assert definition.name == "sport"
    assert definition.display_name == "Sport"
    assert definition.version == "1.0.0"
    assert definition.reasoning_profile == "SportProfile"
    assert definition.metadata.metadata["phase"] == "10.28"
    assert build_sport_domain_definition().to_dict() == definition.to_dict()


def test_sport_catalog_exact_counts() -> None:
    assert len(SPORT_ENTITY_IDS) == 11
    assert len(SPORT_RESOURCE_IDS) == 9
    assert len(SPORT_RULE_IDS) == 6
    assert len(SPORT_OPERATION_IDS) == 8
    assert len(SPORT_WORKFLOW_IDS) == 5
```

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_catalog.py \
  tests/domains/test_sport_domain_definition.py
```

Expected: RED because `cmm.domains.sport` does not yet exist.

- [ ] **Step 3: GREEN minimal implementation**

Required constants:

```python
SPORT_DOMAIN_ID = "domain:sport"
SPORT_DOMAIN_VERSION = "1.0.0"
SPORT_MANIFEST_ID = "manifest:sport:1.0.0"
SPORT_PROFILE_NAME = "SportProfile"
SPORT_PERMISSION_IDS = ("domain-permission:sport:1.0.0",)
```

Definition capabilities should cover, without inventing extra engines:

```text
sport_training_planning
sport_training_load_review
sport_progress_review
sport_recovery_review
sport_measurement_tracking
sport_risk_identification
sport_health_constraint_coordination
sport_schedule_proposal
```

- [ ] **Step 4: GREEN + hygiene**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_catalog.py \
  tests/domains/test_sport_domain_definition.py
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  cmm/domains/sport/catalog.py \
  cmm/domains/sport/definition.py \
  tests/domains/test_sport_domain_catalog.py \
  tests/domains/test_sport_domain_definition.py
git diff --cached --check
git commit -m "feat(sport): add domain identity and canonical catalog"
```

---

# Task 2 — SportProfile Binding and Fail-Closed Permissions

**Files**
- Create: `cmm/domains/sport/profile.py`
- Create: `cmm/domains/sport/permissions.py`
- Test: `tests/domains/test_sport_domain_profile.py`
- Test: `tests/domains/test_sport_domain_permissions.py`

**Interfaces**
- Consumes shared `SportProfile`.
- Produces Sport profile builder/adapter and canonical permission policy.

- [ ] **Step 1: Inspect the existing profile first**

Read the actual `SportProfile` definition in the shared profile registry/profile modules. Reuse its semantics. Do not create a second unrelated profile with the same name.

- [ ] **Step 2: RED profile/permission boundaries**

Tests must prove:
- profile identity is `SportProfile`;
- uncertainty/provenance are preserved;
- injury diagnosis is prohibited;
- treatment modification is prohibited;
- high-risk recommendation is prohibited;
- direct calendar mutation is not allowed;
- cross-domain access is default-denied except through an explicit Health constraint request;
- memory write is not direct.

Use only existing `PermissionCapability` values.

- [ ] **Step 3: GREEN using current shared contracts**

Desired effective behavior:

```text
RESOURCE_READ                 allowed
MEMORY_READ                   allowed subject to effective policy
OPERATION_EXECUTE             allowed for Sport operations
WORKFLOW_EXECUTE              allowed for Sport workflows
SENSITIVE_INFERENCE           only as existing shared policy permits, never clinical diagnosis
MEMORY_WRITE                  denied directly
SCHEDULE_MODIFY               denied directly
COMMUNICATION_EXTERNAL        denied by default
DOMAIN_CROSS_ACCESS           denied by default; explicit scoped request required
MEDICAL_DECISION/ACTION       denied
IRREVERSIBLE_CHANGE           denied
```

- [ ] **Step 4: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_profile.py \
  tests/domains/test_sport_domain_permissions.py
git diff --check
git add -- \
  cmm/domains/sport/profile.py \
  cmm/domains/sport/permissions.py \
  tests/domains/test_sport_domain_profile.py \
  tests/domains/test_sport_domain_permissions.py
git diff --cached --check
git commit -m "feat(sport): bind profile and permission boundaries"
```

---

# Task 3 — Canonical Resources

**Files**
- Create: `cmm/domains/sport/resources.py`
- Test: `tests/domains/test_sport_domain_resources.py`

- [ ] **Step 1: RED exact resource parity**

Assert exactly the 9 canonical resource IDs from `catalog.py`, all owned by `domain:sport`.

- [ ] **Step 2: RED Health-resource restriction**

Prove the resource catalog does not itself grant unrestricted Health access.

- [ ] **Step 3: GREEN using the existing `DomainResource` contract**

Follow current Languages/Parenthood resource construction APIs.

- [ ] **Step 4: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_resources.py
git diff --check
git add -- cmm/domains/sport/resources.py tests/domains/test_sport_domain_resources.py
git diff --cached --check
git commit -m "feat(sport): add canonical resources"
```

---

# Task 4 — Training Load and Progressive Overload Rules

**Files**
- Create: `cmm/domains/sport/rules.py`
- Test: `tests/domains/test_sport_domain_rules.py`

**Interfaces**
- Produces public evaluators for all six rules. This task initially closes the load/progression behaviors; Task 5 completes the remaining rules in the same module.

- [ ] **Step 1: RED training-load semantics**

Tests must prove:
- volume/intensity/frequency remain distinguishable;
- missing input stays unknown;
- invalid numeric values fail closed;
- comparable load can be summarized;
- caller-provided Boolean/NaN/Inf values cannot become valid load evidence.

Example behavioral test shape:

```python
result = evaluate_training_load(
    volume=120.0,
    intensity=0.7,
    frequency=3,
)
assert result.status == "evaluated"
assert result.components["volume"] == 120.0
assert result.components["intensity"] == 0.7
assert result.components["frequency"] == 3
```

Use the repository's actual result model style.

- [ ] **Step 2: RED overload semantics**

Tests must prove:
- baseline and proposed loads are compared;
- no universal percentage is assumed when no policy threshold exists;
- an explicit configured threshold can gate progression;
- missing baseline cannot produce false certainty.

- [ ] **Step 3: GREEN minimal pure evaluators**

Keep rules deterministic and free of I/O.

- [ ] **Step 4: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_rules.py -k 'load or overload'
git diff --check
git add -- cmm/domains/sport/rules.py tests/domains/test_sport_domain_rules.py
git diff --cached --check
git commit -m "feat(sport): add load and progression rules"
```

---

# Task 5 — Recovery, Injury Signal, Health Constraint and Measurement Trend Rules

**Files**
- Modify: `cmm/domains/sport/rules.py`
- Modify: `tests/domains/test_sport_domain_rules.py`
- Create: `tests/domains/test_sport_domain_safety.py`

- [ ] **Step 1: RED mutable recovery/readiness**

Prove:
- rest, fatigue, pain and workload can produce a time-bound readiness result;
- new evidence can change readiness;
- a prior readiness value is not treated as immutable identity;
- missing material input can yield `unknown`/equivalent.

- [ ] **Step 2: RED injury-signal boundary**

Prove Sport may return a stop/check/escalation signal but not a diagnosis.

Tests should reject outputs or APIs that claim a named clinical injury as established solely from Sport observations.

- [ ] **Step 3: RED HealthConstraintRule**

Prove:
- authorized `health_constraint` projection is accepted;
- absent/expired/unauthorized projection is not applied;
- full Health dossier/raw clinical record is rejected;
- treatment modification is rejected;
- provenance/authorization reference survive the projection.

- [ ] **Step 4: RED MeasurementTrendRule**

Prove:
- one observation is not a trend;
- mismatched units/methods are not naively combined;
- ordered comparable observations can yield a trend;
- a punctual outlier remains visible;
- Boolean/NaN/Inf values are invalid decision evidence.

- [ ] **Step 5: GREEN + full six-rule parity**

`build_sport_rules()` must return exactly six rules matching `SPORT_RULE_IDS`.

- [ ] **Step 6: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_rules.py \
  tests/domains/test_sport_domain_safety.py
git diff --check
git add -- \
  cmm/domains/sport/rules.py \
  tests/domains/test_sport_domain_rules.py \
  tests/domains/test_sport_domain_safety.py
git diff --cached --check
git commit -m "feat(sport): enforce recovery and safety rules"
```

---

# Task 6 — Core Sport Operations

**Files**
- Create: `cmm/domains/sport/operations.py`
- Test: `tests/domains/test_sport_domain_operations.py`

- [ ] **Step 1: RED exact operation parity**

Assert exactly eight operation IDs.

- [ ] **Step 2: RED behavioral boundaries**

Cover:
- `create_training_plan` returns a plan/proposal, not a medical prescription;
- `review_progress` preserves insufficient evidence;
- `adjust_training_load` respects readiness and explicit Health constraints;
- `generate_workout` cannot bypass a blocking constraint;
- `track_measurements` preserves timestamp/unit/provenance;
- `review_recovery` uses current observations;
- `identify_risks` emits non-diagnostic risk signals;
- `schedule_sessions` creates a scheduling proposal rather than mutating a calendar directly.

- [ ] **Step 3: GREEN through existing DomainOperation contracts**

Do not add direct external adapters.

- [ ] **Step 4: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_operations.py
git diff --check
git add -- cmm/domains/sport/operations.py tests/domains/test_sport_domain_operations.py
git diff --cached --check
git commit -m "feat(sport): add canonical operations"
```

---

# Task 7 — Calendar Approval Boundary

**Files**
- Modify only if required: `cmm/domains/sport/operations.py`
- Modify: `tests/domains/test_sport_domain_operations.py`
- Modify: `tests/domains/test_sport_domain_permissions.py`

- [ ] **Step 1: RED proposed schedule vs applied mutation**

Prove `sport.schedule_sessions` can produce a proposal with session times but cannot itself write the external calendar.

- [ ] **Step 2: RED approval gate**

Use the shared approval/permission contracts to prove:
- no approval → mutation denied/pending;
- valid scoped approval → shared calendar operation may proceed;
- approval for one scope does not become permanent generalized schedule permission.

- [ ] **Step 3: GREEN minimal adaptation**

If current shared approval APIs already express this, keep production changes Sport-local or tests-only.

- [ ] **Step 4: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py
git diff --check
git add -- \
  cmm/domains/sport/operations.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py
git diff --cached --check
git commit -m "test(sport): enforce approval-gated scheduling"
```

If no production file changed, stage only tests and use the same commit message.

---

# Task 8 — Shared-Engine Workflows

**Files**
- Create: `cmm/domains/sport/workflows.py`
- Test: `tests/domains/test_sport_domain_workflows.py`

- [ ] **Step 1: RED exact workflow catalog**

Exactly:

```text
sport.training_plan_setup
sport.weekly_training_review
sport.recovery_review
sport.progress_review
sport.return_to_training_with_health_constraints
```

- [ ] **Step 2: RED shared workflow lifecycle**

Every workflow must use current shared workflow nodes/contracts. No Sport workflow engine.

- [ ] **Step 3: RED Return to Training**

Connected flow must require, as applicable:

```text
load current training state
→ review current recovery/readiness
→ inspect injury signals
→ request authorized Health constraint projection when material
→ apply restrictive constraint
→ produce continue/reduce/hold/stop-and-check recommendation
→ validate
→ return result
```

It must never diagnose or modify treatment.

- [ ] **Step 4: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_workflows.py
git diff --check
git add -- cmm/domains/sport/workflows.py tests/domains/test_sport_domain_workflows.py
git diff --cached --check
git commit -m "feat(sport): add shared-engine workflows"
```

---

# Task 9 — Memory Proposals and Mutable Sport State

**Files**
- Create: `cmm/domains/sport/memory.py`
- Test: `tests/domains/test_sport_domain_memory.py`

- [ ] **Step 1: RED no direct memory write**

Use shared Domain Memory proposal/binding contracts only.

- [ ] **Step 2: RED permitted Sport state**

Prove proposals can preserve explicit:
- sport goals;
- training plans;
- session/workout records;
- measurements;
- timestamped trend results;
- timestamped readiness/recovery results.

- [ ] **Step 3: RED prohibited persistence**

Prove no silent persistence of:
- inferred diagnosis;
- treatment change;
- unrestricted Health context;
- temporary readiness as a permanent trait.

- [ ] **Step 4: RED time/version behavior**

A newer readiness snapshot may supersede operational use of an older one without deleting provenance/history.

- [ ] **Step 5: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_memory.py
git diff --check
git add -- cmm/domains/sport/memory.py tests/domains/test_sport_domain_memory.py
git diff --cached --check
git commit -m "feat(sport): bind mutable state to memory proposals"
```

---

# Task 10 — Presentation and Trace

**Files**
- Create: `cmm/domains/sport/presentation.py`
- Create: `cmm/domains/sport/trace.py`
- Test: `tests/domains/test_sport_domain_presentation.py`
- Test: `tests/domains/test_sport_domain_trace.py`

- [ ] **Step 1: RED presentation semantics**

Presentation must distinguish when material:
- observation;
- measurement;
- trend;
- readiness snapshot;
- risk signal;
- Health constraint;
- recommendation/proposal;
- uncertainty.

No clinical diagnosis language may be introduced by rendering.

- [ ] **Step 2: RED trace ownership**

Trace must use real runtime-generated/request-generated IDs from current shared contracts, not fabricated constants presented as runtime evidence.

Include:
- selected domain/profile;
- rule/operation/workflow IDs;
- constraint provenance/authorization when Health contributes;
- approval reference for scheduling when applicable;
- memory proposal/binding references;
- validation result.

- [ ] **Step 3: GREEN + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_presentation.py \
  tests/domains/test_sport_domain_trace.py
git diff --check
git add -- \
  cmm/domains/sport/presentation.py \
  cmm/domains/sport/trace.py \
  tests/domains/test_sport_domain_presentation.py \
  tests/domains/test_sport_domain_trace.py
git diff --cached --check
git commit -m "feat(sport): add presentation and provenance trace"
```

---

# Task 11 — Validation-First Atomic Integration

**Files**
- Create: `cmm/domains/sport/integration.py`
- Test: `tests/domains/test_sport_domain_integration.py`

- [ ] **Step 1: RED atomic registration**

Prove complete canonical registration of:
- definition;
- profile;
- resources;
- rules;
- operations;
- workflows;
- permissions.

- [ ] **Step 2: RED conflict before mutation**

An incompatible duplicate must fail before partial Sport state is installed.

- [ ] **Step 3: RED rollback**

Fault-inject a mid-registration failure and assert exact parity with pre-registration registry snapshots.

- [ ] **Step 4: RED no parallel infrastructure**

Tests should verify Sport uses passed/shared registries and does not create hidden alternate registries.

- [ ] **Step 5: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_integration.py
git diff --check
git add -- cmm/domains/sport/integration.py tests/domains/test_sport_domain_integration.py
git diff --cached --check
git commit -m "feat(sport): integrate domain atomically"
```

---

# Task 12 — Bootstrap and Public API

**Files**
- Create: `cmm/domains/sport/bootstrap.py`
- Create: `cmm/domains/sport/__init__.py`
- Test: `tests/domains/test_sport_domain_bootstrap.py`
- Test: `tests/domains/test_sport_domain_public_api.py`

- [ ] **Step 1: RED bootstrap composition**

Follow the current sibling bootstrap pattern:

```text
build General/shared bootstrap
→ register_sport_domain(...)
→ return same registries/resolver/services
```

- [ ] **Step 2: RED General fallback**

Non-Sport requests still resolve to General where appropriate.

- [ ] **Step 3: RED runtime purity**

Fresh import of `cmm.domains.sport` must not mutate registries or perform registration I/O.

- [ ] **Step 4: GREEN + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_bootstrap.py \
  tests/domains/test_sport_domain_public_api.py
git diff --check
git add -- \
  cmm/domains/sport/bootstrap.py \
  cmm/domains/sport/__init__.py \
  tests/domains/test_sport_domain_bootstrap.py \
  tests/domains/test_sport_domain_public_api.py
git diff --cached --check
git commit -m "feat(sport): expose standard domain bootstrap"
```

---

# Task 13 — Sport ↔ Health Cross-Domain Boundary

**Files**
- Test: `tests/domains/test_sport_domain_cross_domain.py`
- Modify Sport production only if RED proves a missing Sport adapter/evaluator.
- Modify shared production only if RED proves a generic contract gap and stop for review before broadening architecture.

- [ ] **Step 1: RED authorized minimal projection**

Prove a purpose-bound request can receive only an authorized `health_constraint`.

- [ ] **Step 2: RED deny full Health context**

A request for a complete medical report/Health store/raw clinical history must fail closed.

- [ ] **Step 3: RED restrictive intersection**

If Sport would allow an action but Health/effective permission policy forbids transfer/use, the restrictive result wins.

- [ ] **Step 4: RED stale/expired constraint**

Expired or non-current constraint evidence cannot silently be treated as currently active.

- [ ] **Step 5: RED treatment/diagnosis boundary**

Sport cannot:
- infer a diagnosis from the constraint;
- alter medication/treatment;
- claim clinical clearance.

- [ ] **Step 6: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_safety.py
git diff --check
git add -- tests/domains/test_sport_domain_cross_domain.py
git add -- cmm/domains/sport 2>/dev/null || true
git diff --cached --check
git commit -m "test(sport): prove Health constraint boundary"
```

Before committing, unstage any Sport production file that was not actually changed. Never use blanket staging outside Sport/tests.

---

# Task 14 — Connected AT-DP-028 Acceptance Lifecycle

**Files**
- Create: `tests/domains/test_sport_domain_dp028_acceptance.py`

This is a **single connected deterministic scenario** carrying state and real runtime-owned evidence across checkpoints. Do not replace it with independent methods using unrelated fixtures.

Minimum semantic checkpoints:

```text
01 resolve domain:sport
02 load/reuse SportProfile
03 verify exact 11/9/6/8/5 catalog
04 create explicit sport goal
05 create training plan proposal
06 preserve baseline workload
07 evaluate volume
08 evaluate intensity
09 evaluate frequency
10 preserve missing load evidence as unknown
11 compare progressive overload
12 use explicit progression policy rather than universal percentage
13 generate workout under current plan
14 record completed session evidence
15 ingest relevant wearable observation
16 track body measurement with timestamp/unit
17 reject one observation as a trend
18 derive trend only from comparable ordered observations
19 preserve punctual variation/outlier
20 review current recovery
21 combine rest/fatigue/pain/workload without diagnosis
22 update mutable readiness with newer evidence
23 identify injury signal
24 produce stop/check behavior without injury diagnosis
25 request Health contribution for return-to-training
26 authorize only health_constraint projection
27 deny full medical report/Health dossier
28 preserve Health constraint provenance and authorization
29 reject expired/unauthorized constraint as current
30 run sport.return_to_training_with_health_constraints
31 apply restrictive current constraint to Sport recommendation
32 deny treatment modification
33 deny clinical-clearance claim
34 produce schedule proposal
35 deny direct calendar mutation without approval
36 preserve scoped approval for calendar path
37 produce memory proposal rather than direct write
38 prevent clinical/sensitive Health detail from Sport memory proposal
39 render trend/readiness/risk with uncertainty
40 preserve real runtime trace IDs and cross-domain provenance
41 prove atomic Sport registration
42 prove rollback parity after registration failure
43 prove no parallel Sport runtime/planner/memory/workflow engine
44 prove General fallback compatibility
```

The acceptance test should use actual resolver/composer/workflow/permission/memory/trace outputs wherever the current repository supports them. Direct helper calls may support the scenario but must not substitute for the connected runtime evidence required by a checkpoint.

- [ ] **Step 1: Write connected RED scenario**
- [ ] **Step 2: Run and identify genuine missing behavior**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 3: Fix only proven gaps**

For every production defect exposed, add/retain the smallest focused regression in the relevant earlier test module.

- [ ] **Step 4: GREEN acceptance + full Sport**

```bash
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_dp028_acceptance.py
.venv/bin/python -m pytest -q tests/domains/test_sport_domain_*.py
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  tests/domains/test_sport_domain_dp028_acceptance.py \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py
git diff --cached --check
git commit -m "test(sport): add connected AT-DP-028 acceptance"
```

Inspect the staged file list before commit and ensure only actual Task 14 changes are staged.

---

# Task 15 — Reference Documentation and Implementation-Side DP-028 Evidence

**Files**
- Create: `docs/reference/sport-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `ROADMAP.md` only if the current repository convention updates Phase 10 progress there.

Do this only after implementation and AT-DP-028 are green.

- [ ] **Step 1: Write concise operational reference**

Must include:
- identity/version/profile;
- exact 11/9/6/8/5 inventory;
- training-load semantics;
- progressive-overload policy semantics;
- mutable readiness/recovery;
- injury-signal vs diagnosis boundary;
- Health constraint projection;
- measurement-trend evidence requirements;
- scheduling approval boundary;
- memory behavior;
- workflow IDs;
- package boundary;
- AT-DP-028 entry point;
- limitations/non-goals.

- [ ] **Step 2: Update DP-028 implementation evidence**

Use repository-established status vocabulary equivalent to:

```text
Phase 10.28 — Implemented, pending independent audit
DP-028 — REQUIRES_PHASE_INSPECTION / implementation evidence present
AT-DP-028 — PASS
```

Do **not** claim independent audit closure.

- [ ] **Step 3: Verify docs do not advance 10.29+**

- [ ] **Step 4: Commit**

```bash
git add -- \
  docs/reference/sport-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  ROADMAP.md
git diff --cached --check
git commit -m "docs(sport): record DP-028 implementation evidence"
```

Stage `ROADMAP.md` only if actually modified.

---

# Task 16 — Pre-Audit Verification and Self-Review

No new behavior should be added here unless a failing gate is first reproduced with a focused RED regression.

## A. Scope and package boundary

```bash
git status --short --branch

find cmm/domains/sport -maxdepth 1 -type f -name '*.py' -print | sort

python3 - <<'PY'
from pathlib import Path
expected = {
    "__init__.py",
    "bootstrap.py",
    "catalog.py",
    "definition.py",
    "integration.py",
    "memory.py",
    "operations.py",
    "permissions.py",
    "presentation.py",
    "profile.py",
    "resources.py",
    "rules.py",
    "trace.py",
    "workflows.py",
}
actual = {p.name for p in Path("cmm/domains/sport").glob("*.py")}
print("SPORT_PACKAGE_COUNT=", len(actual))
print("SPORT_PACKAGE_EXACT=", actual == expected)
print("EXTRA=", sorted(actual - expected))
print("MISSING=", sorted(expected - actual))
raise SystemExit(0 if actual == expected else 1)
PY
```

## B. Canonical count gate

Use production `catalog.py` public constants and assert:

```text
entities=11
resources=9
rules=6
operations=8
workflows=5
```

## C. Forbidden duplication/dependency scan

```bash
rg -n \
  'Sport(Agent|Planner|Runtime|WorkflowEngine|MemoryStore|KnowledgeStore|KnowledgeGraph|ClinicalEngine|Scheduler|PermissionEngine)' \
  cmm/domains/sport \
  && exit 1 || true

rg -n \
  'from cmm\.domains\.health\.(memory|rules|operations|integration)|import cmm\.domains\.health\.(memory|rules|operations|integration)' \
  cmm/domains/sport \
  && exit 1 || true
```

Production Sport should consume shared/public cross-domain contracts, not Health private implementation internals.

## D. Placeholder scan

```bash
rg -n \
  'TODO|FIXME|TBD|PLACEHOLDER|XXX|NotImplemented|raise NotImplementedError' \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py \
  docs/reference/sport-domain.md \
  docs/superpowers/plans/2026-08-25-sport-domain-implementation.md \
  || true
```

No required behavior may remain deferred.

## E. Fresh Sport suite

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_sport_domain_*.py
```

## F. Relevant sibling/cross-domain regressions

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_health_domain_*.py \
  tests/domains/test_general_domain_*.py
```

If shell expansion becomes too large or the repository uses different test selection conventions, use the current equivalent selection without weakening coverage.

## G. All domains

```bash
.venv/bin/python -m pytest -q tests/domains
```

## H. Global suite

```bash
.venv/bin/python -m pytest -q
```

Do not hard-code historical pass counts as acceptance criteria. Record the fresh counts.

## I. Compile

```bash
.venv/bin/python -m compileall -q cmm
```

## J. Ruff — changed/Phase 10.28 surface first

```bash
.venv/bin/python -m ruff check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py
```

Then run repository-wide Ruff only if that is a current phase gate. A pre-existing Ruff debt outside Phase 10.28 must be reported separately and must not be “fixed” by broad unrelated edits.

## K. Fresh import

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import cmm.domains.sport
print("SPORT_FRESH_IMPORT=PASS")
PY
```

## L. Diff hygiene and untracked preservation

```bash
git diff --check
git status --short --branch

test -f phase-10.27-audit-v1.tar.gz
test -d tmp

git ls-files --error-unmatch phase-10.27-audit-v1.tar.gz >/dev/null 2>&1 \
  && { echo "ERROR: prior audit bundle became tracked"; exit 1; } \
  || true

git ls-files --error-unmatch tmp >/dev/null 2>&1 \
  && { echo "ERROR: tmp became tracked"; exit 1; } \
  || true
```

## M. Final implementation report

Report:

```text
PHASE10_28_IMPLEMENTATION=COMPLETE|INCOMPLETE
DP_028=IMPLEMENTED_PENDING_AUDIT|NOT_READY
AT_DP_028=PASS|FAIL
AT_DP_028_CHECKPOINTS=<fresh count>
SPORT_TESTS=<fresh result>
DOMAIN_TESTS=<fresh result>
GLOBAL_TESTS=<fresh result>
SPORT_RUFF=PASS|FAIL
SPORT_FORMAT=PASS|FAIL
COMPILE=PASS|FAIL
BLOCKERS=<n>
KNOWN_OUT_OF_SCOPE_DEBT=<description or none>
HEAD=<sha>
PUSH=NO
MERGE=NO
NEXT=INDEPENDENT_AUDIT|REMEDIATE
```

Stop before independent audit.

---

# Plan Self-Review

## Spec coverage

| Requirement | Task(s) |
| --- | --- |
| 11 entities / 9 resources / 6 rules / 8 operations / 5 workflows | 1, 3, 4–8 |
| Training load | 4, 6, 14 |
| Progressive overload | 4, 6, 14 |
| Recovery | 5, 6, 8, 14 |
| Injury signals without diagnosis | 5, 6, 13, 14 |
| Authorized Health constraints only | 2, 5, 8, 13, 14 |
| Mutable readiness | 5, 9, 14 |
| Measurement trends vs punctual variation | 5, 6, 14 |
| Training plan setup | 6, 8 |
| Weekly training review | 6, 8 |
| Recovery review | 5, 6, 8 |
| Progress review | 4–6, 8 |
| Return to Training | 5, 8, 13, 14 |
| Calendar under authorization | 2, 6, 7, 14 |
| No treatment modification | 2, 5, 13, 14 |
| Memory proposals, no silent write | 9, 14 |
| Traceability | 10, 14 |
| Atomic integration / rollback | 11, 14 |
| General fallback | 12, 14 |
| DP-028 / AT-DP-028 evidence | 14–16 |
| Documentation and green verification | 15–16 |

## Type consistency rule

Illustrative result/member names in this plan are behavioral targets, not permission to invent shared types. The executor must inspect the current repository and use existing public contracts. New Sport-local dataclasses are allowed only when no shared result contract exists and they do not duplicate shared infrastructure.

## Scope lock

Implementation ends at **implemented, pending independent audit**. Do not create the audit bundle during implementation and do not close 10.28 in the same execution run.
