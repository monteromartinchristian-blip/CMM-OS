"""Phase 10.29 — Life Plan Domain Permissions.

Fail-closed permission policy for the Life Plan Domain.
Prohibits direct memory writes, autonomous external communications, contracting,
payments, irreversible commitments, or direct calendar mutations.
Cross-domain access is default-denied and requires scoped CrossDomainPermissionRequest
and shared permission resolution / gate evaluation.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.life_plan.catalog import LIFE_PLAN_RESOURCE_KINDS
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

LIFE_PLAN_PERMISSION_POLICY_ID = "domain-permission:life-plan:1.0.0"

LIFE_PLAN_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
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


def build_life_plan_permission_policy() -> DomainPermissionPolicy:
    """Build the Life Plan Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=LIFE_PLAN_PERMISSION_POLICY_ID,
        domain_id="domain:life-plan",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.SENSITIVE_INFERENCE,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
        ),
        prohibited_capabilities=LIFE_PLAN_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.SCHEDULE_MODIFY,
            PermissionCapability.EXPORT,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_resource_kinds=LIFE_PLAN_RESOURCE_KINDS,
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
        metadata={"phase": "10.29"},
    )


__all__ = [
    "LIFE_PLAN_PERMISSION_POLICY_ID",
    "LIFE_PLAN_PROHIBITED_CAPABILITIES",
    "build_life_plan_permission_policy",
    "permission_authorization_allows",
]
