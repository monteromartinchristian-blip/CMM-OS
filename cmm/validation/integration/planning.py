"""Planner System Validation Adapter for CMM OS (Subphase 7.13).

Integrates continuous validation nodes into planning graphs and DAG execution plans.
Provides node validation, cycle detection, and execution helpers.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..interfaces.application import ValidationApplicationService
from ..policy import (
    _POLICY_ALIASES,
    DEFAULT_VALIDATION_POLICIES,
    canonical_validation_policy_name,
)
from .contracts import (
    ValidationAction,
    ValidationDecision,
    ValidationIntegrationResult,
    ValidationPhase,
    ValidationPlanNode,
)


class PlannerValidationError(ValueError):
    """Raised when a validation plan node graph is invalid or malformed."""


class PlannerValidationAdapter:
    """Adapter for integrating validation nodes into planner DAGs and execution plans."""

    def __init__(
        self,
        application_service: ValidationApplicationService | None = None,
        known_policies: Sequence[str] | None = None,
    ) -> None:
        self._application_service = application_service
        pol_set = set(known_policies or DEFAULT_VALIDATION_POLICIES.keys())
        pol_set.update(_POLICY_ALIASES.keys())
        pol_set.update(_POLICY_ALIASES.values())
        pol_set.update(
            {"default", "fast_static_only", "fast_static", "structural_only"}
        )
        for p in list(pol_set):
            canon = canonical_validation_policy_name(p)
            if canon:
                pol_set.add(canon)
        self._known_policies = pol_set

    def validate_plan_nodes(self, nodes: Sequence[ValidationPlanNode]) -> None:
        """Validate a collection of ValidationPlanNode objects for structural correctness.

        Checks:
        1. Unique node IDs
        2. Known policies (if policy_name is specified)
        3. Valid on_pass and on_failure actions
        4. Valid dependencies (no reference to missing node IDs)
        5. Cycle detection (no circular dependencies among nodes)
        """
        node_map: dict[str, ValidationPlanNode] = {}
        for node in nodes:
            if node.id in node_map:
                raise PlannerValidationError(
                    f"Duplicate ValidationPlanNode ID '{node.id}'"
                )
            node_map[node.id] = node

            if node.policy_name:
                canonical = canonical_validation_policy_name(node.policy_name)
                if (
                    node.policy_name not in self._known_policies
                    and canonical not in self._known_policies
                ):
                    raise PlannerValidationError(
                        f"Unknown validation policy '{node.policy_name}' in node '{node.id}'"
                    )

            if not isinstance(node.on_pass, ValidationAction):
                raise PlannerValidationError(
                    f"Invalid on_pass action '{node.on_pass}' in node '{node.id}'"
                )
            if not isinstance(node.on_failure, ValidationAction):
                raise PlannerValidationError(
                    f"Invalid on_failure action '{node.on_failure}' in node '{node.id}'"
                )

        # Validate dependency existence
        for node in nodes:
            for dep_id in node.depends_on:
                if dep_id not in node_map:
                    raise PlannerValidationError(
                        f"Node '{node.id}' depends on non-existent node '{dep_id}'"
                    )

        # Cycle detection using DFS
        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(node_id: str) -> None:
            visited.add(node_id)
            in_stack.add(node_id)

            for dep in node_map[node_id].depends_on:
                if dep not in visited:
                    dfs(dep)
                elif dep in in_stack:
                    raise PlannerValidationError(
                        f"Cycle detected in ValidationPlanNode dependencies involving '{node_id}' -> '{dep}'"
                    )

            in_stack.remove(node_id)

        for node_id in node_map:
            if node_id not in visited:
                dfs(node_id)

    def execute_plan_node(
        self,
        node: ValidationPlanNode,
        project_root: Path | str,
        changed_files: Sequence[Path | str] = (),
        workflow_id: str | None = None,
        actor: str = "planner",
    ) -> ValidationIntegrationResult:
        """Execute continuous validation for a single plan node."""
        root = Path(project_root).resolve(strict=False)

        if self._application_service is None:
            decision = ValidationDecision(
                validation_id=f"plan-node-{node.id}-skipped",
                status="passed",
                allowed_to_continue=True,
                recommended_action=node.on_pass,
                reasons=("Application service absent; plan node validation skipped",),
            )
            return ValidationIntegrationResult(decision=decision)

        # Build integration request using coordinator or application service directly
        from .execution import ExecutionValidationCoordinator

        coord = ExecutionValidationCoordinator(self._application_service)
        result = coord.validate_post_execution(
            project_root=root,
            changed_files=changed_files,
            policy_name=node.policy_name or "default",
            workflow_id=workflow_id,
            actor=actor,
            metadata={"plan_node_id": node.id, **dict(node.metadata)},
        )

        # Override decision action based on node rules
        d = result.decision
        action = node.on_pass if d.allowed_to_continue else node.on_failure
        updated_decision = ValidationDecision(
            validation_id=d.validation_id,
            status=d.status,
            allowed_to_continue=d.allowed_to_continue,
            recommended_action=action,
            reasons=d.reasons,
            blocking_findings=d.blocking_findings,
            warnings=d.warnings,
            gate_result=d.gate_result,
            requires_rollback=action == ValidationAction.ROLLBACK,
            requires_user_input=action
            in (ValidationAction.ASK_USER, ValidationAction.ESCALATE),
            retryable=d.retryable,
            metadata=dict(d.metadata),
        )

        return ValidationIntegrationResult(
            decision=updated_decision,
            validation_result=result.validation_result,
            gate_result=result.gate_result,
            metadata=result.metadata,
        )

    def inject_validation_nodes(
        self,
        plan_nodes: Sequence[dict[str, Any]],
        policy_name: str = "default",
    ) -> list[dict[str, Any]]:
        """Helper to inject validation nodes after mutating operation nodes in plan structures."""
        augmented: list[dict[str, Any]] = []

        for idx, item in enumerate(plan_nodes):
            augmented.append(item)
            item_id = str(item.get("id", f"step_{idx}"))
            is_mutating = bool(item.get("mutating", True))

            if is_mutating:
                val_node = ValidationPlanNode(
                    id=f"val_{item_id}",
                    phase=ValidationPhase.AFTER_EXECUTION,
                    policy_name=policy_name,
                    depends_on=(item_id,),
                    on_pass=ValidationAction.CONTINUE,
                    on_failure=ValidationAction.ROLLBACK,
                )
                augmented.append(val_node.serialize())

        return augmented
