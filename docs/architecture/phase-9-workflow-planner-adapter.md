# Phase 9.7 — Workflow Planner Adapter Architecture

## Overview & Responsabilidad

The **Workflow Planner Adapter** acts as the architectural bridge between Phase 9 autonomous agency context (`Goal`, `AgentRun`, `AgentCognitiveResult`, `ObservationSnapshot`, `InformationAcquisitionResult`) and the existing deterministic engineering `TaskPlanner`.

It translates high-level goal objectives, constraints, and cognitive analysis into an auditable `AgentWorkflowPlan` containing:
- Structured DAG of `AgentWorkflowTask`s and `AgentWorkflowDependency`s;
- Typed provider operations (`AgentWorkflowOperation`);
- Pre/post structural validation nodes (`AgentWorkflowValidationNode`);
- Explicit approval nodes (`AgentWorkflowApprovalNode`);
- Mid-workflow state checkpoints (`AgentWorkflowCheckpoint`);
- Declarative rollback (`AgentWorkflowRollbackStrategy`) and recovery (`AgentWorkflowRecoveryStrategy`) strategies;
- Estimated budget metrics (`AgentWorkflowBudgetEstimate`), identified risks (`AgentWorkflowRisk`), and assumptions (`AgentWorkflowAssumption`).

## Límites (Design Boundaries)

The Workflow Planner Adapter MUST NOT:
1. Implement its own alternative graph planning logic or edit DAG nodes outside the existing `TaskPlanner`;
2. Execute any tasks, operations, commands, or validation scripts;
3. Evaluate definitive policy decisions (delegated to 9.8 Policy Engine);
4. Approve actions or consume live budgets (delegated to 9.10 Approval System & 9.11 Action Budget);
5. Mutate the underlying `Goal` or `AgentRun` entities.

## Contratos Principales

- `AgentPlanningRequest`: Audit-ready input specifying goal ID, run ID, objective, constraints, knowledge/resource IDs, allowed/prohibited operations, policies, and timeout.
- `AgentPlanningContext`: Immutable snapshot encapsulating exact context supplied to the planner.
- `AgentWorkflowPlan`: Auditable plan output containing tasks, dependencies, operations, validations, approvals, checkpoints, version, and confidence score.
- `AgentWorkflowTask`: Individual DAG node with inputs, expected outputs, criteria, and mapped operations.
- `AgentWorkflowDependency`: Directed dependency edge between tasks enforcing strict topological order.
- `AgentWorkflowOperation`: Atomic typed operation specification referencing registered provider capabilities.
- `AgentWorkflowValidationNode`: Structural/contractual validation check node.
- `AgentWorkflowApprovalNode`: Approval node representing required authorization checkpoints for risky steps.
- `AgentWorkflowCheckpoint`: State savepoint specification for recovery and rollback.
- `AgentWorkflowRollbackStrategy` & `AgentWorkflowRecoveryStrategy`: Declarative failure mitigation policies.
- `AgentWorkflowPlanValidation`: Structural validation report detailing blocking errors and warnings.
- `AgentWorkflowPlanVersion`: Version record preserving immutable lineage upon replanning.
- `AgentReplanningRequest` & `AgentReplanningResult`: Re-evaluation contracts for versioned replanning.

## Integración con el Planner Existente

`DefaultWorkflowPlannerAdapter` invokes `TaskPlanner.create_plan(objective)` using the goal objective. It translates the resulting `ExecutionPlan` steps (`PlanStep`) into `AgentWorkflowTask` and `AgentWorkflowOperation` entries, preserving entry points, impacted components, and step order while decorating them with Phase 9 agency metadata.

## DAG, Validaciones y Checkpoints

- **DAG**: Sequential or branching dependencies are registered via `AgentWorkflowDependency`. Cycles and self-dependencies are strictly prohibited and caught by Kahn's topological sort algorithm in `AgentWorkflowPlanValidator`.
- **Validations**: Pre-step, post-step, and workflow-end validation nodes enforce contractual compliance.
- **Checkpoints & Rollback**: Reversible or high-risk operations generate checkpoints and declare step-by-step or full-revert rollback strategies.

## Validación Estructural (`AgentWorkflowPlanValidator`)

Deterministic validation verifying 25 structural rules including:
1. Non-empty mandatory IDs;
2. Positive versions and confidence range `[0.0, 1.0]`;
3. Node ID uniqueness across all plan components;
4. Reference integrity for dependencies, operations, and validations;
5. Topological acyclicity (no graph cycles);
6. Operation registry check (all operations registered);
7. `allowed_operations` and `prohibited_operations` enforcement;
8. Positive timeout and non-negative budget parameters.

## Replanning & Store de Versiones (`InMemoryWorkflowPlanStore`)

When replanning is requested (due to goal change, new information, or operation/validation failure):
- A new `AgentWorkflowPlan` instance is generated with `version = previous.version + 1`;
- `previous_version_id` points to the prior plan version;
- The prior plan is marked as `SUPERSEDED` in `InMemoryWorkflowPlanStore` without altering its past contents;
- Full traceability and evidence history are retained.

## Errores y Seguridad

Hierarchy under `WorkflowPlannerAdapterError`:
- `InvalidAgentPlanningContractError`
- `PlannerUnavailableError`
- `PlannerExecutionError`
- `PlannerResultTranslationError`
- `WorkflowPlanValidationError`
- `WorkflowPlanCycleError`
- `WorkflowOperationNotRegisteredError`
- `WorkflowOperationNotAllowedError`
- `WorkflowOperationProhibitedError`
- `WorkflowPlanVersionError`
- `WorkflowReplanningError`

## Relación con Fases Posteriores

- **9.8 Policy Engine**: Consumes `AgentWorkflowPlan` to evaluate step-by-step authorization;
- **9.10 Human Approval System**: Processes pending `AgentWorkflowApprovalNode` entries;
- **9.11 Action Budget**: Tracks and enforces `AgentWorkflowBudgetEstimate` limits during execution;
- **9.12 Runtime Loop & 9.13 Execution Adapter**: Dispatches `AgentWorkflowTask` and `AgentWorkflowOperation` instances;
- **9.14 Validation Integration**: Executes `AgentWorkflowValidationNode` checks post-step.

## Ejemplo de Uso

```python
from cmm.agent_runtime import (
    AgentPlanningRequest,
    AgentPlanningService,
    DefaultWorkflowPlannerAdapter,
    InMemoryGoalRepository,
)
from cmm.planner import TaskPlanner

# Initialize adapter & service
planner = TaskPlanner(reasoner=my_reasoner)
adapter = DefaultWorkflowPlannerAdapter(planner=planner, goal_repository=my_goal_repo)
service = AgentPlanningService(adapter=adapter)

# Planning request
request = AgentPlanningRequest(
    id="plan-req-001",
    goal_id="goal-123",
    agent_run_id="run-456",
    objective="Refactor technical reasoning module",
    allowed_operations=["python.find_symbol", "python.list_imports", "filesystem.read_file"],
)

# Produce plan
plan = service.plan(request)
print(f"Plan status: {plan.status.value}, tasks count: {len(plan.tasks)}")
```
