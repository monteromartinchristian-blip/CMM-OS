"""Phase 10.28 — Sport Domain Permissions.

Fail-closed permission policy for the Sport Domain.
Direct external calendar action or medical decision/action is prohibited.
Memory write is fail-closed (allow_memory_write=False) and cross-domain access is default-denied
except via scoped Health constraint projection requests.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.sport.catalog import SPORT_RESOURCE_KINDS

SPORT_PERMISSION_POLICY_ID = "domain-permission:sport:1.0.0"

SPORT_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
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


def build_sport_permission_policy() -> DomainPermissionPolicy:
    """Build the Sport Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=SPORT_PERMISSION_POLICY_ID,
        domain_id="domain:sport",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.SENSITIVE_INFERENCE,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
        ),
        prohibited_capabilities=SPORT_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.SCHEDULE_MODIFY,
            PermissionCapability.EXPORT,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_resource_kinds=SPORT_RESOURCE_KINDS,
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
            "schedule.modification",
            "export",
            "file.modification",
        ),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=0,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.28"},
    )


__all__ = [
    "SPORT_PERMISSION_POLICY_ID",
    "SPORT_PROHIBITED_CAPABILITIES",
    "build_sport_permission_policy",
    "permission_authorization_allows",
]
