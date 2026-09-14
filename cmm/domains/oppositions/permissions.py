"""Phase 10.23 — Opposition Domain Permissions.

A fail-closed permission policy for the Opposition Domain.  Denied by default:
anything that could autonomously register, submit an application, pay a fee,
sign, upload formal documents, modify official public-body records, abandon or
switch the target, write memory, or off-board sensitive data.  The autonomous
surface is read + memory-read + execute only.

Three boundaries are exercised through the shared permission contracts and are
NOT hard-denied, so that their authorized narrow paths stay reachable while
remaining denied by default:

* **External verification is OFFICIAL_ONLY and read-only.**
  ``search_external`` may run only against an official source
  (``ExternalSourceRequirement`` with ``minimum_source_class = OFFICIAL_ONLY``).
  Arbitrary search, non-official sources and a missing source context are all
  denied.  It never authorizes any action.
* **Calendar/task mutation is approval-gated.**  ``schedule_modify`` and
  ``task_create`` are not hard-denied; they require a valid scoped approval
  before they may execute.
* **Inbound cross-domain projection is scoped and approval-gated.**
  ``domain_cross_access`` is accepted inbound only for authorized minimal
  Health/University projections; it never grants autonomous outbound access and
  supporting domains can never widen Opposition permissions.  Most-restrictive
  policy wins.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.permission_restriction_contracts import (
    ExternalSourceClass,
    ExternalSourceRequirement,
)
from cmm.domains.oppositions.resources import OPPOSITIONS_RESOURCE_KINDS
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)

OPPOSITIONS_PERMISSION_POLICY_ID = "domain-permission:oppositions:1.0.0"

# Denied by default: everything that could autonomously act on official public-
# body systems, contact systems, mutate strategy, export sensitive data, or
# mutate shared state.  ``search_external``, ``schedule_modify``, ``task_create``
# and inbound ``domain_cross_access`` are intentionally excluded here so their
# authorized narrow paths (official-only / approval-gated / scoped projection)
# remain reachable through the shared evaluator rather than destroyed by a hard
# deny.
OPPOSITIONS_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
    PermissionCapability.MODEL_EXTERNAL,
    PermissionCapability.MEMORY_WRITE,
    PermissionCapability.FILE_MODIFY,
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


def build_oppositions_permission_policy() -> DomainPermissionPolicy:
    """Build the fail-closed Opposition Domain permission policy deterministically."""
    return DomainPermissionPolicy(
        policy_id=OPPOSITIONS_PERMISSION_POLICY_ID,
        domain_id="domain:oppositions",
        version="1.0.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.MEMORY_READ,
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.WORKFLOW_EXECUTE,
            PermissionCapability.SEARCH_EXTERNAL,
            PermissionCapability.TASK_CREATE,
            PermissionCapability.SCHEDULE_MODIFY,
        ),
        prohibited_capabilities=OPPOSITIONS_PROHIBITED_CAPABILITIES,
        approval_capabilities=(
            PermissionCapability.COMMUNICATION_EXTERNAL,
            PermissionCapability.EXPORT,
            PermissionCapability.FILE_MODIFY,
            PermissionCapability.TASK_CREATE,
            PermissionCapability.SCHEDULE_MODIFY,
            PermissionCapability.DOMAIN_CROSS_ACCESS,
        ),
        source_requirement=ExternalSourceRequirement(
            minimum_source_class=ExternalSourceClass.OFFICIAL_ONLY
        ),
        allowed_resource_kinds=OPPOSITIONS_RESOURCE_KINDS,
        # Most-restrictive policy wins; default privacy orientation is
        # subordinate to the most restrictive effective combination.
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
        approval_requirements=(
            "communication.external",
            "export",
            "file.modification",
            "task.create",
            "schedule.modify",
            "domain.cross_access",
        ),
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=0,
            allow_reversible_changes=False,
            allow_irreversible_changes=False,
        ),
        enabled=True,
        metadata={"phase": "10.23"},
    )


__all__ = [
    "OPPOSITIONS_PERMISSION_POLICY_ID",
    "OPPOSITIONS_PROHIBITED_CAPABILITIES",
    "build_oppositions_permission_policy",
]
