# Phase 10.30 — Project Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the canonical `domain:project` Domain Pack required by `DP-030`, with a generic project-management core and a conditional software/self-development capability, while reusing all existing Phase 8–10 shared infrastructure and preserving historical Project compatibility.

**Architecture:** Add exactly the frozen 14-module `cmm/domains/project/` package. `catalog.py` is the single source of canonical IDs; pure factories build resources/profile/rules/operations/workflows/permissions; registration is validation-first and atomic; the standard bootstrap extends the existing Phase 10 chain through Life Plan using the same registries. Generic Project semantics work without repository/code resources. Software semantics activate only from grounded software context and reuse existing development, semantic execution, validation, approval, rollback, memory and trace infrastructure.

**Tech Stack:** Python 3.10+, dataclasses/shared CMM contracts, existing Phase 8 Cognitive Layer, Phase 9 Agent Runtime, Phase 7 Validation, Phase 10 Domain Intelligence registries/contracts, pytest, Ruff, compileall, Git.

**Spec:** `docs/superpowers/specs/2026-08-26-project-domain-design.md`

## Global Constraints

- Design baseline: `c520cbb` on `feature/phase-10-domain-intelligence`; implementation execution starts from plan commit `21c51bb`.
- Canonical identity: `domain:project`, `ProjectProfile`, `manifest:project:1.0.0`, `domain-permission:project:1.0.0`.
- Exact production package: **14 Python modules** under `cmm/domains/project/` and no additional production file in that package.
- Exact canonical inventory: **27 entities, 22 resources, 18 rules, 20 operations, 12 workflows**.
- `catalog.py` is the single source of truth for canonical entity/resource/rule/operation/workflow IDs.
- Generic Project must work without software resources.
- Software capability activation requires grounded software context; `primary_domain == domain:project` is insufficient by itself.
- `project.review_change` is canonical; `project.prepare_change_review` remains legacy-only and is not part of the 20-operation canonical inventory.
- `project.prepare_commit` prepares commit-readiness evidence only and must never execute `git commit`, fabricate a commit hash, or claim a commit occurred.
- All Project operations are **UNAVAILABLE by default** unless a valid implementation is explicitly injected into the shared operation registry.
- File modification requires the existing shared permission/approval path and existing rollback/transaction path.
- Validation is mandatory before commit readiness.
- Project must not create a planner, Agent Runtime, goal system, workflow engine, validation pipeline, memory store, trace system, permission engine, Git backend, or unrestricted shell path.
- Formation remains outside Project and remains a General overlay.
- Life Plan receives only an authorized, purpose-minimized Project projection: project status, dependency, resource impact and timeline impact.
- Use shared Domain Memory Integration contracts; no implicit persistence.
- Use shared `calculate_domain_trace_identity(...)`, `DomainTraceAssembler`, trace validators, and an independently built pre-assembly trace inventory.
- Bootstrap must preserve General fallback and must not auto-register Phase 10.52 Mental Health or 10.53 Neurodivergence.
- Legacy initial Project catalogs remain backward compatible and must not be silently overwritten.
- `AT-DP-030` is frozen at **56 connected checkpoints**: 32 generic/core checkpoints + 24 software/self-development checkpoints.
- Permanent adversarial closure gate is frozen at **34 attack classes**, exactly those listed in the approved design.
- Candidate documentation may mark implementation/acceptance PASS but must keep `DP_030=REQUIRES_PHASE_INSPECTION` and `INDEPENDENT_AUDIT=PENDING` until independent audit closes the phase.
- Audit candidate is produced from committed HEAD with `git archive --format=tar.gz --output=phase-10.30-audit-v1.tar.gz HEAD`; bundle remains untracked.
- No push. No merge.

---

## File Map

### Production — create exactly these 14 files

```text
cmm/domains/project/__init__.py
cmm/domains/project/bootstrap.py
cmm/domains/project/catalog.py
cmm/domains/project/definition.py
cmm/domains/project/integration.py
cmm/domains/project/memory.py
cmm/domains/project/operations.py
cmm/domains/project/permissions.py
cmm/domains/project/presentation.py
cmm/domains/project/profile.py
cmm/domains/project/resources.py
cmm/domains/project/rules.py
cmm/domains/project/trace.py
cmm/domains/project/workflows.py
```

### Tests — create

```text
tests/domains/test_project_domain_catalog.py
tests/domains/test_project_domain_resources.py
tests/domains/test_project_domain_profile.py
tests/domains/test_project_domain_rules.py
tests/domains/test_project_domain_operations.py
tests/domains/test_project_domain_permissions.py
tests/domains/test_project_domain_workflows.py
tests/domains/test_project_domain_cross_domain.py
tests/domains/test_project_domain_memory.py
tests/domains/test_project_domain_trace.py
tests/domains/test_project_domain_presentation.py
tests/domains/test_project_domain_integration.py
tests/domains/test_project_domain_bootstrap.py
tests/domains/test_project_domain_public_api.py
tests/domains/test_project_domain_dp030_acceptance.py
tests/domains/test_project_domain_e2e.py
tests/domains/test_project_domain_self_development_e2e.py
tests/domains/test_project_domain_closure_adversarial.py
```

### Documentation — create/modify near candidate closure

```text
docs/reference/project-domain.md
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
ROADMAP.md
```

### Existing shared files to read, not copy or fork

```text
cmm/domains/life_plan/{catalog,definition,resources,profile,rules,operations,workflows,permissions,memory,trace,presentation,integration,bootstrap,__init__}.py
cmm/domains/sport/{integration,memory,trace,bootstrap}.py
cmm/domains/parenthood/{integration,memory,trace,bootstrap}.py
cmm/domains/operation_registry.py
cmm/domains/permission_registry.py
cmm/domains/permission_resolution.py
cmm/domains/profile_registry.py
cmm/domains/resource_registry.py
cmm/domains/workflow_registry.py
cmm/domains/registry.py
cmm/domains/resolver.py
cmm/domains/memory_contracts.py
cmm/domains/memory_validation.py
cmm/domains/trace.py
cmm/domains/operation_catalog.py
cmm/domains/rule_catalog.py
cmm/domains/workflow_catalog.py
cmm/domains/permission_catalog.py
cmm/development/
cmm/execution/
cmm/transformations/
cmm/validation/
cmm/agent_runtime/
kernel/
```

---

# Task 0 — Baseline Guard and Plan Freeze

**Files:**
- No production changes.
- Verify: `docs/superpowers/specs/2026-08-26-project-domain-design.md`
- Verify: this plan.

**Interfaces:**
- Consumes frozen design commit `c520cbb` and committed implementation plan `21c51bb`.
- Produces a verified clean implementation baseline and frozen acceptance counts.

- [ ] **Step 1: Verify repository state**

```bash
cd "/Users/chris/CMM OS" || exit 1

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
test "$(git rev-parse --short HEAD)" = "21c51bb"
git merge-base --is-ancestor c520cbb HEAD
test -z "$(git diff --name-only)"
test -z "$(git diff --cached --name-only)"

git status --short --branch
```

Historical untracked audit bundles may remain; do not delete, stage, rename or commit them.

- [ ] **Step 2: Read the frozen spec and current sibling implementations completely**

```bash
sed -n '1,9999p' docs/superpowers/specs/2026-08-26-project-domain-design.md
sed -n '1,9999p' cmm/domains/life_plan/catalog.py
sed -n '1,9999p' cmm/domains/life_plan/integration.py
sed -n '1,9999p' cmm/domains/life_plan/bootstrap.py
sed -n '1,9999p' cmm/domains/sport/memory.py
sed -n '1,9999p' cmm/domains/sport/trace.py
```

- [ ] **Step 3: Freeze acceptance numbers in the test skeleton before implementation**

Create `tests/domains/test_project_domain_dp030_acceptance.py` with constants only:

```python
DP_030_CHECKPOINTS = 56
DP_030_GENERIC_CHECKPOINTS = 32
DP_030_SOFTWARE_CHECKPOINTS = 24
```

Create `tests/domains/test_project_domain_closure_adversarial.py` with:

```python
PROJECT_CLOSURE_ATTACK_CLASSES = (
    "GENERIC_PROJECT_NOT_SOFTWARE_ONLY",
    "SOFTWARE_CAPABILITY_NOT_IMPLICIT",
    "FORMATION_NOT_ABSORBED",
    "UNKNOWN_PROJECT_STATUS_FAILS_CLOSED",
    "PROPOSAL_NOT_DECISION",
    "PLAN_NOT_COMPLETION",
    "MILESTONE_COMPLETION_REQUIRES_EVIDENCE",
    "MALFORMED_MILESTONE_FAILS_CLOSED",
    "DEPENDENCY_CYCLE_PRESERVED",
    "MALFORMED_DEPENDENCY_FAILS_CLOSED",
    "RESOURCE_CAPACITY_NOT_INVENTED",
    "PROGRESS_REQUIRES_EVIDENCE",
    "RAW_CROSS_DOMAIN_REJECTED",
    "FORGED_CROSS_DOMAIN_PERMISSION_REJECTED",
    "PURPOSE_MINIMIZATION_ENFORCED",
    "LEGACY_CATALOG_NOT_CANONICAL",
    "LEGACY_COLLISION_NO_SILENT_OVERWRITE",
    "OPERATION_UNAVAILABLE_WITHOUT_IMPLEMENTATION",
    "DIRECT_EXECUTION_BYPASS_REJECTED",
    "FILE_MODIFY_WITHOUT_APPROVAL_REJECTED",
    "FORGED_APPROVAL_REJECTED",
    "VALIDATION_REQUIRED_BEFORE_COMMIT_READINESS",
    "FAILED_VALIDATION_NOT_COMMIT_READY",
    "PREPARE_COMMIT_DOES_NOT_COMMIT",
    "NO_FAKE_COMMIT_REFERENCE",
    "MUTATION_REQUIRES_SHARED_ROLLBACK_PATH",
    "MEMORY_WRITE_FAILS_CLOSED",
    "MEMORY_DOES_NOT_PROMOTE_PROPOSAL",
    "MEMORY_DOES_NOT_PROMOTE_COMMIT_READINESS",
    "TRACE_IDENTITY_USES_SHARED_API",
    "TRACE_INVENTORY_INDEPENDENT",
    "TRACE_TAMPER_REJECTED",
    "ATOMIC_REGISTRATION_ROLLBACK",
    "GENERAL_FALLBACK_PRESERVED",
)


def test_frozen_attack_inventory_is_exact() -> None:
    assert len(PROJECT_CLOSURE_ATTACK_CLASSES) == 34
    assert len(set(PROJECT_CLOSURE_ATTACK_CLASSES)) == 34
```

- [ ] **Step 4: Run the frozen-count tests**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_dp030_acceptance.py \
  tests/domains/test_project_domain_closure_adversarial.py
```

Expected: the attack inventory test passes; the acceptance file contains no connected acceptance test yet.

- [ ] **Step 5: Commit the test-contract freeze**

```bash
git add -- \
  tests/domains/test_project_domain_dp030_acceptance.py \
  tests/domains/test_project_domain_closure_adversarial.py

git diff --cached --check
git commit -m "test(project): freeze phase 10.30 acceptance contracts"
```

---

# Task 1 — Canonical Catalog and Domain Definition

**Files:**
- Create: `cmm/domains/project/catalog.py`
- Create: `cmm/domains/project/definition.py`
- Create: `tests/domains/test_project_domain_catalog.py`

**Interfaces:**
- Produces:
  - `PROJECT_DOMAIN_ID = "domain:project"`
  - `PROJECT_DOMAIN_VERSION = "1.0.0"`
  - `PROJECT_MANIFEST_ID = "manifest:project:1.0.0"`
  - `CANONICAL_PROJECT_ENTITY_TYPES`
  - `CANONICAL_PROJECT_ENTITY_IDS`
  - `CANONICAL_PROJECT_RESOURCE_KINDS`
  - `CANONICAL_PROJECT_RESOURCE_IDS`
  - `CANONICAL_PROJECT_RULE_IDS`
  - `CANONICAL_PROJECT_OPERATION_IDS`
  - `CANONICAL_PROJECT_WORKFLOW_IDS`
  - `build_project_domain_definition() -> DomainDefinition`
- Consumes shared `DomainDefinition`, `DomainCapability`, `DomainMetadata`, `DomainKind.PROJECT`.

- [ ] **Step 1: Write RED exact catalog test**

`tests/domains/test_project_domain_catalog.py` must assert the exact frozen inventory, including:

```python
assert PROJECT_DOMAIN_ID == "domain:project"
assert PROJECT_DOMAIN_VERSION == "1.0.0"
assert len(CANONICAL_PROJECT_ENTITY_TYPES) == 27
assert len(CANONICAL_PROJECT_RESOURCE_KINDS) == 22
assert len(CANONICAL_PROJECT_RULE_IDS) == 18
assert len(CANONICAL_PROJECT_OPERATION_IDS) == 20
assert len(CANONICAL_PROJECT_WORKFLOW_IDS) == 12
assert len(set(CANONICAL_PROJECT_OPERATION_IDS)) == 20
assert "project.review_change" in CANONICAL_PROJECT_OPERATION_IDS
assert "project.prepare_change_review" not in CANONICAL_PROJECT_OPERATION_IDS
```

Also assert the exact ordered tuples from the spec, not set-only equality.

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_catalog.py
```

Expected: import failure because `cmm.domains.project` does not exist.

- [ ] **Step 3: Implement `catalog.py` as the sole canonical ID source**

Use this naming pattern:

```python
PROJECT_DOMAIN_ID = "domain:project"
PROJECT_DOMAIN_VERSION = "1.0.0"
PROJECT_MANIFEST_ID = "manifest:project:1.0.0"
PROJECT_PROFILE_NAME = "ProjectProfile"

CANONICAL_PROJECT_ENTITY_TYPES: tuple[str, ...] = (...)
CANONICAL_PROJECT_ENTITY_IDS: tuple[str, ...] = tuple(
    f"project.entity.{name}" for name in CANONICAL_PROJECT_ENTITY_TYPES
)
CANONICAL_PROJECT_RESOURCE_KINDS: tuple[str, ...] = (...)
CANONICAL_PROJECT_RESOURCE_IDS: tuple[str, ...] = tuple(
    f"project.resource.{kind}" for kind in CANONICAL_PROJECT_RESOURCE_KINDS
)
CANONICAL_PROJECT_RULE_IDS: tuple[str, ...] = (...)
CANONICAL_PROJECT_OPERATION_IDS: tuple[str, ...] = (...)
CANONICAL_PROJECT_WORKFLOW_IDS: tuple[str, ...] = (...)
```

Exact entity types:

```text
project objective milestone work_item deliverable project_resource constraint risk decision status_change project_event repository module package file class method function contract dependency test validation_result issue technical_debt architecture_decision workflow release
```

Exact resource kinds:

```text
project_brief project_plan milestone_record work_item_record dependency_record resource_record status_report decision_record risk_record project_timeline source_code project_file documentation test_result validation_result git_history issue roadmap architecture_document commit pull_request memory_entry
```

Exact rule IDs:

```text
project.scope_consistency
project.milestone_consistency
project.dependency_consistency
project.status_transition
project.resource_constraint
project.decision_state
project.temporal_validity
project.progress_evidence
project.architecture_contract
project.code_documentation_consistency
project.validation_required
project.technical_debt
project.dead_code
project.public_api_change
project.backward_compatibility
project.dependency_boundary
project.test_coverage_impact
project.semantic_transformation
```

Exact operation IDs:

```text
project.create_project_overview
project.review_status
project.plan_milestones
project.review_dependencies
project.review_resources
project.review_risks
project.generate_progress_summary
project.analyse_architecture
project.detect_technical_debt
project.compare_code_documentation
project.detect_dead_code
project.detect_duplication
project.generate_adr
project.create_implementation_plan
project.modify_code
project.run_validation
project.prepare_commit
project.review_change
project.update_documentation
project.generate_release_notes
```

Exact workflow IDs:

```text
project.project_setup
project.status_review
project.milestone_dependency_review
project.periodic_project_review
project.architecture_review
project.feature_implementation
project.bug_resolution
project.technical_debt_review
project.documentation_synchronisation
project.refactor
project.release_preparation
project.self_development
```

- [ ] **Step 4: Implement `build_project_domain_definition()`**

Use only catalog constants and shared contracts. Required shape:

```python
def build_project_domain_definition() -> DomainDefinition:
    return DomainDefinition(
        id=PROJECT_DOMAIN_ID,
        name="project",
        display_name="Project",
        version=PROJECT_DOMAIN_VERSION,
        kind=DomainKind.PROJECT,
        description=(
            "Generic project management with conditional software-project "
            "analysis, development, validation and self-development capability."
        ),
        manifest_id=PROJECT_MANIFEST_ID,
        reasoning_profile=PROJECT_PROFILE_NAME,
        resources=CANONICAL_PROJECT_RESOURCE_IDS,
        rules=CANONICAL_PROJECT_RULE_IDS,
        operations=CANONICAL_PROJECT_OPERATION_IDS,
        workflows=CANONICAL_PROJECT_WORKFLOW_IDS,
        permissions=("domain-permission:project:1.0.0",),
        dependencies=(),
        optional_dependencies=(),
        conflicts=(),
        capabilities=(...),
        enabled=True,
        metadata=DomainMetadata(...),
    )
```

Use the exact actual constructor field names from `cmm/domains/contracts.py`; do not add a compatibility shim if field names differ.

Capabilities must cover generic project management and conditional software-project specialization without creating a second domain.

- [ ] **Step 5: GREEN + static checks**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_catalog.py
.venv/bin/python -m compileall -q cmm/domains/project
.venv/bin/ruff check cmm/domains/project tests/domains/test_project_domain_catalog.py
git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/project/catalog.py \
  cmm/domains/project/definition.py \
  tests/domains/test_project_domain_catalog.py

git diff --cached --check
git commit -m "feat(project): define canonical domain catalog"
```

---

# Task 2 — Resources and Generic Project State Vocabulary

**Files:**
- Create: `cmm/domains/project/resources.py`
- Create: `tests/domains/test_project_domain_resources.py`

**Interfaces:**
- Produces:
  - `build_project_resource_definitions() -> tuple[DomainResourceDefinition, ...]`
  - `PROJECT_STATUS_VALUES`
  - `PROJECT_DECISION_STATE_VALUES`
  - `validate_project_status(value: str) -> str`
- Consumes `CANONICAL_PROJECT_RESOURCE_IDS`, shared resource/provenance/sensitivity contracts.

- [ ] **Step 1: RED exact resources**

Test all 22 definitions are deterministic, unique, `domain:project`, and match catalog IDs exactly.

```python
resources = build_project_resource_definitions()
assert tuple(r.id for r in resources) == CANONICAL_PROJECT_RESOURCE_IDS
assert all(str(r.domain_id) == "domain:project" for r in resources)
```

Use the actual field name (`id`, `resource_id`, etc.) from the current shared contract.

- [ ] **Step 2: RED generic/software separation**

Assert generic resources do not require software context:

```python
GENERIC_KINDS = {
    "project_brief", "project_plan", "milestone_record", "work_item_record",
    "dependency_record", "resource_record", "status_report", "decision_record",
    "risk_record", "project_timeline",
}
SOFTWARE_KINDS = set(CANONICAL_PROJECT_RESOURCE_KINDS) - GENERIC_KINDS
assert "source_code" in SOFTWARE_KINDS
assert "project_brief" not in SOFTWARE_KINDS
```

- [ ] **Step 3: RED status fail-closed vocabulary**

Freeze generic status values:

```text
planned active blocked paused completed failed cancelled
```

And decision-state values:

```text
option proposal decided approved applied rejected deferred cancelled
```

Test:

```python
assert validate_project_status("active") == "active"
with pytest.raises(ValueError):
    validate_project_status("mostly_done")
```

No fuzzy normalization.

- [ ] **Step 4: Implement definitions**

Follow shared `DomainResourceDefinition` construction. Generic Project resources should default to ordinary internal/confidential sensitivity appropriate to the current shared enum; software resources such as source code/Git history must not be made remotely exportable by resource definition alone.

Do not add storage access or loaders here.

- [ ] **Step 5: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_resources.py
.venv/bin/ruff check cmm/domains/project/resources.py tests/domains/test_project_domain_resources.py
git diff --check

git add -- cmm/domains/project/resources.py tests/domains/test_project_domain_resources.py
git diff --cached --check
git commit -m "feat(project): add canonical project resources"
```

---

# Task 3 — ProjectProfile and Conditional Software Capability

**Files:**
- Create: `cmm/domains/project/profile.py`
- Create: `tests/domains/test_project_domain_profile.py`

**Interfaces:**
- Produces:
  - `build_project_profile() -> DomainProfileDefinition`
  - `project_software_capability_active(...) -> bool`
  - `GENERIC_PROJECT_RULE_IDS`
  - `SOFTWARE_PROJECT_RULE_IDS`
- Consumes shared profile contracts and canonical rule IDs.

- [ ] **Step 1: RED single profile identity**

```python
profile = build_project_profile()
assert profile.profile_name == "ProjectProfile"  # use current actual field name
assert str(profile.domain_id) == "domain:project"
```

Assert no `SoftwareProjectProfile` exists or is registered.

- [ ] **Step 2: RED generic/software rule layers**

Freeze:

```python
GENERIC_PROJECT_RULE_IDS = CANONICAL_PROJECT_RULE_IDS[:8]
SOFTWARE_PROJECT_RULE_IDS = CANONICAL_PROJECT_RULE_IDS[8:]
assert len(GENERIC_PROJECT_RULE_IDS) == 8
assert len(SOFTWARE_PROJECT_RULE_IDS) == 10
```

Profile required rules must contain the generic layer. Software rules remain optional/conditional using the actual shared profile fields.

- [ ] **Step 3: RED activation matrix**

`project_software_capability_active(...)` must return true only for grounded signals. Test at least:

```text
TRUE: explicit workflow project.self_development
TRUE: explicit operation project.modify_code
TRUE: source resource project.resource.source_code
TRUE: repository-backed goal metadata owned by trusted runtime fixture
FALSE: primary domain only
FALSE: milestone/dependency/deadline only
FALSE: text containing the word project
FALSE: generic project_brief only
```

Signature should accept explicit structured values rather than free text, for example:

```python
def project_software_capability_active(
    *,
    workflow_id: str | None = None,
    operation_id: str | None = None,
    resource_ids: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    repository_backed: bool = False,
) -> bool:
    ...
```

Caller-controlled `repository_backed=True` is only a routing signal; it is not permission or execution trust evidence.

- [ ] **Step 4: Implement profile using existing shared policies**

Preserve high traceability, provenance visibility, bounded questions, no automatic external action, proposal-only memory behavior, and no software activation by domain alone.

- [ ] **Step 5: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_profile.py
.venv/bin/ruff check cmm/domains/project/profile.py tests/domains/test_project_domain_profile.py
git diff --check

git add -- cmm/domains/project/profile.py tests/domains/test_project_domain_profile.py
git diff --cached --check
git commit -m "feat(project): add conditional project profile"
```

---

# Task 4 — Generic Project Rules

**Files:**
- Create: `cmm/domains/project/rules.py`
- Create: `tests/domains/test_project_domain_rules.py`

**Interfaces:**
- Produces eight pure evaluators plus `build_project_rules()`.
- Required evaluator names:
  - `evaluate_project_scope_consistency(...)`
  - `evaluate_milestone_consistency(...)`
  - `evaluate_dependency_consistency(...)`
  - `evaluate_project_status_transition(...)`
  - `evaluate_project_resource_constraints(...)`
  - `evaluate_project_decision_state(...)`
  - `evaluate_project_temporal_validity(...)`
  - `evaluate_project_progress_evidence(...)`
- Consumes status validator and shared `DomainReasoningRule` contracts.

- [ ] **Step 1: RED scope, status and decision distinctions**

Tests must prove:

```text
proposal != decision
plan != completion
approved != applied
blocked != failed
paused != cancelled
```

Example:

```python
result = evaluate_project_decision_state(
    current_state="proposal",
    proposed_state="applied",
    approval_evidence=None,
    execution_evidence=None,
)
assert result["allowed"] is False
assert result["reason"] == "missing_required_evidence"
```

- [ ] **Step 2: RED milestone evidence**

A completed milestone requires evidence/reference basis. Reject malformed milestones and duplicate IDs.

```python
result = evaluate_milestone_consistency([
    {"id": "m1", "status": "completed", "evidence": []},
])
assert result["valid"] is False
assert "m1" in result["unsupported_completed_milestones"]
```

- [ ] **Step 3: RED dependency cycles and malformed edges**

Use generic dependencies independent of Python imports/modules:

```python
dependencies = [
    {"source": "milestone:a", "target": "milestone:b"},
    {"source": "milestone:b", "target": "milestone:a"},
]
result = evaluate_dependency_consistency(dependencies)
assert result["valid"] is False
assert result["cycles"]
```

Do not silently break the cycle.

- [ ] **Step 4: RED resources and progress**

Missing capacity remains unknown, not invented. Progress requires authoritative status/completed deliverable/validated outcome evidence.

- [ ] **Step 5: RED temporal validity**

Naive or malformed dates are rejected/marked invalid according to current shared temporal conventions. Missing date remains unknown and must not be invented.

- [ ] **Step 6: Implement eight deterministic evaluators**

Return structured dicts with stable keys and explicit `valid`, `status`, `unknowns`, `findings`, `blockers` fields as applicable. No storage, network, model, filesystem or clock side effects; inject/accept timestamps where needed.

- [ ] **Step 7: Implement eight `DomainReasoningRule` wrappers**

Use exact canonical IDs and existing shared rule definition/result contracts. Wrappers delegate to the pure evaluators and preserve provenance references from context metadata.

- [ ] **Step 8: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_rules.py
.venv/bin/ruff check cmm/domains/project/rules.py tests/domains/test_project_domain_rules.py
git diff --check

git add -- cmm/domains/project/rules.py tests/domains/test_project_domain_rules.py
git diff --cached --check
git commit -m "feat(project): implement generic project reasoning"
```

---

# Task 5 — Software Rules Without a Second Analysis Engine

**Files:**
- Modify: `cmm/domains/project/rules.py`
- Modify: `tests/domains/test_project_domain_rules.py`

**Interfaces:**
- Produces 10 software `DomainReasoningRule` implementations inside `build_project_rules()`.
- Consumes `project_software_capability_active(...)` and shared validation/cognitive evidence only.

- [ ] **Step 1: RED software rules are not implicitly active**

For each of the 10 software rules, evaluate a generic Project context with no software signal and assert a not-applicable/no-op structured result, not a technical finding.

- [ ] **Step 2: RED explicit software activation**

With a canonical software signal, assert software rules may evaluate supplied repository/validation metadata.

- [ ] **Step 3: RED no duplicate engines**

Static test production source:

```python
source = Path("cmm/domains/project/rules.py").read_text()
for forbidden in (
    "subprocess.run", "os.system", "shell=True",
    "PythonIndex(", "TechnicalMemory.for_project(", "ExecutionPipeline(",
):
    assert forbidden not in source
```

The rule layer may interpret references/results but must not run repository analysis or validation itself.

- [ ] **Step 4: Implement thin software rule wrappers**

Rules consume already available structured evidence and produce findings for:

```text
architecture contract
code/documentation consistency
validation required
technical debt
dead code
public API change
backward compatibility
dependency boundary
test coverage impact
semantic transformation requirement
```

When required evidence is absent, return unknown/not-applicable or a gap; do not invent analysis.

- [ ] **Step 5: Verify exact 18-rule inventory**

```python
rules = build_project_rules()
assert tuple(rule.definition.id for rule in rules) == CANONICAL_PROJECT_RULE_IDS
```

- [ ] **Step 6: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_rules.py
.venv/bin/ruff check cmm/domains/project/rules.py tests/domains/test_project_domain_rules.py
git diff --check

git add -- cmm/domains/project/rules.py tests/domains/test_project_domain_rules.py
git diff --cached --check
git commit -m "feat(project): add conditional software reasoning"
```

---

# Task 6 — Canonical Operations and Fail-Closed Availability

**Files:**
- Create: `cmm/domains/project/operations.py`
- Create: `tests/domains/test_project_domain_operations.py`

**Interfaces:**
- Produces:
  - `build_project_operation_definitions() -> tuple[DomainOperationDefinition, ...]`
  - pure generic result builders:
    - `create_project_overview_result(...)`
    - `review_project_status_result(...)`
    - `plan_project_milestones_result(...)`
    - `review_project_dependencies_result(...)`
    - `review_project_resources_result(...)`
    - `review_project_risks_result(...)`
    - `generate_project_progress_summary_result(...)`
  - `build_prepare_commit_readiness_result(...)`
- Consumes pure Project evaluators; operation implementations remain registry-injected.

- [ ] **Step 1: RED exact 20 operation definitions**

```python
ops = build_project_operation_definitions()
assert tuple(op.operation_id for op in ops) == CANONICAL_PROJECT_OPERATION_IDS
assert len(ops) == 20
```

Preserve historical types where already defined:

```text
project.analyse_architecture -> ANALYSIS
project.create_implementation_plan -> PLANNING
project.run_validation -> ANALYSIS
```

Use shared `DomainOperationType` for the remaining operations. `project.modify_code` must require file-modification capability and approval under policy; do not invent a new operation type.

- [ ] **Step 2: RED all operations unavailable without implementation**

Register definitions with `implementation=None` into a clean `InMemoryDomainOperationRegistry` and assert active availability is `UNAVAILABLE` for all 20.

- [ ] **Step 3: RED proposal semantics for generic result builders**

Generic result builders return structured analysis/proposals and perform no persistence or external side effect. Planning outputs include `is_proposal=True` and never imply completion.

- [ ] **Step 4: RED `prepare_commit` semantics**

Implement test cases:

```python
failed = build_prepare_commit_readiness_result(
    change_id="change:1",
    validation_passed=False,
    validation_reference="validation:1",
    commit_gate_allowed=False,
    approval_reference=None,
    authoritative_commit_reference=None,
)
assert failed["ready_for_approved_commit"] is False
assert failed["committed"] is False

ready = build_prepare_commit_readiness_result(
    change_id="change:1",
    validation_passed=True,
    validation_reference="validation:1",
    commit_gate_allowed=True,
    approval_reference="approval:1",
    authoritative_commit_reference=None,
)
assert ready["ready_for_approved_commit"] is True
assert ready["committed"] is False
assert "commit_hash" not in ready
```

If current shared commit-gate evidence has a typed object, consume that type instead of booleans in production API; the test may construct the real object.

- [ ] **Step 5: RED no direct execution**

Static test forbids `subprocess`, `git commit`, shell strings, direct `FilesystemExecutor`, direct `GitExecutor` construction, and direct `SemanticRuntime` construction in `operations.py`.

- [ ] **Step 6: Implement definitions and pure result builders**

Operation definitions declare required resources/permissions/output schemas using existing constructors. Do not auto-bind implementations.

- [ ] **Step 7: GREEN + legacy independence**

Also run historical operation catalog tests:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_operations.py \
  tests/domains/test_domain_operation_catalog.py \
  tests/domains/test_domain_operation_registry.py
```

- [ ] **Step 8: Commit**

```bash
git add -- cmm/domains/project/operations.py tests/domains/test_project_domain_operations.py
git diff --cached --check
git commit -m "feat(project): declare controlled project operations"
```

---

# Task 7 — Permission Policy and Approval Boundary

**Files:**
- Create: `cmm/domains/project/permissions.py`
- Create: `tests/domains/test_project_domain_permissions.py`

**Interfaces:**
- Produces `build_project_permission_policy() -> DomainPermissionPolicy`.
- Consumes shared permission enum/resolver/gate; no new permission enum.

- [ ] **Step 1: RED canonical identity and low autonomy**

```python
policy = build_project_permission_policy()
assert policy.policy_id == "domain-permission:project:1.0.0"
assert policy.domain_id == "domain:project"
assert policy.autonomy_limits.maximum_autonomy_level == 1
```

Use actual field/property types.

- [ ] **Step 2: RED baseline and prohibited capabilities**

Baseline eligibility must cover shared equivalents of:

```text
RESOURCE_READ MEMORY_READ OPERATION_EXECUTE WORKFLOW_EXECUTE FILE_MODIFY
```

`FILE_MODIFY` must be in approval-required capabilities.

Prohibit by default:

```text
IRREVERSIBLE_CHANGE PERMISSION_MODIFY COMMUNICATION_EXTERNAL PUBLICATION
FINANCIAL_ACTION FINANCIAL_SPEND SEARCH_EXTERNAL MODEL_EXTERNAL KNOWLEDGE_DELETE
```

Only use enum members that exist. If a listed semantic maps to a differently named existing capability, use that existing capability and record the mapping in `docs/reference/project-domain.md` later; do not add an enum.

- [ ] **Step 3: RED real permission resolution**

A domain policy declaration is not concrete authorization. Build a `DomainPermissionRequest` for `FILE_MODIFY` and prove resolver/gate returns approval-required or deny without canonical approval evidence.

- [ ] **Step 4: RED forged approval**

Reject caller-only:

```text
approval_id
approved=True
raw mapping
lookalike object
```

Use current service-owned approval validation path.

- [ ] **Step 5: GREEN + shared regression**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_permissions.py \
  tests/domains/test_domain_permission_adapters.py \
  tests/domains/test_domain_permission_resolution.py \
  tests/agent_runtime/test_domain_permission_contracts.py
```

- [ ] **Step 6: Commit**

```bash
git add -- cmm/domains/project/permissions.py tests/domains/test_project_domain_permissions.py
git diff --cached --check
git commit -m "feat(project): enforce supervised project permissions"
```

---

# Task 8 — Generic and Software Workflow Definitions

**Files:**
- Create: `cmm/domains/project/workflows.py`
- Create: `tests/domains/test_project_domain_workflows.py`

**Interfaces:**
- Produces `build_project_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]`.
- Consumes current shared workflow node types and canonical operation IDs.

- [ ] **Step 1: RED exact 12 workflow IDs**

```python
workflows = build_project_workflow_definitions()
assert tuple(w.workflow_id for w in workflows) == CANONICAL_PROJECT_WORKFLOW_IDS
```

- [ ] **Step 2: RED generic workflows contain no software-only node**

For the first four workflows, reject nodes that require source code, repository mutation, Git, validation or software operations.

- [ ] **Step 3: RED software workflows require software capability**

Each of the eight software workflows must either carry existing capability metadata or be guarded by a helper that checks `project_software_capability_active(...)` before execution/selection. A generic Project context cannot start `project.self_development` implicitly.

- [ ] **Step 4: RED self-development flow ordering**

Assert semantic order includes the current shared equivalents of:

```text
observe/load repository
reason/apply ProjectProfile
plan
permission/approval gate
controlled operation execution
validation
outcome review
change review
prepare commit readiness
memory proposal
complete
```

No workflow node executes `git commit` directly.

- [ ] **Step 5: Implement using shared node types only**

Do not add a workflow engine or a Project-only node class.

- [ ] **Step 6: GREEN + workflow shared regression**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_workflows.py \
  tests/domains/test_domain_workflow_registry.py 2>/dev/null || \
.venv/bin/python -m pytest -q tests/domains/test_project_domain_workflows.py
```

If the shared registry test filename differs, locate it with `git ls-files tests/domains | grep workflow_registry` and run the real file; do not create an alias test.

- [ ] **Step 7: Commit**

```bash
git add -- cmm/domains/project/workflows.py tests/domains/test_project_domain_workflows.py
git diff --cached --check
git commit -m "feat(project): add generic and software workflows"
```

---

# Task 9 — Life Plan Projection and Cross-Domain Trust Boundary

**Files:**
- Modify: `cmm/domains/project/rules.py`
- Create: `tests/domains/test_project_domain_cross_domain.py`
- Do not modify Life Plan unless a real generic shared-contract defect is proven.

**Interfaces:**
- Produces:
  - `build_project_life_plan_projection(...) -> Mapping[str, Any]`
  - `authorize_project_life_plan_contribution(...)` using the current shared permission gate/resolver pattern.
- Consumes real `CrossDomainPermissionRequest`/permission evidence and Life Plan's existing `evaluate_cross_domain_impact(...)` trust boundary.

- [ ] **Step 1: RED exact purpose-minimized fields**

Allowed Project-to-Life-Plan projection fields are limited to:

```text
source_domain
project_status_impact
dependency
resource_impact
timeline_impact
source_reference
provenance
effective_from
effective_until
```

Not all fields must be present; anything else must be rejected or dropped before authorized artifact creation.

- [ ] **Step 2: RED raw Project internals rejected**

Reject projection payloads containing:

```text
source_code repository_contents validation_logs unrestricted_issue_text commit_history operation_authority
```

- [ ] **Step 3: RED real authorization path**

Construct the real shared permission request from `source_domain="domain:project"` to `target_domain="domain:life-plan"`. Presence of Life Plan, a raw decision ID, `is_authorized=True`, or a forged `PermissionGateResult` is not enough.

- [ ] **Step 4: RED purpose and context mismatch**

Reject mismatched target, session/actor/purpose, expired temporal authorization, or projection source domain mismatch where current shared contracts expose those checks.

- [ ] **Step 5: GREEN minimal adapter**

Reuse the same gate-owned trust discipline already hardened in Life Plan. Do not create a Project-specific cross-domain engine.

- [ ] **Step 6: Run Project + Life Plan security regressions**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_safety.py
```

- [ ] **Step 7: Commit**

```bash
git add -- cmm/domains/project/rules.py tests/domains/test_project_domain_cross_domain.py
git diff --cached --check
git commit -m "feat(project): enforce life-plan projection boundary"
```

---

# Task 10 — Shared Memory View, Proposal and Binding

**Files:**
- Create: `cmm/domains/project/memory.py`
- Create: `tests/domains/test_project_domain_memory.py`

**Interfaces:**
- Produces:
  - `build_project_memory_view_request(...)`
  - `build_project_memory_view(...)`
  - `build_project_memory_proposal(...)`
  - `build_project_memory_binding(...)`
  - `validate_project_memory_binding(...)`
- Consumes current shared memory contracts and validator.

- [ ] **Step 1: Read sibling memory files completely**

```bash
sed -n '1,9999p' cmm/domains/life_plan/memory.py
sed -n '1,9999p' cmm/domains/sport/memory.py
sed -n '1,9999p' cmm/domains/parenthood/memory.py
sed -n '1,9999p' cmm/domains/memory_contracts.py
sed -n '1,9999p' cmm/domains/memory_validation.py
```

- [ ] **Step 2: RED proposal-only memory behavior**

Prove no store write occurs when building a proposal/binding.

- [ ] **Step 3: RED forbidden promotion states**

These cannot become durable confirmed Project state merely because reasoning mentioned them:

```text
proposed milestone
proposed deadline
proposed status change
unapproved decision
inferred progress
unvalidated technical finding
planned code change
commit readiness
```

- [ ] **Step 4: RED authoritative commit distinction**

A memory proposal may describe `ready_for_approved_commit=True` but must not write `committed=True` without an authoritative commit reference produced outside Project.

- [ ] **Step 5: RED binding integrity**

Reject domain/view/proposal/trace mismatch, missing confirmation where required, invalid permission evidence, affected-reference mismatch and unverified cross-domain contribution.

- [ ] **Step 6: Implement by adapting sibling shared-contract wrappers**

No `ProjectMemoryStore` or persistent repository.

- [ ] **Step 7: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_memory.py
.venv/bin/ruff check cmm/domains/project/memory.py tests/domains/test_project_domain_memory.py
git diff --check

git add -- cmm/domains/project/memory.py tests/domains/test_project_domain_memory.py
git diff --cached --check
git commit -m "feat(project): bind controlled project memory"
```

---

# Task 11 — Shared Domain Trace and Independent Inventory

**Files:**
- Create: `cmm/domains/project/trace.py`
- Create: `tests/domains/test_project_domain_trace.py`

**Interfaces:**
- Produces:
  - `build_project_trace_reference(...)`
  - `build_project_trace_contribution(...)`
  - `build_supporting_project_trace_contribution(...)`
  - `assemble_project_trace(...)`
  - `validate_project_trace(...)`
- Consumes shared `calculate_domain_trace_identity(...)`, `DomainTraceAssembler`, shared trace contracts/validator.

- [ ] **Step 1: RED shared trace identity API is used**

Static + runtime test must prove no Project-local identity algorithm and no `domain-trace:probe` appears in production Project code.

- [ ] **Step 2: RED generic/software capability evidence**

Trace must record whether software capability was active and reference the grounded signal/result that justified it; a generic Project trace must not imply software activation.

- [ ] **Step 3: RED independent pre-assembly inventory**

Build expected inventory directly from runtime artifacts before calling `assemble_project_trace(...)`.

Forbidden test pattern:

```python
trace = assemble_project_trace(...)
expected = inventory_from(trace)
validate_project_trace(trace, expected)
```

Correct pattern:

```python
inventory = inventory_from_runtime_artifacts(...)
trace = assemble_project_trace(...)
report = validate_project_trace(trace, inventory)
```

- [ ] **Step 4: RED tamper cases**

Reject orphan/mismatched references, wrong domain ownership, missing permission/approval references, missing validation reference when commit readiness is claimed, fake commit reference and post-inventory trace mutation.

- [ ] **Step 5: Implement using current sibling trace pattern**

No duplicate `DomainTrace` dataclass.

- [ ] **Step 6: GREEN + trace regression**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_trace.py \
  tests/domains/test_life_plan_domain_trace.py
```

- [ ] **Step 7: Commit**

```bash
git add -- cmm/domains/project/trace.py tests/domains/test_project_domain_trace.py
git diff --cached --check
git commit -m "feat(project): add shared provenance trace"
```

---

# Task 12 — Presentation Fidelity

**Files:**
- Create: `cmm/domains/project/presentation.py`
- Create: `tests/domains/test_project_domain_presentation.py`

**Interfaces:**
- Produces:
  - `build_project_presentation_policy()`
  - `present_project_result(...)`
- Consumes shared Domain Presentation contracts; presentation is reference/structure only where current contract requires it.

- [ ] **Step 1: RED generic Project output sections**

Preserve objective/scope, status, milestones, dependencies, resource constraints, risks, decisions, blockers, progress and next review.

- [ ] **Step 2: RED software conditional sections**

Architecture/validation/technical-debt/change-review sections appear only when software capability is active and evidence exists.

- [ ] **Step 3: RED epistemic fidelity**

Presentation must not turn proposal into decision, plan into completion, commit readiness into commit, or hide blockers/failed validation/uncertainty/approval requirements/provenance.

- [ ] **Step 4: Implement pure presentation plan/result wrapper**

No model call or UI rendering engine inside Project.

- [ ] **Step 5: GREEN + commit**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_presentation.py
.venv/bin/ruff check cmm/domains/project/presentation.py tests/domains/test_project_domain_presentation.py
git diff --check

git add -- cmm/domains/project/presentation.py tests/domains/test_project_domain_presentation.py
git diff --cached --check
git commit -m "feat(project): preserve project presentation semantics"
```

---

# Task 13 — Validation-First Atomic Registration and Legacy Collision Safety

**Files:**
- Create: `cmm/domains/project/integration.py`
- Create: `tests/domains/test_project_domain_integration.py`

**Interfaces:**
- Produces:
  - `ProjectDomainIntegrationResult`
  - `register_project_domain(...)`
- Consumes passed shared registries and optional `operation_implementations: dict[str, Any] | None` only.

- [ ] **Step 1: Read current atomic integration implementations completely**

```bash
sed -n '1,9999p' cmm/domains/life_plan/integration.py
sed -n '1,9999p' cmm/domains/sport/integration.py
sed -n '1,9999p' cmm/domains/parenthood/integration.py
```

- [ ] **Step 2: RED complete canonical registration**

Assert registration installs exactly:

```text
1 definition
1 ProjectProfile
22 resources
18 rules
20 operations
12 workflows
1 permission policy
```

- [ ] **Step 3: RED provided implementation validation**

Unknown operation implementation IDs must fail before mutation. Each supplied implementation must pass `validate_domain_operation_implementation(...)` against the matching canonical definition.

- [ ] **Step 4: RED legacy catalog collision**

Preload a registry with a legacy same-ID/same-version incompatible definition such as `project.analyse_architecture`. Calling `register_project_domain(...)` must fail before/safely during registration and restore all registries exactly; it must not unregister or replace the legacy entry.

- [ ] **Step 5: RED historical catalogs remain independently buildable**

Run existing tests for:

```text
cmm/domains/operation_catalog.py
cmm/domains/rule_catalog.py
cmm/domains/workflow_catalog.py
cmm/domains/permission_catalog.py
```

No legacy ID is deleted merely to permit canonical bootstrap.

- [ ] **Step 6: RED forced mid-registration failure**

Fault-inject failure after at least one registry mutated and prove exact snapshot parity for domain/profile/resource/rule/operation/workflow/permission registries.

- [ ] **Step 7: RED rollback failure visibility**

Preserve sibling explicit rollback failure behavior; do not swallow an incomplete rollback.

- [ ] **Step 8: Implement validation-first + snapshots + rollback**

Do not instantiate replacement registries inside `register_project_domain(...)`.

- [ ] **Step 9: GREEN + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_integration.py \
  tests/domains/test_domain_operation_catalog.py

git diff --check

git add -- cmm/domains/project/integration.py tests/domains/test_project_domain_integration.py
git diff --cached --check
git commit -m "feat(project): register project domain atomically"
```

---

# Task 14 — Canonical Bootstrap and Public API

**Files:**
- Create: `cmm/domains/project/bootstrap.py`
- Create: `cmm/domains/project/__init__.py`
- Create: `tests/domains/test_project_domain_bootstrap.py`
- Create: `tests/domains/test_project_domain_public_api.py`

**Interfaces:**
- Produces:
  - `PROJECT_BOOTSTRAP_NAME = "ProjectDomainBootstrap"`
  - `ProjectDomainBootstrap`
  - `build_standard_project_domain_bootstrap(...)`
  - intentional public exports.
- Consumes `build_standard_life_plan_domain_bootstrap()` and `register_project_domain(...)`.

- [ ] **Step 1: RED bootstrap extends 10.29 chain, not General-only**

Expected conceptual code:

```python
def build_standard_project_domain_bootstrap(
    *, operation_implementations: dict[str, Any] | None = None
) -> ProjectDomainBootstrap:
    prior = build_standard_life_plan_domain_bootstrap()
    register_project_domain(
        domain_registry=prior.domain_registry,
        profile_registry=prior.profile_registry,
        resource_registry=prior.resource_registry,
        rule_registry=prior.rule_registry,
        operation_registry=prior.operation_registry,
        workflow_registry=prior.workflow_registry,
        permission_registry=prior.permission_registry,
        operation_implementations=operation_implementations,
    )
    return ProjectDomainBootstrap(...same registry objects..., resolver=...)
```

Use the actual current bootstrap constructor fields.

- [ ] **Step 2: RED chain identity and fallback**

Assert `domain:general`, previously completed domains needed by the 10.29 bootstrap chain, `domain:life-plan`, and `domain:project` are present as expected by the actual standard chain; assert `domain:mental-health` and `domain:neurodivergence` are absent.

Assert resolver fallback remains `domain:general`.

- [ ] **Step 3: RED operation availability**

Default bootstrap has all 20 Project operation definitions but no Project implementation; all remain unavailable.

- [ ] **Step 4: RED fresh import purity**

```bash
.venv/bin/python - <<'PY'
import cmm.domains.project
print("fresh_import=OK")
PY
```

Import performs no registration, filesystem write, repository analysis, workflow execution, network call or user-data read.

- [ ] **Step 5: RED exact 14-module package**

```python
files = sorted(p.name for p in Path("cmm/domains/project").glob("*.py"))
assert files == sorted([
    "__init__.py", "bootstrap.py", "catalog.py", "definition.py",
    "integration.py", "memory.py", "operations.py", "permissions.py",
    "presentation.py", "profile.py", "resources.py", "rules.py",
    "trace.py", "workflows.py",
])
```

- [ ] **Step 6: GREEN public API**

Export intentional constants/factories/evaluators only. Do not export internal trust-token constructors or snapshot mutation helpers.

- [ ] **Step 7: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_bootstrap.py \
  tests/domains/test_project_domain_public_api.py
.venv/bin/python -m compileall -q cmm/domains/project
.venv/bin/ruff check cmm/domains/project tests/domains/test_project_domain_*.py
git diff --check

git add -- \
  cmm/domains/project/bootstrap.py \
  cmm/domains/project/__init__.py \
  tests/domains/test_project_domain_bootstrap.py \
  tests/domains/test_project_domain_public_api.py

git diff --cached --check
git commit -m "feat(project): expose standard project bootstrap"
```

---

# Task 15 — Generic Project Domain E2E

**Files:**
- Create: `tests/domains/test_project_domain_e2e.py`
- Modify production only if RED exposes a real missing Project behavior.

**Interfaces:**
- Consumes canonical bootstrap/profile/rules/workflow/cross-domain/memory/trace surfaces.
- Produces a connected generic Project lifecycle proving `DP-030` without software semantics.

- [ ] **Step 1: Build deterministic runtime fixtures**

Use fixed timezone-aware clock and ID factory following the Life Plan acceptance pattern. Do not use wall-clock randomness for expected IDs/digests.

- [ ] **Step 2: RED connected generic lifecycle**

Execute:

```text
resolve domain:project
→ ProjectProfile
→ project_brief/project_plan/milestone/dependency/resource/status resources
→ scope evaluator
→ milestone evaluator
→ dependency evaluator
→ resource constraint evaluator
→ status/progress evaluator
→ risk/blocker result
→ generic project workflow through shared workflow runtime/evaluator path
→ DomainResult
→ authorized purpose-minimized Project→Life Plan projection
→ memory view/proposal/binding validation
→ independent trace inventory
→ trace assembly and validation
→ General fallback check
```

- [ ] **Step 3: Prove software capability remains off**

No source code, repository, Git, validation or software rule finding should appear in the connected generic scenario.

- [ ] **Step 4: Prove no Formation behavior**

No tutoring/instructor/lesson/curriculum behavior or Formation identifier is introduced.

- [ ] **Step 5: GREEN**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_e2e.py
```

- [ ] **Step 6: Commit**

```bash
git add -- tests/domains/test_project_domain_e2e.py cmm/domains/project
git diff --cached --check
git commit -m "test(project): prove generic project lifecycle"
```

Only stage changed Project production files if the RED test required a real fix.

---

# Task 16 — Software/Self-Development E2E Using Existing Shared Runtime

**Files:**
- Create: `tests/domains/test_project_domain_self_development_e2e.py`
- Modify `cmm/domains/project/operations.py` only for thin result/adaptation helpers proven necessary.
- Do not add another production module.

**Interfaces:**
- Consumes actual shared repository analysis/development/planning/execution/validation/approval/rollback contracts.
- Produces a connected `project.self_development` proof with explicit injected operation implementations.

- [ ] **Step 1: Use a temporary repository fixture**

Create a Git/Python project under `tmp_path`; never mutate the real CMM OS repo.

- [ ] **Step 2: RED grounded software activation**

Resolve/activate Project using explicit repository/source-code resources or `project.self_development`; assert software capability becomes active for this scenario only.

- [ ] **Step 3: RED repository observation + architecture reasoning**

Use the existing shared repository/project analysis or Technical Memory path to produce authoritative repository context. Feed only references/structured results to Project software rules.

- [ ] **Step 4: RED implementation-plan path**

Use the existing shared planning/development contract. Project must not instantiate a custom planner.

- [ ] **Step 5: RED permission + approval before mutation**

Obtain the real shared permission/gate decision for file mutation. A caller-provided approval ID must fail.

- [ ] **Step 6: RED controlled semantic mutation**

Inject a test operation implementation for `project.modify_code` that delegates to the existing controlled semantic/development execution path. It must use the existing rollback/transaction mechanism and operate only inside the temporary project.

- [ ] **Step 7: RED shared validation**

Run the existing Phase 7 validation service/pipeline against the changed temporary project. Capture its authoritative result/reference.

- [ ] **Step 8: RED failed validation blocks commit readiness**

First create a controlled failure variant and assert:

```text
ready_for_approved_commit = false
committed = false
rollback/failed outcome is visible
```

- [ ] **Step 9: RED successful validation allows readiness but does not commit**

Successful variant:

```text
validation PASS
commit gate eligible/allowed
canonical approval evidence present where required
ready_for_approved_commit = true
committed = false
```

Record `git rev-parse HEAD` before and after `project.prepare_commit`; they must be identical.

- [ ] **Step 10: RED no fabricated commit evidence in memory/trace**

Memory and trace may include readiness and validation refs but no authoritative commit ref/hash because none exists.

- [ ] **Step 11: GREEN + shared execution regressions**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_project_domain_self_development_e2e.py \
  tests/test_phase5_execution.py \
  tests/validation/test_validation_phase7_e2e.py
```

If actual validation E2E filename differs, locate it with `git ls-files tests/validation | grep 'phase7.*e2e'` and run that file.

- [ ] **Step 12: Commit**

```bash
git add -- tests/domains/test_project_domain_self_development_e2e.py cmm/domains/project/operations.py
git diff --cached --check
git commit -m "test(project): prove controlled self-development"
```

If `operations.py` did not change, stage only the test.

---

# Task 17 — AT-DP-030: 56 Connected Checkpoints

**Files:**
- Complete: `tests/domains/test_project_domain_dp030_acceptance.py`
- Modify production only for defects exposed by this connected test.

**Interfaces:**
- Produces one connected acceptance function/state machine with exactly 56 named checkpoints.
- Consumes both generic E2E and software/self-development production surfaces; it must not merely call the two E2E test functions.

## Frozen checkpoint inventory

### Generic/core checkpoints 01–32

```text
01 baseline bootstrap constructed
02 domain:project registered
03 ProjectProfile registered
04 exact 27 entity inventory
05 exact 22 resource inventory
06 exact 18 rule inventory
07 exact 20 operation inventory
08 exact 12 workflow inventory
09 generic resolution selects Project
10 General fallback preserved
11 generic software capability remains inactive
12 scope/objective grounded
13 milestone structure accepted
14 unsupported milestone completion rejected
15 dependency structure accepted
16 dependency cycle preserved as blocker
17 resource capacity not invented
18 valid status recognized
19 unknown status rejected
20 proposal remains proposal
21 decision state evidence enforced
22 temporal uncertainty preserved
23 progress evidence required
24 risk/unknown result produced
25 generic workflow evaluated/executed through shared path
26 DomainResult built
27 real Project→Life Plan permission request resolved
28 purpose-minimized projection produced
29 raw Project internals absent from projection
30 memory proposal/view/binding validated
31 independent trace inventory built before trace
32 DomainTrace assembled and validated
```

### Software/self-development checkpoints 33–56

```text
33 software context grounded by repository/workflow signal
34 software capability activates conditionally
35 generic rules remain present with software layer
36 repository observation uses shared infrastructure
37 architecture finding references shared evidence
38 implementation plan uses shared planning path
39 project.modify_code unavailable before injection
40 valid injected implementation accepted
41 file modification permission resolved
42 mutation requires canonical approval
43 forged approval rejected
44 controlled semantic mutation runs in temp repo
45 shared rollback/transaction path is present
46 shared Phase 7 validation executes
47 failed validation blocks commit readiness
48 successful validation evidence accepted
49 change review remains distinct from approval
50 project.prepare_commit evaluates readiness
51 project.prepare_commit performs no git commit
52 no fake commit reference is created
53 software memory proposal preserves readiness vs committed distinction
54 software trace includes permission/execution/validation refs
55 Formation remains outside Project
56 legacy Project catalog remains unmodified and canonical bootstrap isolated
```

- [ ] **Step 1: Implement checkpoint recorder**

Use a tiny local test helper only:

```python
checkpoints: list[str] = []

def checkpoint(name: str) -> None:
    checkpoints.append(name)
```

Do not put acceptance-only checkpoint machinery in production.

- [ ] **Step 2: Implement one connected test**

The test should carry forward actual artifacts between checkpoints instead of reconstructing trusted evidence from IDs.

- [ ] **Step 3: Assert exact checkpoint count and order**

```python
assert len(checkpoints) == DP_030_CHECKPOINTS == 56
assert len(checkpoints[:32]) == DP_030_GENERIC_CHECKPOINTS == 32
assert len(checkpoints[32:]) == DP_030_SOFTWARE_CHECKPOINTS == 24
assert len(set(checkpoints)) == 56
```

- [ ] **Step 4: Ensure trace inventory is independent**

Build inventory from stored runtime artifacts before final trace assembly. Do not inspect final trace to create expected inventory.

- [ ] **Step 5: GREEN**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_dp030_acceptance.py
```

Expected summary: `AT-DP-030` test PASS with 56 checkpoints.

- [ ] **Step 6: Commit**

```bash
git add -- tests/domains/test_project_domain_dp030_acceptance.py cmm/domains/project
git diff --cached --check
git commit -m "test(project): connect AT-DP-030 acceptance"
```

Stage Project production only if acceptance exposed a defect that was fixed.

---

# Task 18 — Permanent 34-Class Adversarial Closure Gate

**Files:**
- Complete: `tests/domains/test_project_domain_closure_adversarial.py`
- Modify production only when RED proves a real defect.

**Interfaces:**
- Produces 34 independent adversarial tests, one per frozen attack class.
- Must not use privileged production helpers to manufacture the exact trusted evidence being attacked.

- [ ] **Step 1: Implement all 34 attacks as separate tests**

Use names mapping one-to-one to the frozen constants, for example:

```python
def test_attack_generic_project_not_software_only(): ...
def test_attack_software_capability_not_implicit(): ...
def test_attack_formation_not_absorbed(): ...
...
def test_attack_general_fallback_preserved(): ...
```

All 34 classes from the spec must have executable assertions.

- [ ] **Step 2: Trust-boundary attacks are independently constructed**

For forged permission/approval/cross-domain/trace attacks, build malicious mappings/lookalikes/direct dataclass construction only where the public constructor permits it; do not call the internal trusted factory that marks an artifact verified.

- [ ] **Step 3: Execution attacks prove no bypass**

Attempt direct Project mutation without injected implementation and without approval; assert unavailable/deny. Verify no file changes.

- [ ] **Step 4: Commit-readiness attacks**

Test failed validation, fake validation reference, fake approval, fake commit hash and readiness-vs-committed distinction.

- [ ] **Step 5: Atomic rollback attack**

Fault-inject mid-registration failure and compare all registry snapshots exactly.

- [ ] **Step 6: Run focused adversarial gate repeatedly**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_closure_adversarial.py
```

Expected: 34 attack classes PASS; parametrization may yield more than 34 pytest cases, but every frozen class must remain represented.

- [ ] **Step 7: Run all Project tests**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_*.py
```

- [ ] **Step 8: Commit**

```bash
git add -- tests/domains/test_project_domain_closure_adversarial.py cmm/domains/project
git diff --cached --check
git commit -m "test(project): harden permanent closure gate"
```

---

# Task 19 — Documentation and Candidate-State Synchronization

**Files:**
- Create: `docs/reference/project-domain.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `ROADMAP.md`

**Interfaces:**
- Produces candidate-state documentation only; independent audit remains pending.

- [ ] **Step 1: Write canonical reference**

`docs/reference/project-domain.md` must record:

```text
domain:project
ProjectProfile
14 modules
27 entities
22 resources
18 rules
20 operations
12 workflows
56 AT-DP-030 checkpoints
34 adversarial attack classes
generic core + conditional software capability
project.review_change canonical
project.prepare_change_review legacy-only
project.prepare_commit never commits
Formation boundary
Life Plan minimized projection
shared memory/trace/permission/workflow/execution reuse
```

Include actual test counts/results observed at implementation time, not invented values.

- [ ] **Step 2: Update Phase 10 roadmap candidate status**

Mark 10.30 implementation complete/pending independent audit. Preserve 10.52 and 10.53 as later planned phases.

Do not write final closure wording yet.

- [ ] **Step 3: Update requirements matrix conservatively**

Set implementation evidence/path for `DP-030`, but keep:

```text
DP_030=REQUIRES_PHASE_INSPECTION
AT_DP_030=PASS
INDEPENDENT_AUDIT=PENDING
```

- [ ] **Step 4: Update public ROADMAP**

Reflect that Project candidate implementation is complete and awaiting independent audit; do not claim Phase 10.30 independently closed.

- [ ] **Step 5: Documentation consistency tests/searches**

```bash
rg -n '10\.30|DP-030|AT-DP-030|domain:project|ProjectProfile' \
  docs/reference/project-domain.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  ROADMAP.md

git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  docs/reference/project-domain.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  ROADMAP.md

git diff --cached --check
git commit -m "docs(project): record phase 10.30 audit candidate"
```

---

# Task 20 — Full Verification and Audit Candidate Bundle

**Files:**
- No new production files unless verification exposes a defect.
- Create untracked external artifact: `phase-10.30-audit-v1.tar.gz`.

**Interfaces:**
- Produces verified candidate HEAD and versioned audit bundle.

- [ ] **Step 1: Verify exact production package**

```bash
test "$(find cmm/domains/project -maxdepth 1 -type f -name '*.py' | wc -l | tr -d ' ')" = "14"
printf '%s\n' "$(find cmm/domains/project -maxdepth 1 -type f -name '*.py' -print | sort)"
```

- [ ] **Step 2: Run focused Project suite**

```bash
.venv/bin/python -m pytest -q tests/domains/test_project_domain_*.py
```

Record actual count.

- [ ] **Step 3: Run all Domain tests**

```bash
.venv/bin/python -m pytest -q tests/domains
```

Record actual count.

- [ ] **Step 4: Run global suite**

```bash
.venv/bin/python -m pytest -q
```

All tests must pass. Do not weaken tests to reach green.

- [ ] **Step 5: Run static/format/compile gates**

```bash
.venv/bin/ruff check cmm/domains/project tests/domains/test_project_domain_*.py
.venv/bin/ruff format --check cmm/domains/project tests/domains/test_project_domain_*.py
.venv/bin/python -m compileall -q cmm/domains/project
git diff --check
```

- [ ] **Step 6: Verify no forbidden fragmentation**

```bash
find cmm/domains/project -maxdepth 1 -type f -print | sort

! rg -n 'subprocess|os\.system|shell=True|git commit|ProjectMemoryStore|ProjectPlanner|ProjectAgentRuntime|ProjectWorkflowEngine|ProjectTraceStore' cmm/domains/project
! rg -n 'domain-trace:probe' cmm/domains/project
```

- [ ] **Step 7: Verify candidate git hygiene**

```bash
git status --short --branch
test -z "$(git diff --name-only)"
test -z "$(git diff --cached --name-only)"
git log -12 --oneline --decorate
```

Only historical untracked audit bundles may remain before generating the new bundle.

- [ ] **Step 8: Generate audit bundle from committed HEAD only**

```bash
rm -f phase-10.30-audit-v1.tar.gz
git archive \
  --format=tar.gz \
  --output=phase-10.30-audit-v1.tar.gz \
  HEAD

tar -tzf phase-10.30-audit-v1.tar.gz | grep -q '^cmm/domains/project/catalog.py$'
tar -tzf phase-10.30-audit-v1.tar.gz | grep -q '^tests/domains/test_project_domain_dp030_acceptance.py$'
shasum -a 256 phase-10.30-audit-v1.tar.gz
```

- [ ] **Step 9: Final candidate evidence block**

Print actual values only:

```text
PHASE10_30_IMPLEMENTATION=COMPLETE
DP_030=REQUIRES_PHASE_INSPECTION
AT_DP_030=PASS
AT_DP_030_CHECKPOINTS=56
PROJECT_CLOSURE_ADVERSARIAL_GATE=PASS
PROJECT_CLOSURE_ATTACK_CLASSES=34
PROJECT_TESTS=<actual>
DOMAIN_TESTS=<actual>
GLOBAL_TESTS=<actual>
RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
INDEPENDENT_AUDIT=PENDING
AUDIT_BUNDLE=phase-10.30-audit-v1.tar.gz
PUSH=NO
MERGE=NO
```

- [ ] **Step 10: Stop at audit boundary**

Do **not** mark `DP-030=VERIFIED_EXISTING` and do not write `FINAL_INDEPENDENT_CLOSURE_AUDIT=PASS` yet.

Hand `phase-10.30-audit-v1.tar.gz` to ChatGPT for independent audit.

---

# Candidate Commit Sequence

Expected coherent commit series; exact hashes are not known in advance:

```text
test(project): freeze phase 10.30 acceptance contracts
feat(project): define canonical domain catalog
feat(project): add canonical project resources
feat(project): add conditional project profile
feat(project): implement generic project reasoning
feat(project): add conditional software reasoning
feat(project): declare controlled project operations
feat(project): enforce supervised project permissions
feat(project): add generic and software workflows
feat(project): enforce life-plan projection boundary
feat(project): bind controlled project memory
feat(project): add shared provenance trace
feat(project): preserve project presentation semantics
feat(project): register project domain atomically
feat(project): expose standard project bootstrap
test(project): prove generic project lifecycle
test(project): prove controlled self-development
test(project): connect AT-DP-030 acceptance
test(project): harden permanent closure gate
docs(project): record phase 10.30 audit candidate
```

Do not squash unless explicitly requested later. No push and no merge.

---

# Plan Self-Review Checklist

Before implementation starts, this plan must satisfy:

```text
[x] exact 14-module production boundary covered
[x] exact 27/22/18/20/12 inventory covered
[x] generic Project independent of software covered
[x] conditional software activation covered
[x] ProjectProfile single-profile invariant covered
[x] legacy Project catalog compatibility covered
[x] project.review_change vs prepare_change_review covered
[x] operation unavailable-by-default covered
[x] Project permission/approval boundary covered
[x] no direct execution bypass covered
[x] project.prepare_commit no-commit semantics covered
[x] shared validation/rollback path covered
[x] Project→Life Plan purpose minimization covered
[x] Formation boundary covered
[x] shared memory proposal/binding covered
[x] shared trace identity + independent inventory covered
[x] validation-first atomic registration covered
[x] exact rollback parity covered
[x] General fallback covered
[x] Project Domain E2E covered
[x] Project self-development E2E covered
[x] AT-DP-030 frozen at 56 connected checkpoints
[x] permanent closure gate frozen at 34 attack classes
[x] documentation candidate-vs-closure distinction covered
[x] committed-HEAD git archive audit bundle covered
[x] no push / no merge covered
```

No placeholder markers, vague implementation steps, or new architectural subsystems are authorized by this plan.
