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
→ explicit workflow selection (requested ∩ available; absent requested fails closed)
→ most-restrictive AgentPlanningRequest preparation
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

## Most-restrictive composition rules

```text
prepared allowed
  = incoming allowed ∩ Domain available (or Domain available when unrestricted)
prepared prohibited
  = incoming prohibited ∪ Domain prohibited
prepared approvals/validations
  = stable union (additive obligations, never removable)
prepared permissions
  = incoming ∩ Domain effective (never added)
prepared autonomy/budget
  = preserved exactly (never increased; missing Domain value invents nothing)
prepared metadata
  = incoming preserved + generic "workflow_references" IDs,
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

## Scope boundaries

Phase 10.42 does not implement Phase 10.43 (Validation System integration)
or Phase 10.44 (Memory / Knowledge Graph integration). Required validations
are discovered from existing declarations, represented in canonical plan
nodes, and never bypassed; broader validation-system ownership stays with
Phase 10.43.
