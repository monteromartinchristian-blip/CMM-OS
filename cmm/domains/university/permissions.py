"""Phase 10.22 — University Domain Permissions.

A fail-closed permission policy for the University Domain.  Denied by default:
anything that could autonomously act on the official academic record, send
email, submit a formal procedure, create calendar/task events, or off-board
sensitive academic information.  The autonomous surface is read + memory-read
+ execute only; any external/mutating/decision-making capability is denied and
never auto-granted.

Calendar and task mutation are only reachable through shared approval-gated
capabilities; ``update_subject_status`` remains INTERNAL Academic State only.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.university.resources import UNIVERSITY_RESOURCE_KINDS

UNIVERSITY_PERMISSION_POLICY_ID = "domain-permission:university:1.0.0"

# Denied by default: everything that could autonomously act on the academic
# record, contact systems, export sensitive data, or mutate shared state.
UNIVERSITY_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.SEARCH_EXTERNAL,
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.SCHEDULE_MODIFY,
    PermissionCapability.TASK_CREATE,
    PermissionCapability.GOAL_UPDATE,
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.SENSITIVE_INFERENCE,
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


def build_university_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed University Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=UNIVERSITY_PERMISSION_POLICY_ID,
        domain_id="domain:university",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
        ),
        prohibited_capabilities=UNIVERSITY_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.EXPORT,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_resource_kinds=UNIVERSITY_RESOURCE_KINDS,
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
        metadata={"phase": "10.22"},
    )


__all__ = [
    "UNIVERSITY_PERMISSION_POLICY_ID",
    "UNIVERSITY_PROHIBITED_CAPABILITIES",
    "build_university_permission_policy",
]