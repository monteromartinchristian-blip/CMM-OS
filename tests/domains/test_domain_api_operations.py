"""Phase 10.36 — Domain API operation routing tests.

Proves execute_operation delegates to the authoritative
DefaultDomainOperationOrchestrator and cannot bypass permission/approval.
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
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
from cmm.domains.api import DefaultDomainAPI
from tests.domains.test_domain_api_contracts import _make_collaborators


def _definition() -> DomainOperationDefinition:
    return DomainOperationDefinition(
        operation_id="general.prepare_structured_summary",
        domain_id="domain:general",
        version="1.0.0",
        name="Prepare summary",
        description="Prepare safe structure",
        operation_type=DomainOperationType.PREPARATION,
        reversible=False,
        input_schema={
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string"}},
            "additionalProperties": False,
        },
    )


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


def _orchestrator_and_implementation():
    definition = _definition()
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


def _request() -> DomainOperationRequest:
    return DomainOperationRequest(
        request_id="request:1",
        operation_id="general.prepare_structured_summary",
        operation_version="1.0.0",
        inputs={"text": "hello"},
        agent_run_id="run:1",
        task_id="task:1",
        primary_domain_id="domain:general",
        idempotency_key="idem:1",
        capabilities=("execute",),
    )


def _api_with_orchestrator(
    orchestrator: DefaultDomainOperationOrchestrator,
) -> DefaultDomainAPI:
    collaborators = _make_collaborators()
    collaborators["operation_orchestrator"] = orchestrator
    return DefaultDomainAPI(**collaborators)


class TestExecuteOperation:
    def test_delegates_to_authoritative_orchestrator(self) -> None:
        orchestrator, implementation = _orchestrator_and_implementation()
        api = _api_with_orchestrator(orchestrator)
        result = api.execute_operation(_request())
        assert implementation.calls == 1
        assert result.status is DomainOperationStatus.COMPLETED
        assert result.output == {"summary": "HELLO"}
        assert result.operation_id == "general.prepare_structured_summary"

    def test_blocked_permission_prevents_execution(self) -> None:
        orchestrator, implementation = _orchestrator_and_implementation()
        api = _api_with_orchestrator(orchestrator)
        # No permission gate is wired, so claiming granted permissions must
        # fail closed through the canonical orchestrator path.
        request = DomainOperationRequest(
            request_id="request:2",
            operation_id="general.prepare_structured_summary",
            operation_version="1.0.0",
            inputs={"text": "hello"},
            agent_run_id="run:1",
            task_id="task:1",
            primary_domain_id="domain:general",
            idempotency_key="idem:2",
            capabilities=("execute",),
            granted_permissions=("domain:operation",),
        )
        result = api.execute_operation(request)
        assert result.status is DomainOperationStatus.BLOCKED
        assert implementation.calls == 0

    def test_invalid_input_fails_before_implementation(self) -> None:
        orchestrator, implementation = _orchestrator_and_implementation()
        api = _api_with_orchestrator(orchestrator)
        from cmm.domains.errors import DomainOperationValidationError

        request = DomainOperationRequest(
            request_id="request:3",
            operation_id="general.prepare_structured_summary",
            operation_version="1.0.0",
            inputs={"unknown": True},
            agent_run_id="run:1",
            task_id="task:1",
            primary_domain_id="domain:general",
            idempotency_key="idem:3",
            capabilities=("execute",),
        )
        with pytest.raises(DomainOperationValidationError):
            api.execute_operation(request)
        assert implementation.calls == 0

    def test_canonical_exception_type_propagates_unchanged(self) -> None:
        orchestrator, _ = _orchestrator_and_implementation()
        api = _api_with_orchestrator(orchestrator)
        from cmm.domains.errors import DomainOperationValidationError

        request = DomainOperationRequest(
            request_id="request:4",
            operation_id="general.prepare_structured_summary",
            operation_version="1.0.0",
            inputs={"unknown": True},
            agent_run_id="run:1",
            task_id="task:1",
            primary_domain_id="domain:general",
            idempotency_key="idem:4",
            capabilities=("execute",),
        )
        with pytest.raises(DomainOperationValidationError) as excinfo:
            api.execute_operation(request)
        assert type(excinfo.value) is DomainOperationValidationError
