from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.enums import AgentOperationExecutionStatus
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
    DomainOperationValidationError,
    InMemoryDomainOperationRegistry,
)


def _definition(**overrides: object) -> DomainOperationDefinition:
    values = {
        "operation_id": "general.prepare_structured_summary",
        "domain_id": "domain:general",
        "version": "1.0.0",
        "name": "Prepare summary",
        "description": "Prepare safe structure",
        "operation_type": DomainOperationType.PREPARATION,
        "reversible": False,
        "input_schema": {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
            "additionalProperties": False,
        },
    }
    values.update(overrides)
    return DomainOperationDefinition(**values)  # type: ignore[arg-type]


def _request(**overrides: object) -> DomainOperationRequest:
    values = {
        "request_id": "request:1",
        "operation_id": "general.prepare_structured_summary",
        "operation_version": "1.0.0",
        "inputs": {"text": "hello"},
        "agent_run_id": "run:1",
        "task_id": "task:1",
        "primary_domain_id": "domain:general",
        "idempotency_key": "idem:1",
        "capabilities": ("execute",),
    }
    values.update(overrides)
    return DomainOperationRequest(**values)  # type: ignore[arg-type]


class SummaryImplementation:
    def __init__(self, definition: DomainOperationDefinition) -> None:
        self.definition = definition
        self.calls = 0

    def execute(self, request: AgentOperationRequest) -> dict[str, object]:
        self.calls += 1
        return {
            "success": True,
            "output": {"summary": request.parameters["text"].upper()},
        }


def _system(definition: DomainOperationDefinition | None = None):
    definition = definition or _definition()
    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    implementation = SummaryImplementation(definition)
    registry.register(definition, implementation)
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
    )
    orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
    return orchestrator, implementation


def test_end_to_end_execution_delegates_through_common_adapter() -> None:
    orchestrator, implementation = _system()
    result = orchestrator.execute(_request())
    assert implementation.calls == 1
    assert result.status is DomainOperationStatus.COMPLETED
    assert result.output == {"summary": "HELLO"}
    assert result.operation_id == "general.prepare_structured_summary"


def test_invalid_input_fails_before_implementation() -> None:
    orchestrator, implementation = _system()
    with pytest.raises(DomainOperationValidationError, match="input"):
        orchestrator.execute(_request(inputs={"unknown": True}))
    assert implementation.calls == 0


def test_invalid_output_is_structured_failure() -> None:
    definition = _definition()

    class InvalidOutput(SummaryImplementation):
        def execute(self, request: AgentOperationRequest) -> dict[str, object]:
            self.calls += 1
            return {"success": True, "output": {"unexpected": True}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    implementation = InvalidOutput(definition)
    registry.register(definition, implementation)
    adapter = AgentExecutionAdapter(
        registry=common, execution_delegate=DomainOperationExecutionDelegate(registry)
    )
    result = DefaultDomainOperationOrchestrator(registry, adapter).execute(_request())
    assert result.status is DomainOperationStatus.FAILED
    assert result.error["code"] == "DOMAIN_OPERATION_VALIDATION_ERROR"


def test_programming_exception_from_implementation_is_not_hidden() -> None:
    definition = _definition()

    class Broken(SummaryImplementation):
        def execute(self, request: AgentOperationRequest) -> dict[str, object]:
            raise TypeError("implementation bug")

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Broken(definition))
    adapter = AgentExecutionAdapter(
        registry=common, execution_delegate=DomainOperationExecutionDelegate(registry)
    )
    with pytest.raises(TypeError, match="implementation bug"):
        DefaultDomainOperationOrchestrator(registry, adapter).execute(_request())


def test_orchestrator_does_not_access_implementation() -> None:
    definition = _definition()

    class DefinitionOnlyRegistry:
        common_registry = InMemoryAgentOperationRegistry()

        def __init__(self) -> None:
            self.common_registry.register(definition.to_operation_descriptor())

        def get(self, operation_id: str, version: str) -> DomainOperationDefinition:
            return definition

        def get_implementation(self, operation_id: str, version: str) -> object:
            raise AssertionError("orchestrator must not access implementation")

    class Adapter:
        def __init__(self, registry: InMemoryAgentOperationRegistry) -> None:
            self.registry = registry
            self.calls = 0

        def execute(
            self, request: AgentOperationRequest
        ) -> AgentOperationExecutionResult:
            self.calls += 1
            now = datetime.now(timezone.utc).isoformat()
            return AgentOperationExecutionResult(
                id="common:result",
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name=request.operation_name,
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                status=AgentOperationExecutionStatus.COMPLETED,
                success=True,
                output={"summary": "safe"},
                started_at=now,
                completed_at=now,
            )

    registry = DefinitionOnlyRegistry()
    adapter = Adapter(registry.common_registry)
    result = DefaultDomainOperationOrchestrator(registry, adapter).execute(_request())  # type: ignore[arg-type]
    assert adapter.calls == 1
    assert result.status is DomainOperationStatus.COMPLETED


def test_validation_policy_is_delegated_to_common_adapter() -> None:
    definition = _definition(validation_policy_id="validation:domain-output")

    class Registry:
        common_registry = InMemoryAgentOperationRegistry()

        def __init__(self) -> None:
            self.common_registry.register(definition.to_operation_descriptor())

        def get(self, operation_id: str, version: str) -> DomainOperationDefinition:
            return definition

    class Adapter:
        registry = Registry.common_registry

        def __init__(self) -> None:
            self.request: AgentOperationRequest | None = None

        def execute(
            self, request: AgentOperationRequest
        ) -> AgentOperationExecutionResult:
            self.request = request
            now = datetime.now(timezone.utc).isoformat()
            return AgentOperationExecutionResult(
                id="common:validated",
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name=request.operation_name,
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                status=AgentOperationExecutionStatus.COMPLETED,
                success=True,
                output={"summary": "safe"},
                started_at=now,
                completed_at=now,
            )

    adapter = Adapter()
    result = DefaultDomainOperationOrchestrator(Registry(), adapter).execute(  # type: ignore[arg-type]
        _request(capabilities=("execute", "validation"))
    )
    assert result.status is DomainOperationStatus.COMPLETED
    assert adapter.request is not None
    assert adapter.request.metadata["requires_validation"] is True
    assert adapter.request.metadata["validation_policy_id"] == "validation:domain-output"


def test_common_result_identity_mismatch_is_contract_error() -> None:
    definition = _definition()

    class Registry:
        common_registry = InMemoryAgentOperationRegistry()

        def __init__(self) -> None:
            self.common_registry.register(definition.to_operation_descriptor())

        def get(self, operation_id: str, version: str) -> DomainOperationDefinition:
            return definition

    class Adapter:
        registry = Registry.common_registry

        def execute(
            self, request: AgentOperationRequest
        ) -> AgentOperationExecutionResult:
            now = datetime.now(timezone.utc).isoformat()
            return AgentOperationExecutionResult(
                id="common:result",
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name="general.other",
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                success=True,
                output={"summary": "safe"},
                started_at=now,
                completed_at=now,
            )

    with pytest.raises(Exception, match="identity"):
        DefaultDomainOperationOrchestrator(Registry(), Adapter()).execute(_request())  # type: ignore[arg-type]


def test_common_cancellation_maps_to_domain_cancelled() -> None:
    definition = _definition()

    class Registry:
        common_registry = InMemoryAgentOperationRegistry()

        def __init__(self) -> None:
            self.common_registry.register(definition.to_operation_descriptor())

        def get(self, operation_id: str, version: str) -> DomainOperationDefinition:
            return definition

    class Adapter:
        registry = Registry.common_registry

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
                started_at=now,
                completed_at=now,
            )

    result = DefaultDomainOperationOrchestrator(Registry(), Adapter()).execute(  # type: ignore[arg-type]
        _request()
    )
    assert result.status is DomainOperationStatus.CANCELLED


def test_direct_memory_write_effect_is_rejected() -> None:
    definition = _definition(
        operation_id="general.propose_memory_update",
        operation_type=DomainOperationType.MEMORY,
    )

    class MemoryWrite(SummaryImplementation):
        def execute(self, request: AgentOperationRequest) -> dict[str, object]:
            self.calls += 1
            return {
                "success": True,
                "output": {"summary": "proposal"},
                "effects": ("memory_write",),
            }

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, MemoryWrite(definition))
    adapter = AgentExecutionAdapter(
        registry=common, execution_delegate=DomainOperationExecutionDelegate(registry)
    )
    result = DefaultDomainOperationOrchestrator(registry, adapter).execute(
        _request(operation_id=definition.operation_id)
    )
    assert result.status is DomainOperationStatus.FAILED
    assert result.error["code"] == "DOMAIN_OPERATION_VALIDATION_ERROR"
