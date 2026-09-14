# Phase 10.30 — Project Domain Design

**Status:** Frozen design approved for implementation planning
**Date:** 2026-08-26
**Baseline:** `dd07570e5a5875a25387bc4a12527abb7d96411f`
**Branch:** `feature/phase-10-domain-intelligence`
**Canonical domain:** `domain:project`
**Canonical profile:** `ProjectProfile`
**Requirement:** `DP-030`
**Acceptance:** `AT-DP-030`

---

## 1. Purpose

Phase 10.30 implements one canonical Project Domain Pack that can represent and reason about **generic projects** while preserving the historical CMM OS requirement that Project also specialize software-project analysis, development, validation, maintenance, and self-development.

The canonical requirement is:

```text
DP-030
Project: generic project resources, milestones, dependencies, status,
operations, and workflows.
```

The historical Phase 10.30 roadmap additionally requires software-project semantics, `ProjectProfile`, Project Domain E2E, and Project Domain self-development.

These requirements are reconciled through **one domain with two capability layers**, not two domains.

```text
domain:project
│
├── Generic Project Core
│   ├── project identity and objective
│   ├── status
│   ├── milestones
│   ├── dependencies
│   ├── work and deliverables
│   ├── resources and constraints
│   ├── risks
│   ├── decisions
│   └── timeline and progress
│
└── Software Project Capability
    ├── repository
    ├── source code and structure
    ├── architecture and contracts
    ├── documentation
    ├── tests and validation
    ├── technical debt
    ├── controlled changes
    ├── releases
    └── self-development
```

A non-software project remains a first-class Project Domain case and must not be forced through repository, code, Git, or validation semantics.

A software project activates the software capability only when the request, resources, workflow, or explicit context supports it.

---

## 2. Architectural decision

The approved strategy is:

> **One generic Project Domain Pack with an internal software-project capability.**

Rejected alternatives:

1. **Software-only Project Domain** — rejected because it would not satisfy the current canonical `DP-030` contract or the Project projection already expected by Life Plan.
2. **Generic-only Project Domain** — rejected because it would abandon the historical Project contracts, `ProjectProfile`, software operations, Project E2E, and Project self-development requirements.
3. **Separate `domain:software-project`** — rejected because it would fragment Project semantics and create an unnecessary new Domain Pack.

Project is the owner of project-specific semantics. Software specialization is conditional behavior inside the same pack.

---

## 3. Non-fragmentation invariant

Project must reuse the already implemented shared architecture.

```text
Same Kernel
Same Cognitive Layer
Same Knowledge Model / Store / Graph
Same Agent Runtime
Same Goal System
Same Planner
Same Workflow Engine
Same Execution Engine
Same Validation System
Same Permission / Approval Infrastructure
Same Memory Contracts
Same Domain Trace
+
Project resources
Project profile configuration
Project rules
Project operations
Project workflows
Project permission policy
Project presentation
```

Project must not create:

- a Project-specific planner;
- a Project-specific Agent Runtime;
- a Project-specific goal system;
- a Project-specific workflow engine;
- a Project-specific execution engine;
- a Project-specific validation pipeline;
- a Project-specific permission or approval engine;
- a Project-specific memory store;
- a Project-specific Knowledge Store or Knowledge Graph;
- a Project-specific trace system;
- a Project-specific Git runtime;
- a Project-specific repository persistence subsystem.

Files such as `planner.py`, `engine.py`, `repository.py`, `state_store.py`, `permission_engine.py`, or `trace_store.py` are out of scope for the Domain Pack.

---

## 4. Package boundary

Phase 10.30 follows the hardened recent Domain Pack boundary exactly.

```text
cmm/domains/project/
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

Exact production package size: **14 Python modules**.

`catalog.py` is the single source of truth for canonical entity, resource, rule, operation, and workflow identifiers.

No canonical ID list may be duplicated independently in another Project module.

---

## 5. Canonical identity

```text
domain_id              = domain:project
profile                 = ProjectProfile
domain_version          = 1.0.0
manifest_id             = manifest:project:1.0.0
permission_policy_id    = domain-permission:project:1.0.0
requirement             = DP-030
acceptance               = AT-DP-030
```

The Domain Kind uses the existing shared Project-compatible `DomainKind` value. No new kind is introduced.

Project depends on the existing shared Domain Intelligence infrastructure and preserves General fallback.

---

## 6. Canonical inventory

The frozen implementation candidate uses:

```text
27 entities
22 resources
18 rules
20 operations
12 workflows
```

The exact identifiers below are canonical.

### 6.1 Entities — exactly 27

Generic project entities:

```text
project
objective
milestone
work_item
deliverable
project_resource
constraint
risk
decision
status_change
project_event
```

Historical/software entities retained:

```text
repository
module
package
file
class
method
function
contract
dependency
test
validation_result
issue
technical_debt
architecture_decision
workflow
release
```

The generic core must not require software entities to be present.

### 6.2 Resources — exactly 22

Generic project resources:

```text
project_brief
project_plan
milestone_record
work_item_record
dependency_record
resource_record
status_report
decision_record
risk_record
project_timeline
```

Historical/software resources retained:

```text
source_code
project_file
documentation
test_result
validation_result
git_history
issue
roadmap
architecture_document
commit
pull_request
memory_entry
```

Resource definitions reuse shared `DomainResourceDefinition`, provenance, temporal scope, sensitivity, and permission contracts.

Project may specialize interpretation of a shared resource but must not create persistent copies merely to make it Project-specific.

---

## 7. ProjectProfile

There is exactly one canonical specialized profile:

```text
ProjectProfile
```

It must reuse the existing shared profile registry and resolver.

The profile has two rule layers.

### Generic core

Always applicable when Project is primary:

```text
project.scope_consistency
project.milestone_consistency
project.dependency_consistency
project.status_transition
project.resource_constraint
project.decision_state
project.temporal_validity
project.progress_evidence
```

### Software capability

Conditionally applicable when repository/software context is materially present:

```text
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

Software rules must not fire merely because the primary domain is Project.

Activation must be grounded in explicit workflow, operation, resource, capability, or equivalent shared context.

No second `SoftwareProjectProfile` is introduced.

---

## 8. Rules — exactly 18

### 8.1 Generic project rules

#### `ProjectScopeConsistencyRule`

Canonical ID:

```text
project.scope_consistency
```

Preserves the declared project objective, scope, exclusions, and deliverables. A later inference or proposed task must not silently redefine project scope.

#### `MilestoneConsistencyRule`

Canonical ID:

```text
project.milestone_consistency
```

Checks milestone identity, ordering, completion basis, dates where known, and relationship to declared deliverables.

A milestone must not be marked complete only because a related task changed state.

#### `DependencyConsistencyRule`

Canonical ID:

```text
project.dependency_consistency
```

Checks known project dependencies, unresolved blockers, missing references, and contradictory dependency states.

Cycles or malformed dependency structures must fail closed rather than being silently linearized.

#### `ProjectStatusTransitionRule`

Canonical ID:

```text
project.status_transition
```

Requires project and milestone status changes to be grounded in authoritative state/evidence.

Unknown status values fail closed.

#### `ProjectResourceConstraintRule`

Canonical ID:

```text
project.resource_constraint
```

Relates available resources and constraints to milestones, work, and feasible progress without inventing capacity.

#### `ProjectDecisionStateRule`

Canonical ID:

```text
project.decision_state
```

Separates:

```text
option != decision
proposal != decision
decision != execution
planned change != completed change
review-ready != approved
approved != applied
```

#### `ProjectTemporalValidityRule`

Canonical ID:

```text
project.temporal_validity
```

Preserves date validity and ordering without inventing timestamps, deadlines, or chronology.

#### `ProjectProgressEvidenceRule`

Canonical ID:

```text
project.progress_evidence
```

Progress claims must be linked to grounded status, completed deliverables, validated outcomes, or equivalent evidence.

Narrative optimism, a plan, or a proposed change cannot independently prove progress.

### 8.2 Software-project rules

Canonical IDs:

```text
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

These preserve the historical 10.30 semantics:

- architectural contracts;
- code/documentation consistency;
- validation before accepting a change;
- technical-debt analysis;
- dead-code identification;
- public API impact;
- backward compatibility;
- dependency/layer boundaries;
- relationship between changes and tests;
- use of semantic/controlled transformation infrastructure where applicable.

They reuse shared Cognitive and Validation contracts and must not implement a second static-analysis or validation engine.

---

## 9. Operations — exactly 20

All Project operations are declarations through the shared Domain Operation infrastructure.

They are **UNAVAILABLE by default** until a real implementation/adapter is explicitly injected.

Project must never claim that an operation executed merely because a definition exists.

### 9.1 Generic project operations — 7

```text
project.create_project_overview
project.review_status
project.plan_milestones
project.review_dependencies
project.review_resources
project.review_risks
project.generate_progress_summary
```

Expected semantics:

- `create_project_overview` — prepare a structured project overview from authorized resources;
- `review_status` — analyze current project/milestone status and blockers;
- `plan_milestones` — produce a milestone/dependency plan without silently persisting it;
- `review_dependencies` — analyze dependency state and blocking relationships;
- `review_resources` — analyze resource/constraint feasibility;
- `review_risks` — produce evidence-calibrated project risks and unknowns;
- `generate_progress_summary` — prepare a grounded progress report.

### 9.2 Software-project operations — 13

Historical canonical IDs are retained:

```text
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

### 9.3 Execution boundary

Domain code must not implement unrestricted filesystem, shell, Git, Python editing, or transformation execution.

Injected software-operation adapters must reuse existing shared capabilities, including the applicable current equivalents of:

- repository/project analysis;
- Technical Memory;
- shared planners;
- Semantic Runtime;
- controlled filesystem/Python/Git executors;
- architectural transformation pipeline;
- Phase 7 Validation;
- shared policy/approval gates;
- rollback/transaction infrastructure.

No operation may call arbitrary shell commands.

---

## 10. `project.prepare_commit` semantics

`project.prepare_commit` does **not** perform `git commit`.

It prepares commit-readiness evidence through shared validation and policy contracts.

Expected conceptual result:

```text
change identity
validation evidence
commit-gate decision
known blockers
approval state
review references
ready_for_approved_commit = true | false
```

It must not fabricate commit hashes, mutate Git history, or claim a commit occurred.

If a future/current shared authorized commit capability is available, Project may hand off to that capability through normal Operation/Agent Runtime/Approval contracts.

If no shared commit capability is available, the workflow stops safely at:

```text
ready_for_approved_commit
```

This reconciles the historical roadmap's conceptual `Commit` step without creating a Project-local Git commit implementation.

---

## 11. Workflows — exactly 12

All workflows use the common shared workflow engine and existing node types.

### 11.1 Generic project workflows — 4

```text
project.project_setup
project.status_review
project.milestone_dependency_review
project.periodic_project_review
```

#### `project.project_setup`

```text
Load authorized project resources
→ Apply ProjectProfile
→ Resolve objective/scope
→ Resolve known milestones
→ Resolve known dependencies
→ Resolve resource constraints
→ Detect blocking information gaps
→ Prepare project overview
→ Propose project memory update when authorized
→ Complete
```

#### `project.status_review`

```text
Load project state
→ Apply ProjectProfile
→ Review status
→ Review progress evidence
→ Detect blockers
→ Review risks
→ Prepare status result
→ Complete
```

#### `project.milestone_dependency_review`

```text
Load milestones
→ Load dependencies
→ Apply consistency rules
→ Detect cycles/conflicts/gaps
→ Evaluate resource constraints
→ Prepare revised milestone/dependency proposal
→ Complete
```

#### `project.periodic_project_review`

```text
Load current project state
→ Compare prior authoritative state
→ Review milestones/dependencies/resources
→ Review decisions and open risks
→ Review progress evidence
→ Generate progress summary
→ Propose authorized memory update
→ Complete
```

### 11.2 Software-project workflows — 8

```text
project.architecture_review
project.feature_implementation
project.bug_resolution
project.technical_debt_review
project.documentation_synchronisation
project.refactor
project.release_preparation
project.self_development
```

The workflow names preserve the historical Phase 10.30 roadmap semantics.

---

## 12. Software capability activation

Software-specific rules, operations, and workflows require a grounded software-project signal.

Valid signals may include shared-contract equivalents of:

- an explicit software workflow;
- an explicit software Project operation;
- repository/source-code/project-file resources;
- a repository-backed active goal;
- an authorized request explicitly asking for code/project development;
- a software capability resolved through the shared Domain system.

Invalid activation examples:

```text
primary_domain == domain:project        # insufficient by itself
project has a deadline                  # insufficient
project has dependencies                # insufficient
word "project" appears in text          # insufficient
```

A generic personal/professional project must not be subjected to code validation, Git, test, or repository semantics unless software context is real.

---

## 13. Self-development workflow

`project.self_development` specializes CMM OS self-development without rebuilding the development stack.

Canonical conceptual flow:

```text
Observe Repository
↓
Detect Improvement
↓
Create/resolve Goal through shared Agent Runtime
↓
Apply ProjectProfile + software capability
↓
Create implementation plan through shared planning path
↓
Evaluate permissions / approvals
↓
Execute controlled semantic operations through shared execution
↓
Run Phase 7 validation
↓
Evaluate outcome
↓
Review change
↓
Prepare commit-readiness evidence
↓
Request/verify approval where required
↓
Handoff to shared authorized commit capability, if configured
OR
Complete as ready_for_approved_commit
↓
Propose Project knowledge/memory update from authoritative outcome
```

### Mandatory invariants

- Project does not directly instantiate its own planner.
- Project does not directly instantiate its own autonomous loop.
- Project does not bypass Agent Runtime policy.
- `project.modify_code` cannot run without its injected shared execution adapter.
- file modification requires effective permission and canonical approval where policy requires it;
- validation is mandatory before commit readiness;
- rollback remains shared-runtime responsibility;
- a failed validation cannot become `ready_for_approved_commit=true`;
- a prepared review is not an approval;
- an approval ID supplied by the caller is not trusted by itself;
- no commit is claimed without authoritative commit evidence;
- memory cannot claim the change was committed if only commit readiness was reached.

---

## 14. Historical catalog compatibility

The preflight found pre-10.30 Project fixtures in shared initial catalogs.

Historical IDs include:

```text
ProjectProfile

project.architecture_contract
project.code_documentation_consistency
project.validation_required
project.technical_debt

project.analyse_architecture
project.create_implementation_plan
project.run_validation
project.prepare_change_review

project.architecture_review
```

These artifacts are compatibility/demo infrastructure from earlier Phase 10 work, not the canonical Phase 10.30 Domain Pack.

### Rules

1. `cmm/domains/project/catalog.py` becomes the canonical source for Phase 10.30 inventory.
2. Existing shared initial catalogs must remain backward compatible and their existing tests must remain green.
3. The canonical Project bootstrap must not load the historical initial Project catalog as its source of truth.
4. Exact overlapping canonical IDs may coexist in source code only because the legacy catalog and canonical pack are separate construction paths.
5. If registration is attempted into a registry that already contains an incompatible same-ID/same-version legacy definition, registration must **fail closed and roll back**.
6. No silent overwrite, unregister-and-replace, or mutation of preexisting definitions is allowed.
7. `project.prepare_change_review` remains a historical compatibility operation and is **not** part of the 20-operation canonical Phase 10.30 inventory.
8. Canonical Phase 10.30 uses `project.review_change` as specified by the historical 10.30 roadmap.
9. Legacy behavior must not be removed merely to make the new bootstrap pass.

Tests must cover:

- legacy initial catalogs still build independently;
- canonical Project bootstrap builds independently;
- incompatible preloaded overlapping definitions fail atomically;
- no silent replacement occurs.

---

## 15. Permissions

Project uses one canonical Domain Permission Policy:

```text
domain-permission:project:1.0.0
```

Default policy is fail-closed and low-autonomy.

### Baseline capabilities

Project may declare eligibility for shared-contract equivalents of:

```text
RESOURCE_READ
MEMORY_READ
OPERATION_EXECUTE
WORKFLOW_EXECUTE
FILE_MODIFY
```

`FILE_MODIFY` is approval-gated and does not imply autonomous mutation.

### Prohibited by default

Project must not silently obtain capabilities equivalent to:

```text
IRREVERSIBLE_CHANGE
PERMISSION_MODIFY
COMMUNICATION_EXTERNAL
PUBLICATION
FINANCIAL_ACTION
FINANCIAL_SPEND
SEARCH_EXTERNAL
MODEL_EXTERNAL
KNOWLEDGE_DELETE
```

The exact enum set must use existing shared contracts; no new permission enum is introduced solely for Project.

### Autonomy

Preserve the low-autonomy historical Project policy.

Reversible modifications remain supervised and bounded by shared operation, approval, validation, transaction, and rollback policy.

A domain permission definition is not permission evidence for a concrete execution. Effective permission must come from the shared resolver/gate for the actual request.

---

## 16. Generic project state semantics

Project state is knowledge, not static rule configuration.

A project/milestone/dependency status must preserve:

- identity;
- provenance;
- temporal validity;
- explicit state;
- evidence/reference basis;
- uncertainty where unresolved;
- version/history where represented by shared knowledge contracts.

### Required distinctions

```text
planned != active
active != completed
blocked != failed
paused != cancelled
proposal != approved decision
milestone due != milestone missed
work produced != work validated
change implemented != change accepted
```

Unknown or malformed status is not normalized into a convenient known state.

---

## 17. Dependencies and milestones

Project must support generic dependency and milestone reasoning independently of software dependencies.

Examples:

```text
milestone A blocks milestone B
deliverable X requires resource Y
work item C depends on decision D
project completion depends on external milestone E
```

Software module/package dependencies are a specialization of Project's technical capability and must not overwrite generic project dependency semantics.

Dependency analysis must preserve unresolved or cyclic structures explicitly.

A cycle may be reported as a blocker/contradiction but must not be silently broken.

---

## 18. Life Plan integration

Life Plan already defines the authorized Project projection boundary.

Project may expose, through shared authorized cross-domain contracts, only purpose-minimized Project information such as:

```text
authorized project status
authorized dependency
authorized resource impact
authorized timeline impact
```

Project retains project-specific execution semantics.

Life Plan must not receive through this projection:

- raw source code;
- repository internals unrelated to the Life Plan decision;
- unrestricted issue text;
- validation logs by default;
- commit history by default;
- private implementation details;
- Project operation authority.

Presence of Life Plan as a supporting or target domain is not authorization by itself.

A raw mapping, boolean, ID, or caller-created object is not trusted cross-domain evidence.

---

## 19. Other cross-domain composition

Project may compose with General and other specialized domains only through shared resolution, composition, permission, and projection contracts.

Project does not absorb those domains' factual semantics.

Examples:

```text
Project + Concerns
→ Project owns project facts/status/execution semantics
→ Concerns owns concern/support framing

Project + Life Plan
→ Project owns project status/dependencies/resources
→ Life Plan owns long-horizon cross-domain planning
```

Project does not gain Health, legal, financial, academic, relationship, or other specialized authority merely because those matters affect a project.

---

## 20. Formation boundary

Formation remains an overlay on General as already assigned by the requirements matrix.

Project must not absorb Formation.

Project must not add generic tutoring/instructor behavior merely because learning may occur inside a project.

```text
project management != formation
project documentation != teaching profile
implementation plan != instructional curriculum
```

This boundary is an explicit `DP-030` acceptance condition.

---

## 21. Memory integration

Project reuses the shared Domain Memory Integration contracts.

Expected helper surface follows the stabilized recent Domain Pack pattern:

```text
build_project_memory_view_request
build_project_memory_view
build_project_memory_proposal
build_project_memory_binding
validate_project_memory_binding
```

Exact signatures must follow current shared contracts.

### Memory invariants

No implicit persistence.

The following must not become durable confirmed Project knowledge merely because they appeared in planning or reasoning:

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

A committed change can only be represented as committed when authoritative commit evidence exists.

Project does not create a separate project-memory store.

Memory writes/proposals must follow real shared permission, confirmation, provenance, and binding validation.

---

## 22. Trace integration

Project reuses shared Domain Trace contracts, assembler, validators, and the shared preassembly trace identity API.

Project must use the canonical shared equivalent of:

```text
calculate_domain_trace_identity(...)
DomainTraceAssembler
```

No local `domain-trace:probe`, Project-specific trace identity algorithm, or duplicate DomainTrace is allowed.

Trace evidence must expose, by reference where shared contracts require it:

- Project resolution;
- generic versus software capability activation;
- effective ProjectProfile;
- selected rules;
- resources used;
- milestone/dependency/status findings;
- selected operation/workflow;
- permission and approval decisions;
- execution references;
- validation references;
- rollback reference where relevant;
- commit-readiness state;
- authoritative commit reference only when one exists;
- cross-domain projection decisions;
- memory proposal/binding;
- final DomainResult.

AT-DP-030 must construct trace inventory independently from the final trace object before assembly.

---

## 23. Presentation

Project presentation may adapt structure for:

- project objective and scope;
- current status;
- milestones;
- dependencies;
- resource constraints;
- risks;
- decisions;
- blockers;
- progress;
- next review/next step;
- architecture findings when software capability is active;
- validation evidence;
- technical debt;
- change review;
- release readiness.

Presentation must not:

- turn a proposal into a decision;
- turn planned work into completed work;
- hide blockers or failed validation;
- hide uncertainty;
- hide approval requirements;
- claim a commit occurred when only commit readiness exists;
- activate software semantics for a generic project;
- remove provenance.

---

## 24. Definition and registration

`build_project_domain_definition()` and related pure factories must build the canonical Project pack from `catalog.py`.

`register_project_domain(...)` must use the established validation-first + snapshot + registration + rollback pattern.

Registration covers the shared registries required by recent Domain Packs.

On any required-component failure:

- no partial Project registration remains;
- every touched registry returns to exact prior state;
- previously registered domains remain unchanged;
- General fallback remains intact;
- rollback failure is surfaced explicitly.

No best-effort partial Project activation is accepted.

---

## 25. Canonical bootstrap

Canonical bootstrap:

```text
build_standard_project_domain_bootstrap()
```

It must extend the already completed standard Phase 10 Domain Pack chain through Life Plan and register Project into those **same registry objects**.

Conceptually:

```text
standard bootstrap through 10.29
→ same domain registry
→ same resource registry
→ same profile registry
→ same rule registry
→ same operation registry
→ same workflow registry
→ same permission registry
→ register Project atomically
→ expose resolver with General fallback preserved
```

It must not automatically register Phase 10.52 Mental Health or Phase 10.53 Neurodivergence.

If Project cannot resolve for a request, normal shared resolution/fallback behavior remains available.

---

## 26. Project Domain E2E

The historical `Project Domain E2E` requirement is implemented as a generic Project lifecycle, not merely a code example.

Minimum connected scenario:

```text
resolve domain:project
→ ProjectProfile
→ load generic project resources
→ establish project objective/scope
→ resolve milestones
→ resolve dependencies
→ resolve resources/constraints
→ review status
→ evaluate progress evidence
→ detect blocker/risk
→ execute generic Project workflow through shared workflow runtime
→ produce DomainResult
→ create purpose-minimized authorized Life Plan projection
→ build memory proposal/view/binding
→ validate memory boundary
→ build independent trace inventory
→ assemble DomainTrace
→ validate trace
→ prove atomic bootstrap + General fallback
```

This scenario proves `DP-030` independently of software-project specialization.

---

## 27. Project self-development E2E

A second connected scenario proves the historical `Project Domain self-development` requirement.

Minimum scenario:

```text
resolve CMM OS as domain:project
→ activate ProjectProfile software capability
→ load repository/documentation resources
→ run architecture/consistency reasoning
→ create implementation plan through shared planning path
→ obtain real permission/approval decision for mutation
→ execute controlled shared semantic change
→ run shared Validation System
→ evaluate outcome
→ review change
→ prepare commit-readiness evidence
→ prove no direct git.commit occurred inside Project
→ create Project memory proposal from authoritative state
→ trace complete lifecycle
```

The candidate may use a temporary project/repository fixture for E2E execution. It must not mutate the real CMM OS repository as part of automated tests.

---

## 28. AT-DP-030 connected acceptance

`AT-DP-030` is one connected acceptance suite with two linked paths:

```text
A. Generic project lifecycle
B. Software/self-development specialization
```

Target: approximately **50–60 connected checkpoints**. The implementation plan freezes the exact checkpoint count before coding.

Minimum proof categories:

```text
identity and exact catalog
ProjectProfile
software capability conditional activation
generic project resources
status
milestones
dependencies
resource constraints
progress evidence
risks/unknowns
workflow execution
operation availability fail-closed
Life Plan projection
purpose minimization
real permission path
approval path
software repository context
implementation planning
controlled mutation adapter
validation-required gate
rollback evidence
change review
prepare_commit readiness semantics
no direct git commit
memory proposal/view/binding
memory validation
DomainResult
independent trace inventory
trace assembly/validation
tamper rejection
legacy catalog isolation
atomic registration/rollback
General fallback
Formation boundary
```

Candidate-side acceptance does not independently close the phase.

---

## 29. Permanent adversarial closure gate

Phase 10.30 must include a permanent adversarial test suite from the first audit candidate.

Required attack classes include:

```text
GENERIC_PROJECT_NOT_SOFTWARE_ONLY
SOFTWARE_CAPABILITY_NOT_IMPLICIT
FORMATION_NOT_ABSORBED
UNKNOWN_PROJECT_STATUS_FAILS_CLOSED
PROPOSAL_NOT_DECISION
PLAN_NOT_COMPLETION
MILESTONE_COMPLETION_REQUIRES_EVIDENCE
MALFORMED_MILESTONE_FAILS_CLOSED
DEPENDENCY_CYCLE_PRESERVED
MALFORMED_DEPENDENCY_FAILS_CLOSED
RESOURCE_CAPACITY_NOT_INVENTED
PROGRESS_REQUIRES_EVIDENCE
RAW_CROSS_DOMAIN_REJECTED
FORGED_CROSS_DOMAIN_PERMISSION_REJECTED
PURPOSE_MINIMIZATION_ENFORCED
LEGACY_CATALOG_NOT_CANONICAL
LEGACY_COLLISION_NO_SILENT_OVERWRITE
OPERATION_UNAVAILABLE_WITHOUT_IMPLEMENTATION
DIRECT_EXECUTION_BYPASS_REJECTED
FILE_MODIFY_WITHOUT_APPROVAL_REJECTED
FORGED_APPROVAL_REJECTED
VALIDATION_REQUIRED_BEFORE_COMMIT_READINESS
FAILED_VALIDATION_NOT_COMMIT_READY
PREPARE_COMMIT_DOES_NOT_COMMIT
NO_FAKE_COMMIT_REFERENCE
MUTATION_REQUIRES_SHARED_ROLLBACK_PATH
MEMORY_WRITE_FAILS_CLOSED
MEMORY_DOES_NOT_PROMOTE_PROPOSAL
MEMORY_DOES_NOT_PROMOTE_COMMIT_READINESS
TRACE_IDENTITY_USES_SHARED_API
TRACE_INVENTORY_INDEPENDENT
TRACE_TAMPER_REJECTED
ATOMIC_REGISTRATION_ROLLBACK
GENERAL_FALLBACK_PRESERVED
```

Adversarial tests must not manufacture trusted evidence using the same helper under test when doing so would make the attack circular.

---

## 30. Test strategy

Implementation must include focused tests covering at least:

- catalog and public API;
- resources/entities;
- profile activation;
- generic rules;
- software rules;
- generic operations;
- software-operation declarations and availability;
- workflows;
- permissions/approvals;
- generic project semantics;
- software capability activation boundary;
- Life Plan cross-domain projection;
- memory integration;
- trace integration;
- atomic integration/bootstrap;
- legacy catalog compatibility/isolation;
- `AT-DP-030` connected acceptance;
- permanent adversarial closure gate;
- Project E2E;
- Project self-development E2E;
- domain suite regression;
- global suite regression.

Use TDD during implementation.

Do not weaken existing tests or replace adversarial cases with benign coverage.

---

## 31. Documentation

Implementation must add/update the minimum canonical documentation:

```text
docs/reference/project-domain.md
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
ROADMAP.md
```

Before independent audit, documentation may state:

```text
PHASE10_30_IMPLEMENTATION=COMPLETE
AT_DP_030=PASS
DP_030=REQUIRES_PHASE_INSPECTION
INDEPENDENT_AUDIT=PENDING
```

It must not state final independent closure before the audit passes.

After successful independent closure audit, the closure-only documentation commit may set:

```text
PHASE10_30=COMPLETE
FINAL_INDEPENDENT_CLOSURE_AUDIT=PASS
DP_030=VERIFIED_EXISTING
AT_DP_030=PASS
```

---

## 32. Audit candidate

The audit bundle must be produced from versioned HEAD only:

```bash
git archive \
  --format=tar.gz \
  --output=phase-10.30-audit-v1.tar.gz \
  HEAD
```

The bundle remains untracked external evidence.

Do not use a working-directory `tar` as the canonical audit candidate.

Independent audit is performed by ChatGPT after the versioned candidate bundle exists.

---

## 33. Scope exclusions

Phase 10.30 does not implement:

- a second generic planner;
- a second Agent Runtime;
- a second autonomous development loop;
- a second validation pipeline;
- a second Semantic Runtime;
- a Project-specific Git backend;
- unrestricted shell execution;
- direct Git commit inside the Domain Pack;
- Project-specific persistent state/storage;
- new shared memory infrastructure;
- new shared trace infrastructure;
- new shared permission/approval infrastructure;
- new shared workflow infrastructure;
- Phase 11 UI/orchestration/backend;
- Phase 10.52 Mental Health;
- Phase 10.53 Neurodivergence;
- Formation as Project functionality;
- unrelated refactoring of completed domains.

---

## 34. Definition of done — implementation candidate

Phase 10.30 is ready for independent audit only when:

```text
[ ] cmm/domains/project exists
[ ] exactly 14 production modules
[ ] exactly 27 entities
[ ] exactly 22 resources
[ ] exactly 18 rules
[ ] exactly 20 operations
[ ] exactly 12 workflows
[ ] ProjectProfile registered through shared infrastructure
[ ] generic Project works without software resources
[ ] software capability activates only with grounded software context
[ ] historical software semantics preserved
[ ] legacy catalogs remain backward compatible
[ ] canonical catalog is Project single source of truth
[ ] incompatible legacy collisions fail atomically
[ ] generic milestones/dependencies/status/resources work
[ ] Project -> Life Plan projection is authorized and purpose-minimized
[ ] Formation boundary preserved
[ ] operations UNAVAILABLE without injected implementation
[ ] code mutation uses existing controlled execution infrastructure
[ ] validation is mandatory before commit readiness
[ ] project.prepare_commit performs no git commit
[ ] no fabricated commit evidence
[ ] shared permission/approval path reused
[ ] shared workflow runtime reused
[ ] shared memory integration reused
[ ] shared trace identity/assembler/validation reused
[ ] independent trace inventory
[ ] atomic registration
[ ] exact rollback
[ ] General fallback preserved
[ ] Project Domain E2E PASS
[ ] Project self-development E2E PASS
[ ] AT-DP-030 PASS
[ ] permanent adversarial gate PASS
[ ] focused Project tests PASS
[ ] all domain tests PASS
[ ] global tests PASS
[ ] Ruff/format/compile gates PASS
[ ] documentation synchronized
[ ] DP-030 remains REQUIRES_PHASE_INSPECTION
[ ] audit bundle generated from committed HEAD
[ ] no push
[ ] no merge
```

---

## 35. Frozen design decision

Approved implementation strategy:

> **Standard 14-module `domain:project` Domain Pack on existing shared Phase 10 infrastructure, with a generic Project core and a conditional software/self-development capability inside the same domain.**

The following are frozen:

```text
domain:project
ProjectProfile
14 production modules
27 entities
22 resources
18 rules
20 operations
12 workflows
project.review_change is canonical
project.prepare_change_review is legacy-only
project.prepare_commit never performs git commit
Formation remains outside Project
Project self-development reuses existing shared development/execution/validation infrastructure
```

Any material architectural change to these decisions requires explicit design review before implementation.
