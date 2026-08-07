"""Phase 10.19 — General Domain Permissions."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

GENERAL_PERMISSION_POLICY_ID = "domain-permission:general:1.0.0"


def build_general_permission_policy() -> DomainPermissionPolicy:
    """Build the General Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=GENERAL_PERMISSION_POLICY_ID,
        domain_id="domain:general",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
        ),
        prohibited_capabilities=(
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
        ),
        approval_capabilities=(
            PermissionCapability.TASK_CREATE,
            PermissionCapability.GOAL_UPDATE,
        ),
        allowed_resource_kinds=(
            "user_message",
            "conversation",
            "calendar_event",
            "note",
            "document",
            "memory_entry",
            "generic_task",
            "generic_goal",
            "external_source",
        ),
        allowed_sensitivity_levels=("internal", "public"),
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
        approval_requirements=("task.create", "goal.update"),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=1,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.19"},
    )


__all__ = ["GENERAL_PERMISSION_POLICY_ID", "build_general_permission_policy"]