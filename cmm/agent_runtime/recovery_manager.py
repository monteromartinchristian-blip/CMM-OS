"""Phase 9.16 – Recovery Manager.

Main orchestrator managing autonomous recovery from failures in CMM OS Agent Runtime.
Coordinates error classification, policy evaluation, decision engine, repository storage,
event bus publication, action budget reservation/consumption, and explicit 17-strategy execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.action_budget_contracts import BudgetAllocation
from cmm.agent_runtime.enums import (
    BudgetConsumptionOutcome,
    BudgetResourceType,
    RecoveryStatus,
    RecoveryStrategy,
)
from cmm.agent_runtime.errors import (
    BudgetCancelledError,
    BudgetExhaustedError,
    BudgetPausedError,
    InsufficientBudgetError,
    RecoveryBudgetError,
    RecoveryContextError,
    RecoveryDecisionError,
    RecoveryStrategyUnavailableError,
)
from cmm.agent_runtime.recovery_backoff import RecoveryBackoffCalculator
from cmm.agent_runtime.recovery_contracts import (
    EscalationPolicy,
    RecoveryAttempt,
    RecoveryContext,
    RecoveryDecision,
    RecoveryExecutionResult,
    RecoveryStrategyResult,
    ReplanPolicy,
    RetryPolicy,
    RollbackPolicy,
)
from cmm.agent_runtime.recovery_decision_engine import RecoveryDecisionEngine
from cmm.agent_runtime.recovery_error_classifier import RecoveryErrorClassifier
from cmm.agent_runtime.recovery_policy import RecoveryPolicyResolver
from cmm.agent_runtime.recovery_repository import (
    InMemoryRecoveryRepository,
    RecoveryRepository,
)
from cmm.agent_runtime.recovery_strategies import (
    AskUserStrategyExecutor,
    CompensateStrategyExecutor,
    CompletePartiallyStrategyExecutor,
    EscalateStrategyExecutor,
    ReloadResourceStrategyExecutor,
    ReobserveStrategyExecutor,
    ReplanStrategyExecutor,
    RequestApprovalStrategyExecutor,
    RerunValidationStrategyExecutor,
    RetryLaterStrategyExecutor,
    RetryStrategyExecutor,
    RollbackStrategyExecutor,
    SkipOptionalTaskStrategyExecutor,
    TerminalStrategyExecutor,
)


class RecoveryManager:
    """Explicit, deterministic, and auditable Recovery Manager for CMM OS Agent Runtime."""

    def __init__(
        self,
        repository: RecoveryRepository | None = None,
        classifier: RecoveryErrorClassifier | None = None,
        decision_engine: RecoveryDecisionEngine | None = None,
        policy_resolver: RecoveryPolicyResolver | None = None,
        backoff_calculator: RecoveryBackoffCalculator | None = None,
        integrations: dict[str, Any] | None = None,
    ) -> None:
        self.repository = repository or InMemoryRecoveryRepository()
        self.classifier = classifier or RecoveryErrorClassifier()
        self.policy_resolver = policy_resolver or RecoveryPolicyResolver()
        self.backoff_calculator = backoff_calculator or RecoveryBackoffCalculator()
        self.decision_engine = decision_engine or RecoveryDecisionEngine(
            policy_resolver=self.policy_resolver,
            backoff_calculator=self.backoff_calculator,
        )
        self.integrations = integrations or {}
        self._audit_event_errors: list[str] = []

        # Explicit lookup map for ALL 17 RecoveryStrategy values
        self._executors: dict[RecoveryStrategy, Any] = {
            RecoveryStrategy.RETRY: RetryStrategyExecutor(),
            RecoveryStrategy.RETRY_WITH_MODIFIED_PARAMETERS: RetryStrategyExecutor(),
            RecoveryStrategy.RETRY_LATER: RetryLaterStrategyExecutor(),
            RecoveryStrategy.REOBSERVE: ReobserveStrategyExecutor(),
            RecoveryStrategy.RELOAD_RESOURCE: ReloadResourceStrategyExecutor(),
            RecoveryStrategy.RERUN_VALIDATION: RerunValidationStrategyExecutor(),
            RecoveryStrategy.REPLAN: ReplanStrategyExecutor(),
            RecoveryStrategy.ROLLBACK: RollbackStrategyExecutor(),
            RecoveryStrategy.COMPENSATE: CompensateStrategyExecutor(),
            RecoveryStrategy.ASK_USER: AskUserStrategyExecutor(),
            RecoveryStrategy.REQUEST_APPROVAL: RequestApprovalStrategyExecutor(),
            RecoveryStrategy.ESCALATE: EscalateStrategyExecutor(),
            RecoveryStrategy.PAUSE: TerminalStrategyExecutor(),
            RecoveryStrategy.SKIP_OPTIONAL_TASK: SkipOptionalTaskStrategyExecutor(),
            RecoveryStrategy.COMPLETE_PARTIALLY: CompletePartiallyStrategyExecutor(),
            RecoveryStrategy.ABORT: TerminalStrategyExecutor(),
            RecoveryStrategy.FAIL: TerminalStrategyExecutor(),
        }

    def register_integration(self, name: str, service: Any) -> None:
        """Register an integration service (e.g. event_bus, action_budget_service, etc.)."""
        self.integrations[name] = service

    def _publish_event(
        self,
        event_type: str,
        context: RecoveryContext,
        decision: RecoveryDecision | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> None:
        """Helper publishing structured domain events to EventBus with trace metadata."""
        event_bus = self.integrations.get("event_bus")
        if not event_bus or not hasattr(event_bus, "publish"):
            return

        payload = {
            "event_id": f"evt-rec-{uuid.uuid4().hex[:12]}",
            "recovery_context_id": context.recovery_context_id,
            "recovery_decision_id": decision.recovery_decision_id if decision else None,
            "run_id": context.agent_run_id,
            "goal_id": context.goal_id,
            "workflow_id": context.workflow_id,
            "iteration_id": context.iteration_id,
            "strategy": decision.strategy.value if decision else None,
            "correlation_id": context.recovery_context_id,
            "causation_id": decision.recovery_decision_id
            if decision
            else context.recovery_context_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason_codes": [
                r.value if hasattr(r, "value") else str(r)
                for r in (decision.reason_codes if decision else ())
            ],
            "metadata": dict(context.metadata) if context.metadata else {},
        }
        if extra_payload:
            payload.update(extra_payload)

        try:
            event_bus.publish(event_type, payload)
        except (AttributeError, RuntimeError, TypeError, ValueError) as err:
            self._audit_event_errors.append(
                f"Failed to publish event '{event_type}': {err}"
            )

    def decide(
        self,
        context: RecoveryContext,
        exc: Exception | None = None,
        retry_policy: RetryPolicy | None = None,
        replan_policy: ReplanPolicy | None = None,
        rollback_policy: RollbackPolicy | None = None,
        escalation_policy: EscalationPolicy | None = None,
        checkpoint_obj: Any | None = None,
    ) -> RecoveryDecision:
        """1-Step Decision: Classify failure, evaluate policies, make & persist RecoveryDecision."""
        if not context:
            raise RecoveryContextError("RecoveryContext cannot be None.")

        # Persist context if new
        saved_ctx = self.repository.get_context(context.recovery_context_id)
        if not saved_ctx:
            saved_ctx = self.repository.save_context(context)

        # Emit RECOVERY_CONTEXT_CREATED and RECOVERY_DECISION_REQUESTED
        self._publish_event("RECOVERY_CONTEXT_CREATED", saved_ctx)
        self._publish_event("RECOVERY_DECISION_REQUESTED", saved_ctx)

        # Classify error
        classification = self.classifier.classify(saved_ctx, exc=exc)

        # Make decision
        decision = self.decision_engine.make_decision(
            context=saved_ctx,
            classification=classification,
            retry_policy=retry_policy,
            replan_policy=replan_policy,
            rollback_policy=rollback_policy,
            escalation_policy=escalation_policy,
            checkpoint_obj=checkpoint_obj,
        )

        # Persist decision
        saved_decision = self.repository.save_decision(decision)

        # Emit strategy-specific decision events
        self._publish_event("RECOVERY_DECISION_MADE", saved_ctx, saved_decision)

        strat = saved_decision.strategy
        if strat in (
            RecoveryStrategy.RETRY,
            RecoveryStrategy.RETRY_LATER,
            RecoveryStrategy.RETRY_WITH_MODIFIED_PARAMETERS,
        ):
            self._publish_event(
                "RETRY_SCHEDULED",
                saved_ctx,
                saved_decision,
                {"delay_seconds": saved_decision.delay_seconds},
            )
        elif (
            strat == RecoveryStrategy.REOBSERVE
            or strat == RecoveryStrategy.RELOAD_RESOURCE
        ):
            self._publish_event("REOBSERVATION_REQUESTED", saved_ctx, saved_decision)
        elif strat == RecoveryStrategy.REPLAN:
            self._publish_event("REPLAN_REQUESTED", saved_ctx, saved_decision)
        elif strat == RecoveryStrategy.ROLLBACK:
            self._publish_event("ROLLBACK_REQUESTED", saved_ctx, saved_decision)
        elif strat == RecoveryStrategy.COMPENSATE:
            self._publish_event("COMPENSATION_REQUESTED", saved_ctx, saved_decision)
        elif strat == RecoveryStrategy.ASK_USER:
            self._publish_event("USER_INPUT_REQUESTED", saved_ctx, saved_decision)
        elif strat == RecoveryStrategy.REQUEST_APPROVAL:
            self._publish_event("APPROVAL_REQUESTED", saved_ctx, saved_decision)

        if "RETRIES_EXHAUSTED" in [
            r.value if hasattr(r, "value") else str(r)
            for r in saved_decision.reason_codes
        ]:
            self._publish_event("RETRY_EXHAUSTED", saved_ctx, saved_decision)

        return saved_decision

    def execute(
        self,
        decision: RecoveryDecision,
        attempt_index: int | None = None,
    ) -> RecoveryExecutionResult:
        """Step 2: Execute a decided recovery strategy with real ActionBudgetService reservation & confirmation."""
        if not decision:
            raise RecoveryDecisionError("RecoveryDecision cannot be None.")

        context = self.repository.get_context(decision.recovery_context_id)
        if not context:
            raise RecoveryContextError(
                f"RecoveryContext ID '{decision.recovery_context_id}' not found in repository."
            )

        # Strict lookup: strategy MUST be registered in self._executors
        if decision.strategy not in self._executors:
            raise RecoveryStrategyUnavailableError(
                f"Recovery strategy '{decision.strategy.value}' is not registered or available."
            )

        executor = self._executors[decision.strategy]
        actual_attempt_index = (
            attempt_index
            if attempt_index is not None
            else len(context.retry_history) + 1
        )

        # REAL ActionBudgetService Reservation & Pre-execution Budget Check
        budget_service = self.integrations.get("action_budget_service")
        from types import MappingProxyType

        budget_id = (
            context.remaining_budget.get("budget_id")
            if isinstance(context.remaining_budget, (dict, MappingProxyType))
            else None
        ) or context.agent_run_id
        reservation = None

        if budget_service and hasattr(budget_service, "reserve"):
            # Determine resource cost for the strategy
            if decision.strategy in (
                RecoveryStrategy.RETRY,
                RecoveryStrategy.RETRY_WITH_MODIFIED_PARAMETERS,
                RecoveryStrategy.RETRY_LATER,
            ):
                allocs = [
                    BudgetAllocation(resource_type=BudgetResourceType.RETRY, amount=1)
                ]
            else:
                allocs = [
                    BudgetAllocation(
                        resource_type=BudgetResourceType.OPERATION, amount=1
                    )
                ]

            try:
                reservation = budget_service.reserve(
                    budget_id=budget_id,
                    allocations=allocs,
                    operation_id=context.failed_operation_id,
                    workflow_id=context.workflow_id,
                    idempotency_key=decision.idempotency_key,
                )
            except (
                BudgetExhaustedError,
                InsufficientBudgetError,
                BudgetPausedError,
                BudgetCancelledError,
            ) as b_err:
                raise RecoveryBudgetError(
                    f"Action budget reservation failed for '{budget_id}': {b_err}"
                ) from b_err
            except Exception as b_err:
                if (
                    "exhausted" in str(b_err).lower()
                    or "insufficient" in str(b_err).lower()
                ):
                    raise RecoveryBudgetError(
                        f"Action budget reservation failed: {b_err}"
                    ) from b_err
                self._audit_event_errors.append(f"Budget reservation error: {b_err}")
        elif budget_service and hasattr(budget_service, "is_exhausted"):
            if budget_service.is_exhausted(budget_id):
                raise RecoveryBudgetError(f"Action budget '{budget_id}' is exhausted.")

        # Create starting attempt
        attempt = RecoveryAttempt(
            attempt_index=actual_attempt_index,
            strategy=decision.strategy,
            started_at=decision.decided_at,
            status=RecoveryStatus.EXECUTING,
        )
        self.repository.save_attempt(context.recovery_context_id, attempt)

        # Emit strategy/retry started events
        self._publish_event("RECOVERY_STRATEGY_STARTED", context, decision)
        if decision.strategy in (
            RecoveryStrategy.RETRY,
            RecoveryStrategy.RETRY_WITH_MODIFIED_PARAMETERS,
        ):
            self._publish_event("RETRY_STARTED", context, decision)

        # Execute executor
        try:
            strat_result: RecoveryStrategyResult = executor.execute(
                context=context,
                decision=decision,
                integrations=self.integrations,
            )
        except Exception as exc:  # noqa: BLE001
            strat_result = RecoveryStrategyResult(
                strategy=decision.strategy,
                status=RecoveryStatus.FAILED,
                success=False,
                error_message=f"Executor raised unhandled exception: {exc}",
            )

        # REAL ActionBudgetService Confirm or Fail Reservation
        if budget_service and reservation and hasattr(budget_service, "confirm"):
            try:
                if strat_result.success:
                    budget_service.confirm(
                        reservation_id=reservation.id,
                        outcome=BudgetConsumptionOutcome.SUCCESS,
                    )
                else:
                    budget_service.fail(
                        reservation_id=reservation.id,
                        reason=strat_result.error_message or "Recovery strategy failed",
                    )
            except Exception as c_err:  # noqa: BLE001
                self._audit_event_errors.append(f"Budget confirmation error: {c_err}")

        # Complete attempt
        final_status = strat_result.status
        completed_attempt = RecoveryAttempt(
            attempt_index=actual_attempt_index,
            strategy=decision.strategy,
            started_at=attempt.started_at,
            completed_at=decision.decided_at,
            status=final_status,
            result_outcome="success" if strat_result.success else "failure",
            error=strat_result.error_message,
        )
        self.repository.save_attempt(context.recovery_context_id, completed_attempt)

        exec_id = f"rec-exec-{uuid.uuid4().hex[:12]}"
        exec_result = RecoveryExecutionResult(
            recovery_execution_id=exec_id,
            recovery_decision_id=decision.recovery_decision_id,
            recovery_context_id=context.recovery_context_id,
            strategy=decision.strategy,
            status=final_status,
            success=strat_result.success,
            attempt=completed_attempt,
            strategy_result=strat_result,
            error=strat_result.error_message,
            fingerprint=decision.fingerprint,
        )
        saved_exec_result = self.repository.save_execution_result(exec_result)

        # Emit outcome events
        if strat_result.status == RecoveryStatus.PARTIALLY_SUCCEEDED:
            self._publish_event(
                "RECOVERY_STRATEGY_PARTIALLY_SUCCEEDED", context, decision
            )
        elif strat_result.success:
            self._publish_event("RECOVERY_STRATEGY_SUCCEEDED", context, decision)
        else:
            self._publish_event("RECOVERY_STRATEGY_FAILED", context, decision)

        if decision.strategy == RecoveryStrategy.ABORT:
            self._publish_event("RECOVERY_ABORTED", context, decision)

        return saved_exec_result

    def recover(
        self,
        context: RecoveryContext,
        exc: Exception | None = None,
        retry_policy: RetryPolicy | None = None,
        replan_policy: ReplanPolicy | None = None,
        rollback_policy: RollbackPolicy | None = None,
        escalation_policy: EscalationPolicy | None = None,
        checkpoint_obj: Any | None = None,
    ) -> RecoveryExecutionResult:
        """2-in-1 composition helper: Decide and immediately execute strategy."""
        decision = self.decide(
            context=context,
            exc=exc,
            retry_policy=retry_policy,
            replan_policy=replan_policy,
            rollback_policy=rollback_policy,
            escalation_policy=escalation_policy,
            checkpoint_obj=checkpoint_obj,
        )
        return self.execute(decision)
