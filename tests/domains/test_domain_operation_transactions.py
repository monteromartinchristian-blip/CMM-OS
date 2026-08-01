from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.enums import AgentOperationExecutionStatus
from cmm.agent_runtime.errors import TransactionRollbackError
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationExecutionResult,
    AgentOperationRequest,
)
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.domains import (
    DefaultDomainOperationOrchestrator,
    DomainOperationDefinition,
    DomainOperationExecutionDelegate,
    DomainOperationRequest,
    DomainOperationStatus,
    DomainOperationType,
    InMemoryDomainOperationRegistry,
)


class Boundary:
    id = "transaction:1"


class TransactionManagerSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def start_transaction(self, **kwargs: object):
        self.calls.append("start")
        return Boundary(), "checkpoint:1"

    def register_operation(self, **kwargs: object) -> None:
        self.calls.append("register")

    def commit(self, transaction_id: str) -> None:
        self.calls.append("commit")

    def mark_rollback_started(self, transaction_id: str) -> None:
        self.calls.append("rollback_started")

    def mark_rolled_back(self, transaction_id: str) -> None:
        self.calls.append("rolled_back")


class RollbackSpy:
    def __init__(self, succeeds: bool = True) -> None:
        self.succeeds = succeeds
        self.calls = 0

    def rollback(self, transaction_id: str, checkpoint_id: str | None) -> bool:
        self.calls += 1
        return self.succeeds


class FailingCloseTransactionManager(TransactionManagerSpy):
    def mark_rolled_back(self, transaction_id: str) -> None:
        self.calls.append("rolled_back")
        raise TransactionRollbackError("transaction close failed")


def _execute_cancelled(*, manager=None, rollback=None, reversible: bool = True):
    definition = DomainOperationDefinition(
        operation_id="project.prepare_change_review",
        domain_id="domain:project",
        version="1.0.0",
        name="Prepare review",
        description="Prepare change review",
        operation_type=DomainOperationType.PREPARATION,
        reversible=reversible,
        rollback_policy_id="rollback.safe" if reversible else None,
        output_schema={"type": "object"},
    )

    class Implementation:
        def __init__(self) -> None:
            self.definition = definition

        def execute(self, request: AgentOperationRequest) -> dict[str, object]:
            return {"success": True, "output": {}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())

    class CancelledAdapter:
        registry = common

        def execute(
            self, request: AgentOperationRequest
        ) -> AgentOperationExecutionResult:
            now = datetime.now(timezone.utc).isoformat()
            return AgentOperationExecutionResult(
                id="common:cancelled",
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name=request.operation_name,
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                status=AgentOperationExecutionStatus.CANCELLED,
                success=False,
                error={"code": "OPERATION_CANCELLED", "details": {}},
                started_at=now,
                completed_at=now,
            )

    capabilities = ("execute", "transaction", "rollback") if manager else ("execute",)
    request = DomainOperationRequest(
        request_id="request:cancel",
        operation_id=definition.operation_id,
        operation_version=definition.version,
        inputs={},
        agent_run_id="run:1",
        workflow_id="workflow:1",
        task_id="task:1",
        primary_domain_id="domain:project",
        idempotency_key="idem:cancel",
        capabilities=capabilities,
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        CancelledAdapter(),
        transaction_manager=manager,
        rollback_executor=rollback,
    )
    return orchestrator.execute(request), manager, rollback


def _execute(*, success: bool, rollback_succeeds: bool = True):
    definition = DomainOperationDefinition(
        operation_id="project.prepare_change_review",
        domain_id="domain:project",
        version="1.0.0",
        name="Prepare review",
        description="Prepare change review",
        operation_type=DomainOperationType.PREPARATION,
        reversible=True,
        rollback_policy_id="rollback.safe",
        output_schema={"type": "object"},
    )

    class Implementation:
        def __init__(self) -> None:
            self.definition = definition

        def execute(self, request: AgentOperationRequest) -> dict[str, object]:
            return {"success": success, "output": {}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())
    adapter = AgentExecutionAdapter(
        registry=common, execution_delegate=DomainOperationExecutionDelegate(registry)
    )
    manager = TransactionManagerSpy()
    rollback = RollbackSpy(rollback_succeeds)
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        transaction_manager=manager,
        rollback_executor=rollback,
    )
    request = DomainOperationRequest(
        request_id="request:tx",
        operation_id=definition.operation_id,
        operation_version=definition.version,
        inputs={},
        agent_run_id="run:1",
        workflow_id="workflow:1",
        task_id="task:1",
        primary_domain_id="domain:project",
        idempotency_key="idem:tx",
        capabilities=("execute", "transaction", "rollback"),
    )
    return orchestrator.execute(request), manager, rollback


def test_reversible_success_uses_common_transaction_and_commits_after_validation() -> (
    None
):
    result, manager, rollback = _execute(success=True)
    assert result.status is DomainOperationStatus.COMPLETED
    assert result.transaction_id == "transaction:1"
    assert manager.calls == ["start", "register", "commit"]
    assert rollback.calls == 0


def test_execution_failure_rolls_back_successfully() -> None:
    result, manager, rollback = _execute(success=False)
    assert result.status is DomainOperationStatus.ROLLED_BACK
    assert manager.calls == ["start", "rollback_started", "rolled_back"]
    assert rollback.calls == 1
    assert result.rollback_result.succeeded is True


def test_rollback_failure_preserves_original_and_rollback_errors() -> None:
    result, manager, _rollback = _execute(success=False, rollback_succeeds=False)
    assert result.status is DomainOperationStatus.FAILED
    assert result.error["code"] == "OPERATION_EXECUTION_FAILED"
    assert result.rollback_result.error["code"] == "DOMAIN_OPERATION_ROLLBACK_ERROR"
    assert manager.calls == ["start", "rollback_started"]


def test_cancellation_without_transaction_remains_cancelled() -> None:
    result, manager, rollback = _execute_cancelled(reversible=False)
    assert result.status is DomainOperationStatus.CANCELLED
    assert result.error["code"] == "OPERATION_CANCELLED"
    assert manager is None
    assert rollback is None


def test_cancellation_rolls_back_and_closes_reversible_transaction() -> None:
    manager = TransactionManagerSpy()
    rollback = RollbackSpy()
    result, _manager, _rollback = _execute_cancelled(manager=manager, rollback=rollback)
    assert result.status is DomainOperationStatus.CANCELLED
    assert result.error["code"] == "OPERATION_CANCELLED"
    assert result.rollback_result.succeeded is True
    assert manager.calls == ["start", "rollback_started", "rolled_back"]
    assert rollback.calls == 1


def test_cancellation_rollback_failure_is_structured_and_not_hidden() -> None:
    manager = TransactionManagerSpy()
    rollback = RollbackSpy(succeeds=False)
    result, _manager, _rollback = _execute_cancelled(manager=manager, rollback=rollback)
    assert result.status is DomainOperationStatus.FAILED
    assert result.error["code"] == "OPERATION_CANCELLED"
    assert result.rollback_result.error["code"] == "DOMAIN_OPERATION_ROLLBACK_ERROR"
    assert manager.calls == ["start", "rollback_started"]
    assert rollback.calls == 1


def test_cancellation_close_failure_is_structured_and_not_hidden() -> None:
    manager = FailingCloseTransactionManager()
    rollback = RollbackSpy()
    result, _manager, _rollback = _execute_cancelled(manager=manager, rollback=rollback)
    assert result.status is DomainOperationStatus.FAILED
    assert result.error["code"] == "OPERATION_CANCELLED"
    assert result.rollback_result.error["code"] == "DOMAIN_OPERATION_ROLLBACK_ERROR"
    assert manager.calls == ["start", "rollback_started", "rolled_back"]
    assert rollback.calls == 1
