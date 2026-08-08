"""Phase 10.20 — Health Domain Permissions.

A fail-closed permission policy for the Health Domain.  Denially listed
capabilities include every sensitive, medical, external, and mutating action;
the autonomous surface is read + memory-read + execute only.  Any medical
action or decision requires approval and is never auto-granted.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.health.resources import HEALTH_RESOURCE_KINDS
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

HEALTH_PERMISSION_POLICY_ID = "domain-permission:health:1.0.0"

# Denied by default: everything that could autonomously act on a person's
# health, export sensitive data, or mutate shared state.
HEALTH_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.SEARCH_EXTERNAL,
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.SCHEDULE_MODIFY,
    PermissionCapability.TASK_CREATE,
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.SENSITIVE_INFERENCE,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.EXPORT,
    PermissionCapability.IRREVERSIBLE_CHANGE,
    PermissionCapability.KNOWLEDGE_DELETE,
    PermissionCapability.PERMISSION_MODIFY,
    PermissionCapability.MEDICAL_DECISION,
    PermissionCapability.MEDICAL_ACTION,
    PermissionCapability.LEGAL_DECISION,
    PermissionCapability.LEGAL_ACTION,
    PermissionCapability.FINANCIAL_DECISION,
    PermissionCapability.FINANCIAL_ACTION,
    PermissionCapability.FINANCIAL_SPEND,
)


def build_health_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed Health Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=HEALTH_PERMISSION_POLICY_ID,
        domain_id="domain:health",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
        ),
        prohibited_capabilities=HEALTH_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.MEDICAL_ACTION,
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.EXPORT,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_resource_kinds=HEALTH_RESOURCE_KINDS,
        allowed_sensitivity_levels=("restricted", "secret"),
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
        allow_sensitive_inference=False,
        allow_cross_domain_access=False,
        approval_requirements=("medical.action", "communication.external", "export"),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=0,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.20"},
    )


__all__ = ["HEALTH_PERMISSION_POLICY_ID", "HEALTH_PROHIBITED_CAPABILITIES", "build_health_permission_policy"]
