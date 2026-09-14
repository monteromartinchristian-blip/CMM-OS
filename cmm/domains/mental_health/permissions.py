"""Phase 10.25 pattern — Phase 10.52 Mental Health Domain Permissions.

A fail-closed permission policy for the Mental Health Domain.  Denied by
default: everything that could autonomously persist sensitive inference,
transfer or export sensitive content, communicate externally, or modify
permissions.  The autonomous surface is read + memory-read + execute only.

Mental Health is highly sensitive: fears, intuitions, inferred emotional
patterns, loops, psychological/psychiatric interpretations and third-party
motives are never silently persisted.  Most-restrictive policy wins under
composition; unknown or malformed permission state denies; only literal
boolean ``True`` authorizes a boolean permission gate.

This module encodes a *policy*.  It is never a permission engine, never a
resolver and never a grant of cross-domain authority.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.mental_health.resources import MENTAL_HEALTH_RESOURCE_KINDS
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

MENTAL_HEALTH_PERMISSION_POLICY_ID = "domain-permission:mental-health:1.0.0"

# Denied by default: everything that could autonomously act on sensitive
# emotional state, persist inference, transfer/export sensitive content or
# communicate externally (frozen design §14, §40, §41).
MENTAL_HEALTH_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.SEARCH_EXTERNAL,
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.FILE_MODIFY,
    PermissionCapability.TASK_CREATE,
    PermissionCapability.SCHEDULE_MODIFY,
    PermissionCapability.GOAL_UPDATE,
    PermissionCapability.COMMUNICATION_EXTERNAL,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
    PermissionCapability.EXPORT,
    PermissionCapability.PUBLICATION,
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
    # Cross-domain access is purpose-constrained and never granted by default.
    PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
    PermissionCapability.DOMAIN_CROSS_ACCESS,
)

# Capability separation: read != infer != propose persistence != persist
# != transfer != export != communicate != external mutation.
MENTAL_HEALTH_CAPABILITY_SEPARATION: dict[str, tuple[PermissionCapability, ...]] = {
    "read": (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.KNOWLEDGE_READ,
        PermissionCapability.ENTITY_READ,
        PermissionCapability.MEMORY_READ,
    ),
    "infer": (PermissionCapability.SENSITIVE_INFERENCE,),
    "propose_persistence": (PermissionCapability.SENSITIVE_INFERENCE,),
    "persist": (PermissionCapability.SENSITIVE_INFERENCE_PERSIST,),
    "transfer": (PermissionCapability.DOMAIN_CROSS_ACCESS,),
    "export": (PermissionCapability.EXPORT,),
    "communicate": (PermissionCapability.COMMUNICATION_EXTERNAL,),
    "external_mutation": (
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.IRREVERSIBLE_CHANGE,
    ),
}


def permission_authorization_allows(value) -> bool:
    """Strict runtime authorization: only the literal ``True`` authorizes.

    Strings, numerics, collections, ``None`` and arbitrary objects never
    authorize.  No coercion and no string parsing.
    """
    return value is True


def build_mental_health_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed Mental Health permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=MENTAL_HEALTH_PERMISSION_POLICY_ID,
        domain_id="domain:mental-health",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.KNOWLEDGE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
            # Inference is allowed; persisting it is not.
            PermissionCapability.SENSITIVE_INFERENCE,
        ),
        prohibited_capabilities=MENTAL_HEALTH_PROHIBITED_CAPABILITIES,
        # Approval is required — never automatic — for the sensitive paths.
        approval_capabilities=(
            PermissionCapability.MEMORY_WRITE,
            PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
            PermissionCapability.EXPORT,
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.DOMAIN_CROSS_ACCESS,
        ),
        allowed_resource_kinds=MENTAL_HEALTH_RESOURCE_KINDS,
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
        # Inbound authorized projections are allowed; outgoing transfer is not.
        allow_inbound_cross_domain_access=True,
        approval_requirements=(
            "memory.persist",
            "sensitive.inference.persist",
            "export",
            "communication.external",
            "domain.cross_access",
        ),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=0,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={
            "phase": "10.52",
            "capability_separation": {
                name: [capability.value for capability in capabilities]
                for name, capabilities in MENTAL_HEALTH_CAPABILITY_SEPARATION.items()
            },
        },
    )


__all__ = [
    "MENTAL_HEALTH_CAPABILITY_SEPARATION",
    "MENTAL_HEALTH_PERMISSION_POLICY_ID",
    "MENTAL_HEALTH_PROHIBITED_CAPABILITIES",
    "build_mental_health_permission_policy",
    "permission_authorization_allows",
]
