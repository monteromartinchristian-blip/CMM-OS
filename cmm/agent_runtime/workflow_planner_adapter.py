"""Phase 9.7 – Workflow Planner Adapter & Agent Planning Service.

Adapts autonomous goal reasoning context to existing deterministic TaskPlanner contracts
and produces auditable AgentWorkflowPlans without executing work or mutating runtime state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentPlanningDecision,
    AgentPlanningStatus,
    WorkflowPlanNodeKind,
    WorkflowPlanRisk,
    WorkflowPlanStatus,
    WorkflowPlanValidationStatus,
)
from cmm.agent_runtime.errors import (
    InvalidAgentPlanningContractError,
    PlannerExecutionError,
    PlannerResultTranslationError,
    PlannerUnavailableError,
    WorkflowReplanningError,
)
from cmm.agent_runtime.goal_contracts import Goal
from cmm.agent_runtime.goal_repository import GoalRepository
from cmm.agent_runtime.observation_contracts import ObservationSnapshot
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningContext,
    AgentPlanningRequest,
    AgentReplanningRequest,
    AgentReplanningResult,
    AgentWorkflowApprovalNode,
    AgentWorkflowAssumption,
    AgentWorkflowBudgetEstimate,
    AgentWorkflowCheckpoint,
    AgentWorkflowDependency,
    AgentWorkflowOperation,
    AgentWorkflowPlan,
    AgentWorkflowPlanValidation,
    AgentWorkflowRecoveryStrategy,
    AgentWorkflowRisk,
    AgentWorkflowRollbackStrategy,
    AgentWorkflowTask,
    AgentWorkflowValidationNode,
    generate_planning_context_id,
    generate_workflow_approval_node_id,
    generate_workflow_checkpoint_id,
    generate_workflow_dependency_id,
    generate_workflow_id,
    generate_workflow_operation_id,
    generate_workflow_plan_id,
    generate_workflow_task_id,
    generate_workflow_validation_node_id,
)
from cmm.agent_runtime.workflow_planner_store import InMemoryWorkflowPlanStore
from cmm.agent_runtime.workflow_planner_validator import AgentWorkflowPlanValidator
from cmm.planner.task_planner import ExecutionPlan, TaskPlanner


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowPlannerAdapter(Protocol):
    """Protocol for translating autonomous planning requests into AgentWorkflowPlans."""

    def plan(self, request: AgentPlanningRequest) -> AgentWorkflowPlan:
        """Create a structured workflow plan for ``request``."""

    def replan(self, request: AgentReplanningRequest) -> AgentReplanningResult:
        """Re-evaluate and version an existing workflow plan."""


class DefaultWorkflowPlannerAdapter:
    """Default implementation of WorkflowPlannerAdapter translating context to TaskPlanner."""

    def __init__(
        self,
        planner: TaskPlanner | None = None,
        goal_repository: GoalRepository | None = None,
        agent_run_provider: Callable[[str], AgentRun | None] | None = None,
        cognitive_result_provider: Callable[[str], Any | None] | None = None,
        snapshot_provider: Callable[[str], ObservationSnapshot | None] | None = None,
        operation_registry: Any | None = None,
        plan_store: InMemoryWorkflowPlanStore | None = None,
        validator: AgentWorkflowPlanValidator | None = None,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._planner = planner
        self._goal_repository = goal_repository
        self._agent_run_provider = agent_run_provider
        self._cognitive_result_provider = cognitive_result_provider
        self._snapshot_provider = snapshot_provider
        self._operation_registry = operation_registry
        self._plan_store = plan_store or InMemoryWorkflowPlanStore()
        self._validator = validator or AgentWorkflowPlanValidator(
            operation_registry=operation_registry
        )
        self._clock = clock or _utc_now_iso
        self._id_factory = id_factory

    def build_context(self, request: AgentPlanningRequest) -> AgentPlanningContext:
        """Construct the immutable planning context delivered to the Planner."""
        if not isinstance(request, AgentPlanningRequest):
            raise InvalidAgentPlanningContractError(
                "Invalid request: must be AgentPlanningRequest."
            )

        goal_obj: Goal | None = None
        if self._goal_repository and request.goal_id:
            try:
                if hasattr(self._goal_repository, "get"):
                    goal_obj = self._goal_repository.get(request.goal_id)
                elif hasattr(self._goal_repository, "get_by_id"):
                    goal_obj = self._goal_repository.get_by_id(request.goal_id)
            except (KeyError, ValueError, RuntimeError, AttributeError):
                goal_obj = None

        agent_run_obj: AgentRun | None = None
        if self._agent_run_provider and request.agent_run_id:
            try:
                agent_run_obj = self._agent_run_provider(request.agent_run_id)
            except (KeyError, ValueError, RuntimeError, AttributeError):
                agent_run_obj = None

        obs_snapshot_obj: ObservationSnapshot | None = None
        if self._snapshot_provider and request.observation_snapshot_id:
            try:
                obs_snapshot_obj = self._snapshot_provider(
                    request.observation_snapshot_id
                )
            except (KeyError, ValueError, RuntimeError, AttributeError):
                obs_snapshot_obj = None

        ctx_id = generate_planning_context_id()
        objective = request.objective or (goal_obj.objective if goal_obj else "")

        return AgentPlanningContext(
            id=ctx_id,
            request_id=request.id,
            goal=goal_obj,
            agent_run=agent_run_obj,
            objective=objective,
            success_criteria=list(request.success_criteria),
            constraints=list(request.constraints),
            requirements=list(request.requirements),
            observation_snapshot=obs_snapshot_obj,
            relevant_facts=[],
            cognitive_recommendations=[],
            accepted_gaps=[],
            assumptions=[
                "Goal objective is actionable and reachable with registered operations."
            ],
            resources=list(request.resource_ids),
            knowledge_ids=list(request.relevant_knowledge_ids),
            allowed_operations=list(request.allowed_operations),
            prohibited_operations=list(request.prohibited_operations),
            permissions=list(request.permissions),
            nominal_policies={"validation_policy": request.validation_policy},
            budget_estimate=dict(request.budget),
            timeout_seconds=request.timeout_seconds,
            metadata=dict(request.metadata),
            created_at=self._clock(),
        )

    def plan(self, request: AgentPlanningRequest) -> AgentWorkflowPlan:
        """Create an AgentWorkflowPlan for the given request using existing TaskPlanner."""
        if not isinstance(request, AgentPlanningRequest):
            raise InvalidAgentPlanningContractError(
                "Request must be instance of AgentPlanningRequest."
            )

        context = self.build_context(request)

        # Check for complete_without_workflow condition
        cognitive_res = None
        if self._cognitive_result_provider and request.cognitive_result_id:
            cognitive_res = self._cognitive_result_provider(request.cognitive_result_id)

        cognitive_decision = getattr(cognitive_res, "decision", None)
        is_already_satisfied = (
            context.goal
            and context.goal.status.value in ("completed", "partially_completed")
        ) or cognitive_decision in (
            "complete_without_action",
            "COMPLETE_WITHOUT_ACTION",
        )

        if is_already_satisfied:
            # Produce completion plan without invoking planner
            wf_id = generate_workflow_id()
            plan_id = generate_workflow_plan_id()
            now = self._clock()

            plan = AgentWorkflowPlan(
                id=plan_id,
                goal_id=request.goal_id,
                agent_run_id=request.agent_run_id,
                workflow_id=wf_id,
                version=1,
                status=WorkflowPlanStatus.COMPLETED,
                objective=context.objective,
                scope=["No action required"],
                tasks=[],
                dependencies=[],
                operations=[],
                validation_nodes=[],
                approval_nodes=[],
                checkpoints=[],
                completion_criteria=["Goal already satisfied"],
                assumptions=[
                    AgentWorkflowAssumption(
                        id="assump-satisfied",
                        statement="Goal objective is already satisfied prior to execution.",
                        validated=True,
                    )
                ],
                confidence=1.0,
                validation=AgentWorkflowPlanValidation(
                    status=WorkflowPlanValidationStatus.PASSED,
                    is_valid=True,
                    validated_at=now,
                ),
                created_at=now,
                updated_at=now,
                metadata={
                    "decision": AgentPlanningDecision.COMPLETE_WITHOUT_WORKFLOW.value
                },
            )
            self._plan_store.add(plan)
            return plan

        # Planner invocation
        if self._planner is None:
            raise PlannerUnavailableError(
                "TaskPlanner instance is not configured in adapter."
            )

        objective_text = context.objective
        if not objective_text.strip():
            raise PlannerExecutionError(
                "Goal objective is empty; cannot invoke TaskPlanner."
            )

        try:
            exec_plan: ExecutionPlan = self._planner.create_plan(objective_text)
        except Exception as err:
            raise PlannerExecutionError(f"TaskPlanner execution failed: {err}") from err

        if not isinstance(exec_plan, ExecutionPlan):
            raise PlannerResultTranslationError(
                "TaskPlanner did not return a valid ExecutionPlan."
            )

        # Translate ExecutionPlan to AgentWorkflowPlan
        wf_plan = self.translate_plan(exec_plan, request, context)

        # Structural Validation
        val_result = self._validator.validate(wf_plan, request=request)

        # Update status according to validation
        if not val_result.is_valid:
            status = WorkflowPlanStatus.INVALID
        elif val_result.status == WorkflowPlanValidationStatus.PASSED_WITH_WARNINGS:
            status = WorkflowPlanStatus.VALID
        else:
            status = WorkflowPlanStatus.VALID

        final_plan = AgentWorkflowPlan.from_dict(
            {
                **wf_plan.to_dict(),
                "status": status.value,
                "validation": val_result.to_dict(),
                "updated_at": self._clock(),
            }
        )

        self._plan_store.add(final_plan)
        return final_plan

    def translate_plan(
        self,
        exec_plan: ExecutionPlan,
        request: AgentPlanningRequest,
        context: AgentPlanningContext | None = None,
    ) -> AgentWorkflowPlan:
        """Translate existing TaskPlanner's ExecutionPlan to AgentWorkflowPlan."""
        context = context or self.build_context(request)
        wf_id = generate_workflow_id()
        plan_id = generate_workflow_plan_id()
        now = self._clock()

        tasks: list[AgentWorkflowTask] = []
        dependencies: list[AgentWorkflowDependency] = []
        operations: list[AgentWorkflowOperation] = []
        validation_nodes: list[AgentWorkflowValidationNode] = []
        approval_nodes: list[AgentWorkflowApprovalNode] = []
        checkpoints: list[AgentWorkflowCheckpoint] = []

        prev_task_id: str | None = None

        # Map steps from ExecutionPlan to AgentWorkflowTask & Operations
        for step in exec_plan.steps:
            t_id = generate_workflow_task_id()
            op_id = generate_workflow_operation_id()
            val_node_id = generate_workflow_validation_node_id()

            # Determine operation name and parameters based on step title
            step_title_lower = step.title.lower()
            if "entry point" in step_title_lower or "analyze" in step_title_lower:
                op_name = "python.find_symbol"
            elif "dependenc" in step_title_lower:
                op_name = "python.list_imports"
            elif "impact" in step_title_lower or "risk" in step_title_lower:
                op_name = "python.describe_module"
            elif "prepare" in step_title_lower or "modif" in step_title_lower:
                op_name = "filesystem.read_file"
            else:
                op_name = "filesystem.exists"

            # Check for allowed / prohibited restrictions
            op_risk = WorkflowPlanRisk.LOW
            if "modif" in step_title_lower or "prepare" in step_title_lower:
                op_risk = WorkflowPlanRisk.MEDIUM

            # Operation definition
            operation = AgentWorkflowOperation(
                id=op_id,
                task_id=t_id,
                operation_name=op_name,
                parameters={"target": getattr(exec_plan, "goal", "")},
                expected_effects=[f"Execute step: {step.title}"],
                reversible=True,
                rollback_operation=f"{op_name}.revert"
                if op_risk != WorkflowPlanRisk.NONE
                else None,
                risk=op_risk,
                metadata={"plan_step_order": step.order, "rationale": step.rationale},
            )
            operations.append(operation)

            # Validation node for post-step check
            val_node = AgentWorkflowValidationNode(
                id=val_node_id,
                workflow_id=wf_id,
                policy=request.validation_policy,
                timing="post",
                required=True,
                blocking=True,
                related_id=t_id,
                expected_result="passed",
            )
            validation_nodes.append(val_node)

            # Approval node if requested or high risk
            if request.required_approvals or op_risk in (
                WorkflowPlanRisk.HIGH,
                WorkflowPlanRisk.CRITICAL,
            ):
                appr_id = generate_workflow_approval_node_id()
                approval_nodes.append(
                    AgentWorkflowApprovalNode(
                        id=appr_id,
                        workflow_id=wf_id,
                        reason=f"Approval required for step: {step.title}",
                        risk=op_risk,
                        related_id=t_id,
                        pending=True,
                    )
                )

            # Task definition
            task = AgentWorkflowTask(
                id=t_id,
                workflow_id=wf_id,
                name=step.title,
                description=step.description,
                kind=WorkflowPlanNodeKind.TASK,
                status="pending",
                dependency_ids=[prev_task_id] if prev_task_id else [],
                operation_ids=[op_id],
                validation_node_ids=[val_node_id],
                inputs={"goal": exec_plan.goal},
                expected_outputs={"result": f"Output of {step.title}"},
                success_criteria=[step.rationale],
                metadata={"order": step.order},
            )
            tasks.append(task)

            # Dependency definition
            if prev_task_id:
                dep_id = generate_workflow_dependency_id()
                dependencies.append(
                    AgentWorkflowDependency(
                        id=dep_id,
                        source_task_id=prev_task_id,
                        target_task_id=t_id,
                        dependency_type="requires_completion",
                        blocking=True,
                    )
                )

            prev_task_id = t_id

        # Add checkpoint if multi-step
        if len(tasks) > 1:
            chk_id = generate_workflow_checkpoint_id()
            checkpoints.append(
                AgentWorkflowCheckpoint(
                    id=chk_id,
                    workflow_id=wf_id,
                    name="Mid-plan Checkpoint",
                    position=len(tasks) // 2,
                    affected_resources=list(request.resource_ids),
                    reason="Verify intermediate state stability",
                    required=True,
                )
            )

        # Build strategy, budget, risks, assumptions
        rollback_strat = AgentWorkflowRollbackStrategy(
            id=f"rollback-{wf_id}",
            available=True,
            kind="step_by_step",
            trigger_conditions=["operation_failed", "validation_failed"],
            scope="workflow",
        )

        recovery_strat = AgentWorkflowRecoveryStrategy(
            id=f"recovery-{wf_id}",
            actions=["retry", "replan", "rollback"],
            maximum_attempts=3,
        )

        budget_est = AgentWorkflowBudgetEstimate(
            estimated_tokens=len(tasks) * 500,
            estimated_cost=0.01 * len(tasks),
            estimated_duration_seconds=float(len(tasks) * 10),
            estimated_operations=len(operations),
            limits=dict(request.budget),
        )

        risks = [
            AgentWorkflowRisk(
                id=f"risk-{wf_id}-1",
                name="Complexity Risk",
                level=WorkflowPlanRisk.LOW
                if len(tasks) <= 3
                else WorkflowPlanRisk.MEDIUM,
                description=f"Plan estimated complexity: {exec_plan.estimated_complexity}",
            )
        ]

        assumptions = [
            AgentWorkflowAssumption(
                id=f"assump-{wf_id}-1",
                statement="Planner step sequence is deterministically orderable.",
                validated=True,
            )
        ]

        completion_criteria = [
            f"Complete all {len(tasks)} planned steps for goal: {exec_plan.goal}"
        ]

        return AgentWorkflowPlan(
            id=plan_id,
            goal_id=request.goal_id,
            agent_run_id=request.agent_run_id,
            workflow_id=wf_id,
            planner_plan_id=f"plan-{id(exec_plan)}",
            version=1,
            status=WorkflowPlanStatus.DRAFT,
            objective=context.objective,
            scope=[s.title for s in exec_plan.steps],
            tasks=tasks,
            dependencies=dependencies,
            operations=operations,
            validation_nodes=validation_nodes,
            approval_nodes=approval_nodes,
            checkpoints=checkpoints,
            rollback_strategy=rollback_strat,
            recovery_strategy=recovery_strat,
            completion_criteria=completion_criteria,
            pause_conditions=["validation_failed", "approval_rejected"],
            cancellation_conditions=["goal_cancelled", "resource_revoked"],
            assumptions=assumptions,
            risks=risks,
            expected_effects=[f"Achieve: {context.objective}"],
            estimated_budget=budget_est,
            timeout_seconds=request.timeout_seconds or 300.0,
            confidence=0.9,
            created_at=now,
            updated_at=now,
            metadata={"estimated_complexity": exec_plan.estimated_complexity},
        )

    def replan(self, request: AgentReplanningRequest) -> AgentReplanningResult:
        """Generate a new version of an existing workflow plan."""
        if not isinstance(request, AgentReplanningRequest):
            raise InvalidAgentPlanningContractError(
                "Request must be instance of AgentReplanningRequest."
            )

        prev_plan = self._plan_store.get(request.plan_id)
        if not prev_plan:
            raise WorkflowReplanningError(
                f"Previous plan '{request.plan_id}' not found in plan store."
            )

        # Construct sub-planning request
        base_planning_req = request.planning_request or AgentPlanningRequest(
            id=f"req-replan-{request.id}",
            goal_id=prev_plan.goal_id,
            agent_run_id=prev_plan.agent_run_id,
            objective=prev_plan.objective,
            timeout_seconds=prev_plan.timeout_seconds,
        )

        new_plan_draft = self.plan(base_planning_req)

        # Incremented version and link previous version
        new_version_num = prev_plan.version + 1
        new_plan_id = generate_workflow_plan_id()
        new_plan = AgentWorkflowPlan.from_dict(
            {
                **new_plan_draft.to_dict(),
                "id": new_plan_id,
                "workflow_id": prev_plan.workflow_id,
                "version": new_version_num,
                "previous_version_id": prev_plan.id,
                "status": WorkflowPlanStatus.VALID.value,
                "updated_at": self._clock(),
                "metadata": {
                    **new_plan_draft.metadata,
                    "replan_reason": request.reason.value,
                    "replan_details": request.reason_details,
                },
            }
        )

        # Update store: mark previous plan as superseded
        self._plan_store.supersede(prev_plan.id, new_plan.id)
        self._plan_store.add(new_plan)

        res_id = f"replan-res-{request.id}"
        return AgentReplanningResult(
            id=res_id,
            request_id=request.id,
            status=AgentPlanningStatus.COMPLETED,
            decision=AgentPlanningDecision.REPLAN,
            previous_plan_id=prev_plan.id,
            new_plan=new_plan,
            version=new_version_num,
            change_reason=request.reason,
            created_at=self._clock(),
        )


class AgentPlanningService:
    """Public high-level facade for managing agent planning, context building, validation, and store history."""

    def __init__(
        self,
        adapter: DefaultWorkflowPlannerAdapter | None = None,
        plan_store: InMemoryWorkflowPlanStore | None = None,
        validator: AgentWorkflowPlanValidator | None = None,
    ) -> None:
        self._store = plan_store or (
            adapter._plan_store if adapter else InMemoryWorkflowPlanStore()
        )
        self._validator = validator or (
            adapter._validator if adapter else AgentWorkflowPlanValidator()
        )
        self._adapter = adapter or DefaultWorkflowPlannerAdapter(
            plan_store=self._store, validator=self._validator
        )

    def plan(self, request: AgentPlanningRequest) -> AgentWorkflowPlan:
        """Create a new workflow plan for ``request``."""
        return self._adapter.plan(request)

    def replan(self, request: AgentReplanningRequest) -> AgentReplanningResult:
        """Trigger replanning and produce a new versioned plan."""
        return self._adapter.replan(request)

    def build_context(self, request: AgentPlanningRequest) -> AgentPlanningContext:
        """Build the immutable planning context."""
        return self._adapter.build_context(request)

    def translate_plan(
        self, execution_plan: ExecutionPlan, request: AgentPlanningRequest
    ) -> AgentWorkflowPlan:
        """Translate ExecutionPlan to AgentWorkflowPlan directly."""
        return self._adapter.translate_plan(execution_plan, request)

    def validate_plan(
        self, plan: AgentWorkflowPlan, request: AgentPlanningRequest | None = None
    ) -> AgentWorkflowPlanValidation:
        """Perform structural validation on ``plan``."""
        return self._validator.validate(plan, request=request)

    def get_plan(self, plan_id: str) -> AgentWorkflowPlan | None:
        """Retrieve stored plan by ID."""
        return self._store.get(plan_id)

    def get_latest_plan(self, workflow_id: str) -> AgentWorkflowPlan | None:
        """Retrieve latest plan version for workflow ID."""
        return self._store.get_latest(workflow_id)

    def list_versions(self, workflow_id: str) -> list[AgentWorkflowPlan]:
        """List all version instances for workflow ID."""
        return self._store.list_versions(workflow_id)
