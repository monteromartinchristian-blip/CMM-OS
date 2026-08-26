"""Phase 10.30 — Project Domain Permissions.

Fail-closed permission policy for the Project Domain.
Prohibits unapproved file modification, direct memory writes, autonomous external communications,
payments, or irreversible actions.
File modification is approval-gated and supervised.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_RESOURCE_KINDS,
    PROJECT_DOMAIN_ID,
    PROJECT_DOMAIN_VERSION,
)

PROJECT_PERMISSION_POLICY_ID = "domain-permission:project:1.0.0"

PROJECT_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.SEARCH_EXTERNAL,
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
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


def build_project_permission_policy() -> DomainPermissionPolicy:
    """Build the Project Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=PROJECT_PERMISSION_POLICY_ID,
        domain_id=PROJECT_DOMAIN_ID,
        version=PROJECT_DOMAIN_VERSION,
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.SENSITIVE_INFERENCE,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
            PermissionCapability.FILE_MODIFY,
        ),
        prohibited_capabilities=PROJECT_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_resource_kinds=CANONICAL_PROJECT_RESOURCE_KINDS,
        allowed_sensitivity_levels=("internal", "confidential", "restricted", "secret"),
        allow_memory_read=True,
        allow_memory_write=False,
        allow_external_search=False,
        allow_external_models=False,
        allow_external_communication=False,
        allow_file_modification=True,
        allow_task_creation=False,
        allow_schedule_modification=False,
        allow_goal_update=False,
        allow_export=False,
        allow_sensitive_inference=True,
        allow_cross_domain_access=False,
        allow_inbound_cross_domain_access=True,
        approval_requirements=(
            "file.modification",
        ),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=1,
            allow_reversible_changes=True,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.30"},
    )


__all__ = [
    "PROJECT_PERMISSION_POLICY_ID",
    "PROJECT_PROHIBITED_CAPABILITIES",
    "build_project_permission_policy",
    "permission_authorization_allows",
]
