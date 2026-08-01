"""Approval requirement mapping for domain operations."""

from __future__ import annotations

from types import MappingProxyType

from cmm.agent_runtime.approval_contracts import ApprovalRequirement
from cmm.agent_runtime.enums import ApprovalRequirementSource
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import (
    DomainOperationDefinition,
    DomainOperationRequest,
    _thaw,
)


def build_domain_operation_approval_requirement(
    definition: DomainOperationDefinition,
    request: DomainOperationRequest,
) -> ApprovalRequirement:
    """Build a pending approval specification without granting or persisting it."""

    if (
        definition.operation_id != request.operation_id
        or definition.version != request.operation_version
    ):
        raise ValueError("definition and request operation identity must match")
    descriptor = definition.to_operation_descriptor()
    return ApprovalRequirement(
        id=f"approval-requirement:{request.request_id}",
        source=ApprovalRequirementSource.OPERATION,
        title=f"Approve {definition.name}",
        description="Explicit approval is required before this domain operation can execute.",
        reason_codes=(
            "domain_operation.destructive"
            if definition.operation_type is DomainOperationType.DESTRUCTIVE
            else "domain_operation.approval_required",
        ),
        risk_level=definition.risk_level,
        scope="operation",
        agent_run_id=request.agent_run_id,
        workflow_id=request.workflow_id,
        operation_id=definition.operation_id,
        expected_effects=tuple(descriptor.effects),
        rollback_available=definition.reversible,
        rollback_description=(
            f"Rollback policy: {definition.rollback_policy_id}"
            if definition.rollback_policy_id
            else None
        ),
        allow_modifications=False,
        metadata=MappingProxyType(
            {
                "domain_request_fingerprint": request.calculate_fingerprint(),
                "operation_version": definition.version,
                "operation_parameters": _thaw(request.inputs),
                "primary_domain_id": request.primary_domain_id,
                "supporting_domain_ids": list(request.supporting_domain_ids),
                "scope": "domain_operation",
            }
        ),
    )


__all__ = ["build_domain_operation_approval_requirement"]
