"""Phase 10.27 — Parenthood Domain Permissions.

A fail-closed permission policy for the Parenthood Domain.
Direct external action (communication, contracting, payment, legal/medical
commitments, child enrollment) is prohibited.
Memory write is fail-closed (allow_memory_write=False) and mutation requires
explicit approval and valid Domain Memory proposal/binding chains.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.parenthood.catalog import PARENTHOOD_RESOURCE_KINDS
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

PARENTHOOD_PERMISSION_POLICY_ID = "domain-permission:parenthood:1.0.0"

PARENTHOOD_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.SEARCH_EXTERNAL,
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.SCHEDULE_MODIFY,
    PermissionCapability.TASK_CREATE,
    PermissionCapability.GOAL_UPDATE,
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.EXPORT,
    PermissionCapability.PUBLICATION,
    PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
    PermissionCapability.IRREVERSIBLE_CHANGE,
    PermissionCapability.KNOWLEDGE_DELETE,
    PermissionCapability.PERMISSION_MODIFY,
    PermissionCapability.DOMAIN_CROSS_ACCESS,
    PermissionCapability.MEDICAL_DECISION,
    PermissionCapability.MEDICAL_ACTION,
    PermissionCapability.LEGAL_DECISION,
    PermissionCapability.LEGAL_ACTION,
    PermissionCapability.FINANCIAL_DECISION,
    PermissionCapability.FINANCIAL_ACTION,
    PermissionCapability.FINANCIAL_SPEND,
)


def permission_authorization_allows(value: Any) -> bool:
    """Strict runtime authorization: only literal boolean True authorizes."""
    return value is True


def persistence_confirmation_accepted(
    *,
    confirmation: Any = None,
    confirmation_binding: Any = None,
    confirmation_inventory: Any = None,
    proposal_id: str | None = None,
    content_kind: str | None = None,
    child_id: str | None = None,
    repetition_count: int = 0,
) -> dict[str, Any]:
    """Evaluate whether a memory-persistence confirmation is acceptable."""
    record: dict[str, Any] = {
        "accepted": False,
        "authorization_accepted": False,
        "authorization_malformed": False,
        "chain_valid": False,
        "content_kind": content_kind if isinstance(content_kind, str) else None,
        "proposal_id": proposal_id,
        "child_id": child_id,
        "repetition_is_not_authorization": True,
    }

    if confirmation is not None:
        record["authorization_malformed"] = True
        return record

    if confirmation_binding is None or confirmation_inventory is None:
        record["authorization_malformed"] = (
            confirmation_binding is not None or confirmation_inventory is not None
        )
        return record

    try:
        from cmm.domains.parenthood.memory import validate_parenthood_memory_binding

        validation = validate_parenthood_memory_binding(
            binding=confirmation_binding,
            inventory=confirmation_inventory,
            child_id=child_id,
        )
        record["chain_valid"] = bool(validation.is_valid)
    except Exception:
        record["chain_valid"] = False
        record["authorization_malformed"] = True
        return record

    binding_matches = (
        proposal_id is not None
        and tuple(getattr(confirmation_binding, "memory_proposal_ids", ())) == (proposal_id,)
    )
    approvals = getattr(confirmation_inventory, "approval_requests", ())
    decisions = getattr(confirmation_inventory, "approval_decisions", ())
    linked = any(
        request.request_id in {decision.request_id for decision in decisions}
        for request in approvals
    )
    approved = any(
        decision.approved is True
        for decision in decisions
        if any(request.request_id == decision.request_id for request in approvals)
    )

    record["authorization_accepted"] = bool(
        record["chain_valid"] and binding_matches and linked and approved
    )
    if not record["authorization_accepted"]:
        record["authorization_malformed"] = True
    record["accepted"] = record["authorization_accepted"]
    return record


def build_parenthood_permission_policy() -> DomainPermissionPolicy:
    """Build the Parenthood Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=PARENTHOOD_PERMISSION_POLICY_ID,
        domain_id="domain:parenthood",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.SENSITIVE_INFERENCE,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
        ),
        prohibited_capabilities=PARENTHOOD_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.EXPORT,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_resource_kinds=PARENTHOOD_RESOURCE_KINDS,
        allowed_sensitivity_levels=("internal", "confidential", "restricted", "secret"),
        allow_memory_read=True,
        allow_memory_write=False,
        allow_external_search=False,
        allow_external_models=False,
        allow_external_communication=False,
        allow_file_modification=False,
        allow_task_creation=False,
        allow_schedule_modification=False,
        allow_goal_update=False,
        allow_export=False,
        allow_sensitive_inference=True,
        allow_cross_domain_access=False,
        allow_inbound_cross_domain_access=True,
        approval_requirements=(
            "communication.external",
            "export",
            "file.modification",
        ),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=0,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.27"},
    )


__all__ = [
    "PARENTHOOD_PERMISSION_POLICY_ID",
    "PARENTHOOD_PROHIBITED_CAPABILITIES",
    "build_parenthood_permission_policy",
    "permission_authorization_allows",
    "persistence_confirmation_accepted",
]
