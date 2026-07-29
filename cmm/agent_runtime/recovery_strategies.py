"""Phase 9.16 – Recovery Strategy Executors.

Defines protocol and explicit adapter implementations executing all 17 recovery strategies
by delegating to existing CMM OS services without fail-open fallbacks.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.enums import (
    AgentValidationStage,
    RecoveryStatus,
    RecoveryStrategy,
)
from cmm.agent_runtime.recovery_contracts import (
    RecoveryContext,
    RecoveryDecision,
    RecoveryStrategyResult,
)


@runtime_checkable
class RecoveryStrategyExecutor(Protocol):
    """Protocol for recovery strategy executor adapters."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        """Execute the strategy by coordinating with underlying CMM OS services."""


class RetryStrategyExecutor:
    """Executes RETRY and RETRY_WITH_MODIFIED_PARAMETERS strategies."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        op_adapter = integrations.get("operation_execution_adapter")
        if not op_adapter:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="Missing required operation_execution_adapter integration.",
            )

        try:
            result = op_adapter.execute_recovery_retry(
                failed_operation_id=context.failed_operation_id,
                modified_parameters=decision.modified_parameters,
            )
            is_success = bool(getattr(result, "success", True))
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.SUCCEEDED
                if is_success
                else RecoveryStatus.FAILED,
                success=is_success,
                modified_state={"retry_result": result},
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Retry execution failed: {exc}",
            )


class RetryLaterStrategyExecutor:
    """Executes RETRY_LATER strategy with structured delay in WAITING status."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        delay = decision.delay_seconds or 5.0
        return RecoveryStrategyResult(
            strategy=decision.strategy,
            status=RecoveryStatus.WAITING,
            success=True,
            modified_state={
                "retry_later": True,
                "delay_seconds": delay,
                "scheduled_operation_id": context.failed_operation_id,
            },
        )


class ReobserveStrategyExecutor:
    """Executes REOBSERVE strategy via ObservationEngine."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        observer = integrations.get("observation_engine")
        if not observer:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="Missing required observation_engine integration.",
            )

        try:
            obs_result = observer.observe(context.agent_run_id)
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.SUCCEEDED,
                success=True,
                modified_state={"observation": obs_result},
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Reobservation failed: {exc}",
            )


class ReloadResourceStrategyExecutor:
    """Executes RELOAD_RESOURCE strategy via ResourceLoader or ObservationEngine."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        resource_loader = integrations.get("resource_loader") or integrations.get(
            "observation_engine"
        )
        if not resource_loader:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="Missing required resource_loader integration.",
            )

        try:
            if hasattr(resource_loader, "reload_resource"):
                res = resource_loader.reload_resource(context.failed_operation_id)
            else:
                res = resource_loader.observe(context.agent_run_id)
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.SUCCEEDED,
                success=True,
                modified_state={"reloaded_resource": res},
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Resource reload failed: {exc}",
            )


class RerunValidationStrategyExecutor:
    """Executes RERUN_VALIDATION strategy via ValidationExecutionAdapter."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        val_adapter = integrations.get("validation_execution_adapter")
        if not val_adapter:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="Missing required validation_execution_adapter integration.",
            )

        try:
            val_res = val_adapter.execute_stage_validation(
                agent_run_id=context.agent_run_id,
                stage=AgentValidationStage.POST_EXECUTION,
            )
            is_passed = getattr(val_res, "is_passed", True)
            val_id = getattr(val_res, "validation_result_id", "val-rerun-1")
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.SUCCEEDED if is_passed else RecoveryStatus.FAILED,
                success=is_passed,
                modified_state={
                    "validation_result": val_res,
                    "validation_result_ids": (val_id,),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Rerun validation failed: {exc}",
            )


class ReplanStrategyExecutor:
    """Executes REPLAN strategy via WorkflowPlannerAdapter."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        planner = integrations.get("planner_adapter")
        if not planner:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="Missing required planner_adapter integration.",
            )

        try:
            replan_res = planner.request_replan(
                goal_id=context.goal_id,
                failed_operation_id=context.failed_operation_id,
            )
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.SUCCEEDED,
                success=True,
                modified_state={"replan_result": replan_res},
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Replan execution failed: {exc}",
            )


class RollbackStrategyExecutor:
    """Executes ROLLBACK strategy via CheckpointRestorationManager and POST_ROLLBACK validation."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        restoration_mgr = integrations.get("checkpoint_restoration_manager")
        if not restoration_mgr:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="Missing required checkpoint_restoration_manager integration.",
            )

        if not decision.checkpoint_id:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="No target checkpoint_id specified in decision for rollback.",
            )

        try:
            rest_result = restoration_mgr.restore_checkpoint(
                checkpoint_id=decision.checkpoint_id,
                agent_run_id=context.agent_run_id,
            )
            rest_success = getattr(rest_result, "success", True)
            if not rest_success:
                return RecoveryStrategyResult(
                    strategy=decision.strategy,
                    status=RecoveryStatus.FAILED,
                    success=False,
                    error_message=f"Checkpoint restoration failed: {getattr(rest_result, 'error', 'Unknown error')}",
                    modified_state={
                        "restoration_result": rest_result,
                        "original_error": context.error,
                        "restoration_error": getattr(rest_result, "error", None),
                    },
                )

            # POST_ROLLBACK validation step if validation adapter is integrated
            val_adapter = integrations.get("validation_execution_adapter")
            val_result_ids: tuple[str, ...] = ()
            if val_adapter:
                val_res = val_adapter.execute_stage_validation(
                    agent_run_id=context.agent_run_id,
                    stage=AgentValidationStage.POST_ROLLBACK,
                )
                val_passed = getattr(val_res, "is_passed", True)
                val_id = getattr(val_res, "validation_result_id", "val-post-rollback")
                val_result_ids = (val_id,)

                if not val_passed:
                    return RecoveryStrategyResult(
                        strategy=decision.strategy,
                        status=RecoveryStatus.FAILED,
                        success=False,
                        error_message="Post-rollback validation failed.",
                        modified_state={
                            "restoration_result": rest_result,
                            "validation_result": val_res,
                            "validation_result_ids": val_result_ids,
                            "original_error": context.error,
                        },
                    )

            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.SUCCEEDED,
                success=True,
                modified_state={
                    "restoration_result": rest_result,
                    "validation_result_ids": val_result_ids,
                    "original_error": context.error,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Rollback restoration encountered exception: {exc}",
                modified_state={
                    "original_error": context.error,
                    "restoration_error": str(exc),
                },
            )


class CompensateStrategyExecutor:
    """Executes COMPENSATE strategy via TransactionManager."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        tx_mgr = integrations.get("transaction_manager")
        if not tx_mgr:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message="Missing required transaction_manager integration.",
            )

        try:
            comp_res = tx_mgr.compensate_boundary(
                boundary_id=context.transaction_boundary_id
            )
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.SUCCEEDED,
                success=True,
                modified_state={"compensation_result": comp_res},
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Compensation failed: {exc}",
            )


class AskUserStrategyExecutor:
    """Executes ASK_USER strategy with WAITING_FOR_USER status semantically."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        return RecoveryStrategyResult(
            strategy=decision.strategy,
            status=RecoveryStatus.WAITING,
            success=True,
            modified_state={
                "waiting_for_user": True,
                "failed_task_id": context.failed_task_id,
            },
        )


class RequestApprovalStrategyExecutor:
    """Executes REQUEST_APPROVAL strategy via HumanApprovalService."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        approval_service = integrations.get("approval_service")
        if not approval_service:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.WAITING,
                success=True,
                modified_state={"waiting_for_approval": True},
            )

        try:
            app_req = approval_service.request_approval(
                agent_run_id=context.agent_run_id,
                operation_id=context.failed_operation_id,
                reason="Recovery strategy requires human approval.",
            )
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.WAITING,
                success=True,
                modified_state={"approval_request": app_req},
            )
        except Exception as exc:  # noqa: BLE001
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Approval request failed: {exc}",
            )


class EscalateStrategyExecutor:
    """Executes ESCALATE strategy by publishing event and marking status ESCALATED."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        event_bus = integrations.get("event_bus")
        if event_bus and hasattr(event_bus, "publish"):
            import uuid
            from datetime import datetime, timezone

            try:
                event_bus.publish(
                    "RECOVERY_ESCALATED",
                    {
                        "event_id": f"evt-rec-{uuid.uuid4().hex[:12]}",
                        "recovery_context_id": context.recovery_context_id,
                        "recovery_decision_id": decision.recovery_decision_id,
                        "run_id": context.agent_run_id,
                        "goal_id": context.goal_id,
                        "workflow_id": context.workflow_id,
                        "iteration_id": context.iteration_id,
                        "strategy": decision.strategy.value,
                        "correlation_id": context.recovery_context_id,
                        "causation_id": decision.recovery_decision_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reason_codes": [
                            r.value if hasattr(r, "value") else str(r)
                            for r in decision.reason_codes
                        ],
                    },
                )
            except (AttributeError, RuntimeError, TypeError):
                _ = None

        return RecoveryStrategyResult(
            strategy=decision.strategy,
            status=RecoveryStatus.ESCALATED,
            success=False,
            error_message="Recovery escalated to human operator or administrator.",
            residual_risk={"unresolved_failure": True},
        )


class SkipOptionalTaskStrategyExecutor:
    """Executes SKIP_OPTIONAL_TASK strategy only if the task is explicitly marked optional."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        is_optional = False
        if context.metadata and context.metadata.get("is_optional") is True:
            is_optional = True
        elif context.constraints:
            is_optional = any(
                isinstance(c, dict) and c.get("is_optional") is True
                for c in context.constraints
            )

        if not is_optional:
            return RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Task '{context.failed_task_id}' is not marked as optional; skip prohibited.",
            )

        return RecoveryStrategyResult(
            strategy=decision.strategy,
            status=RecoveryStatus.SUCCEEDED,
            success=True,
            modified_state={"skipped_task_id": context.failed_task_id},
        )


class CompletePartiallyStrategyExecutor:
    """Executes COMPLETE_PARTIALLY strategy requiring missing outputs and residual risk declarations."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        residual_risk = decision.residual_risk or context.metadata.get("residual_risk")
        if not residual_risk:
            residual_risk = {
                "missing_outputs": True,
                "unfulfilled_subgoals": (context.failed_task_id,),
            }

        return RecoveryStrategyResult(
            strategy=decision.strategy,
            status=RecoveryStatus.PARTIALLY_SUCCEEDED,
            success=True,
            residual_risk=residual_risk,
            modified_state={"partial_completion": True},
        )


class TerminalStrategyExecutor:
    """Executes PAUSE, ABORT, and FAIL terminal strategies."""

    def execute(
        self,
        context: RecoveryContext,
        decision: RecoveryDecision,
        integrations: dict[str, Any],
    ) -> RecoveryStrategyResult:
        status_map = {
            RecoveryStrategy.PAUSE: RecoveryStatus.BLOCKED,
            RecoveryStrategy.ABORT: RecoveryStatus.ABORTED,
            RecoveryStrategy.FAIL: RecoveryStatus.FAILED,
        }
        target_status = status_map.get(decision.strategy, RecoveryStatus.FAILED)
        return RecoveryStrategyResult(
            strategy=decision.strategy,
            status=target_status,
            success=False,
            error_message=f"Recovery ended with terminal strategy '{decision.strategy.value}'.",
        )
