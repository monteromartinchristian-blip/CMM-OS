"""Conservative, explicit starter policies for built-in domains."""

from __future__ import annotations

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)


def build_initial_permission_catalog() -> tuple[DomainPermissionPolicy, ...]:
    return (
        DomainPermissionPolicy(
            "domain-permission:general:1.0.0", "domain:general", "1.0.0",
            allowed_capabilities=(PermissionCapability.RESOURCE_READ, PermissionCapability.MEMORY_READ),
            prohibited_capabilities=(PermissionCapability.SEARCH_EXTERNAL, PermissionCapability.MODEL_EXTERNAL, PermissionCapability.MEMORY_WRITE, PermissionCapability.FILE_MODIFY, PermissionCapability.SCHEDULE_MODIFY, PermissionCapability.TASK_CREATE, PermissionCapability.COMMUNICATION_EXTERNAL),
            allowed_resource_kinds=("internal",), allow_memory_read=True,
            autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=1),
        ),
        DomainPermissionPolicy(
            "domain-permission:health:1.0.0", "domain:health", "1.0.0",
            allowed_capabilities=(PermissionCapability.RESOURCE_READ, PermissionCapability.MEMORY_READ, PermissionCapability.SENSITIVE_INFERENCE, PermissionCapability.MEDICAL_DECISION),
            prohibited_capabilities=(PermissionCapability.SENSITIVE_INFERENCE_PERSIST, PermissionCapability.SEARCH_EXTERNAL, PermissionCapability.MODEL_EXTERNAL, PermissionCapability.MEMORY_WRITE),
            approval_capabilities=(PermissionCapability.MEDICAL_DECISION,),
            allowed_resource_kinds=("clinical", "internal"), allowed_sensitivity_levels=("internal", "confidential"),
            allow_memory_read=True, allow_sensitive_inference=True,
            approval_requirements=("medical.decision", "sensitive_inference.persist"),
            autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=1),
        ),
        DomainPermissionPolicy(
            "domain-permission:university:1.0.0", "domain:university", "1.0.0",
            allowed_capabilities=(PermissionCapability.RESOURCE_READ, PermissionCapability.MEMORY_READ, PermissionCapability.TASK_CREATE, PermissionCapability.SCHEDULE_MODIFY),
            prohibited_capabilities=(PermissionCapability.SEARCH_EXTERNAL, PermissionCapability.MODEL_EXTERNAL, PermissionCapability.MEMORY_WRITE),
            approval_capabilities=(PermissionCapability.TASK_CREATE, PermissionCapability.SCHEDULE_MODIFY),
            allowed_resource_kinds=("internal", "academic"), allow_memory_read=True,
            autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=1),
        ),
        DomainPermissionPolicy(
            "domain-permission:relationships:1.0.0", "domain:relationships", "1.0.0",
            allowed_capabilities=(PermissionCapability.RESOURCE_READ, PermissionCapability.MEMORY_READ, PermissionCapability.SENSITIVE_INFERENCE),
            prohibited_capabilities=(PermissionCapability.SENSITIVE_INFERENCE_PERSIST, PermissionCapability.COMMUNICATION_EXTERNAL, PermissionCapability.MEMORY_WRITE),
            allowed_resource_kinds=("internal", "reflection"), allow_memory_read=True,
            allow_sensitive_inference=True,
            approval_requirements=("sensitive_inference.persist",),
            autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=1),
        ),
        DomainPermissionPolicy(
            "domain-permission:project:1.0.0", "domain:project", "1.0.0",
            allowed_capabilities=(PermissionCapability.RESOURCE_READ, PermissionCapability.MEMORY_READ, PermissionCapability.FILE_MODIFY, PermissionCapability.OPERATION_EXECUTE),
            prohibited_capabilities=(PermissionCapability.IRREVERSIBLE_CHANGE, PermissionCapability.SEARCH_EXTERNAL, PermissionCapability.MODEL_EXTERNAL),
            approval_capabilities=(PermissionCapability.FILE_MODIFY,),
            allowed_resource_kinds=("internal", "repository"), allow_memory_read=True,
            approval_requirements=("file.modify",),
            autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=2, allow_reversible_changes=True),
        ),
    )


__all__ = ["build_initial_permission_catalog"]
