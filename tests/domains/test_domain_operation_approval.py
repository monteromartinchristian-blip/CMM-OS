from __future__ import annotations

from cmm.agent_runtime.approval_contracts import ApprovalRequirement
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.enums import ApprovalRequestStatus
from cmm.domains import (
    DomainOperationDefinition,
    DomainOperationRequest,
    DomainOperationType,
    build_domain_operation_approval_requirement,
)


def test_approval_requirement_binds_operation_version_inputs_and_context() -> None:
    definition = DomainOperationDefinition(
        operation_id="health.prepare_medical_appointment",
        domain_id="domain:health",
        version="1.0.0",
        name="Prepare appointment",
        description="Prepare safe material",
        operation_type=DomainOperationType.SENSITIVE,
        requires_approval=True,
    )
    request = DomainOperationRequest(
        request_id="request:approval",
        operation_id=definition.operation_id,
        operation_version=definition.version,
        inputs={"notes": "safe"},
        agent_run_id="run:1",
        workflow_id="workflow:1",
        task_id="task:1",
        primary_domain_id="domain:health",
        idempotency_key="idem:approval",
    )
    requirement = build_domain_operation_approval_requirement(definition, request)
    assert isinstance(requirement, ApprovalRequirement)
    assert requirement.operation_id == definition.operation_id
    assert (
        requirement.metadata["domain_request_fingerprint"]
        == request.calculate_fingerprint()
    )
    assert requirement.metadata["operation_version"] == "1.0.0"
    approval = ApprovalService().create_request_from_requirement(requirement)
    assert approval.status is ApprovalRequestStatus.PENDING
    assert approval.metadata["operation_parameters"] == {"notes": "safe"}


def test_changed_inputs_produce_different_approval_binding() -> None:
    definition = DomainOperationDefinition(
        operation_id="project.prepare_change_review",
        domain_id="domain:project",
        version="1.0.0",
        name="Review",
        description="Prepare review",
        operation_type="preparation",
        requires_approval=True,
    )
    base = {
        "request_id": "request:1",
        "operation_id": definition.operation_id,
        "operation_version": definition.version,
        "agent_run_id": "run:1",
        "task_id": "task:1",
        "primary_domain_id": "domain:project",
        "idempotency_key": "idem:1",
    }
    first = DomainOperationRequest(inputs={"change": "a"}, **base)
    second = DomainOperationRequest(inputs={"change": "b"}, **base)
    assert (
        build_domain_operation_approval_requirement(definition, first).metadata[
            "domain_request_fingerprint"
        ]
        != build_domain_operation_approval_requirement(definition, second).metadata[
            "domain_request_fingerprint"
        ]
    )
