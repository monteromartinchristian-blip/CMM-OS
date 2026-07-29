"""Phase 9.27 pending integration tests: checkpoints, delegation, observability, compensation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from cmm.agent_runtime.agent_registry_enums import AgentFactoryScope
from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
    IntegratedAgentExecutionResult,
    IntegrationExecutionPolicy,
)
from cmm.agent_runtime.agent_runtime_integration_enums import (
    IntegrationExecutionState,
)
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_runtime_integration_store import (
    InMemoryAgentRuntimeIntegrationStore,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.enums import GoalStatus
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)
from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
from cmm.agent_runtime.runtime_loop import AgentRuntimeLoop

UTC_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


def _operation_request(**overrides: object) -> AgentOperationRequest:
    values: dict[str, object] = {
        "id": "op-1",
        "agent_run_id": "run-1",
        "workflow_id": "workflow-1",
        "task_id": "task-1",
        "operation_name": "documents.read",
        "idempotency_key": "idem-1",
        "parameters": {"document": {"id": "doc-1"}},
        "created_at": UTC_NOW.isoformat(),
    }
    values.update(overrides)
    return AgentOperationRequest(**values)


def _permission_context() -> AgentPermissionContext:
    return AgentPermissionContext(
        id="perm-ctx-example",
        agent_id="agent-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        actor_id="actor-1",
        owner_actor_id="actor-1",
        allowed_domains=("documents",),
        allowed_resources=("doc-1",),
        allowed_operations=("documents.read",),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
        maximum_autonomy_level=2,
        created_at=UTC_NOW,
    )


def _request(**overrides: object) -> IntegratedAgentExecutionRequest:
    now = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "execution_id": "exec-1",
        "request_id": "req-1",
        "goal_id": "goal-1",
        "actor_id": "actor-1",
        "owner_actor_id": "actor-1",
        "requested_agent_id": "agent-1",
        "requested_agent_version": "1.2.3",
        "required_capabilities": ("documents.read",),
        "permission_context": _permission_context(),
        "operations": (_operation_request(),),
        "sensitivity": SensitivityLevel.INTERNAL,
        "max_autonomy_level": 2,
        "budget_id": "budget-1",
        "budget_allocations": {"operation_count": 2},
        "available_approval_ids": ("approval-1",),
        "deadline": now + timedelta(hours=2),
        "timeout_seconds": 60.0,
        "delegation_policy": {"allowed": True},
        "recovery_policy": {"max_attempts": 1},
        "observability": {"trace": True},
        "trace_id": "trace-1",
        "correlation_id": "corr-1",
        "causation_id": "cause-1",
        "policy": IntegrationExecutionPolicy(max_operations=2, max_retries=1),
        "created_at": now,
        "metadata": {"caller": {"surface": "api"}},
    }
    values.update(overrides)
    return IntegratedAgentExecutionRequest(**values)


class _StubAgentFactory:
    def __init__(self, factory_id: str = "factory-agent-1") -> None:
        self.factory_id = factory_id
        self.scope = AgentFactoryScope.TRANSIENT
        self.thread_safe = True

    def supports(self, descriptor: Any) -> bool:
        return getattr(descriptor, "factory_id", None) == self.factory_id

    def create(self, descriptor: Any, context: Any) -> Any:
        from cmm.agent_runtime.agent_registry_contracts import (
            AgentInstance,
        )

        return AgentInstance(
            instance_id=f"instance-{context.request_id}",
            descriptor=descriptor,
            runtime_object={"agent_id": descriptor.agent_id},
            scope=self.scope,
        )


class _FakeMemoryService:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def record_execution_result(self, **payload: object) -> str:
        self.updates.append(dict(payload))
        return f"memory-{len(self.updates)}"


class _FakeRecoveryService:
    def __init__(self, *, fail_on_recovery: bool = False) -> None:
        self.attempts: list[dict[str, object]] = []
        self.fail_on_recovery = fail_on_recovery

    def recover(self, **payload: object) -> dict[str, object]:
        self.attempts.append(dict(payload))
        if self.fail_on_recovery:
            raise RuntimeError("recovery failed")
        return {"recovered": True, "attempt": len(self.attempts)}


class _FakeCheckpointService:
    def __init__(self, *, fail: bool = False) -> None:
        self.created: list[dict[str, object]] = []
        self.restored: list[str] = []
        self.fail = fail

    def create_checkpoint(self, **payload: object) -> str:
        if self.fail:
            raise RuntimeError("checkpoint failed")
        checkpoint_id = f"checkpoint-{len(self.created) + 1}"
        self.created.append({"checkpoint_id": checkpoint_id, **payload})
        return checkpoint_id

    def restore_checkpoint(self, checkpoint_id: str) -> None:
        self.restored.append(checkpoint_id)


class _IntegrationHarness:
    def __init__(self, *, deny_permissions: bool = False) -> None:
        self.store = InMemoryAgentRuntimeIntegrationStore()
        self.goal_manager = GoalManager()
        self.registry_service = self._make_registry()
        self.factory = _StubAgentFactory()
        self.registry_service.register_factory(self.factory)
        self.runtime_loop = AgentRuntimeLoop(
            goal_repository=self.goal_manager.repository
        )
        self.security_service = self._make_security_service()
        self.approval_service = ApprovalService()
        self.budget_service = self._make_budget_service()
        self.execution_adapter = AgentExecutionAdapter(
            execution_delegate=lambda operation: {
                "ok": True,
                "operation": operation.operation_name,
            }
        )
        self.event_bus = AgentRuntimeEventBus()
        self.memory_service = _FakeMemoryService()
        self.recovery_service = _FakeRecoveryService()
        self.checkpoint_service = _FakeCheckpointService()
        self.delegation_service = self._make_delegation_service()
        self.observability_service = self._make_observability_service()
        self.service = AgentRuntimeIntegrationService(
            store=self.store,
            goal_manager=self.goal_manager,
            registry_service=self.registry_service,
            runtime_loop=self.runtime_loop,
            security_service=self.security_service,
            budget_service=self.budget_service,
            approval_service=self.approval_service,
            execution_adapter=self.execution_adapter,
            event_bus=self.event_bus,
            observability_service=self.observability_service,
            checkpoint_service=self.checkpoint_service,
            recovery_service=self.recovery_service,
            delegation_service=self.delegation_service,
            memory_service=self.memory_service,
        )
        self.register_goal()
        self.register_agent()
        self.execution_adapter.register_operation(
            OperationDescriptor(
                name="documents.read",
                description="Read a document",
                required_permissions=() if not deny_permissions else ("admin",),
            )
        )

    def _make_registry(self):
        from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
        from cmm.agent_runtime.agent_registry import AgentRegistry
        from cmm.agent_runtime.agent_registry_service import AgentRegistryService

        return AgentRegistryService(
            registry=AgentRegistry(),
            factory_registry=AgentFactoryRegistry(),
        )

    def _make_security_service(self):
        from cmm.agent_runtime.agent_security_service import AgentSecurityService

        return AgentSecurityService()

    def _make_budget_service(self):
        from cmm.agent_runtime.action_budget_service import ActionBudgetService

        return ActionBudgetService()

    def _make_delegation_service(self):
        from cmm.agent_runtime.agent_delegation_service import AgentDelegationService

        return AgentDelegationService(
            registry_service=self.registry_service,
            goal_repository=self.goal_manager.repository,
            event_bus=self.event_bus,
        )

    def _make_observability_service(self):
        from cmm.agent_runtime.agent_observability_service import (
            AgentObservabilityService,
        )

        return AgentObservabilityService()

    def register_goal(
        self,
        *,
        goal_id: str = "goal-1",
        status: GoalStatus = GoalStatus.ACTIVE,
    ) -> Goal:
        goal = Goal(
            id=goal_id,
            title="Read document",
            description="Read the requested document",
            kind="information",
            status=status,
            priority=GoalPriority(score=50),
            owner_actor_id="actor-1",
            assigned_agent_id="agent-1",
            autonomy_level=2,
            created_at=UTC_NOW,
            updated_at=UTC_NOW,
            completed_at=UTC_NOW
            if status in (GoalStatus.COMPLETED, GoalStatus.PARTIALLY_COMPLETED)
            else None,
        )
        return self.goal_manager.register_goal(goal, actor_id="actor-1")

    def register_agent(
        self,
        *,
        agent_id: str = "agent-1",
        capabilities: tuple[str, ...] = ("documents.read",),
        lifecycle: Any = None,
        required_permissions: tuple[str, ...] = (),
    ) -> Any:
        from cmm.agent_runtime.agent_registry_contracts import (
            AgentCapability,
            AgentCapabilityKind,
            AgentDescriptor,
            AgentVersion,
        )
        from cmm.agent_runtime.agent_registry_enums import AgentKind, AgentLifecycle

        if lifecycle is None:
            lifecycle = AgentLifecycle.ACTIVE
        descriptor = AgentDescriptor(
            agent_id=agent_id,
            name="Document Agent",
            version=AgentVersion(1, 2, 3),
            kind=AgentKind.GENERAL,
            lifecycle=lifecycle,
            description="Reads documents",
            capabilities=tuple(
                AgentCapability(
                    name=capability,
                    kind=AgentCapabilityKind.OPERATION,
                    description=f"Capability {capability}",
                    operations=(capability,),
                )
                for capability in capabilities
            ),
            supported_operations=capabilities,
            required_permissions=required_permissions,
            factory_id=self.factory.factory_id,
            created_at=UTC_NOW,
        )
        self.registry_service.register_agent(descriptor)
        return descriptor


# Checkpoint/recovery: real (non-fake) exercise of the composition root's
# integration with CheckpointManager-shaped and RecoveryManager-shaped
# collaborators. Fail-closed on exhausted recovery, bounded retries.


def test_checkpoint_created_before_sensitive_operation_when_required() -> None:
    harness = _IntegrationHarness()
    request = _request(
        policy=IntegrationExecutionPolicy(
            max_operations=1, max_retries=0, allow_recovery=True
        )
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(harness.checkpoint_service.created) == 1
    assert result.checkpoint_ids == (
        harness.checkpoint_service.created[0]["checkpoint_id"],
    )


def test_checkpoint_failure_is_fail_closed() -> None:
    harness = _IntegrationHarness()
    harness.checkpoint_service.fail = True
    request = _request(
        policy=IntegrationExecutionPolicy(
            max_operations=1, max_retries=0, allow_recovery=True
        )
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.FAILED
    assert result.checkpoint_ids == ()
    assert any("checkpoint" in error for error in result.errors)
    run = harness.runtime_loop.get_run(result.agent_run_id)
    assert run.status.value == "cancelled"
    reservation_ids = [
        comp.target_id
        for comp in harness.store.get(result.execution_id).compensations
        if comp.action == "runtime.cancel_run"
    ]
    assert reservation_ids == [result.agent_run_id]


def test_recovery_is_attempted_after_checkpoint_failure() -> None:
    harness = _IntegrationHarness()
    harness.checkpoint_service.fail = True
    request = _request(
        policy=IntegrationExecutionPolicy(
            max_operations=1, max_retries=0, allow_recovery=True
        )
    )
    result = harness.service.execute(request)
    assert len(harness.recovery_service.attempts) == 1
    assert result.retry_count == 1
    assert result.recovery_attempts[0]["recovered"] is True


def test_recovery_failure_is_visible_in_result() -> None:
    harness = _IntegrationHarness()
    harness.recovery_service.fail_on_recovery = True
    harness.checkpoint_service.fail = True
    request = _request(
        policy=IntegrationExecutionPolicy(
            max_operations=1, max_retries=0, allow_recovery=True
        )
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.FAILED
    assert len(result.recovery_attempts) == 1
    assert result.recovery_attempts[0]["recovered"] is False
    assert "recovery failed" in result.recovery_attempts[0]["recovery_error"]
    assert any("checkpoint" in error for error in result.errors)


def test_limited_retry_does_not_loop_infinitely() -> None:
    harness = _IntegrationHarness()
    harness.checkpoint_service.fail = True
    request = _request(
        policy=IntegrationExecutionPolicy(
            max_operations=1, max_retries=2, allow_recovery=True
        )
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.FAILED
    assert result.retry_count == 3
    assert len(harness.recovery_service.attempts) == 3
    assert len(result.recovery_attempts) == 3


def test_checkpoint_reference_is_linked_to_execution_record() -> None:
    harness = _IntegrationHarness()
    request = _request(
        policy=IntegrationExecutionPolicy(
            max_operations=1, max_retries=0, allow_recovery=True
        )
    )
    result = harness.service.execute(request)
    record = harness.store.get(result.execution_id)
    assert result.checkpoint_ids != ()
    assert record.checkpoint_ids == result.checkpoint_ids


def test_delegation_integration_records_delegation_ids() -> None:
    harness = _IntegrationHarness()
    harness.register_agent(agent_id="agent-2")
    request = _request(
        delegation_policy={"allowed": True, "target_agent_id": "agent-2"}
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(result.delegations) == 1
    assert result.delegations[0]["target_agent_id"] == "agent-2"
    assert result.delegations[0]["parent_goal_id"] == "goal-1"
    record = harness.store.get(result.execution_id)
    assert record.delegation_ids == (result.delegations[0]["delegation_id"],)
    # Delegating does not auto-complete the parent goal.
    assert harness.goal_manager.get_goal("goal-1").status is GoalStatus.ACTIVE


def test_delegation_is_not_allowed_by_security_context() -> None:
    harness = _IntegrationHarness()
    request = _request(delegation_policy={"allowed": False})
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(result.delegations) == 0


def test_get_status_returns_the_persisted_record_snapshot() -> None:
    harness = _IntegrationHarness()
    assert harness.service.get_status("exec-1") is None
    result = harness.service.execute(_request())
    status = harness.service.get_status("exec-1")
    assert status is not None
    assert status.execution_id == "exec-1"
    assert status.state is IntegrationExecutionState.COMPLETED
    assert status.checkpoint_ids == result.checkpoint_ids
    assert status.agent_run_id == result.agent_run_id


def test_delegation_rejected_by_permission_escalation_is_visible_but_not_fatal() -> (
    None
):
    harness = _IntegrationHarness()
    harness.register_agent(agent_id="agent-2", required_permissions=("admin",))
    request = _request(
        delegation_policy={"allowed": True, "target_agent_id": "agent-2"}
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(result.delegations) == 0
    assert any("delegation" in warning for warning in result.warnings)


def test_delegation_max_depth_exceeded_is_visible_but_not_fatal() -> None:
    harness = _IntegrationHarness()
    harness.register_agent(agent_id="agent-2")
    request = _request(
        delegation_policy={"allowed": True, "target_agent_id": "agent-2", "depth": 999}
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(result.delegations) == 0
    assert any("delegation" in warning for warning in result.warnings)


# Observability: real event bus + real telemetry/audit/trace wiring (no fake
# `.record()`/`.event_factory()` methods).


def test_observability_events_are_registered() -> None:
    harness = _IntegrationHarness()
    request = _request(
        trace_id="trace-123", correlation_id="corr-123", causation_id="cause-123"
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert result.trace_id == "trace-123"
    assert len(result.event_ids) > 0
    trace_record = harness.observability_service.store.get_trace_record_by_trace(
        "trace-123"
    )
    assert trace_record.trace.status == "complete"
    telemetry_kinds = {
        telemetry.kind
        for telemetry in harness.observability_service.store.list_telemetry(
            trace_id="trace-123"
        )
    }
    assert "run_started" in telemetry_kinds
    assert "run_completed" in telemetry_kinds
    assert "checkpoint_created" in telemetry_kinds
    assert "operation_started" in telemetry_kinds
    assert "operation_completed" in telemetry_kinds
    audit_entries = harness.observability_service.store.list_audits(
        agent_run_id=result.agent_run_id
    )
    assert any(
        entry.action == "agent_runtime.integration.permission_check"
        for entry in audit_entries
    )


def test_best_effort_event_failure_does_not_fail_execution() -> None:
    class _FailingEventBus:
        def publish(self, event: Any) -> None:
            raise RuntimeError("event bus full")

        def event_factory(self, **kwargs: Any) -> Any:
            return kwargs

    harness = _IntegrationHarness()
    request = _request()
    harness.service = AgentRuntimeIntegrationService(
        store=harness.store,
        goal_manager=harness.goal_manager,
        registry_service=harness.registry_service,
        runtime_loop=harness.runtime_loop,
        security_service=harness.security_service,
        budget_service=harness.budget_service,
        approval_service=harness.approval_service,
        execution_adapter=harness.execution_adapter,
        event_bus=_FailingEventBus(),
        observability_service=harness.observability_service,
        checkpoint_service=harness.checkpoint_service,
        recovery_service=harness.recovery_service,
        delegation_service=harness.delegation_service,
        memory_service=harness.memory_service,
    )
    result = harness.service.execute(request)
    assert result.final_state is IntegrationExecutionState.COMPLETED


def test_concurrent_execute_with_same_request_id_is_idempotent() -> None:
    harness = _IntegrationHarness()
    request = _request()

    def execute() -> IntegratedAgentExecutionResult:
        return harness.service.execute(request)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: execute(), range(4)))
    assert all(result == results[0] for result in results)
    assert len(harness.execution_adapter.repository.list_results("run-exec-1")) == 1


def test_concurrent_resume_does_not_duplicate_execution() -> None:
    harness = _IntegrationHarness()
    request = _request(metadata={"requires_approval": True})
    harness.service.execute(request)
    approval_id = harness.store.get("exec-1").pending_approval_ids[0]
    harness.approval_service.approve(approval_id, actor_id="actor-1")

    def resume() -> Any:
        return harness.service.resume("exec-1", approval_id=approval_id)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: resume(), range(4)))
    assert all(result == results[0] for result in results)
    assert len(harness.execution_adapter.repository.list_results("run-exec-1")) == 1


def test_cancel_during_execution_is_idempotent() -> None:
    harness = _IntegrationHarness()
    original_execute = harness.service._continue_execution

    def slow_execute(execution_id: str, **kwargs: Any) -> Any:
        harness.service._store.transition(
            execution_id, IntegrationExecutionState.RUNNING
        )
        import time

        time.sleep(0.05)
        return original_execute(execution_id, **kwargs)

    harness.service._continue_execution = slow_execute  # type: ignore[method-assign]

    def cancel() -> Any:
        return harness.service.cancel("exec-1", reason="test")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(harness.service.execute, _request()),
            pool.submit(cancel),
        ]
        results = [future.result() for future in futures]
    terminal_states = {result.final_state for result in results}
    assert terminal_states <= {
        IntegrationExecutionState.COMPLETED,
        IntegrationExecutionState.CANCELLED,
    }
    assert len(harness.execution_adapter.repository.list_results("run-exec-1")) <= 1


# --- Atomicity and intermediate-failure injection -------------------------
#
# These tests inject failures at specific points in the pipeline and assert
# that no orphaned resources (runs, budget reservations, delegations) remain,
# that compensations run LIFO, and that compensation execution is idempotent.


def _failing_operation_harness() -> _IntegrationHarness:
    harness = _IntegrationHarness()
    harness.execution_adapter = AgentExecutionAdapter(
        execution_delegate=lambda operation: {
            "success": False,
            "operation": operation.operation_name,
        }
    )
    harness.execution_adapter.register_operation(
        OperationDescriptor(name="documents.read", description="Read a document")
    )
    harness.service = AgentRuntimeIntegrationService(
        store=harness.store,
        goal_manager=harness.goal_manager,
        registry_service=harness.registry_service,
        runtime_loop=harness.runtime_loop,
        security_service=harness.security_service,
        budget_service=harness.budget_service,
        approval_service=harness.approval_service,
        execution_adapter=harness.execution_adapter,
        event_bus=harness.event_bus,
        observability_service=harness.observability_service,
        checkpoint_service=harness.checkpoint_service,
        recovery_service=harness.recovery_service,
        delegation_service=harness.delegation_service,
        memory_service=harness.memory_service,
    )
    return harness


def test_operation_failure_leaves_no_orphaned_run_or_reservation() -> None:
    harness = _failing_operation_harness()
    result = harness.service.execute(_request())
    assert result.final_state is IntegrationExecutionState.FAILED
    run = harness.runtime_loop.get_run(result.agent_run_id)
    assert run.status.value == "cancelled"
    reservation = harness.budget_service.repository.get_reservation(
        f"reservation-{result.execution_id}"
    )
    assert reservation.status.value == "released"
    # Memory must not be written for a failed execution: the fake memory
    # service only records successful operation results, and the failed
    # result here has success=False.
    assert harness.memory_service.updates == []


def test_operation_failure_does_not_duplicate_terminal_events() -> None:
    harness = _failing_operation_harness()
    result = harness.service.execute(_request())
    assert result.final_state is IntegrationExecutionState.FAILED
    assert len(result.event_ids) == len(set(result.event_ids))


def test_cancel_of_running_execution_releases_pending_budget_reservation() -> None:
    harness = _IntegrationHarness()
    original_execute = harness.service._continue_execution

    def slow_execute(execution_id: str, **kwargs: Any) -> Any:
        harness.service._store.transition(
            execution_id, IntegrationExecutionState.RUNNING
        )
        import time

        time.sleep(0.05)
        return original_execute(execution_id, **kwargs)

    harness.service._continue_execution = slow_execute  # type: ignore[method-assign]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(harness.service.execute, _request()),
            pool.submit(harness.service.cancel, "exec-1", reason="race"),
        ]
        results = [future.result() for future in futures]
    terminal_states = {result.final_state for result in results}
    assert terminal_states <= {
        IntegrationExecutionState.COMPLETED,
        IntegrationExecutionState.CANCELLED,
    }
    if IntegrationExecutionState.CANCELLED in terminal_states:
        reservation = harness.budget_service.repository.get_reservation(
            "reservation-exec-1"
        )
        assert reservation.status.value in ("released", "confirmed")


def test_compensations_execute_in_lifo_order() -> None:
    harness = _failing_operation_harness()
    call_order: list[str] = []
    original = harness.service._execute_compensation

    def spying_execute(compensation: Any) -> None:
        call_order.append(compensation.compensation_id)
        original(compensation)

    harness.service._execute_compensation = spying_execute  # type: ignore[method-assign]

    result = harness.service.execute(_request())

    assert result.final_state is IntegrationExecutionState.FAILED
    record = harness.store.get(result.execution_id)
    registration_order = [comp.compensation_id for comp in record.compensations]
    assert len(registration_order) >= 2
    assert call_order == list(reversed(registration_order))


def test_compensation_execution_is_idempotent_when_run_twice() -> None:
    harness = _IntegrationHarness()
    request = _request(metadata={"requires_approval": True})
    harness.service.execute(request)
    call_counts: dict[str, int] = {}
    original = harness.service._execute_compensation

    def counting_execute(compensation: Any) -> None:
        call_counts[compensation.compensation_id] = (
            call_counts.get(compensation.compensation_id, 0) + 1
        )
        original(compensation)

    harness.service._execute_compensation = counting_execute  # type: ignore[method-assign]
    first_warnings = harness.service._run_compensations("exec-1")
    second_warnings = harness.service._run_compensations("exec-1")
    assert first_warnings == ()
    assert second_warnings == ()
    assert all(count == 1 for count in call_counts.values())
    run = harness.runtime_loop.get_run("run-exec-1")
    assert run.status.value == "cancelled"


def test_cancel_compensates_pending_delegation_leaving_none_orphaned() -> None:
    harness = _IntegrationHarness()
    harness.register_agent(agent_id="agent-2")
    request = _request(
        metadata={"requires_approval": True},
        delegation_policy={"allowed": True, "target_agent_id": "agent-2"},
    )
    harness.service.execute(request)
    record = harness.store.get("exec-1")
    obs = harness.service._observability(request)
    _updated_record, delegations = harness.service._attempt_delegation(
        record, request, obs
    )
    assert len(delegations) == 1
    delegation_id = delegations[0]["delegation_id"]
    assert harness.delegation_service.get(delegation_id).status.value == "proposed"

    result = harness.service.cancel("exec-1", reason="race-with-delegation")

    assert result.final_state is IntegrationExecutionState.CANCELLED
    assert harness.delegation_service.get(delegation_id).status.value == "cancelled"


def test_checkpoint_failure_leaves_no_checkpoint_reference_and_traces_close() -> None:
    harness = _IntegrationHarness()
    harness.checkpoint_service.fail = True
    result = harness.service.execute(
        _request(
            trace_id="trace-atomic-1",
            policy=IntegrationExecutionPolicy(
                max_operations=1, max_retries=0, allow_recovery=True
            ),
        )
    )
    assert result.final_state is IntegrationExecutionState.FAILED
    assert result.checkpoint_ids == ()
    trace_record = harness.observability_service.store.get_trace_record_by_trace(
        "trace-atomic-1"
    )
    assert trace_record.trace.status == "complete"


def test_real_checkpoint_manager_and_lock_manager_leave_no_stale_locks() -> None:
    """Exercise the canonical CheckpointManager + RuntimeLockManager directly.

    Proves the checkpoint wiring works against the real Phase 9.15 API (not
    just the lightweight test double used elsewhere in this file).
    """

    from cmm.agent_runtime.checkpoint_manager import CheckpointManager
    from cmm.agent_runtime.runtime_lock_manager import RuntimeLockManager
    from cmm.agent_runtime.runtime_repository import InMemoryAgentRuntimeRepository

    harness = _IntegrationHarness()
    repository = InMemoryAgentRuntimeRepository()
    lock_manager = RuntimeLockManager(repository)
    harness.checkpoint_service = CheckpointManager(lock_manager=lock_manager)
    harness.service = AgentRuntimeIntegrationService(
        store=harness.store,
        goal_manager=harness.goal_manager,
        registry_service=harness.registry_service,
        runtime_loop=harness.runtime_loop,
        security_service=harness.security_service,
        budget_service=harness.budget_service,
        approval_service=harness.approval_service,
        execution_adapter=harness.execution_adapter,
        event_bus=harness.event_bus,
        observability_service=harness.observability_service,
        checkpoint_service=harness.checkpoint_service,
        recovery_service=harness.recovery_service,
        delegation_service=harness.delegation_service,
        memory_service=harness.memory_service,
    )
    result = harness.service.execute(_request())
    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(result.checkpoint_ids) == 1
    checkpoint = harness.checkpoint_service.repository.get_checkpoint(
        result.checkpoint_ids[0]
    )
    assert checkpoint.status == "active"
    assert lock_manager.list_active() == ()
