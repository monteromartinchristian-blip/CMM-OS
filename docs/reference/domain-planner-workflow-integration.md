# Domain ↔ Planner and Workflow Engine Integration (Phase 10.42)

**Status:** Phase 10.42 implemented, pending independent audit.
`DP-042=IMPLEMENTED_PENDING_AUDIT`; `AT-DP-042=PASS`.

Phase 10.42 is an **integration phase, not an ownership phase**. It lets the
canonical Phase 9 planning path use registered, available,
permission-compatible Domain operations and workflows without introducing
incompatible nodes or parallel infrastructure.

---

## Purpose and ownership

Phase 10.42 connects Domain Intelligence to the canonical Planner and the
shared Workflow Engine so plans can use Domain capabilities while every
lifecycle remains owned by its existing canonical service:

```text
canonical Planner owner
  → Phase 9 TaskPlanner / AgentPlanningService

canonical plan contract
  → AgentWorkflowPlan (the only plan contract)

canonical Domain operation execution
  → Phase 10.41 dispatch path
    (AgentExecutionAdapter → DomainOperationDispatchAdapter
     → DefaultDomainOperationOrchestrator → current DomainPermissionGate
     → AgentExecutionAdapter → DomainOperationExecutionDelegate
     → registered Domain operation implementation)

canonical Domain workflow execution
  → DomainWorkflowExecutor backed by the shared WorkflowEngine
    (cmm.workflows.engine.WorkflowEngine)

canonical approvals
  → Phase 9 approval infrastructure (AgentWorkflowApprovalNode)

canonical validation execution
  → existing validation infrastructure (AgentWorkflowValidationNode)

canonical replanning
  → AgentPlanningService.replan(...)

canonical Domain authority
  → existing Domain permission resolution / gates
```

The canonical integration owner is `DefaultDomainPlannerWorkflowIntegrator`
(`cmm/domains/planner_workflow_integration.py`), a thin coordination boundary
that receives every stateful owner by dependency injection. It owns
coordination only.

## Dependency direction

```text
cmm.domains → cmm.agent_runtime   (allowed)
cmm.domains → cmm.workflows       (allowed)
cmm.agent_runtime → cmm.domains   (forbidden; AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0)
cmm.workflows → cmm.domains       (forbidden; WORKFLOWS_TO_DOMAIN_IMPORTS=0)
```

Phase 9 stays completely Domain-agnostic. The permitted Phase 9 seams are
generic metadata keys carried from `AgentPlanningRequest.metadata` into
`AgentWorkflowPlan` (`cmm/agent_runtime/workflow_planner_adapter.py`):

```text
workflow_references    opaque workflow reference IDs → plan metadata
operation_semantics    exact per-operation planning semantics
                       (required permissions/validations, approval requirement
                       and approval IDs, reversibility, rollback reference,
                       risk, timeout, provenance metadata) → translated
                       AgentWorkflowOperation fields and approval/validation
                       node bindings
operation_candidates   eligible opaque operation IDs (absent = heuristic
                       Phase 9 translation, backward-compatible; present =
                       every planned operation is selected deterministically
                       from the candidates round-robin in step order; empty =
                       unsatisfiable and fails closed) → planned
                       AgentWorkflowOperation identity; exact
                       operation_semantics overlays then bind by selected ID
dependency_references  operation/workflow/domain dependency references →
                       plan metadata, with operation pairs whose endpoints are
                       both planned materialized as canonical
                       AgentWorkflowDependency edges; required operation pairs
                       naming an unplanned operation are recorded as
                       unresolved_operation_dependencies and fail closed
                       (canonical INVALID plan, deterministic blocking error)
```

Phase 9 never resolves, executes, or authorizes through those references;
every entry is validated generically and unknown fields are rejected.

## New contracts (`cmm/domains/planner_workflow_integration_contracts.py`)

- `DomainPlanningCapabilityView` — immutable read-only projection of
  effective Domain planning capabilities (available/prohibited operations,
  available workflows, operation/workflow dependencies, required
  permissions/approvals/validations, cross-domain constraints, authority
  references, JSON-safe metadata only). Advisory to planning, restrictive to
  execution: presence never authorizes execution.
- `DomainPlannerWorkflowIntegrationRequest` — immutable wrapper binding the
  canonical `DomainResolutionContext` and the canonical
  `AgentPlanningRequest` (plus an optional current plan and JSON-safe
  metadata carrying `requested_workflow_ids`).
- `DomainPlannerWorkflowIntegrationResult` — immutable aggregate binding
  canonical results by reference (`DomainResolutionResult`,
  `DomainComposition`, capability view, prepared `AgentPlanningRequest`,
  `AgentWorkflowPlan`, selected workflow IDs, blocked flag, reason codes).
- `DomainPlannerWorkflowIntegrator` — protocol (`integrate`,
  `execute_workflow_reference`, `replan`).
- `DefaultDomainPlannerWorkflowIntegrator` — the only approved implementation.

All contracts are frozen, deterministic, and JSON-safe following neighboring
Phase 10.41 conventions. No registries, services, stores, executors,
planners, or state machines live in the contracts module.

## Integration sequence

```text
validate wrapper
→ DefaultDomainResolver.resolve(DomainResolutionContext)
→ canonical composition from registry-owned Domain definitions
→ fail closed on Domain/Phase 9 identity conflict
→ fail closed on unresolved blocking composition conflicts
→ read-only capability projection (registered + available + compatible only)
→ final most-restrictive operation authority
  (prepared allowed minus prepared prohibited, permission-compatible)
→ explicit workflow selection with final eligibility (requested ∩ available;
  each requested workflow must resolve active from the canonical workflow
  registry and be canonically available under the final authority through
  _resolve_workflow_for_planning(...) — prepared permissions, final
  permitted operation IDs, exact node definitions, the request's resource references, and the current
  effective composition; unavailable or incompatible requested workflows
  fail closed with `domain_workflow_unavailable` before planner invocation;
  every required INVOKE_SUBWORKFLOW dependency must additionally resolve
  exactly (id, version) and be final-authority eligible recursively,
  cycle-safe, or the parent fails closed with
  `domain_workflow_dependency_not_available` before planner invocation;
  approval-pending workflows remain representable)
→ most-restrictive AgentPlanningRequest preparation
  (canonical approval obligations of the selected workflow graph joined
  after selection: workflow-level gates, node-level approval sources, and
  internal operation approvals/validations, eligible child obligations,
  and canonical cross-domain approval actions)
→ pre-planning blocks (no permitted operations, unsatisfiable permissions)
→ AgentPlanningService.plan(prepared request)
→ canonical AgentWorkflowPlan (post-checks: unresolved required operation
   dependencies block with `domain_unresolved_operation_dependency`, no
   prohibited ops, every planned op within the non-empty allowlist, INVALID
   canonical plans fail closed with `invalid_canonical_plan`, references
   match selection)
→ planned operations execute only through the Phase 10.41 dispatch path
→ planned workflow references execute only through DomainWorkflowExecutor
→ canonical replan on material capability/authority change
```

## Final workflow planning eligibility

A workflow may be selected for planning only if it is registered, active,
available, dependency-compatible, permission-compatible,
resource-compatible, and composition-compatible. Selection evaluates this
through the canonical `resolve_domain_workflow(...)` semantics (no second
resolver), modeled on the final most-restrictive planning authority of the
current attempt:

```text
required planning permission missing        → BLOCK (domain_workflow_unavailable)
required operation unavailable under the
  final exact-version authority              → BLOCK (domain_workflow_unavailable)
required resource outside the canonical
  planning request's resource references    → BLOCK (domain_workflow_unavailable)
required/supporting Domain outside the
  current effective composition             → BLOCK (domain_workflow_unavailable)
inactive / unregistered in the canonical
  workflow registry                         → BLOCK (domain_workflow_unavailable)
required INVOKE_SUBWORKFLOW child missing,
  disabled, or final-authority ineligible
  (recursively, version-exact, cycle-safe)  → BLOCK
                                              (domain_workflow_dependency_not_available)
optional operation or child unavailable     → skip its obligations; no parent block
required child handoff permission DENY       → BLOCK (domain_workflow_dependency_not_available)
approval outstanding but representable      → ALLOW + approval obligation
all constraints satisfied                   → ALLOW
```

The workflow's own approval gates are acknowledged inside the eligibility
inspection context solely so approval-pending status can never mask a
genuine unavailability. They are never treated as granted: outstanding
gates are projected into the canonical plan as approval obligations and
execution-time resolution revalidates everything inside
`DomainWorkflowExecutor`.

### Selected workflow graph obligations (V9)

`_required_subworkflow_closure_for_planning(...)` now inspects operation and
subworkflow permission branches throughout the selected graph. It uses the
canonical branch classification and reference lookup in `permission_adapters`.

For operation nodes, the exact ID/version must identify an enabled definition
under the final available/allowed/prohibited operation authority. Required
permissions are checked on that exact definition. Generic planner candidates
may use a different default version; that version's permission requirements
must not replace the selected node's version. An unavailable required operation
blocks before planning; an unavailable optional operation contributes no
obligations. `resolve_domain_workflow` uses the same required/optional distinction,
allowing the shared engine to skip an optional denied operation.

The existing `_operation_semantics` projection serves both planner-selected
operations and internal graph operations. The latter contribute only static
approval and validation obligations to the generic canonical request. Internal
operations are not expanded into new planner tasks or execution state.

Required child references resolve exactly through `InMemoryDomainWorkflowRegistry`
and are checked recursively under the same prepared permissions, operation
limits, resource references and effective composition. A repeated resolved
ID/version fails the branch closed. Eligible optional children contribute their
approval and validation obligations; missing, disabled, unavailable or denied
optional children contribute neither a parent block nor obligations.

When the executor has a permission gate, its read-only
`planning_permission_context`, `planning_operation_definitions` and
`planning_workflow_definitions` expose the existing policy evaluator, clock and
copies of the exact definitions that execution will revalidate. Planning must
not fill missing gate references from another registry. The existing definition
provider remains usable for static planning where no execution gate is wired;
an exact reference that cannot be established fails closed. A required
cross-domain child without the canonical policy context also fails closed.
These inspection methods do not issue gate decisions, create grants, consume
approvals, execute nodes or retain planning state.

`evaluate_domain_workflow_requirements` and `evaluate_domain_workflow_node`
keep policy decisions under the existing permission owner. Cross-domain child
invocations use the same `evaluate_subworkflow_handoff` helper as the canonical
node evaluator, which calls `DomainPermissionResolver.resolve_cross_domain`.
Source and target ownership come from registered definitions, including when
an ID prefix differs from its owning Domain. The original actor and explicit
resolution-context session are retained; when no session is supplied the
existing agent-run identity is used as the fallback.

Approval actions are obligations, never grants. Canonical cross-domain workflow
invocation uses `CrossDomainPermissionRequest.requires_approval=True`; therefore
an allowed handoff is represented as `APPROVAL_REQUIRED`, not converted to an
approval-free `ALLOW`. Runtime gate evaluation still owns context-bound approval
fingerprints and grant consumption. Plan approval nodes carry the canonical
action IDs through `approval_requirement_ids` and remain pending.

## Canonical workflow node planning classification

`WorkflowNodePermissionBranch` classifies the canonical operation, subworkflow,
approval and non-permissioned branches. The parity tests exhaust this enum and
compare connected planning with canonical decisions across every node type.

Every `WorkflowNodeType` member carries an explicit Phase 10.42 planning
classification, guarded by a dynamic enum-coverage test:

| Node type | Classification |
|---|---|
| `EXECUTE_OPERATION` | exact definition/version, required/optional eligibility, canonical permission decision, internal approval and validation projection |
| `REQUEST_APPROVAL` | workflow approval extraction (`_workflow_approval_ids`) |
| `INVOKE_SUBWORKFLOW` | exact child eligibility, canonical handoff and child permissions, required/optional aggregation and eligible child obligations |
| `WAIT_FOR_RESOURCE` / `LOAD_RESOURCE` | deferred runtime resource semantics; no canonical node-level resource identity — workflow resource obligations live only on `DomainWorkflowDefinition.required_resources` |
| `VALIDATE` | deferred runtime validation (`WorkflowEngine` evaluates node conditions fail-closed); planning validation obligations travel only through the canonical `required_validations` seam |
| `ASK_QUESTION` / `PAUSE` / `ESCALATE` | deferred runtime control flow (WorkflowEngine / Phase 9 runtime); no planning-time capability or approval field |
| `PROPOSE_MEMORY` / `UPDATE_SESSION` | deferred runtime state mutation owned by existing Phase 9/10 safeguards; no planning mutation authority |
| `SEARCH_KNOWLEDGE` / `RESOLVE_ENTITY` / `APPLY_PROFILE` / `REASON` / `DETECT_GAPS` / `EVALUATE_OUTCOME` | deferred runtime cognitive nodes; no separate planning authority |
| `COMPLETE` | terminal marker only; no capability authority |

Approval sources are never inferred from `node_id`, `name`, or free
metadata: the canonical extraction mirrors
`cmm.domains.permission_adapters` node decisions exactly (`approval_gate`
carriers and `REQUEST_APPROVAL` nodes, with the adapter's
`node.approval_gate or node.node_id` source identity).

## Approval obligation composition

Plan-wide required approvals are additive obligations composed from
canonical sources only:

```text
prepared required_approvals
  = incoming canonical required approvals
    ∪ global/composition Domain approval requirements
      (DomainPlanningCapabilityView.required_approval_ids)
    ∪ canonical approval obligations of selected workflows only
      (joined after selection: workflow-level approval_gates ∪ node-level
      approval sources — approval_gate carriers and REQUEST_APPROVAL nodes
      with the canonical `approval_gate or node_id` identity — ∪ the
      eligible child, internal operation and cross-domain obligations; deduplicated, stable
      order)
```

Approval gates of available-but-unselected workflows never enter the
prepared request and never create approval nodes. `required_approval_ids`
on the capability view carries only the global/composition component.
Operation-specific approval obligations keep flowing through the existing
exact-semantics projection (`requires_approval` plus traceable
`approval_requirement_ids` on canonical approval nodes). No approval is
ever synthesized as granted, and `WAITING_FOR_APPROVAL` is never conflated
with `UNAVAILABLE`.

## Most-restrictive composition rules

```text
prepared allowed
  = incoming allowed ∩ Domain available (or Domain available when unrestricted)
prepared prohibited
  = incoming prohibited ∪ Domain prohibited
prepared approvals
  = incoming ∪ Domain global/composition ∪ canonical approval obligations
    of selected workflows (workflow-level + node-level + required
    subworkflow closure; additive obligations, never removable; gates of
    available-but-unselected workflows are never included)
prepared validations
  = stable union (additive obligations, never removable)
prepared permissions
  = incoming ∩ Domain effective (never added)
prepared autonomy/budget
  = preserved exactly (never increased; missing Domain value invents nothing)
prepared metadata
  = incoming preserved + generic "workflow_references" IDs (restricted to
    workflows that pass full final planning eligibility: registry truth,
    prepared permissions, final operation candidates, resource references,
    and current composition),
    generic "operation_candidates" eligible IDs (sorted effective
    operations = prepared allowed minus prepared prohibited, further
    restricted to permission-compatible operations whose canonical
    required permissions are all present in the prepared effective
    permissions when exact operation requirements are known; empty when
    no capability is eligible and fails closed),
    generic "operation_semantics" descriptors, and generic
    "dependency_references" (operation pairs, workflow references,
    domain references) only
```

## Capability semantics projection

The Domain side projects canonical `DomainOperationDefinition` fields into
the generic `operation_semantics` seam for every available operation
(`DefaultDomainPlannerWorkflowIntegrator` with the injected
`operation_definition_provider`; unknown operations contribute no invented
semantics). Per-operation upstream dependencies flow through the generic
`dependency_references` seam (`operation_dependency_provider`), alongside
the capability-view workflow/domain dependency rows, so
`operation_dependency_ids` and `workflow_dependency_ids` are consumed by
planning rather than remaining inert. Required operation pairs whose
endpoints are not both planned never drop silently: the canonical planner
records them as `unresolved_operation_dependencies` plan metadata, the plan
is canonically INVALID, and the integration boundary blocks with
`domain_unresolved_operation_dependency`. Exact Domain approval/validation
requirement IDs stay traceable on canonical approval nodes
(`required_approvers`, `approval_requirement_ids` metadata) and validation
nodes (`validation_requirement_ids` metadata).

## Current-authority revalidation

Planning-time permission is not execution-time authorization. Approval
completion is not execution-time authorization. A stale plan never revives
stale authority:

- every operation is gated by the current `DomainPermissionGate` at actual
  dispatch time;
- every workflow reference re-resolves active definitions and current
  permission/dependency gates inside `DomainWorkflowExecutor`;
- permission downgrade, operation/workflow unavailability, impossible
  approvals, vanished dependencies, composition changes, and blocking
  conflicts drive canonical replanning through `AgentPlanningService.replan`
  (previous plan superseded; no Domain replanning engine; no plan-store
  writes from the integration boundary).

## Cross-domain constraints

Primary/supporting distinction, explicit dependency provenance,
most-restrictive authority, blocking-conflict propagation, and explicit
handoff are preserved from existing composition contracts. A supporting
Domain never expands primary/global authority; there is no silent authority
union and no second planner inside the cross-domain engine.

## Security invariants

```text
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
WORKFLOWS_TO_DOMAIN_IMPORTS=0

NO_PARALLEL_PLANNER=YES
NO_PARALLEL_WORKFLOW_ENGINE=YES
NO_PARALLEL_PLAN_STORE=YES
NO_PARALLEL_WORKFLOW_STORE=YES
NO_PARALLEL_PERMISSION_SYSTEM=YES
NO_PARALLEL_APPROVAL_SYSTEM=YES
NO_PARALLEL_VALIDATION_SYSTEM=YES
NO_PARALLEL_RUNTIME=YES
NO_PARALLEL_EVENT_BUS=YES
NO_PARALLEL_STATE_MACHINE=YES

DOMAIN_PERMISSION_CAN_ONLY_RESTRICT=YES
DOMAIN_APPROVAL_CANNOT_EXPAND_PERMISSION=YES
DOMAIN_VALIDATION_CANNOT_BE_BYPASSED=YES
STALE_DOMAIN_AUTHORITY_REUSED=NO

UNREGISTERED_OPERATION_EXECUTION=0
UNREGISTERED_WORKFLOW_EXECUTION=0
PROHIBITED_CAPABILITY_EXECUTION=0
```

## Tests

- Focused contracts:
  `tests/domains/test_domain_planner_workflow_integration_contracts.py`
- Capability projection, request composition, integration, delegation,
  replanning:
  `tests/domains/test_domain_planner_workflow_integration.py`
- Architecture/fragmentation boundaries:
  `tests/domains/test_domain_planner_workflow_boundaries.py`
- Connected acceptance:
  `tests/domains/test_domain_planner_workflow_dp042_acceptance.py`
  (`AT-DP-042=PASS`)
- Generic Phase 9 seam:
  `tests/agent_runtime/test_workflow_planner_adapter.py`
- Inherited acceptance stays green:
  `tests/domains/test_domain_agent_runtime_dp041_acceptance.py`
  (`AT-DP-041=PASS`)

## Operation Availability Authority Sourcing (V11)

Phase 10.42 V11 eliminates implicit positive authority defaults (`V10_MAJOR_15`).
Positive availability authority is never synthesized merely because a field is
absent from `AgentPlanningRequest.metadata` or integration request metadata.

Core invariants:
- **Omitted authority must never be broader than explicitly empty authority**:
  when availability authority fields (`capabilities`,
  `available_validation_policy_ids`, `available_rollback_policy_ids`,
  `denied_permissions`, `approval_status`, `approval_fingerprint`,
  `request_fingerprint`) are omitted from request metadata, they default strictly
  to fail-closed empty collections or `None`.
- **Every positive field has an auditable canonical source**: defined in
  `OPERATION_AVAILABILITY_CONTEXT_SOURCE_MATRIX` covering all 12 fields of
  `DomainOperationAvailabilityContext`. `may_positive_authority_be_synthesized`
  is `False` across every field.
- **Operation definitions are requirements, never availability grants**:
  `validation_policy_id`, `rollback_policy_id`, and `reversible=True` on
  `DomainOperationDefinition` declare constraints that execution/planning must
  satisfy; they do not grant capability or policy availability.

## Scope boundaries

Phase 10.42 does not implement Phase 10.43 (Validation System integration)
or Phase 10.44 (Memory / Knowledge Graph integration). Required validations
are discovered from existing declarations, represented in canonical plan
nodes, and never bypassed; broader validation-system ownership stays with
Phase 10.43.

V11 implementation evidence: Phase closure still requires Independent Re-Audit V11.
