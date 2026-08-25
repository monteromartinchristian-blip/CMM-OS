# Phase 10.29 — Life Plan Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `domain:life-plan` as the production Phase 10.29 coordinating Domain Pack for long-horizon goals, scenarios, dependencies, resources, constraints, decisions, milestones, cross-domain impact, feasibility and plan drift.

**Architecture:** Build the standard 14-module internal Domain Pack on the already-audited Phase 10 shared infrastructure. Life Plan coordinates purpose-minimized, explicitly authorized supporting-domain contributions but does not take ownership of Health, University, Oppositions, Parenthood, Project or other specialized semantics. Trust remains service/runtime-owned: caller mappings, IDs, booleans and arbitrary objects never constitute authorization, approval, persistence or provenance evidence.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing `cmm.domains`, Cognitive Layer, Agent Runtime, Workflow, Permission, Approval, Memory and Trace contracts.

**Spec:** `docs/superpowers/specs/2026-08-26-life-plan-domain-design.md`

**Design commit:** `9fecb32` — `docs(life-plan): freeze phase 10.29 domain design`

**Primary requirement sources:**
- `docs/roadmap/phase-10-domain-intelligence.md` — `10.29 - Life Plan Domain`
- `docs/reference/domain-intelligence-requirements-matrix.md` — `DP-029` / `AT-DP-029`
- `docs/audits/phase-10.15-prompts-preflight.md` — `life_plan.cross_domain_impact_review`, cross-domain permission and persistence constraints
- `docs/superpowers/specs/2026-08-26-life-plan-domain-design.md` — frozen implementation contract

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Required frozen-design ancestor: `9fecb32`.
- Required Phase 10.28 closure ancestor: `da83b50`.
- Existing untracked `phase-10.28-audit-v6.tar.gz` is external evidence: do not edit, delete, stage or use it as production input.
- Canonical domain ID: `domain:life-plan`.
- Public display name: `Life Plan`.
- Canonical profile: `LifePlanProfile`.
- Domain version: `1.0.0`.
- Canonical manifest ID: `manifest:life-plan:1.0.0`.
- Canonical permission policy ID: `domain-permission:life-plan:1.0.0`.
- Exact canonical counts: **13 entities / 12 resources / 8 rules / 10 operations / 7 workflows**.
- Exact production package size: **14 Python modules**.
- `catalog.py` is the single source of truth for canonical entity/resource/rule/operation/workflow IDs.
- The seventh workflow set must include `life_plan.cross_domain_impact_review`; it is the canonical workflow ID behind public **Major Decision Support**. Do not create an eighth workflow.
- `LifePlanProfile` must reuse the current profile system; do not create a parallel profile registry or resolver.
- Life Plan is a coordinating domain. Specialized source domains retain their factual/semantic ownership.
- Cross-domain access is explicit, granular, purpose-bounded and default-denied.
- Effective composition follows **most restrictive permission wins**.
- Supporting-domain data must be purpose-minimized.
- A raw mapping, raw ID, caller boolean, duck-typed object or arbitrary dataclass instance is never sufficient authorization or approval evidence.
- `preference != decision`.
- `scenario != decision`.
- `scenario != commitment`.
- `inference != confirmed fact`.
- An alternative route does not imply failure or abandonment.
- A closed decision must not reopen without explicit new evidence or a valid state transition.
- Missing/malformed resource constraints do not silently become zero.
- No automatic goal abandonment.
- No automatic external commitment.
- No payment through an unapproved Life Plan path.
- Calendar/external mutation follows the shared approval path where required.
- No direct memory write. Use shared memory proposal/view/binding/validation contracts.
- Unconfirmed preferences, scenarios, inferences, hypotheses and decisions must not become durable confirmed memory.
- Trace inventory must be assembled independently from final trace assembly.
- No import-time registration.
- Registration must be validation-first, atomic and exactly rollbackable.
- General remains resolver fallback.
- No Life Plan-specific planner, reasoning engine, workflow engine, permission engine, approval engine, memory store, trace engine, cross-domain engine, repository or persistent state subsystem.
- Shared production code may change only when a RED test proves a genuine generic contract gap. If that happens, stop and report the exact gap before broadening architecture.
- TDD: RED → verify the RED reason → minimal GREEN → focused regression → commit.
- Do not weaken existing tests.
- Do not opportunistically fix unrelated Languages/documentation debt.
- Do not advance Phase 10.30.
- Do not push.
- Do not merge.
- Implementation-side status remains `DP_029=REQUIRES_PHASE_INSPECTION` until independent audit passes.

---

# Planned Production Package

Create exactly:

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

Do not add production `state.py`, `models.py`, `planner.py`, `repository.py`, `engine.py` or equivalent parallel subsystem.

Primary tests:

```text
tests/domains/test_life_plan_domain_catalog.py
tests/domains/test_life_plan_domain_definition.py
tests/domains/test_life_plan_domain_profile.py
tests/domains/test_life_plan_domain_permissions.py
tests/domains/test_life_plan_domain_resources.py
tests/domains/test_life_plan_domain_rules.py
tests/domains/test_life_plan_domain_operations.py
tests/domains/test_life_plan_domain_workflows.py
tests/domains/test_life_plan_domain_memory.py
tests/domains/test_life_plan_domain_presentation.py
tests/domains/test_life_plan_domain_trace.py
tests/domains/test_life_plan_domain_integration.py
tests/domains/test_life_plan_domain_bootstrap.py
tests/domains/test_life_plan_domain_public_api.py
tests/domains/test_life_plan_domain_cross_domain.py
tests/domains/test_life_plan_domain_safety.py
tests/domains/test_life_plan_domain_closure_adversarial.py
tests/domains/test_life_plan_domain_dp029_acceptance.py
```

---

# Canonical Inventory

## Entities — exactly 13

```text
life_plan.entity.life_goal
life_plan.entity.milestone
life_plan.entity.scenario
life_plan.entity.dependency
life_plan.entity.constraint
life_plan.entity.risk
life_plan.entity.decision
life_plan.entity.financial_resource
life_plan.entity.career_path
life_plan.entity.education_path
life_plan.entity.housing_goal
life_plan.entity.family_goal
life_plan.entity.timeline
```

## Resources — exactly 12

```text
life_plan.resource.life_plan
life_plan.resource.financial_plan
life_plan.resource.academic_plan
life_plan.resource.opposition_plan
life_plan.resource.health_constraints
life_plan.resource.family_plan
life_plan.resource.housing_plan
life_plan.resource.goal
life_plan.resource.decision
life_plan.resource.calendar_event
life_plan.resource.memory_entry
life_plan.resource.user_message
```

These catalog resources do not grant cross-domain access by themselves.

## Rules — exactly 8

```text
life_plan.rule.goal_dependency
life_plan.rule.scenario_consistency
life_plan.rule.resource_constraint
life_plan.rule.decision_status
life_plan.rule.long_term_temporal
life_plan.rule.alternative_route
life_plan.rule.cross_domain_impact
life_plan.rule.plan_drift
```

Public rule classes:

```text
GoalDependencyRule
ScenarioConsistencyRule
ResourceConstraintRule
DecisionStatusRule
LongTermTemporalRule
AlternativeRouteRule
CrossDomainImpactRule
PlanDriftRule
```

## Operations — exactly 10

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

## Workflows — exactly 7

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

---

# Shared Runtime References to Inspect Before Each Relevant Task

Use these exact sibling files as structural references, not as copy-without-reading templates:

```text
cmm/domains/sport/catalog.py
cmm/domains/sport/definition.py
cmm/domains/sport/profile.py
cmm/domains/sport/permissions.py
cmm/domains/sport/resources.py
cmm/domains/sport/rules.py
cmm/domains/sport/operations.py
cmm/domains/sport/workflows.py
cmm/domains/sport/memory.py
cmm/domains/sport/presentation.py
cmm/domains/sport/trace.py
cmm/domains/sport/integration.py
cmm/domains/sport/bootstrap.py
cmm/domains/sport/__init__.py

cmm/domains/languages/trace.py
cmm/domains/languages/memory.py
cmm/domains/languages/integration.py

cmm/domains/parenthood/permissions.py
cmm/domains/parenthood/operations.py
cmm/domains/parenthood/memory.py

cmm/domains/cross_domain_contracts.py
cmm/domains/cross_domain_engine.py
cmm/domains/cross_domain_context.py
cmm/domains/composition_permissions.py
cmm/domains/permission_gate.py
cmm/domains/permission_resolution.py
cmm/domains/operation_approval.py
cmm/domains/approval_bridge.py
cmm/domains/workflow_execution.py
cmm/domains/memory_contracts.py
cmm/domains/memory_validation.py
cmm/domains/trace_contracts.py
cmm/domains/trace_validation.py
cmm/domains/profile_registry.py
```

The executor must use the repository's actual constructor fields and enum members. Do not invent new shared enum values when an existing supported value can represent the behavior.

---

# Core Semantic Contracts

## Decision-state lattice

Canonical public states:

```text
idea
preference
goal
scenario
decision
commitment
```

Allowed progression requires explicit evidence/state transition.

Forbidden promotions:

```text
preference -> decision       # without confirmation
scenario -> decision         # without confirmation
scenario -> commitment       # without confirmation
inference -> decision        # without confirmation
```

A closed decision may only reopen when explicit new evidence or an explicit user/state transition justifies it.

## Resource constraints

Evaluate independently:

```text
time
money
energy
available_capacity
```

Each dimension can be:

```text
known
unknown
invalid
constrained
sufficient
```

or the closest existing repository-supported structured vocabulary.

Do not coerce:

```text
missing -> 0
None -> 0
False -> 0
NaN -> usable number
Inf -> usable number
```

## Cross-domain trust

Canonical path:

```text
Life Plan need
→ CrossDomainPermissionRequest
→ shared permission resolution/gate
→ authorized minimized supporting-domain contribution
→ Life Plan rule / operation / workflow
```

Forbidden path:

```text
caller mapping / raw ID / boolean / arbitrary object
→ trusted cross-domain mutation
```

## Specialized ownership

Life Plan may consume only authorized planning impact/projection:

```text
Health       → functional/current planning constraint
University   → workload/milestone/compatibility contribution
Oppositions  → workload/progress/strategy milestone contribution
Parenthood   → family goal/dependency/timeline/financial impact
Project      → project status/dependency/resource/timeline impact
```

Life Plan does not own:

```text
diagnosis
treatment
academic rule interpretation
official opposition rules
parenthood legal/medical semantics
project execution semantics
```

---

# Task 0 — Execution Preflight and Baseline Lock

**Files:** none.

**Interfaces:**
- Consumes: repository state.
- Produces: verified execution baseline only.

- [ ] **Step 1: Verify branch, ancestors and working tree**

Run:

```bash
cd "/Users/chris/CMM OS"

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"

git merge-base --is-ancestor da83b50 HEAD
git merge-base --is-ancestor 9fecb32 HEAD

echo "HEAD=$(git rev-parse --short HEAD)"
git log -3 --oneline --decorate
git status --short --branch
```

Expected:
- branch is correct;
- both ancestor checks return 0;
- `9fecb32` is at or behind HEAD;
- the known `phase-10.28-audit-v6.tar.gz` may remain untracked;
- no unexpected staged or modified production files exist.

- [ ] **Step 2: Verify frozen design exists**

```bash
test -f docs/superpowers/specs/2026-08-26-life-plan-domain-design.md
rg -n \
  '13 entities|12 resources|8 rules|10 operations|7 workflows|life_plan\.cross_domain_impact_review|DP_029=REQUIRES_PHASE_INSPECTION' \
  docs/superpowers/specs/2026-08-26-life-plan-domain-design.md
```

Expected: all frozen markers found.

- [ ] **Step 3: Confirm package does not pre-exist**

```bash
test ! -d cmm/domains/life_plan
```

Expected: exit 0.

Do not commit anything in Task 0.

---

# Task 1 — Canonical Catalog and Immutable Definition

**Files:**
- Create: `cmm/domains/life_plan/catalog.py`
- Create: `cmm/domains/life_plan/definition.py`
- Create: `tests/domains/test_life_plan_domain_catalog.py`
- Create: `tests/domains/test_life_plan_domain_definition.py`

**Interfaces:**
- Produces:
  - `LIFE_PLAN_ENTITY_IDS`
  - `LIFE_PLAN_RESOURCE_IDS`
  - `LIFE_PLAN_RULE_IDS`
  - `LIFE_PLAN_OPERATION_IDS`
  - `LIFE_PLAN_WORKFLOW_IDS`
  - `LIFE_PLAN_DOMAIN_ID`
  - `LIFE_PLAN_DOMAIN_VERSION`
  - `LIFE_PLAN_MANIFEST_ID`
  - `LIFE_PLAN_PROFILE_NAME`
  - `build_life_plan_domain_definition()`
- Consumed by all later production modules.

- [ ] **Step 1: Read current sibling constructors**

Read completely:

```text
cmm/domains/sport/catalog.py
cmm/domains/sport/definition.py
cmm/domains/parenthood/catalog.py
cmm/domains/parenthood/definition.py
```

Use the actual current `DomainDefinition`, `DomainCapability`, metadata and manifest conventions.

- [ ] **Step 2: Write RED catalog tests**

At minimum:

```python
def test_life_plan_catalog_exact_counts() -> None:
    assert len(LIFE_PLAN_ENTITY_IDS) == 13
    assert len(LIFE_PLAN_RESOURCE_IDS) == 12
    assert len(LIFE_PLAN_RULE_IDS) == 8
    assert len(LIFE_PLAN_OPERATION_IDS) == 10
    assert len(LIFE_PLAN_WORKFLOW_IDS) == 7


def test_life_plan_required_cross_domain_workflow_is_inside_seven() -> None:
    assert "life_plan.cross_domain_impact_review" in LIFE_PLAN_WORKFLOW_IDS
    assert len(LIFE_PLAN_WORKFLOW_IDS) == 7
```

Also assert exact ordered tuples match the frozen inventory above.

- [ ] **Step 3: Write RED definition tests**

```python
def test_life_plan_domain_identity_contract() -> None:
    definition = build_life_plan_domain_definition()
    assert str(definition.id) == "domain:life-plan"
    assert definition.name == "life-plan"
    assert definition.display_name == "Life Plan"
    assert definition.version == "1.0.0"
    assert definition.reasoning_profile == "LifePlanProfile"
    assert definition.metadata.metadata["phase"] == "10.29"
    assert build_life_plan_domain_definition().to_dict() == definition.to_dict()
```

Use the sibling-supported `DomainKind`; do not invent a kind.

- [ ] **Step 4: Verify RED**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_catalog.py \
  tests/domains/test_life_plan_domain_definition.py
```

Expected: RED because `cmm.domains.life_plan` does not yet exist.

- [ ] **Step 5: Implement minimal GREEN**

Required constants:

```python
LIFE_PLAN_DOMAIN_ID = "domain:life-plan"
LIFE_PLAN_DOMAIN_VERSION = "1.0.0"
LIFE_PLAN_MANIFEST_ID = "manifest:life-plan:1.0.0"
LIFE_PLAN_PROFILE_NAME = "LifePlanProfile"
LIFE_PLAN_PERMISSION_IDS = ("domain-permission:life-plan:1.0.0",)
```

Capabilities should cover only:

```text
life_plan_goal_review
life_plan_scenario_comparison
life_plan_dependency_analysis
life_plan_resource_constraint_review
life_plan_decision_tracking
life_plan_timeline_planning
life_plan_feasibility_review
life_plan_cross_domain_coordination
life_plan_plan_drift_review
life_plan_periodic_review
```

- [ ] **Step 6: GREEN + hygiene**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_catalog.py \
  tests/domains/test_life_plan_domain_definition.py
git diff --check
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/life_plan/catalog.py \
  cmm/domains/life_plan/definition.py \
  tests/domains/test_life_plan_domain_catalog.py \
  tests/domains/test_life_plan_domain_definition.py

git diff --cached --check
git commit -m "feat(life-plan): add domain identity and canonical catalog"
```

---

# Task 2 — LifePlanProfile and Fail-Closed Permission Policy

**Files:**
- Create: `cmm/domains/life_plan/profile.py`
- Create: `cmm/domains/life_plan/permissions.py`
- Create: `tests/domains/test_life_plan_domain_profile.py`
- Create: `tests/domains/test_life_plan_domain_permissions.py`

**Interfaces:**
- Produces:
  - `LIFE_PLAN_PROFILE_ID = "life-plan.profile"`
  - `LIFE_PLAN_PROFILE_NAME = "LifePlanProfile"`
  - `build_life_plan_profile()`
  - `LIFE_PLAN_PERMISSION_POLICY_ID = "domain-permission:life-plan:1.0.0"`
  - `build_life_plan_permission_policy()`
  - authorization/confirmation helpers only if required by the current shared policy pattern.
- Consumes the existing shared profile, memory, production and permission contracts.

- [ ] **Step 1: Inspect current shared profile surface**

Read:

```text
cmm/domains/profile_registry.py
cmm/domains/sport/profile.py
cmm/domains/sport/permissions.py
cmm/domains/parenthood/profile.py
cmm/domains/parenthood/permissions.py
```

Confirm the existing name fixture already includes `LifePlanProfile`.

- [ ] **Step 2: RED profile semantics**

Tests must prove:
- profile ID is `life-plan.profile`;
- name is `LifePlanProfile`;
- domain is `domain:life-plan`;
- uncertainty/provenance are preserved;
- alternatives are allowed;
- plan coordination does not grant specialized-domain ownership;
- direct persistence is prohibited;
- autonomous external commitment is prohibited;
- sensitive inference remains limited by shared policy.

Example shape:

```python
def test_life_plan_profile_identity() -> None:
    profile = build_life_plan_profile()
    assert profile.profile_id == "life-plan.profile"
    assert profile.name == "LifePlanProfile"
```

Use the actual sibling field names.

- [ ] **Step 3: RED permission boundaries**

Prove:
- read/reasoning operations use only existing supported capabilities;
- direct memory write is denied;
- direct external communication is denied;
- direct financial action/spend is denied;
- irreversible commitment is denied;
- raw cross-domain access is denied by default;
- explicit cross-domain access still requires shared `CrossDomainPermissionRequest`/gate;
- a supporting domain cannot widen effective permissions;
- effective intersection is restrictive.

Do not add new `PermissionCapability` members.

- [ ] **Step 4: Implement GREEN using shared contracts**

Use the closest existing supported permission capabilities from the repository.

Life Plan policy intent:

```text
RESOURCE_READ             allowed under effective policy
MEMORY_READ               allowed under effective policy
OPERATION_EXECUTE         allowed for canonical Life Plan operations
WORKFLOW_EXECUTE          allowed for canonical Life Plan workflows
SENSITIVE_INFERENCE       limited according to existing policy
MEMORY_WRITE              denied directly
COMMUNICATION_EXTERNAL    denied directly
SCHEDULE_MODIFY           denied directly unless canonical approval path owns execution
FINANCIAL_ACTION/SPEND    denied directly
IRREVERSIBLE_CHANGE       denied
DOMAIN_CROSS_ACCESS       denied as blanket access; explicit scoped request required
```

- [ ] **Step 5: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_profile.py \
  tests/domains/test_life_plan_domain_permissions.py
git diff --check

git add -- \
  cmm/domains/life_plan/profile.py \
  cmm/domains/life_plan/permissions.py \
  tests/domains/test_life_plan_domain_profile.py \
  tests/domains/test_life_plan_domain_permissions.py

git diff --cached --check
git commit -m "feat(life-plan): bind profile and permission boundaries"
```

---

# Task 3 — Canonical Resources

**Files:**
- Create: `cmm/domains/life_plan/resources.py`
- Create: `tests/domains/test_life_plan_domain_resources.py`

**Interfaces:**
- Produces:
  - `LIFE_PLAN_RESOURCE_KINDS`
  - `build_life_plan_resource_definitions()`
- Consumes canonical resource IDs from `catalog.py`.

- [ ] **Step 1: RED exact 12-resource parity**

```python
def test_life_plan_resources_match_catalog_exactly() -> None:
    resources = build_life_plan_resource_definitions()
    assert tuple(resource.id for resource in resources) == LIFE_PLAN_RESOURCE_IDS
    assert len(resources) == 12
```

Use the actual resource ID field type.

- [ ] **Step 2: RED ownership and non-authorizing semantics**

Prove:
- every resource is owned by `domain:life-plan`;
- `health_constraints`, `academic_plan`, `opposition_plan`, `family_plan` do not themselves grant cross-domain access;
- source-domain contributions remain provenance-bearing values rather than raw dossier imports.

- [ ] **Step 3: GREEN**

Follow the current Sport/Parenthood `DomainResourceDefinition` construction style.

- [ ] **Step 4: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_resources.py
git diff --check

git add -- \
  cmm/domains/life_plan/resources.py \
  tests/domains/test_life_plan_domain_resources.py

git diff --cached --check
git commit -m "feat(life-plan): add canonical resources"
```

---

# Task 4 — Decision Status, Scenarios and Alternative Routes

**Files:**
- Create: `cmm/domains/life_plan/rules.py`
- Create: `tests/domains/test_life_plan_domain_rules.py`
- Create: `tests/domains/test_life_plan_domain_safety.py`

**Interfaces:**
- Produces pure evaluators:
  - `evaluate_decision_status(...)`
  - `evaluate_scenario_consistency(...)`
  - `evaluate_alternative_route(...)`
- Produces rule classes:
  - `DecisionStatusRule`
  - `ScenarioConsistencyRule`
  - `AlternativeRouteRule`
- Task 5 extends the same module with the remaining five rules.

- [ ] **Step 1: RED decision-state lattice**

Tests must prove:

```text
preference != decision
scenario != decision
scenario != commitment
inference != confirmed fact
```

Minimum behavioral cases:

```python
result = evaluate_decision_status(
    current_status="preference",
    proposed_status="decision",
    confirmation_evidence=None,
)
assert result["allowed"] is False
```

```python
result = evaluate_decision_status(
    current_status="scenario",
    proposed_status="commitment",
    confirmation_evidence=None,
)
assert result["allowed"] is False
```

Use the repository's established deterministic result style; if sibling rules return `RuleEvaluationResult`, follow that exact contract instead of returning a new dict model.

- [ ] **Step 2: RED closed-decision reopening**

Prove:
- `decision -> scenario/preference/open` is rejected when no explicit new evidence or valid transition exists;
- explicit new evidence may produce a review/reopen recommendation without silently mutating persisted state.

- [ ] **Step 3: RED scenario consistency**

Prove:
- mutually exclusive assumptions are detected;
- a coherent scenario remains a scenario;
- feasibility/coherence never promotes it into a decision;
- unknown assumptions remain unknown instead of becoming false.

- [ ] **Step 4: RED alternative route semantics**

Prove:

```text
alternative != abandonment
fallback != failure
contingency != target replacement
```

- [ ] **Step 5: Implement minimal deterministic GREEN**

No I/O, persistence, registry access, model calls or domain resolution inside rule evaluators.

- [ ] **Step 6: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_safety.py \
  -k 'decision or scenario or alternative or reopening'
git diff --check

git add -- \
  cmm/domains/life_plan/rules.py \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_safety.py

git diff --cached --check
git commit -m "feat(life-plan): enforce decision and scenario semantics"
```

---

# Task 5 — Dependencies, Constraints, Temporal Logic, Cross-Domain Impact and Plan Drift

**Files:**
- Modify: `cmm/domains/life_plan/rules.py`
- Modify: `tests/domains/test_life_plan_domain_rules.py`
- Modify: `tests/domains/test_life_plan_domain_safety.py`

**Interfaces:**
- Produces pure evaluators:
  - `evaluate_goal_dependencies(...)`
  - `evaluate_resource_constraints(...)`
  - `evaluate_long_term_temporal(...)`
  - `evaluate_cross_domain_impact(...)`
  - `evaluate_plan_drift(...)`
- Produces:
  - `GoalDependencyRule`
  - `ResourceConstraintRule`
  - `LongTermTemporalRule`
  - `CrossDomainImpactRule`
  - `PlanDriftRule`
  - `build_life_plan_rules()`

- [ ] **Step 1: RED goal dependency semantics**

Prove:
- prerequisite vs related goal remain distinct;
- cycles are rejected/detected deterministically;
- missing dependency data does not invent a prerequisite;
- caller preference does not become dependency.

- [ ] **Step 2: RED resource constraints**

Cover each dimension independently:

```text
time
money
energy
available_capacity
```

Attack malformed numerics:

```python
bad_values = [True, False, float("nan"), float("inf"), float("-inf")]
```

They must never become valid decision-driving numeric evidence.

Prove missing remains unknown.

- [ ] **Step 3: RED temporal reasoning**

Prove:
- ordered milestones pass;
- impossible ordering is rejected;
- uncertain date remains uncertain;
- missing dates do not fabricate chronology;
- stale timeline evidence is not silently current when freshness metadata is material.

- [ ] **Step 4: RED cross-domain impact trust**

Tests must create both:
1. an authorized purpose-bounded runtime contribution;
2. caller-crafted lookalikes.

Prove only the runtime-authorized/minimized contribution may affect Life Plan evaluation.

Reject:
- raw mappings;
- arbitrary authorization IDs;
- `is_authorized=True`;
- forged/standalone permission-decision objects not rooted in canonical runtime ownership;
- unrelated fields from source-domain dossiers.

- [ ] **Step 5: RED plan drift**

Compare:

```text
planned_state
confirmed_decisions
actual_state
```

Prove:
- drift is explicit;
- actual deviation does not equal abandonment;
- unconfirmed old scenarios do not override current confirmed decisions;
- provenance for each compared state remains distinguishable.

- [ ] **Step 6: Complete all eight canonical rules**

```python
rules = build_life_plan_rules()
assert len(rules) == 8
```

Exact order must match `LIFE_PLAN_RULE_IDS`.

- [ ] **Step 7: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_safety.py
git diff --check

git add -- \
  cmm/domains/life_plan/rules.py \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_safety.py

git diff --cached --check
git commit -m "feat(life-plan): add dependency constraint and drift rules"
```

---

# Task 6 — Canonical Operations

**Files:**
- Create: `cmm/domains/life_plan/operations.py`
- Create: `tests/domains/test_life_plan_domain_operations.py`

**Interfaces:**
- Produces:
  - `build_life_plan_operation_definitions()`
  - `build_timeline_result(...)`
  - `compare_scenarios_result(...)`
  - `review_goals_result(...)`
  - `detect_dependencies_result(...)`
  - `identify_risks_result(...)`
  - `update_plan_result(...)`
  - `create_milestones_result(...)`
  - `generate_periodic_review_result(...)`
  - `evaluate_feasibility_result(...)`
  - `track_decisions_result(...)`
- Exact argument shapes must use current repository operation conventions and JSON-safe data only.

- [ ] **Step 1: RED exact 10-operation registry parity**

```python
def test_life_plan_operation_ids_are_exact() -> None:
    definitions = build_life_plan_operation_definitions()
    assert tuple(item.id for item in definitions) == LIFE_PLAN_OPERATION_IDS
    assert len(definitions) == 10
```

Use actual ID accessors.

- [ ] **Step 2: RED schemas**

Every operation must have deterministic schema and declared resources. No operation may expose a schema field such as:

```text
is_authorized
approved
trusted
permission_granted
```

as caller-controlled proof of privilege.

- [ ] **Step 3: RED decision-sensitive operations**

`update_plan_result(...)` and `track_decisions_result(...)` must preserve:

```text
preference
scenario
inference
hypothesis
```

unless explicit valid confirmation/state-transition evidence exists.

A proposal may be returned, but no implicit persistence or commitment.

- [ ] **Step 4: RED feasibility semantics**

`evaluate_feasibility_result(...)` must:
- consume resource-constraint evaluation;
- keep hard constraints distinguishable from preferences;
- return unknown when decision-driving evidence is missing;
- preserve scenario status.

- [ ] **Step 5: RED timeline/milestone semantics**

`build_timeline_result(...)` and `create_milestones_result(...)` must:
- preserve temporal uncertainty;
- reject contradictory ordering;
- never invent dates.

- [ ] **Step 6: GREEN minimal implementations**

Reuse rule evaluators. Do not duplicate rule semantics in operations.

- [ ] **Step 7: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_operations.py
git diff --check

git add -- \
  cmm/domains/life_plan/operations.py \
  tests/domains/test_life_plan_domain_operations.py

git diff --cached --check
git commit -m "feat(life-plan): add canonical operations"
```

---

# Task 7 — Canonical Workflows and Shared Runtime Execution

**Files:**
- Create: `cmm/domains/life_plan/workflows.py`
- Create: `tests/domains/test_life_plan_domain_workflows.py`

**Interfaces:**
- Produces:
  - `build_life_plan_workflow_definitions()`
  - a runtime-backed helper for `life_plan.cross_domain_impact_review` only if the current Sport pattern requires a domain helper around the shared executor.
- Consumes shared workflow definitions/execution contracts.

- [ ] **Step 1: RED exact seven workflows**

Assert exact ordered IDs and display names.

Critical invariant:

```python
assert "life_plan.cross_domain_impact_review" in ids
assert len(ids) == 7
```

- [ ] **Step 2: RED workflow graph semantics**

All workflow definitions must:
- use canonical registered operations;
- have deterministic node ordering;
- preserve failure/blocked states;
- avoid side-effectful external mutation nodes;
- expose Major Decision Support through `life_plan.cross_domain_impact_review`.

- [ ] **Step 3: RED shared runtime**

Construct the actual current shared workflow registry/executor and prove the cross-domain impact workflow can be resolved/executed through it.

Do not count direct invocation of a Life Plan result helper as workflow execution.

- [ ] **Step 4: RED invalid workflow evidence**

Reject:
- arbitrary workflow-result ID;
- caller-created mapping claiming `"status": "completed"`;
- unregistered operation implementation;
- mismatched workflow ID/result.

- [ ] **Step 5: GREEN**

Follow the current Sport workflow definition/runtime pattern.

- [ ] **Step 6: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_workflows.py
git diff --check

git add -- \
  cmm/domains/life_plan/workflows.py \
  tests/domains/test_life_plan_domain_workflows.py

git diff --cached --check
git commit -m "feat(life-plan): add shared-runtime workflows"
```

---

# Task 8 — Cross-Domain Permission and Purpose-Minimized Contributions

**Files:**
- Create: `tests/domains/test_life_plan_domain_cross_domain.py`
- Modify Life Plan production modules only if RED exposes a missing adapter/evaluator.
- Modify shared production only if RED proves a generic shared-contract defect; if so, stop and report before changing architecture.

**Interfaces:**
- Consumes:
  - `CrossDomainPermissionRequest`
  - current shared permission resolution/gate
  - current cross-domain composition/aggregation contracts
- Produces verified Life Plan usage pattern, not a new cross-domain subsystem.

- [ ] **Step 1: RED real permission request**

Use the actual contract to create a request equivalent to:

```python
CrossDomainPermissionRequest(
    source_domain="domain:life-plan",
    target_domain="domain:health",
    reason="Evaluate health constraints affecting long-term plan",
    ...
)
```

Fill every required actual field from the current constructor.

- [ ] **Step 2: RED Health purpose minimization**

Authorized Life Plan input may contain only the planning-relevant Health projection supported by current contracts.

Reject a payload containing unrelated clinical dossier fields.

- [ ] **Step 3: RED multiple supporting domains**

Prove explicit requests can independently authorize relevant minimized contributions from examples such as:

```text
domain:health
domain:university
domain:oppositions
domain:parenthood
```

No blanket `"supporting_domains": [...]` declaration is itself authorization.

- [ ] **Step 4: RED most-restrictive-wins**

Create a composition where one supporting policy is more restrictive.

Assert effective capability set does not exceed the restrictive intersection.

- [ ] **Step 5: RED forged authorization attacks**

Reject at minimum:

```text
raw mapping
raw authorization_id
is_authorized=True
standalone fake permission decision
duck-typed object
target-domain mismatch
purpose mismatch
expired/invalid temporal authorization where supported
```

- [ ] **Step 6: GREEN minimal Life Plan adapter/evaluator only if needed**

Do not create cross-domain engine code under `life_plan/`.

- [ ] **Step 7: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_cross_domain.py
git diff --check

git add -- \
  tests/domains/test_life_plan_domain_cross_domain.py \
  cmm/domains/life_plan

git diff --cached --check
git commit -m "test(life-plan): enforce cross-domain trust boundary"
```

Before commit, inspect staged files and ensure no unrelated Life Plan file was accidentally staged.

---

# Task 9 — Memory Proposals, Binding and Fail-Closed Persistence

**Files:**
- Create: `cmm/domains/life_plan/memory.py`
- Create: `tests/domains/test_life_plan_domain_memory.py`

**Interfaces:**
- Produces:
  - `build_life_plan_memory_view_request(...)`
  - `build_life_plan_memory_proposal(...)`
  - `build_life_plan_memory_view(...)`
  - `build_life_plan_memory_binding(...)`
  - `validate_life_plan_memory_binding(...)`
- Consumes current shared memory contracts/validators.

- [ ] **Step 1: Read stabilized sibling memory implementations**

Read completely:

```text
cmm/domains/languages/memory.py
cmm/domains/sport/memory.py
cmm/domains/parenthood/memory.py
cmm/domains/memory_contracts.py
cmm/domains/memory_validation.py
```

- [ ] **Step 2: RED proposal-only behavior**

Prove `build_life_plan_memory_proposal(...)` creates a proposal and performs no storage/write side effect.

- [ ] **Step 3: RED decision-status persistence**

Reject durable confirmed memory promotion for:

```text
preference
scenario
inference
hypothesis
unconfirmed decision
unconfirmed commitment
```

Explicit confirmed goals/decisions may be proposed for persistence according to shared policy.

- [ ] **Step 4: RED provenance/permission binding**

Binding fails closed when:
- confirmation is absent when required;
- proposal and binding IDs mismatch;
- domain mismatch exists;
- permission evidence is invalid/unowned;
- source cross-domain contribution is unverified;
- sensitive minimized-data policy is violated.

- [ ] **Step 5: RED no specialized dossier persistence**

A minimized Health constraint may be represented when allowed; unrelated medical dossier fields must not appear in Life Plan memory proposal content.

- [ ] **Step 6: GREEN using shared contracts**

Mirror current Sport/Languages runtime-owner discipline.

- [ ] **Step 7: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_memory.py
git diff --check

git add -- \
  cmm/domains/life_plan/memory.py \
  tests/domains/test_life_plan_domain_memory.py

git diff --cached --check
git commit -m "feat(life-plan): bind controlled memory proposals"
```

---

# Task 10 — Presentation and Provenance Trace

**Files:**
- Create: `cmm/domains/life_plan/presentation.py`
- Create: `cmm/domains/life_plan/trace.py`
- Create: `tests/domains/test_life_plan_domain_presentation.py`
- Create: `tests/domains/test_life_plan_domain_trace.py`

**Interfaces:**
- Produces:
  - `build_life_plan_presentation_policy()`
  - `present_life_plan_result(...)`
  - `build_life_plan_trace_reference(...)`
  - `build_life_plan_trace_contribution(...)`
  - `build_supporting_trace_contribution(...)`
  - `assemble_life_plan_trace(...)`
  - `validate_life_plan_trace(...)`

- [ ] **Step 1: RED presentation fidelity**

Presentation must preserve:
- explicit decision status;
- scenario vs decision distinction;
- uncertainty;
- alternatives;
- resource constraints;
- drift;
- supporting-domain provenance.

It must not add conclusions absent from the result.

- [ ] **Step 2: RED trace ownership**

Primary references belong to `domain:life-plan`; supporting references keep their actual source domains.

- [ ] **Step 3: RED independent inventory discipline**

Create an independent evidence inventory from authoritative runtime objects before final trace assembly.

Test code must not derive the expected inventory by reading the final trace under test.

- [ ] **Step 4: RED trace tampering**

Reject:
- orphan IDs;
- wrong primary domain;
- supporting domain equal to primary when not valid;
- mismatched domain-result pairing;
- forged permission/approval references;
- missing workflow/operation evidence where the execution claims it occurred;
- final-trace mutation after inventory creation.

- [ ] **Step 5: GREEN**

Follow hardened Languages/Sport trace pattern exactly.

- [ ] **Step 6: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_presentation.py \
  tests/domains/test_life_plan_domain_trace.py
git diff --check

git add -- \
  cmm/domains/life_plan/presentation.py \
  cmm/domains/life_plan/trace.py \
  tests/domains/test_life_plan_domain_presentation.py \
  tests/domains/test_life_plan_domain_trace.py

git diff --cached --check
git commit -m "feat(life-plan): add presentation and provenance trace"
```

---

# Task 11 — Validation-First Atomic Integration

**Files:**
- Create: `cmm/domains/life_plan/integration.py`
- Create: `tests/domains/test_life_plan_domain_integration.py`

**Interfaces:**
- Produces:
  - `LifePlanDomainIntegrationResult`
  - `register_life_plan_domain(...)`
- Consumes passed/shared registries only.

- [ ] **Step 1: Read current atomic integration**

Read completely:

```text
cmm/domains/sport/integration.py
cmm/domains/languages/integration.py
```

Preserve current snapshot APIs and error taxonomy.

- [ ] **Step 2: RED complete canonical registration**

Prove registration installs:
- definition;
- profile;
- 12 resources;
- 8 rules;
- 10 operations;
- 7 workflows;
- permission policy.

- [ ] **Step 3: RED conflict before mutation**

Create a duplicate/incompatible registration conflict.

Assert every registry snapshot is byte/structurally equal to the pre-call snapshot.

- [ ] **Step 4: RED forced mid-registration failure**

Fault-inject a failure after at least one registry has mutated.

Assert exact rollback parity across every touched registry.

- [ ] **Step 5: RED rollback failure visibility**

If current sibling integration exposes explicit rollback failure behavior, reproduce it and prove the exception is not swallowed.

- [ ] **Step 6: RED no parallel registries**

Static/runtime tests must prove `register_life_plan_domain(...)` uses the passed shared registries and does not instantiate hidden replacement registries.

- [ ] **Step 7: GREEN**

Adapt the current Sport validation-first/snapshot/rollback pattern.

- [ ] **Step 8: Verify + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_integration.py
git diff --check

git add -- \
  cmm/domains/life_plan/integration.py \
  tests/domains/test_life_plan_domain_integration.py

git diff --cached --check
git commit -m "feat(life-plan): integrate domain atomically"
```

---

# Task 12 — Bootstrap and Public API

**Files:**
- Create: `cmm/domains/life_plan/bootstrap.py`
- Create: `cmm/domains/life_plan/__init__.py`
- Create: `tests/domains/test_life_plan_domain_bootstrap.py`
- Create: `tests/domains/test_life_plan_domain_public_api.py`

**Interfaces:**
- Produces:
  - `LIFE_PLAN_BOOTSTRAP_NAME = "LifePlanDomainBootstrap"`
  - `LifePlanDomainBootstrap`
  - `build_standard_life_plan_domain_bootstrap(...)`
  - intentional package exports.

- [ ] **Step 1: RED General + Life Plan bootstrap**

Pattern:

```text
build standard General/shared registries
→ register_life_plan_domain(...)
→ return the same registry/service objects
```

Prove both `domain:general` and `domain:life-plan` are available.

- [ ] **Step 2: RED LifePlanProfile registry lookup**

Use the actual profile registry API:

```text
get_by_domain(DomainId("life-plan"))
```

or current equivalent.

Assert returned profile name is `LifePlanProfile`.

- [ ] **Step 3: RED General fallback**

Resolve a non-Life-Plan/general request and prove normal General fallback remains intact.

- [ ] **Step 4: RED import purity**

Run in a clean subprocess:

```bash
.venv/bin/python - <<'PY'
import cmm.domains.life_plan
print("fresh_import=OK")
PY
```

Import must not register globally, write files, read user data, execute workflows, make network calls or mutate external state.

- [ ] **Step 5: RED public API exactness**

Expose only intentional public Life Plan constants/builders/evaluators/classes. Do not export internal trust-token construction helpers that would widen the attack surface.

- [ ] **Step 6: GREEN + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_bootstrap.py \
  tests/domains/test_life_plan_domain_public_api.py
git diff --check

git add -- \
  cmm/domains/life_plan/bootstrap.py \
  cmm/domains/life_plan/__init__.py \
  tests/domains/test_life_plan_domain_bootstrap.py \
  tests/domains/test_life_plan_domain_public_api.py

git diff --cached --check
git commit -m "feat(life-plan): expose standard domain bootstrap"
```

---

# Task 13 — Permanent Closure Adversarial Gate FIRST

This gate is mandatory before AT-DP-029 and before documentation claims implementation completion.

**Files:**
- Create: `tests/domains/test_life_plan_domain_closure_adversarial.py`
- Modify Life Plan production only when a test exposes a real defect.

**Interfaces:**
- Produces a permanent independent-auditor-style regression suite.
- Tests must construct malicious inputs independently rather than relying on privileged production helpers to manufacture trusted artifacts.

Freeze **24 distinct adversarial tests**.

- [ ] **Step 1: Add all 24 attack cases**

Required tests:

```text
01 preference cannot become decision without confirmation
02 scenario cannot become decision without confirmation
03 scenario cannot become commitment without confirmation
04 inference cannot become confirmed fact
05 closed decision cannot reopen without explicit new evidence
06 alternative route cannot imply abandonment
07 missing resource constraint does not become zero
08 NaN/Inf/bool resource evidence fails closed
09 raw cross-domain mapping is rejected
10 arbitrary authorization ID is rejected
11 caller authorization boolean is rejected
12 standalone/forged permission object is rejected
13 target-domain or purpose mismatch is rejected
14 supporting-domain contribution is purpose-minimized
15 most-restrictive permission intersection wins
16 unrelated sensitive source-domain dossier fields are rejected
17 automatic goal abandonment is impossible
18 external commitment without canonical approval is rejected
19 payment/financial spend without approved external path is rejected
20 forged approval ID/object is rejected
21 memory write without valid confirmation/binding fails closed
22 memory proposal cannot promote inference/scenario to confirmed state
23 trace inventory is independent from final trace
24 trace tamper/orphan/mismatched provenance is rejected and registration rollback + General fallback remain unaffected
```

For test 24, keep separate assertions for trace tamper and post-failure platform state so a single malicious scenario proves the whole boundary remains stable.

- [ ] **Step 2: Verify tests are independently adversarial**

Inspection rule:

```text
No test may call a private production helper whose sole purpose is to mint the same trusted evidence the attack is supposed to forge.
```

Using canonical public runtime services to create the valid control case is correct.

- [ ] **Step 3: Run RED/GREEN cycles by root cause**

For each failing attack:
1. identify root cause;
2. keep the adversarial test;
3. add a focused regression in the responsible module if useful;
4. implement minimal root fix;
5. rerun focused + adversarial.

- [ ] **Step 4: Verify exact count**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_closure_adversarial.py
rg -n '^def test_' tests/domains/test_life_plan_domain_closure_adversarial.py | wc -l
```

Expected:
- `24 passed` or more collected cases only if parametrization expands while there remain exactly 24 top-level attack tests;
- top-level `def test_` count = `24`.

- [ ] **Step 5: Commit**

```bash
git diff --check

git add -- \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  cmm/domains/life_plan

git diff --cached --check
git commit -m "test(life-plan): lock closure adversarial invariants"
```

Inspect staged scope before commit.

---

# Task 14 — Connected AT-DP-029 Acceptance Lifecycle

**Files:**
- Create: `tests/domains/test_life_plan_domain_dp029_acceptance.py`
- Modify focused production/test files only if the connected lifecycle exposes a genuine defect.

**Interfaces:**
- Produces implementation-side candidate evidence for `AT-DP-029`.
- Must use actual resolver/profile/workflow/permission/memory/trace/integration runtime objects where available.
- Freeze exactly **45 state-linked semantic checkpoints**.

- [ ] **Step 1: Build one connected scenario, not unrelated fixtures**

Use one deterministic Life Plan scenario with carried-forward state/evidence.

Required checkpoint sequence:

```text
01 resolve domain:life-plan as primary domain
02 load/reuse LifePlanProfile
03 verify exact 13/12/8/10/7 canonical inventories
04 create explicit long-term goal
05 preserve goal as goal rather than decision
06 register first milestone candidate
07 detect explicit prerequisite dependency
08 reject mere related preference as prerequisite
09 establish baseline time constraint
10 establish baseline money constraint
11 establish baseline energy constraint
12 establish baseline available-capacity constraint
13 preserve missing constraint evidence as unknown
14 construct scenario A
15 construct scenario B
16 compare scenarios without choosing one
17 preserve coherent scenario as scenario
18 reject scenario-to-commitment promotion
19 record explicit preference without promoting it
20 record explicit confirmed decision through valid transition
21 reject reopening of closed decision without new evidence
22 preserve alternative route without abandoning primary goal
23 evaluate long-term temporal ordering
24 reject contradictory milestone ordering
25 create real CrossDomainPermissionRequest from Life Plan to supporting domain
26 resolve canonical permission/gate evidence
27 ingest only authorized purpose-minimized supporting contribution
28 reject raw/untrusted cross-domain payload
29 prove most-restrictive effective permission wins
30 evaluate cross-domain impact without importing source dossier semantics
31 resolve life_plan.cross_domain_impact_review
32 execute that workflow through shared workflow runtime
33 evaluate feasibility using constraints + authorized impacts
34 identify explicit risk without converting uncertainty into fact
35 build timeline without inventing missing dates
36 create milestones consistent with timeline/dependencies
37 generate periodic review
38 detect plan drift between planned/confirmed/actual state
39 track decision status without implicit persistence
40 enforce external-action/approval boundary and reject forged approval
41 create controlled memory proposal/view/binding and reject invalid persistence
42 create real DomainResult/runtime references for the lifecycle
43 assemble trace inventory independently before final trace and validate final trace
44 prove atomic registration and exact rollback parity after injected failure
45 prove package has no parallel engine and General fallback remains compatible
```

- [ ] **Step 2: Checkpoint implementation discipline**

Represent checkpoints in a deterministic ordered structure, following current Sport AT-DP-028 style.

The test must assert exactly 45 checkpoints.

Example shape:

```python
assert len(checkpoints) == 45
assert tuple(checkpoints) == EXPECTED_CHECKPOINTS
```

Use the actual existing acceptance-test structure.

- [ ] **Step 3: Runtime ownership requirements**

Checkpoints 25-33, 40-43 must not use fake success booleans/IDs.

They must carry actual runtime-produced evidence forward where current shared infrastructure supports it.

- [ ] **Step 4: Independent trace inventory requirement**

Build inventory from the objects produced in the same acceptance run before calling final trace assembly.

Do not compute expected references from the assembled trace.

- [ ] **Step 5: RED defects stay RED**

If AT-DP-029 exposes a defect:
1. do not loosen the checkpoint;
2. retain/add focused regression;
3. fix root cause;
4. rerun focused module;
5. rerun adversarial gate;
6. rerun AT-DP-029.

- [ ] **Step 6: Verify exact 45**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_dp029_acceptance.py

rg -n \
  '45-checkpoint|45 checkpoints|len\(checkpoints\).*45|AT-DP-029' \
  tests/domains/test_life_plan_domain_dp029_acceptance.py
```

Expected: PASS and exactly 45 semantic checkpoints.

- [ ] **Step 7: Commit**

```bash
git diff --check

git add -- \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py

git diff --cached --check
git commit -m "test(life-plan): add connected AT-DP-029 acceptance"
```

Inspect staged scope carefully before commit.

---

# Task 15 — Documentation and Implementation-Side DP-029 Evidence

**Files:**
- Create: `docs/reference/life-plan-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `ROADMAP.md` only if the current Phase 10 convention requires a top-level progress marker.

**Interfaces:**
- Produces implementation documentation only.
- Must not claim independent audit success.

- [ ] **Step 1: Run implementation gates before status edits**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_*.py
```

Expected: PASS.

Do not update status if focused Life Plan tests are red.

- [ ] **Step 2: Create reference documentation**

`docs/reference/life-plan-domain.md` must record:
- identity/profile;
- `13/12/8/10/7`;
- 14-module package;
- decision-state semantics;
- cross-domain permission/minimization;
- workflow ID mapping for Major Decision Support;
- memory boundary;
- trace inventory discipline;
- AT-DP-029 exact 45 checkpoints;
- closure adversarial exact 24 top-level tests;
- implementation status pending independent audit.

- [ ] **Step 3: Update requirements matrix conservatively**

DP-029 must remain:

```text
REQUIRES_PHASE_INSPECTION
```

The repository mapping may now mention:
- `cmm/domains/life_plan/`;
- frozen design;
- implementation reference.

AT-DP-029 may say candidate/implementation-side `PASS` only if test actually passes.

Do not set `VERIFIED_EXISTING`.

- [ ] **Step 4: Update roadmap 10.29**

Use wording equivalent to:

```text
Phase 10.29 — Implemented, pending independent audit.
AT-DP-029 — candidate PASS (45 connected checkpoints).
Closure adversarial gate — PASS (24 top-level attack tests).
DP-029 — REQUIRES_PHASE_INSPECTION.
```

Do not say:
- complete;
- independently audited;
- final closure PASS.

- [ ] **Step 5: Verify no premature closure**

```bash
rg -n \
  '10\.29|DP-029|AT-DP-029|Life Plan|independently audited|VERIFIED_EXISTING|REQUIRES_PHASE_INSPECTION' \
  docs/reference/life-plan-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md
```

Inspect manually that any `VERIFIED_EXISTING` hits belong only to earlier closed DPs.

- [ ] **Step 6: Commit**

```bash
git diff --check

git add -- \
  docs/reference/life-plan-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md

if ! git diff --quiet -- ROADMAP.md; then
  git add -- ROADMAP.md
fi

git diff --cached --check
git commit -m "docs(life-plan): record DP-029 implementation evidence"
```

---

# Task 16 — Full Pre-Audit Verification

**Files:** no intended production modifications.

**Interfaces:**
- Produces a clean implementation candidate.
- Does not create the independent audit result.

- [ ] **Step 1: Verify package shape and canonical counts**

```bash
find cmm/domains/life_plan -maxdepth 1 -type f -name '*.py' -print | sort
test "$(find cmm/domains/life_plan -maxdepth 1 -type f -name '*.py' | wc -l | tr -d ' ')" = "14"

.venv/bin/python - <<'PY'
from cmm.domains.life_plan.catalog import (
    LIFE_PLAN_ENTITY_IDS,
    LIFE_PLAN_RESOURCE_IDS,
    LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_OPERATION_IDS,
    LIFE_PLAN_WORKFLOW_IDS,
)

assert len(LIFE_PLAN_ENTITY_IDS) == 13
assert len(LIFE_PLAN_RESOURCE_IDS) == 12
assert len(LIFE_PLAN_RULE_IDS) == 8
assert len(LIFE_PLAN_OPERATION_IDS) == 10
assert len(LIFE_PLAN_WORKFLOW_IDS) == 7
assert "life_plan.cross_domain_impact_review" in LIFE_PLAN_WORKFLOW_IDS

print("LIFE_PLAN_CANON=13/12/8/10/7")
PY
```

- [ ] **Step 2: Run focused Life Plan suite**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_*.py
```

Record exact passed count.

- [ ] **Step 3: Run adversarial gate separately**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_closure_adversarial.py
test "$(rg '^def test_' tests/domains/test_life_plan_domain_closure_adversarial.py | wc -l | tr -d ' ')" = "24"
```

Expected: PASS.

- [ ] **Step 4: Run AT-DP-029 separately**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_dp029_acceptance.py
```

Expected: PASS / exact 45 checkpoints.

- [ ] **Step 5: Run entire Domain suite**

```bash
.venv/bin/python -m pytest -q tests/domains
```

Record exact passed count.

- [ ] **Step 6: Run global suite**

```bash
.venv/bin/python -m pytest -q
```

Record exact passed count.

Any new failure must be investigated. Do not hide or xfail a failure to create a green candidate.

- [ ] **Step 7: Ruff**

Run current repository convention:

```bash
.venv/bin/python -m ruff check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py
```

If the repository's existing command differs, use the installed current Ruff CLI without changing unrelated files.

Then, if repository-wide Ruff is an established Phase 10 gate:

```bash
.venv/bin/python -m ruff check .
```

Report pre-existing unrelated debt separately; do not broad-fix unrelated scope.

- [ ] **Step 8: Compile**

```bash
.venv/bin/python -m compileall -q cmm/domains/life_plan tests/domains
```

Expected: exit 0.

- [ ] **Step 9: Fresh import**

```bash
.venv/bin/python - <<'PY'
import cmm.domains.life_plan
print("LIFE_PLAN_FRESH_IMPORT=PASS")
PY
```

- [ ] **Step 10: Architecture scan**

```bash
rg -n \
  'class .*Engine|class .*Planner|class .*Repository|DomainRegistry\(|InMemoryDomainRegistryStore\(|is_authorized\s*=\s*True|approved\s*=\s*True' \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py || true
```

Manually inspect every hit. Legitimate test fixtures are not automatically defects, but production privilege must not depend on caller booleans/IDs.

- [ ] **Step 11: No premature DP-029 closure**

```bash
rg -n \
  'DP-029.*VERIFIED_EXISTING|Phase 10\.29.*Complete.*independently audited|FINAL_INDEPENDENT_CLOSURE_AUDIT=PASS' \
  docs cmm tests || true
```

Expected: no current-candidate claim that 10.29 is independently closed.

- [ ] **Step 12: Diff hygiene and repository state**

```bash
git diff --check
git diff --cached --check
git status --short --branch
git log -8 --oneline --decorate
```

Only known untracked external audit evidence from earlier phase may remain.

- [ ] **Step 13: Commit any final candidate-only correction**

Only if verification required a legitimate Life Plan fix:

```bash
git add -- <exact Life Plan files only>
git diff --cached --check
git commit -m "fix(life-plan): close pre-audit verification gaps"
```

Rerun every affected gate after this commit.

---

# Task 17 — Build the Versioned-HEAD Audit Bundle

This task creates external evidence only after all implementation gates are green.

**Files:** no tracked modifications intended.

**Interfaces:**
- Produces: `phase-10.29-audit-v1.tar.gz` from exact versioned HEAD.
- Does not perform the independent audit.

- [ ] **Step 1: Confirm candidate is committed**

```bash
git status --short --branch
git log -1 --oneline --decorate
```

No tracked modifications or staged changes are allowed.

Known previous untracked audit bundles may remain.

- [ ] **Step 2: Capture candidate HEAD**

```bash
CANDIDATE_HEAD="$(git rev-parse HEAD)"
echo "CANDIDATE_HEAD=$CANDIDATE_HEAD"
```

- [ ] **Step 3: Create versioned-HEAD-only bundle**

From repository root:

```bash
git archive \
  --format=tar.gz \
  --output=phase-10.29-audit-v1.tar.gz \
  HEAD
```

Do not use raw `tar` over the working directory.

- [ ] **Step 4: Verify bundle**

```bash
tar -tzf phase-10.29-audit-v1.tar.gz >/tmp/phase-10.29-audit-v1-files.txt

grep -q '^cmm/domains/life_plan/' /tmp/phase-10.29-audit-v1-files.txt
grep -q '^tests/domains/test_life_plan_domain_dp029_acceptance.py$' /tmp/phase-10.29-audit-v1-files.txt
grep -q '^tests/domains/test_life_plan_domain_closure_adversarial.py$' /tmp/phase-10.29-audit-v1-files.txt
grep -q '^docs/reference/life-plan-domain.md$' /tmp/phase-10.29-audit-v1-files.txt
grep -q '^docs/superpowers/specs/2026-08-26-life-plan-domain-design.md$' /tmp/phase-10.29-audit-v1-files.txt
grep -q '^docs/superpowers/plans/2026-08-26-life-plan-domain-implementation.md$' /tmp/phase-10.29-audit-v1-files.txt

if grep -E '(^|/)(\.env|\.git|\.venv|\.tokensave|\.worktrees|tmp)(/|$)|audit-v[0-9]+\.tar\.gz$' \
  /tmp/phase-10.29-audit-v1-files.txt; then
  echo "ERROR: forbidden audit-bundle content"
  exit 1
fi

shasum -a 256 phase-10.29-audit-v1.tar.gz
ls -lh phase-10.29-audit-v1.tar.gz
```

- [ ] **Step 5: Keep bundle untracked**

```bash
git status --short --branch
```

Expected: bundle appears as `?? phase-10.29-audit-v1.tar.gz`.

Do not stage or commit the audit bundle.

- [ ] **Step 6: Stop for independent audit**

Do not self-mark closure.

Deliver the TAR.GZ to ChatGPT, the independent CMM OS closure auditor.

---

# Pre-Audit Candidate Status Contract

Before independent audit, the final implementation response must state only:

```text
PHASE10_29_IMPLEMENTATION=COMPLETE
AT_DP_029=PASS
AT_DP_029_CHECKPOINTS=45
CLOSURE_ADVERSARIAL_GATE=PASS
CLOSURE_ADVERSARIAL_TESTS=24
DP_029=REQUIRES_PHASE_INSPECTION
INDEPENDENT_AUDIT=PENDING
PUSH=NO
MERGE=NO
```

It must not state:

```text
PHASE10_29=COMPLETE
DP_029=VERIFIED_EXISTING
FINAL_INDEPENDENT_CLOSURE_AUDIT=PASS
```

Those are auditor-controlled closure states.

---

# Expected Commit Sequence

Use coherent task-sized commits. The exact SHA values are naturally unknown until execution, but the message contract is fixed:

```text
feat(life-plan): add domain identity and canonical catalog
feat(life-plan): bind profile and permission boundaries
feat(life-plan): add canonical resources
feat(life-plan): enforce decision and scenario semantics
feat(life-plan): add dependency constraint and drift rules
feat(life-plan): add canonical operations
feat(life-plan): add shared-runtime workflows
test(life-plan): enforce cross-domain trust boundary
feat(life-plan): bind controlled memory proposals
feat(life-plan): add presentation and provenance trace
feat(life-plan): integrate domain atomically
feat(life-plan): expose standard domain bootstrap
test(life-plan): lock closure adversarial invariants
test(life-plan): add connected AT-DP-029 acceptance
docs(life-plan): record DP-029 implementation evidence
```

A final `fix(life-plan): close pre-audit verification gaps` commit is permitted only if Task 16 finds a real candidate defect.

Do not squash away useful implementation history before audit.

---

# Self-Review Matrix

Before execution, this plan covers every frozen design requirement:

| Frozen requirement | Plan task |
|---|---|
| 14-module standard Domain Pack | Tasks 1–12, 16 |
| 13 entities | Task 1 |
| 12 resources | Tasks 1, 3 |
| 8 rules | Tasks 4–5 |
| 10 operations | Task 6 |
| 7 workflows | Task 7 |
| `life_plan.cross_domain_impact_review` inside seven | Tasks 1, 7, 14 |
| `LifePlanProfile` | Task 2, 12 |
| preference != decision | Tasks 4, 6, 13, 14 |
| scenario != decision/commitment | Tasks 4, 6, 13, 14 |
| inference != confirmed fact | Tasks 4, 9, 13 |
| closed-decision reopening protection | Tasks 4, 13, 14 |
| alternative route != abandonment | Tasks 4, 13, 14 |
| resource constraints | Tasks 5, 6, 13, 14 |
| temporal compatibility | Tasks 5, 6, 14 |
| explicit cross-domain permission | Tasks 5, 8, 13, 14 |
| purpose minimization | Tasks 5, 8, 9, 13, 14 |
| most restrictive permission wins | Tasks 2, 8, 13, 14 |
| no automatic goal abandonment | Tasks 4, 13 |
| approval/external commitment boundary | Tasks 2, 6, 13, 14 |
| no unapproved payment | Tasks 2, 13, 14 |
| memory fail closed | Tasks 9, 13, 14 |
| independent trace inventory | Tasks 10, 13, 14 |
| atomic integration/rollback | Tasks 11, 13, 14 |
| General fallback | Tasks 12–14 |
| connected AT-DP-029 | Task 14 |
| adversarial gate from V1 | Task 13 |
| conservative docs / DP-029 pending | Task 15 |
| full verification | Task 16 |
| versioned-HEAD audit bundle | Task 17 |

No frozen requirement is intentionally deferred.

---

# Agent Execution Rules

The implementation agent must:

1. read the frozen spec and this plan before changing code;
2. work task-by-task;
3. use RED → GREEN discipline;
4. make the listed coherent commits;
5. investigate failures before fixing them;
6. never loosen acceptance/adversarial tests to manufacture green;
7. avoid unrelated refactoring;
8. stop and report before changing shared architecture for a supposed generic gap;
9. keep `DP_029=REQUIRES_PHASE_INSPECTION`;
10. finish with all verification gates green;
11. generate the versioned-HEAD-only audit bundle;
12. stop before independent audit;
13. never push;
14. never merge;
15. never begin Phase 10.30.

---

# Final Agent Response Format

When the implementation candidate is genuinely complete, respond concisely with:

```markdown
## Phase 10.29 implementation

Implemented:
- 14-module Life Plan Domain Pack
- 13 entities / 12 resources / 8 rules / 10 operations / 7 workflows
- LifePlanProfile + fail-closed permissions
- cross-domain impact workflow through shared runtime
- controlled memory + independent provenance trace
- atomic registration + General fallback

Hardening:
- preference != decision
- scenario != commitment
- inference != confirmed fact
- raw/forged cross-domain authorization rejected
- most-restrictive permission wins
- no automatic abandonment/commitment/payment
- memory fail closed
- trace inventory independent
- 24-test permanent closure adversarial gate

Verification:
- Life Plan focused: <exact passed count> PASS
- AT-DP-029: PASS — 45 checkpoints
- Closure adversarial: PASS — 24 top-level tests
- Domain suite: <exact passed count> PASS
- Global suite: <exact passed count> PASS
- Ruff: PASS
- format: PASS
- compileall: PASS
- fresh import: PASS
- diff checks: PASS

Documentation:
- docs/reference/life-plan-domain.md
- requirements matrix updated
- roadmap 10.29 updated
- DP-029=REQUIRES_PHASE_INSPECTION

Audit candidate:
- HEAD=<full SHA>
- bundle=phase-10.29-audit-v1.tar.gz
- SHA256=<sha256>

Status:
- PHASE10_29_IMPLEMENTATION=COMPLETE
- AT_DP_029=PASS
- AT_DP_029_CHECKPOINTS=45
- CLOSURE_ADVERSARIAL_GATE=PASS
- CLOSURE_ADVERSARIAL_TESTS=24
- DP_029=REQUIRES_PHASE_INSPECTION
- INDEPENDENT_AUDIT=PENDING
- PUSH=NO
- MERGE=NO
```

If any gate remains blocked, do not present Phase 10.29 as implemented. Report the exact blocker, failing command and current HEAD instead.
