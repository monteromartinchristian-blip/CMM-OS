"""Phase 9.12 – Agent Runtime Step Handlers.

Defines the protocol and concrete step handlers for each operational step in the Runtime Loop cycle.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any, Protocol

from cmm.agent_runtime.enums import (
    AgentRuntimeStatus,
    AgentValidationDecision,
    ApprovalRequestStatus,
    PolicyDecision,
    RuntimeStep,
    RuntimeStepStatus,
)
from cmm.agent_runtime.errors import RuntimeStepExecutionError
from cmm.agent_runtime.runtime_loop_contracts import (
    RuntimeStepContext,
    RuntimeStepResult,
)
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter


def _value_as_string(value: Any) -> str:
    """Return an enum value or the string representation of a runtime value."""
    enum_value = getattr(value, "value", value)
    return str(enum_value)


class RuntimeStepHandler(Protocol):
    """Protocol for executable runtime step handlers."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        """Execute step logic against the provided immutable context."""
        ...


def _build_step_result(
    context: RuntimeStepContext,
    step: RuntimeStep | str,
    next_status: AgentRuntimeStatus | str,
    success: bool = True,
    status: RuntimeStepStatus | str = RuntimeStepStatus.COMPLETED,
    requires_user: bool = False,
    requires_resource: bool = False,
    requires_approval: bool = False,
    retryable: bool = False,
    reason_codes: tuple[str, ...] = (),
    produced_ids: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> RuntimeStepResult:
    iter_id = context.iteration.id if context.iteration else "iter-0"
    return RuntimeStepResult(
        agent_run_id=context.agent_run.id,
        iteration_id=iter_id,
        step=step,
        created_at=context.now,
        status=status,
        next_status=next_status,
        success=success,
        retryable=retryable,
        requires_user=requires_user,
        requires_resource=requires_resource,
        requires_approval=requires_approval,
        reason_codes=reason_codes,
        produced_ids=produced_ids,
        metadata=metadata or {},
    )


class LoadGoalHandler:
    """Handler for RuntimeStep.LOAD_GOAL."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        goal_id = getattr(context.goal, "id", context.agent_run.goal_id)
        if not goal_id:
            return _build_step_result(
                context,
                step=RuntimeStep.LOAD_GOAL,
                next_status=AgentRuntimeStatus.FAILED,
                success=False,
                status=RuntimeStepStatus.FAILED,
                reason_codes=("runtime.goal_not_found",),
            )
        return _build_step_result(
            context,
            step=RuntimeStep.LOAD_GOAL,
            next_status=AgentRuntimeStatus.INITIALIZING,
            reason_codes=("runtime.goal_loaded",),
            produced_ids=(goal_id,),
        )


class ValidateGoalHandler:
    """Handler for RuntimeStep.VALIDATE_GOAL."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        if context.goal is not None:
            status_val = getattr(context.goal, "status", None)
            status_str = _value_as_string(status_val)
            if status_str in ("completed", "cancelled", "failed", "abandoned"):
                return _build_step_result(
                    context,
                    step=RuntimeStep.VALIDATE_GOAL,
                    next_status=AgentRuntimeStatus.FAILED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.goal_terminal",),
                )
        elif not context.agent_run.goal_id:
            return _build_step_result(
                context,
                step=RuntimeStep.VALIDATE_GOAL,
                next_status=AgentRuntimeStatus.FAILED,
                success=False,
                status=RuntimeStepStatus.FAILED,
                reason_codes=("runtime.goal_invalid",),
            )

        return _build_step_result(
            context,
            step=RuntimeStep.VALIDATE_GOAL,
            next_status=AgentRuntimeStatus.OBSERVING,
            reason_codes=("runtime.goal_valid",),
        )


class CheckDependenciesHandler:
    """Handler for RuntimeStep.CHECK_DEPENDENCIES."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        deps = getattr(context.goal, "dependencies", ()) if context.goal else ()
        for dep in deps:
            status_val = getattr(dep, "status", None)
            st_str = _value_as_string(status_val)
            if st_str in ("blocked", "failed"):
                return _build_step_result(
                    context,
                    step=RuntimeStep.CHECK_DEPENDENCIES,
                    next_status=AgentRuntimeStatus.BLOCKED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.dependencies_blocked",),
                )
        return _build_step_result(
            context,
            step=RuntimeStep.CHECK_DEPENDENCIES,
            next_status=AgentRuntimeStatus.OBSERVING,
            reason_codes=("runtime.dependencies_satisfied",),
        )


class ObserveHandler:
    """Handler for RuntimeStep.OBSERVE."""

    def __init__(
        self, observation_func: Callable[[RuntimeStepContext], str] | None = None
    ) -> None:
        self._observation_func = observation_func

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        obs_id = f"obs-{uuid.uuid4().hex[:8]}"
        if self._observation_func:
            try:
                obs_id = self._observation_func(context)
            except Exception as exc:
                raise RuntimeStepExecutionError(
                    f"Observation execution failed: {exc}"
                ) from exc

        return _build_step_result(
            context,
            step=RuntimeStep.OBSERVE,
            next_status=AgentRuntimeStatus.REASONING,
            reason_codes=("runtime.observation_completed",),
            produced_ids=(obs_id,),
        )


class LoadKnowledgeHandler:
    """Handler for RuntimeStep.LOAD_KNOWLEDGE."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        kn_id = f"kn-{uuid.uuid4().hex[:8]}"
        return _build_step_result(
            context,
            step=RuntimeStep.LOAD_KNOWLEDGE,
            next_status=AgentRuntimeStatus.REASONING,
            reason_codes=("runtime.knowledge_loaded",),
            produced_ids=(kn_id,),
        )


class ReasonHandler:
    """Handler for RuntimeStep.REASON."""

    def __init__(
        self,
        reasoning_func: Callable[[RuntimeStepContext], dict[str, Any]] | None = None,
    ) -> None:
        self._reasoning_func = reasoning_func

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        res_data = {"decision": "plan", "reason_code": "runtime.reasoning_completed"}
        if self._reasoning_func:
            try:
                res_data = self._reasoning_func(context)
            except Exception as exc:
                raise RuntimeStepExecutionError(
                    f"Reasoning execution failed: {exc}"
                ) from exc

        decision = res_data.get("decision", "plan")
        reason_code = res_data.get("reason_code", "runtime.reasoning_completed")
        rec_id = f"reason-{uuid.uuid4().hex[:8]}"

        if decision == "ask_user":
            return _build_step_result(
                context,
                step=RuntimeStep.REASON,
                next_status=AgentRuntimeStatus.WAITING_FOR_USER,
                requires_user=True,
                reason_codes=("runtime.user_input_required", reason_code),
                produced_ids=(rec_id,),
            )
        elif decision == "load_resource":
            return _build_step_result(
                context,
                step=RuntimeStep.REASON,
                next_status=AgentRuntimeStatus.WAITING_FOR_RESOURCE,
                requires_resource=True,
                reason_codes=("runtime.resource_required", reason_code),
                produced_ids=(rec_id,),
            )
        elif decision == "complete":
            return _build_step_result(
                context,
                step=RuntimeStep.REASON,
                next_status=AgentRuntimeStatus.COMPLETED,
                reason_codes=("runtime.completed", reason_code),
                produced_ids=(rec_id,),
            )
        elif decision == "fail":
            return _build_step_result(
                context,
                step=RuntimeStep.REASON,
                next_status=AgentRuntimeStatus.FAILED,
                success=False,
                status=RuntimeStepStatus.FAILED,
                reason_codes=("runtime.failed", reason_code),
                produced_ids=(rec_id,),
            )
        elif decision == "blocked":
            return _build_step_result(
                context,
                step=RuntimeStep.REASON,
                next_status=AgentRuntimeStatus.BLOCKED,
                success=False,
                reason_codes=("runtime.blocked", reason_code),
                produced_ids=(rec_id,),
            )

        return _build_step_result(
            context,
            step=RuntimeStep.REASON,
            next_status=AgentRuntimeStatus.PLANNING,
            reason_codes=(reason_code,),
            produced_ids=(rec_id,),
        )


class ResolveInformationGapsHandler:
    """Handler for RuntimeStep.RESOLVE_INFORMATION_GAPS."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        return _build_step_result(
            context,
            step=RuntimeStep.RESOLVE_INFORMATION_GAPS,
            next_status=AgentRuntimeStatus.REASONING,
            reason_codes=("runtime.information_resolved",),
        )


class DecideHandler:
    """Handler for RuntimeStep.DECIDE."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        dec_id = f"dec-{uuid.uuid4().hex[:8]}"
        return _build_step_result(
            context,
            step=RuntimeStep.DECIDE,
            next_status=AgentRuntimeStatus.PLANNING,
            reason_codes=("runtime.decision_made",),
            produced_ids=(dec_id,),
        )


class PlanHandler:
    """Handler for RuntimeStep.PLAN."""

    def __init__(
        self, planner_func: Callable[[RuntimeStepContext], str] | None = None
    ) -> None:
        self._planner_func = planner_func

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        if self._planner_func:
            try:
                plan_id = self._planner_func(context)
            except Exception as exc:
                raise RuntimeStepExecutionError(
                    f"Planning execution failed: {exc}"
                ) from exc

        return _build_step_result(
            context,
            step=RuntimeStep.PLAN,
            next_status=AgentRuntimeStatus.PLANNING,
            reason_codes=("runtime.plan_created",),
            produced_ids=(plan_id,),
        )


class EvaluatePoliciesHandler:
    """Handler for RuntimeStep.EVALUATE_POLICIES."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        for pol_res in context.policy_results:
            decision = getattr(pol_res, "decision", None)
            dec_str = _value_as_string(decision)
            if dec_str == PolicyDecision.DENY.value or dec_str == "deny":
                return _build_step_result(
                    context,
                    step=RuntimeStep.EVALUATE_POLICIES,
                    next_status=AgentRuntimeStatus.BLOCKED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.policy_denied",),
                )
            elif (
                dec_str == PolicyDecision.REQUIRE_APPROVAL.value
                or dec_str == "require_approval"
            ):
                return _build_step_result(
                    context,
                    step=RuntimeStep.EVALUATE_POLICIES,
                    next_status=AgentRuntimeStatus.WAITING_FOR_APPROVAL,
                    requires_approval=True,
                    reason_codes=("runtime.approval_required",),
                )
        return _build_step_result(
            context,
            step=RuntimeStep.EVALUATE_POLICIES,
            next_status=AgentRuntimeStatus.PLANNING,
            reason_codes=("runtime.policy_allowed",),
        )


class RequestApprovalHandler:
    """Handler for RuntimeStep.REQUEST_APPROVAL."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        for app in context.approval_resolutions:
            status = getattr(app, "status", None)
            st_str = _value_as_string(status)
            if st_str in (ApprovalRequestStatus.REJECTED.value, "rejected"):
                return _build_step_result(
                    context,
                    step=RuntimeStep.REQUEST_APPROVAL,
                    next_status=AgentRuntimeStatus.FAILED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.approval_rejected",),
                )
            elif st_str in (
                ApprovalRequestStatus.APPROVED_WITH_CHANGES.value,
                "approved_with_changes",
            ):
                return _build_step_result(
                    context,
                    step=RuntimeStep.REQUEST_APPROVAL,
                    next_status=AgentRuntimeStatus.PLANNING,
                    reason_codes=("runtime.approval_approved_with_changes",),
                )
            elif st_str in (ApprovalRequestStatus.APPROVED.value, "approved"):
                return _build_step_result(
                    context,
                    step=RuntimeStep.REQUEST_APPROVAL,
                    next_status=AgentRuntimeStatus.EXECUTING,
                    reason_codes=("runtime.approval_granted",),
                )

        req_id = f"app-{uuid.uuid4().hex[:8]}"
        return _build_step_result(
            context,
            step=RuntimeStep.REQUEST_APPROVAL,
            next_status=AgentRuntimeStatus.WAITING_FOR_APPROVAL,
            requires_approval=True,
            reason_codes=("runtime.approval_required",),
            produced_ids=(req_id,),
        )


class ReserveBudgetHandler:
    """Handler for RuntimeStep.RESERVE_BUDGET."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        if context.budget is not None:
            status = getattr(context.budget, "status", None)
            st_str = _value_as_string(status)
            if st_str in ("exhausted", "paused", "cancelled"):
                return _build_step_result(
                    context,
                    step=RuntimeStep.RESERVE_BUDGET,
                    next_status=AgentRuntimeStatus.BLOCKED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.budget_exhausted",),
                )
        res_id = f"res-{uuid.uuid4().hex[:8]}"
        return _build_step_result(
            context,
            step=RuntimeStep.RESERVE_BUDGET,
            next_status=AgentRuntimeStatus.EXECUTING,
            reason_codes=("runtime.budget_reserved",),
            produced_ids=(res_id,),
        )


class ExecuteHandler:
    """Handler for RuntimeStep.EXECUTE."""

    def __init__(
        self,
        executor_func: Callable[[RuntimeStepContext], str] | None = None,
        adapter: Any | None = None,
    ) -> None:
        self._executor_func = executor_func
        self._adapter = adapter

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        if self._adapter is not None:
            op_request = context.metadata.get("operation_request") or getattr(
                context, "operation_request", None
            )
            if op_request is None:
                raise RuntimeStepExecutionError(
                    "ExecuteHandler invoked with adapter but no AgentOperationRequest was provided in context."
                )
            res = self._adapter.execute(op_request)
            if res.success:
                return _build_step_result(
                    context,
                    step=RuntimeStep.EXECUTE,
                    next_status=AgentRuntimeStatus.VALIDATING,
                    reason_codes=("runtime.execution_completed", *res.reason_codes),
                    produced_ids=(res.id,),
                    metadata={"execution_result": res.to_dict()},
                )
            else:
                next_st = (
                    AgentRuntimeStatus.BLOCKED
                    if res.status == "blocked"
                    else AgentRuntimeStatus.RECOVERING
                )
                return _build_step_result(
                    context,
                    step=RuntimeStep.EXECUTE,
                    next_status=next_st,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    retryable=True,
                    reason_codes=("runtime.execution_failed", *res.reason_codes),
                    produced_ids=(res.id,),
                    metadata={"execution_result": res.to_dict()},
                )

        if self._executor_func is not None:
            exec_id = f"exec-{uuid.uuid4().hex[:8]}"
            try:
                exec_id = self._executor_func(context)
            except Exception as exc:  # noqa: BLE001
                return _build_step_result(
                    context,
                    step=RuntimeStep.EXECUTE,
                    next_status=AgentRuntimeStatus.RECOVERING,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    retryable=True,
                    reason_codes=("runtime.execution_failed", str(exc)),
                )
            return _build_step_result(
                context,
                step=RuntimeStep.EXECUTE,
                next_status=AgentRuntimeStatus.VALIDATING,
                reason_codes=("runtime.execution_completed",),
                produced_ids=(exec_id,),
            )

        raise RuntimeStepExecutionError(
            "ExecuteHandler requires an injected AgentExecutionAdapter or explicit executor delegate; arbitrary execution is forbidden."
        )


class ValidateHandler:
    """Handler for RuntimeStep.VALIDATE."""

    def __init__(
        self,
        adapter: AgentValidationAdapter | None = None,
    ) -> None:
        self._adapter = adapter

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        if self._adapter is not None:
            val_req = context.metadata.get("validation_request") or getattr(
                context, "validation_request", None
            )
            if val_req is not None:
                res = self._adapter.validate(val_req)
                if res.decision == AgentValidationDecision.CONTINUE:
                    next_st = AgentRuntimeStatus.EVALUATING
                elif res.decision == AgentValidationDecision.BLOCK:
                    next_st = AgentRuntimeStatus.BLOCKED
                elif res.decision in (
                    AgentValidationDecision.RETRY,
                    AgentValidationDecision.ROLLBACK,
                ):
                    next_st = AgentRuntimeStatus.RECOVERING
                elif res.decision == AgentValidationDecision.REPLAN:
                    next_st = AgentRuntimeStatus.PLANNING
                elif res.decision == AgentValidationDecision.ESCALATE:
                    next_st = AgentRuntimeStatus.WAITING_FOR_APPROVAL
                elif res.decision == AgentValidationDecision.PAUSE:
                    next_st = AgentRuntimeStatus.PAUSED
                elif res.decision == AgentValidationDecision.ABORT:
                    next_st = AgentRuntimeStatus.FAILED
                else:
                    raise RuntimeStepExecutionError(
                        f"Unknown or unmapped AgentValidationDecision '{res.decision}' "
                        "cannot be translated into a runtime transition."
                    )

                success = res.decision == AgentValidationDecision.CONTINUE
                return _build_step_result(
                    context,
                    step=RuntimeStep.VALIDATE,
                    next_status=next_st,
                    success=success,
                    status=RuntimeStepStatus.COMPLETED
                    if success
                    else RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.validation_completed", res.decision.value),
                    produced_ids=(res.request_id,),
                    metadata={"validation_result": res.to_dict()},
                )

        val_id = f"val-{uuid.uuid4().hex[:8]}"
        return _build_step_result(
            context,
            step=RuntimeStep.VALIDATE,
            next_status=AgentRuntimeStatus.EVALUATING,
            reason_codes=("runtime.validation_completed",),
            produced_ids=(val_id,),
        )


class EvaluateOutcomeHandler:
    """Handler for RuntimeStep.EVALUATE_OUTCOME."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        eval_id = f"eval-{uuid.uuid4().hex[:8]}"
        return _build_step_result(
            context,
            step=RuntimeStep.EVALUATE_OUTCOME,
            next_status=AgentRuntimeStatus.COMPLETED,
            reason_codes=("runtime.outcome_success",),
            produced_ids=(eval_id,),
        )


class UpdateGoalHandler:
    """Handler for RuntimeStep.UPDATE_GOAL."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        return _build_step_result(
            context,
            step=RuntimeStep.UPDATE_GOAL,
            next_status=AgentRuntimeStatus.COMPLETED,
            reason_codes=("runtime.goal_updated",),
        )


class UpdateKnowledgeHandler:
    """Handler for RuntimeStep.UPDATE_KNOWLEDGE."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        return _build_step_result(
            context,
            step=RuntimeStep.UPDATE_KNOWLEDGE,
            next_status=AgentRuntimeStatus.COMPLETED,
            reason_codes=("runtime.knowledge_updated",),
        )


class RecoverHandler:
    """Handler for RuntimeStep.RECOVER."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        return _build_step_result(
            context,
            step=RuntimeStep.RECOVER,
            next_status=AgentRuntimeStatus.PLANNING,
            reason_codes=("runtime.recovery_planned",),
        )


class CompleteHandler:
    """Handler for RuntimeStep.COMPLETE."""

    def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
        return _build_step_result(
            context,
            step=RuntimeStep.COMPLETE,
            next_status=AgentRuntimeStatus.COMPLETED,
            reason_codes=("runtime.completed",),
        )
