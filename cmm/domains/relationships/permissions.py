"""Phase 10.21 — Relationships Domain Permissions.

A fail-closed permission policy for the Relationships Domain.  Denially listed
capabilities include every sensitive, external, mutating, and decision-making
action; the autonomous surface is read + memory-read + execute only.  Any
relational action (contact, message, boundary modification, relationship end,
reconciliation initiation) is denied by default and never auto-granted.

The relational prohibitions live in ``RELATIONSHIPS_PROHIBITED_ACTIONS`` (the
profile); this policy additionally denies the generic ``PermissionCapability``
surface (communication, export, sensitive inference, memory write, mutating
state) so the domain cannot act on or off-board relationship information.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.relationships.resources import RELATIONSHIPS_RESOURCE_KINDS

RELATIONSHIPS_PERMISSION_POLICY_ID = "domain-permission:relationships:1.0.0"

# Denied by default: everything that could autonomously act on a relationship,
# contact another person, export sensitive data, or mutate shared state.
RELATIONSHIPS_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
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


def build_relationships_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed Relationships Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=RELATIONSHIPS_PERMISSION_POLICY_ID,
        domain_id="domain:relationships",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.SENSITIVE_INFERENCE,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
        ),
        prohibited_capabilities=RELATIONSHIPS_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.EXPORT,
            PermissionCapability.FILE_MODIFY,
        ),
        allowed_resource_kinds=RELATIONSHIPS_RESOURCE_KINDS,
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
        allow_sensitive_inference=True,
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
        metadata={"phase": "10.21"},
    )


__all__ = [
    "RELATIONSHIPS_PERMISSION_POLICY_ID",
    "RELATIONSHIPS_PROHIBITED_CAPABILITIES",
    "build_relationships_permission_policy",
]
