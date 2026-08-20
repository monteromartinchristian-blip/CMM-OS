"""Phase 10.24 — Reflection Domain Permissions.

A fail-closed permission policy for the Reflection Domain.  Denied by default:
anything that could classify identity, present a diagnosis, persist sensitive
inference, write semantic memory, adopt a personal decision, or perform an
external write.  The autonomous surface is read + memory-read + execute only.

Reflection is high sensitivity: ``SENSITIVE_INFERENCE`` and
``SENSITIVE_INFERENCE_PERSIST`` are denied; identity hypotheses require the
user-provided-narrative path only and any persistence waits on a valid
confirmation.  Most-restrictive policy wins under composition; unknown or
malformed permission state denies; only literal boolean ``True`` authorizes a
boolean permission gate.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.reflection.resources import REFLECTION_RESOURCE_KINDS

REFLECTION_PERMISSION_POLICY_ID = "domain-permission:reflection:1.0.0"

# Denied by default: everything that could autonomously act on identity,
# psychological state, memory, external systems, or personal decisions.
REFLECTION_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.SEARCH_EXTERNAL,
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.TASK_CREATE,
    PermissionCapability.SCHEDULE_MODIFY,
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
    PermissionCapability.MEDICAL_DECISION,
    PermissionCapability.MEDICAL_ACTION,
    PermissionCapability.LEGAL_DECISION,
    PermissionCapability.LEGAL_ACTION,
    PermissionCapability.FINANCIAL_DECISION,
    PermissionCapability.FINANCIAL_ACTION,
    PermissionCapability.FINANCIAL_SPEND,
)


def permission_authorization_allows(value) -> bool:
    """Strict runtime authorization: only the literal ``True`` authorizes.

    Strings (``"true"``), numerics (``1``, ``0``), collections (``[]``,
    ``{}``), ``None`` and arbitrary objects never authorize.  No coercion and
    no string parsing.
    """
    return value is True


def build_reflection_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed Reflection Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=REFLECTION_PERMISSION_POLICY_ID,
        domain_id="domain:reflection",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
        ),
        prohibited_capabilities=REFLECTION_PROHIBITED_CAPABILITIES,
        approval_capabilities=(),
        allowed_resource_kinds=REFLECTION_RESOURCE_KINDS,
        # Most-restrictive policy wins; sensitivity levels remain restricted.
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
        allow_inbound_cross_domain_access=True,
        approval_requirements=(),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=0,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.24"},
    )


__all__ = [
    "REFLECTION_PERMISSION_POLICY_ID",
    "REFLECTION_PROHIBITED_CAPABILITIES",
    "build_reflection_permission_policy",
    "permission_authorization_allows",
]