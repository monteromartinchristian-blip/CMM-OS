"""Phase 10.53 — Neurodivergence Domain Permissions.

A fail-closed permission policy for the Neurodivergence Domain.  Denied by
default: everything that could autonomously persist sensitive inference,
transfer or export sensitive content, communicate externally, take a medical
decision, or modify permissions.  The autonomous surface is
read + memory-read + execute + sensitive inference only.

The pack distinguishes, through the existing capability contract:

    read != infer != propose persistence != persist
        != transfer != export != communicate != external mutation

Required principles (frozen design §14):

- permission to infer is not permission to persist;
- permission to read is not permission to transfer;
- provider availability is not permission;
- a technical transfer object is not authority.

This module encodes a *policy*.  It is never a permission engine, never a
resolver, and never a grant of cross-domain authority.  Most-restrictive
policy wins under composition; unknown or malformed permission state denies;
only a literal boolean ``True`` authorizes a boolean permission gate.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.neurodivergence.resources import NEURODIVERGENCE_RESOURCE_KINDS
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

NEURODIVERGENCE_PERMISSION_POLICY_ID = "domain-permission:neurodivergence:1.0.0"

# Denied by default: everything that could autonomously act on sensitive
# developmental/assessment material, persist an inference, transfer or export
# sensitive content, communicate externally, take a medical decision, or alter
# authority itself (frozen design §14, §16, §28).
NEURODIVERGENCE_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
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

# Capability separation: each stage is a distinct authority and none of them
# implies the next.
NEURODIVERGENCE_CAPABILITY_SEPARATION: dict[str, tuple[PermissionCapability, ...]] = {
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


def build_neurodivergence_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed Neurodivergence permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=NEURODIVERGENCE_PERMISSION_POLICY_ID,
        domain_id="domain:neurodivergence",
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
        prohibited_capabilities=NEURODIVERGENCE_PROHIBITED_CAPABILITIES,
        # Approval is required — never automatic — for the sensitive paths.
        approval_capabilities=(
            PermissionCapability.MEMORY_WRITE,
            PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
            PermissionCapability.EXPORT,
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.DOMAIN_CROSS_ACCESS,
        ),
        allowed_resource_kinds=NEURODIVERGENCE_RESOURCE_KINDS,
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
            "phase": "10.53",
            "capability_separation": {
                name: [capability.value for capability in capabilities]
                for name, capabilities in (
                    NEURODIVERGENCE_CAPABILITY_SEPARATION.items()
                )
            },
        },
    )


__all__ = [
    "NEURODIVERGENCE_CAPABILITY_SEPARATION",
    "NEURODIVERGENCE_PERMISSION_POLICY_ID",
    "NEURODIVERGENCE_PROHIBITED_CAPABILITIES",
    "build_neurodivergence_permission_policy",
    "permission_authorization_allows",
]
