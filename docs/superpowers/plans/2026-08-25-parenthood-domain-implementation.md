# Phase 10.27 — Parenthood Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `domain:parenthood` as a production Domain Pack supporting both `parenthood.journey` and isolated `parenthood.child:<child_id>` workspaces, with fail-closed handling of sensitive family/minor data and explicit journey→child transfer.

**Architecture:** Reuse the current Phase 10 Domain Pack pattern. Languages is the structural reference for catalog/definition/profile/integration/bootstrap; Health and Relationships are the sensitivity/permission references. Parenthood remains one Domain Pack with one `ParenthoodProfile`; journey and per-child spaces are functional scopes, not separate reasoning engines.

**Tech Stack:** Python 3.10+, pytest, existing `cmm.domains`, Cognitive Layer and Agent Runtime contracts.

**Spec:** `docs/roadmap/phase-10-domain-intelligence.md` — `10.27 - Paternidad Domain`

**Functional requirement sources:**
- `docs/roadmap/requirements/parenthood/README.md`
- `docs/roadmap/requirements/parenthood/camino-a-la-paternidad.md`
- `docs/roadmap/requirements/parenthood/paternidad.md`

## Global constraints

- Canonical domain ID: `domain:parenthood`.
- Public name: `Paternidad`.
- Profile: `ParenthoodProfile`.
- Scopes: `parenthood.journey` and `parenthood.child:<child_id>`.
- Personal child names are presentation data only.
- Multiple children use one Domain Pack.
- Sibling identity/history/health/education/decisions/memory must never silently merge.
- Journey→child transfer is explicit, selective, provenance-preserving and permission/approval bound.
- Information concerning minors receives restrictive defaults.
- No autonomous medical, legal, financial, enrollment, contracting, payment, consent, external communication or high-impact parental decision.
- Current legal/admin/medical claims require current-source verification when temporally mutable.
- No import-time registration or parallel infrastructure.
- General remains resolver fallback.
- `tmp/` from Phase 10.26 is out of scope and must remain unstaged.
- TDD: RED → minimal GREEN → focused regression → commit.
- No merge or push.

---

## Planned package

```text
cmm/domains/parenthood/
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
├── workspaces.py
└── workflows.py
```

Tests mirror the production package under `tests/domains/test_parenthood_domain_*.py`, with a final connected `test_parenthood_domain_dp027_acceptance.py`.

---

## Task 1 — Canonical catalog and immutable definition

**Create:**
- `cmm/domains/parenthood/catalog.py`
- `cmm/domains/parenthood/definition.py`
- `tests/domains/test_parenthood_domain_catalog.py`
- `tests/domains/test_parenthood_domain_definition.py`

### Required public constants

```python
PARENTHOOD_DOMAIN_ID = "domain:parenthood"
PARENTHOOD_DOMAIN_VERSION = "1.0.0"
PARENTHOOD_MANIFEST_ID = "manifest:parenthood:1.0.0"
PARENTHOOD_PROFILE_NAME = "ParenthoodProfile"
PARENTHOOD_PERMISSION_IDS = ("domain-permission:parenthood:1.0.0",)
```

### Canonical entities

Journey:

```text
parenthood_goal
parenthood_pathway
jurisdiction
medical_pathway
medical_provider
participant
legal_requirement
administrative_requirement
documentation_requirement
financial_scenario
ethical_constraint
timeline
decision
risk
birth_transition
```

Child:

```text
child
developmental_stage
care_need
routine
milestone
education_plan
school
activity
health_context
wellbeing_signal
family_context
support_network
parental_decision
value
boundary
schedule
residence_plan
long_term_plan
```

### Canonical resources

```text
parenthood.resource.life_plan
parenthood.resource.legal_document
parenthood.resource.medical_report
parenthood.resource.financial_plan
parenthood.resource.provider_information
parenthood.resource.jurisdiction_information
parenthood.resource.decision
parenthood.resource.note
parenthood.resource.parenting_note
parenthood.resource.education_document
parenthood.resource.child_development_resource
parenthood.resource.health_summary
parenthood.resource.schedule
parenthood.resource.parental_decision
parenthood.resource.school_information
parenthood.resource.activity_information
parenthood.resource.user_message
parenthood.resource.external_source
parenthood.resource.memory_entry
```

### Canonical rules

```text
parenthood.rule.parenthood_decision_explicit
parenthood.rule.legal_temporal_validity
parenthood.rule.medical_legal_separation
parenthood.rule.ethical_constraint
parenthood.rule.cost_uncertainty
parenthood.rule.journey_dependency
parenthood.rule.journey_to_child_boundary
parenthood.rule.child_interest_and_wellbeing
parenthood.rule.developmental_context
parenthood.rule.age_appropriate_guidance
parenthood.rule.parent_child_boundary
parenthood.rule.health_boundary
parenthood.rule.education_boundary
parenthood.rule.minor_privacy
parenthood.rule.long_term_continuity
parenthood.rule.parental_uncertainty
parenthood.rule.sibling_identity_isolation
```

### Canonical operations

Journey:

```text
parenthood.journey.build_timeline
parenthood.journey.compare_pathways
parenthood.journey.review_requirements
parenthood.journey.review_financial_scenarios
parenthood.journey.prepare_questions
parenthood.journey.track_decisions
parenthood.journey.update_plan
parenthood.journey.generate_documentation_checklist
parenthood.journey.review_risks
```

Child:

```text
parenthood.child.review_needs
parenthood.child.review_developmental_stage
parenthood.child.plan_routines
parenthood.child.prepare_parental_decision
parenthood.child.review_education_plan
parenthood.child.review_family_context
parenthood.child.track_milestones
parenthood.child.prepare_questions
parenthood.child.track_decisions
parenthood.child.update_parenting_plan
parenthood.child.review_risks_and_needs
```

### Canonical workflows

```text
parenthood.workflow.path_to_parenthood_review
parenthood.workflow.pathway_comparison
parenthood.workflow.provider_review
parenthood.workflow.requirements_review
parenthood.workflow.financial_readiness_review
parenthood.workflow.medical_preparation_review
parenthood.workflow.documentation_review
parenthood.workflow.annual_journey_plan_update
parenthood.workflow.child_needs_review
parenthood.workflow.developmental_stage_review
parenthood.workflow.education_planning_review
parenthood.workflow.routine_review
parenthood.workflow.parental_decision_review
parenthood.workflow.family_context_review
parenthood.workflow.milestone_review
parenthood.workflow.annual_parenting_plan_review
```

### RED tests

```python
def test_parenthood_domain_identity_contract() -> None:
    definition = build_parenthood_domain_definition()
    assert str(definition.id) == "domain:parenthood"
    assert definition.name == "parenthood"
    assert definition.display_name == "Paternidad"
    assert definition.version == "1.0.0"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.reasoning_profile == "ParenthoodProfile"
    assert definition.metadata.metadata["phase"] == "10.27"
    assert build_parenthood_domain_definition().to_dict() == definition.to_dict()
```

Run RED:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_parenthood_domain_catalog.py \
  tests/domains/test_parenthood_domain_definition.py
```

Expected: import/collection failure because package does not exist.

### GREEN implementation

Follow `cmm/domains/languages/definition.py` exactly for structure. Define ten capabilities:

```text
parenthood_journey_planning
parenthood_pathway_comparison
parenthood_requirements_review
parenthood_financial_scenario_review
parenthood_child_workspace
parenthood_developmental_review
parenthood_parental_decision_support
parenthood_family_context_review
parenthood_journey_to_child_transition
parenthood_multi_child_isolation
```

Use:

```python
kind=DomainKind.PERSONAL
presentation_policy={
    "detail_level": "detailed",
    "include_uncertainty": True,
    "include_provenance": True,
    "include_alternatives": True,
    "allow_speculation": False,
    "require_disclaimers": True,
}
```

Run GREEN and commit:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_parenthood_domain_catalog.py \
  tests/domains/test_parenthood_domain_definition.py

git diff --check

git add \
  cmm/domains/parenthood/catalog.py \
  cmm/domains/parenthood/definition.py \
  tests/domains/test_parenthood_domain_catalog.py \
  tests/domains/test_parenthood_domain_definition.py

git commit -m "feat(parenthood): add domain identity and catalog"
```

---

## Task 2 — ParenthoodProfile and fail-closed permissions

**Create:**
- `cmm/domains/parenthood/profile.py`
- `cmm/domains/parenthood/permissions.py`
- `tests/domains/test_parenthood_domain_profile.py`
- `tests/domains/test_parenthood_domain_permissions.py`

### Profile contract

```python
PARENTHOOD_PROFILE_ID = "parenthood.profile"
PARENTHOOD_PROFILE_NAME = "ParenthoodProfile"
PARENTHOOD_FUNCTIONAL_SCOPES = (
    "parenthood.journey",
    "parenthood.child",
)
```

Profile must prohibit at least:

```text
direct_memory_write
silent_memory_persistence
external_communication
child_enrollment
contracting
payment
consent
legal_commitment
medical_decision
legal_decision
financial_decision
high_impact_parental_decision
```

Allowed inferences:

```text
journey_dependency
pathway_comparison
requirement_gap
cost_uncertainty
developmental_context
age_appropriate_need
child_wellbeing_signal
parent_child_preference_separation
parenting_option
parental_uncertainty
sibling_specific_context
transfer_candidate
```

Prohibited inferences:

```text
inferred_parental_decision_as_adopted
child_trait_as_stable_identity_without_evidence
cross_sibling_identity_merge
medical_diagnosis_from_parenting_context
legal_conclusion_without_current_verification
financial_commitment_as_decided
journey_history_auto_transfer
silent_memory_persistence
```

Use the existing `DomainMemoryPolicy`, `DomainTemporalPolicy`, `DomainProductionPolicy` and `DomainQuestionPolicy` contracts. Do not add new shared enums. If the shared `SensitivityLevel` does not expose a literal `SENSITIVE`, use the highest existing repository-supported level that corresponds to the intended restrictive policy and lock it with tests.

### Permission contract

Follow Health/Relationships fail-closed style.

Allowed capabilities only:

```python
(
    PermissionCapability.RESOURCE_READ,
    PermissionCapability.MEMORY_READ,
    PermissionCapability.SENSITIVE_INFERENCE,
    PermissionCapability.OPERATION_EXECUTE,
    PermissionCapability.WORKFLOW_EXECUTE,
)
```

Prohibit at least:

```text
MEMORY_WRITE
FILE_MODIFY
TASK_CREATE
SCHEDULE_MODIFY
GOAL_UPDATE
COMMUNICATION_EXTERNAL
SENSITIVE_INFERENCE_PERSIST
EXPORT
PUBLICATION
EXTERNAL_DOMAIN_ACTIVATE
IRREVERSIBLE_CHANGE
KNOWLEDGE_DELETE
PERMISSION_MODIFY
DOMAIN_CROSS_ACCESS
MEDICAL_DECISION
MEDICAL_ACTION
LEGAL_DECISION
LEGAL_ACTION
FINANCIAL_DECISION
FINANCIAL_ACTION
FINANCIAL_SPEND
```

Require:

```python
allow_memory_read=True
allow_memory_write=False
allow_external_search=False
allow_external_models=False
allow_external_communication=False
allow_file_modification=False
allow_task_creation=False
allow_schedule_modification=False
allow_goal_update=False
allow_export=False
allow_sensitive_inference=True
allow_cross_domain_access=False
maximum_autonomy_level=0
```

### RED tests

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_parenthood_domain_profile.py \
  tests/domains/test_parenthood_domain_permissions.py
```

### GREEN + commit

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_parenthood_domain_profile.py \
  tests/domains/test_parenthood_domain_permissions.py

git diff --check

git add \
  cmm/domains/parenthood/profile.py \
  cmm/domains/parenthood/permissions.py \
  tests/domains/test_parenthood_domain_profile.py \
  tests/domains/test_parenthood_domain_permissions.py

git commit -m "feat(parenthood): add profile and permission boundaries"
```

---

## Task 3 — Functional scope and child workspace contracts

Create `workspaces.py` + tests.

Contracts:

```python
@dataclass(frozen=True, slots=True)
class ParenthoodScope:
    kind: Literal["journey", "child"]
    child_id: str | None = None

@dataclass(frozen=True, slots=True)
class ChildParentingWorkspace:
    id: str
    domain_id: str
    display_name: str
    status: str
    developmental_stage: str | None
    created_at: datetime
    metadata: Mapping[str, JSONValue]
```

Functions:

```text
parse_parenthood_scope
build_child_workspace
validate_child_workspace
ensure_sibling_identity_isolation
select_journey_transfer_candidates
```

Tests must prove:
- stable internal child ID independent of display name;
- no child name becomes a Domain Pack ID;
- two siblings remain isolated;
- shared-family records require explicit shared scope;
- whole journey dossier transfer is rejected;
- accepted transfer candidates preserve source/provenance and require authorization.

Commit: `feat(parenthood): add child workspace isolation contracts`

---

## Task 4 — Resources

Create `resources.py` + tests. Exact catalog parity, all resources owned by `domain:parenthood`, child-scoped resources never implicitly shared.

Commit: `feat(parenthood): add canonical resources`

---

## Task 5 — Rules

Create `rules.py` + rule/safety tests.

Implement all 17 canonical rules with pure deterministic evaluators. At minimum prove:
- proposals do not become adopted decisions;
- temporally mutable legal/admin claims remain unverified without current evidence;
- medical/legal/financial categories remain distinct;
- cost uncertainty remains ranges/unknowns;
- parent preference and child need remain distinct;
- normal developmental variation does not become diagnosis;
- sibling records do not contaminate each other;
- journey history is not bulk-copied into child context.

Commit: `feat(parenthood): enforce journey and child reasoning rules`

---

## Task 6 — Operations

Create `operations.py` + tests for exact 20-operation parity.

Every result must preserve proposal-only semantics and expose no direct external action. Child operations require explicit `child_id`.

Commit: `feat(parenthood): add journey and child operations`

---

## Task 7 — Workflows

Create `workflows.py` + tests for exact 16-workflow parity. Child workflows carry `child_id`; transition workflow cannot bypass transfer selection/privacy review.

Commit: `feat(parenthood): add scoped domain workflows`

---

## Task 8 — Memory

Create `memory.py` + tests using shared Domain Memory proposal/binding contracts only.

Prove:
- no direct memory write;
- inferred parental decisions cannot silently persist;
- child proposals are child-scoped;
- cross-child binding mismatch fails;
- journey→child transfer persistence requires provenance + permission/approval chain.

Commit: `feat(parenthood): bind sensitive memory proposals to scope`

---

## Task 9 — Presentation

Create `presentation.py` + tests.

Public model:

```text
Paternidad
├── Camino a la Paternidad
└── <configured child display name>
```

Presentation must preserve uncertainty/provenance and distinguish fact/inference/hypothesis/recommendation where material.

Commit: `feat(parenthood): add human-facing scoped presentation`

---

## Task 10 — Trace

Create `trace.py` + tests following Languages AT-DP-026 runtime-owner discipline.

Trace must include active functional scope, stable child ID, and complete source→proposal→permission/approval→destination provenance for journey→child transfers.

Commit: `feat(parenthood): add scoped provenance trace`

---

## Task 11 — Validation-first integration

Create `integration.py` + tests by adapting current Languages integration.

Prove:
- atomic registration;
- conflict preflight before mutation;
- exact rollback after mid-registration failure;
- no parallel registries;
- canonical profile/resources/rules/ops/workflows/permissions registered together.

Commit: `feat(parenthood): integrate domain atomically`

---

## Task 12 — Bootstrap + public API

Create `bootstrap.py`, `__init__.py`, tests.

Pattern:

```text
build General bootstrap
→ register_parenthood_domain(...)
→ return same registries + resolver
```

Prove General remains fallback and package import has no registration side effects.

Commit: `feat(parenthood): expose standard domain bootstrap`

---

## Task 13 — Cross-domain boundaries

Tests only unless a proven shared adapter gap exists.

Prove:
- authorized/relevant Health projection only;
- no medical diagnosis/treatment delegation into Parenthood;
- educational context without duplicating specialized engines;
- restrictive permission intersection wins;
- General remains fallback.

---

## Task 14 — Connected AT-DP-027

Create `test_parenthood_domain_dp027_acceptance.py` with a connected runtime scenario covering at least:

```text
01 resolve journey scope
02 load ParenthoodProfile
03 preserve goal vs decision
04 compare pathways
05 legal temporal uncertainty
06 medical/legal/financial separation
07 cost ranges
08 prepare questions without transmission
09 track explicit journey decision
10 reject inferred decision adoption
11 build journey timeline
12 documentation review
13 create child workspace
14 display name separate from ID
15 resolve child scope
16 developmental stage
17 child need vs parent preference
18 non-diagnostic normal variation
19 scoped health context
20 parental decision proposal
21 reject autonomous enrollment/payment/consent/contact
22 create second child workspace
23 sibling identity isolation
24 sibling health isolation
25 explicit shared-family context
26 select journey→child transfer candidates
27 reject whole-dossier transfer
28 preserve transfer provenance
29 privacy/permission review
30 approval/binding before persistence
31 adopted vs proposed decisions
32 uncertainty + alternatives in presentation
33 runtime trace IDs owned by real runtime objects
34 no parallel infrastructure
35 General fallback compatibility
```

Commit: `test(parenthood): add AT-DP-027 connected acceptance`

---

## Task 15 — Documentation and implementation-side DP-027 evidence

Create `docs/reference/parenthood-domain.md`; update matrix + roadmap only after implementation gates pass.

Do not mark independently closed. Record implementation-side candidate evidence only.

Commit: `docs(parenthood): record DP-027 implementation evidence`

---

## Task 16 — Pre-audit verification

```bash
.venv/bin/python -m pytest -q tests/domains/test_parenthood_domain_*.py
.venv/bin/python -m pytest -q tests/domains
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q cmm
.venv/bin/python -m ruff check cmm tests
.venv/bin/python -m ruff format --check cmm tests
git diff --check
git status --short --branch
```

Verify `tmp/` remains unstaged, no legacy architectural identifier returns, and no Phase 10.28+ production scope changed.

Independent audit begins only after these implementation gates pass.

---

# First execution slice

Execute **Task 1 + Task 2 only**.

Expected production files after the slice:

```text
cmm/domains/parenthood/
├── catalog.py
├── definition.py
├── permissions.py
└── profile.py
```

Gate:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_parenthood_domain_catalog.py \
  tests/domains/test_parenthood_domain_definition.py \
  tests/domains/test_parenthood_domain_profile.py \
  tests/domains/test_parenthood_domain_permissions.py

git diff --check
```

Do not implement workspaces, resources, rules, operations, workflows, memory, presentation, trace, integration or bootstrap until this first slice is green.
