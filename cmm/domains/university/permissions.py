"""Phase 10.22 — University Domain Permissions.

A fail-closed permission policy for the University Domain.  Denied by default:
anything that could autonomously act on the official academic record, send
email, submit a formal procedure, create calendar/task events, or off-board
sensitive academic information.  The autonomous surface is read + memory-read
+ execute only.

Three boundaries are exercised through the shared Phase 10.15 permission
contracts and are NOT hard-denied, so that their authorized narrow paths stay
reachable while remaining denied by default:

* **External verification is OFFICIAL_ONLY.**  ``search_external`` may run only
  against an official source (``ExternalSourceRequirement`` with
  ``minimum_source_class = OFFICIAL_ONLY``).  Arbitrary search, non-official
  sources, and a missing source context are all denied.  The permitted search
  is read-only verification; it never authorizes any action.
* **Calendar/task mutation is approval-gated.**  ``schedule_modify`` and
  ``task_create`` are not hard-denied; they require a valid scoped approval
  before they may execute.  Without approval they are denied (approval
  required); with a valid scoped approval they may proceed.
* **Inbound cross-domain projection is scoped and approval-gated.**
  ``domain_cross_access`` is accepted inbound only for an authorized minimal
  functional constraint (read-only), never for detailed clinical material.
  University grants no outbound cross-domain access and never adopts a
  supporting domain's permissions.

Everything else — email send/submit, export, memory write, file modification,
sensitive inference, knowledge deletion, and every decision/action capability
— remains hard-denied.  ``update_subject_status`` remains INTERNAL Academic
State only.
"""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.permission_restriction_contracts import (
    ExternalSourceClass,
    ExternalSourceRequirement,
)
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.university.resources import UNIVERSITY_RESOURCE_KINDS

UNIVERSITY_PERMISSION_POLICY_ID = "domain-permission:university:1.0.0"

# Denied by default: everything that could autonomously act on the academic
# record, contact systems, export sensitive data, or mutate shared state.
# ``search_external``, ``schedule_modify``, ``task_create``, and inbound
# ``domain_cross_access`` are intentionally excluded here so their authorized
# narrow paths (official-only / approval-gated / scoped projection) remain
# reachable through the shared Phase 10.15 evaluator rather than being
# destroyed by a hard deny.
UNIVERSITY_PROHIBITED_CAPABILITIES: tuple[PermissionCapability, ...] = (
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
            PermissionCapability.SEARCH_EXTERNAL,
            PermissionCapability.TASK_CREATE,
            PermissionCapability.SCHEDULE_MODIFY,
        ),
        prohibited_capabilities=UNIVERSITY_PROHIBITED_CAPABILITIES,
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
        metadata={"phase": "10.22"},
    )


__all__ = [
    "UNIVERSITY_PERMISSION_POLICY_ID",
    "UNIVERSITY_PROHIBITED_CAPABILITIES",
    "build_university_permission_policy",
]