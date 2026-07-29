"""Phase 9.7 – Workflow Planner Structural Validator.

Deterministic structural validator for AgentWorkflowPlan contracts.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import (
    WorkflowPlanRisk,
    WorkflowPlanValidationStatus,
)
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentPlanningWarning,
    AgentWorkflowPlan,
    AgentWorkflowPlanValidation,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentWorkflowPlanValidator:
    """Deterministic structural validator for AgentWorkflowPlan instance validation."""

    def __init__(self, operation_registry: Any | None = None) -> None:
        """Initialize with an optional operation registry facade or list of allowed ops."""
        self._operation_registry = operation_registry

    def validate(
        self,
        plan: AgentWorkflowPlan,
        request: AgentPlanningRequest | None = None,
        allowed_operations_override: list[str] | None = None,
        prohibited_operations_override: list[str] | None = None,
    ) -> AgentWorkflowPlanValidation:
        """Validate structural, contractual, operational, and topological invariants of ``plan``."""
        blocking_errors: list[str] = []
        warnings: list[AgentPlanningWarning] = []
        findings: list[dict[str, Any]] = []

        # 1. Mandatory IDs
        if not plan.id or not isinstance(plan.id, str):
            blocking_errors.append("Plan id must be a non-empty string.")
        if not plan.goal_id or not isinstance(plan.goal_id, str):
            blocking_errors.append("Plan goal_id must be a non-empty string.")
        if not plan.agent_run_id or not isinstance(plan.agent_run_id, str):
            blocking_errors.append("Plan agent_run_id must be a non-empty string.")
        if not plan.workflow_id or not isinstance(plan.workflow_id, str):
            blocking_errors.append("Plan workflow_id must be a non-empty string.")

        # 2. Positive version
        if plan.version <= 0:
            blocking_errors.append(
                f"Plan version must be positive integer (got {plan.version})."
            )

        # 3. Confidence range [0.0, 1.0]
        if not (0.0 <= plan.confidence <= 1.0):
            blocking_errors.append(
                f"Plan confidence must be between 0.0 and 1.0 (got {plan.confidence})."
            )

        # 4. Unique IDs across nodes
        seen_ids: set[str] = set()
        task_ids: set[str] = set()
        op_ids: set[str] = set()
        val_ids: set[str] = set()
        appr_ids: set[str] = set()
        chk_ids: set[str] = set()

        for t in plan.tasks:
            if t.id in seen_ids:
                blocking_errors.append(f"Duplicate task id: {t.id}")
            seen_ids.add(t.id)
            task_ids.add(t.id)

        for op in plan.operations:
            if op.id in seen_ids:
                blocking_errors.append(f"Duplicate operation id: {op.id}")
            seen_ids.add(op.id)
            op_ids.add(op.id)

        for val_node in plan.validation_nodes:
            if val_node.id in seen_ids:
                blocking_errors.append(f"Duplicate validation node id: {val_node.id}")
            seen_ids.add(val_node.id)
            val_ids.add(val_node.id)

        for appr_node in plan.approval_nodes:
            if appr_node.id in seen_ids:
                blocking_errors.append(f"Duplicate approval node id: {appr_node.id}")
            seen_ids.add(appr_node.id)
            appr_ids.add(appr_node.id)

        for chk in plan.checkpoints:
            if chk.id in seen_ids:
                blocking_errors.append(f"Duplicate checkpoint id: {chk.id}")
            seen_ids.add(chk.id)
            chk_ids.add(chk.id)

        # 5. Valid references
        for dep in plan.dependencies:
            if dep.source_task_id not in task_ids:
                blocking_errors.append(
                    f"Dependency {dep.id} references non-existent source task: {dep.source_task_id}"
                )
            if dep.target_task_id not in task_ids:
                blocking_errors.append(
                    f"Dependency {dep.id} references non-existent target task: {dep.target_task_id}"
                )

        for op in plan.operations:
            if op.task_id not in task_ids:
                blocking_errors.append(
                    f"Operation {op.id} references non-existent task_id: {op.task_id}"
                )

        for val_node in plan.validation_nodes:
            if (
                val_node.related_id
                and val_node.related_id not in task_ids
                and val_node.related_id not in op_ids
            ):
                warnings.append(
                    AgentPlanningWarning(
                        code="UNRESOLVED_VALIDATION_REF",
                        message=f"Validation node {val_node.id} references unknown target: {val_node.related_id}",
                        node_id=val_node.id,
                    )
                )

        for appr_node in plan.approval_nodes:
            if (
                appr_node.related_id
                and appr_node.related_id not in task_ids
                and appr_node.related_id not in op_ids
            ):
                warnings.append(
                    AgentPlanningWarning(
                        code="UNRESOLVED_APPROVAL_REF",
                        message=f"Approval node {appr_node.id} references unknown target: {appr_node.related_id}",
                        node_id=appr_node.id,
                    )
                )

        # 6 & 7. Cycle detection & Topological sort
        graph: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {t_id: 0 for t_id in task_ids}

        for dep in plan.dependencies:
            if dep.source_task_id in task_ids and dep.target_task_id in task_ids:
                graph[dep.source_task_id].append(dep.target_task_id)
                in_degree[dep.target_task_id] += 1

        queue = deque([t_id for t_id, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count < len(task_ids):
            blocking_errors.append("Circular dependency detected in plan DAG.")

        # 8, 9, 10. Operation checks (Registered, Allowed, Prohibited)
        allowed_ops = allowed_operations_override
        if allowed_ops is None and request:
            allowed_ops = request.allowed_operations

        prohibited_ops = prohibited_operations_override
        if prohibited_ops is None and request:
            prohibited_ops = request.prohibited_operations

        for op in plan.operations:
            op_name = op.operation_name

            # 8. Check registration if registry provided
            if self._operation_registry is not None:
                is_registered = False
                if isinstance(self._operation_registry, (list, set, tuple)):
                    is_registered = op_name in self._operation_registry
                elif hasattr(self._operation_registry, "supports_operation_name"):
                    is_registered = self._operation_registry.supports_operation_name(
                        op_name
                    )
                elif hasattr(self._operation_registry, "all"):
                    executors = self._operation_registry.all()
                    registered_names = {
                        getattr(e, "name", str(getattr(e, "operation_type", "")))
                        for e in executors
                    }
                    is_registered = op_name in registered_names or any(
                        op_name in str(e) for e in executors
                    )
                elif hasattr(self._operation_registry, "__contains__"):
                    is_registered = op_name in self._operation_registry
                else:
                    is_registered = True  # Fallback if registry format unrecognized

                if not is_registered:
                    blocking_errors.append(
                        f"Operation '{op_name}' (id: {op.id}) is not registered in OperationRegistry."
                    )

            # 9. Check allowed operations
            if allowed_ops and len(allowed_ops) > 0 and op_name not in allowed_ops:
                blocking_errors.append(
                    f"Operation '{op_name}' (id: {op.id}) is not in allowed_operations."
                )

            # 10. Check prohibited operations
            if prohibited_ops and op_name in prohibited_ops:
                blocking_errors.append(
                    f"Operation '{op_name}' (id: {op.id}) is in prohibited_operations."
                )

        # 14 & 21. Success & Completion Criteria
        if not plan.completion_criteria:
            warnings.append(
                AgentPlanningWarning(
                    code="NO_COMPLETION_CRITERIA",
                    message="Plan does not explicitly declare completion_criteria.",
                )
            )

        # 16. Approvals required for high/critical risk or flagged ops
        for op in plan.operations:
            if op.requires_approval or op.risk in (
                WorkflowPlanRisk.HIGH,
                WorkflowPlanRisk.CRITICAL,
            ):
                # Check if approval node exists for this operation or its task
                has_appr = any(
                    a.related_id in (op.id, op.task_id) for a in plan.approval_nodes
                )
                if not has_appr:
                    warnings.append(
                        AgentPlanningWarning(
                            code="MISSING_APPROVAL_NODE",
                            message=f"Operation {op.id} with risk {op.risk.value} lacks explicit approval node.",
                            node_id=op.id,
                        )
                    )

        # 18. Rollback for reversible or high risk operations
        for op in plan.operations:
            if (
                op.reversible
                or op.risk in (WorkflowPlanRisk.HIGH, WorkflowPlanRisk.CRITICAL)
            ) and (not plan.rollback_strategy or not plan.rollback_strategy.available):
                warnings.append(
                    AgentPlanningWarning(
                        code="MISSING_ROLLBACK_STRATEGY",
                        message=f"Operation {op.id} is reversible or risky but plan has no active rollback strategy.",
                        node_id=op.id,
                    )
                )

        # 19. Timeout positive
        if plan.timeout_seconds is not None and plan.timeout_seconds <= 0:
            blocking_errors.append(
                f"Plan timeout_seconds must be positive (got {plan.timeout_seconds})."
            )

        # 20. Budget non-negative
        if plan.estimated_budget:
            b = plan.estimated_budget
            if (
                b.estimated_tokens < 0
                or b.estimated_cost < 0
                or b.estimated_duration_seconds < 0
            ):
                blocking_errors.append(
                    "Estimated budget parameters cannot be negative."
                )

        # Determine validation status
        if blocking_errors:
            status = WorkflowPlanValidationStatus.FAILED
            is_valid = False
        elif warnings:
            status = WorkflowPlanValidationStatus.PASSED_WITH_WARNINGS
            is_valid = True
        else:
            status = WorkflowPlanValidationStatus.PASSED
            is_valid = True

        for err in blocking_errors:
            findings.append({"severity": "error", "message": err})
        for w in warnings:
            findings.append(
                {
                    "severity": "warning",
                    "code": w.code,
                    "message": w.message,
                    "node_id": w.node_id,
                }
            )

        return AgentWorkflowPlanValidation(
            status=status,
            is_valid=is_valid,
            blocking_errors=blocking_errors,
            warnings=warnings,
            findings=findings,
            validated_at=_utc_now_iso(),
            metadata={},
        )
