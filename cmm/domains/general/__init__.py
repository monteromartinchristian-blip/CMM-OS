"""Phase 10.19 — General Domain package."""

from __future__ import annotations

from cmm.domains.general.bootstrap import (
    GeneralDomainBootstrap,
    build_standard_general_domain_bootstrap,
)
from cmm.domains.general.catalog import (
    CANONICAL_GENERAL_OPERATION_IDS,
    CANONICAL_GENERAL_RESOURCE_IDS,
    CANONICAL_GENERAL_RULE_IDS,
    CANONICAL_GENERAL_WORKFLOW_IDS,
    HISTORICAL_GENERAL_OPERATION_IDS,
)
from cmm.domains.general.definition import (
    GENERAL_DOMAIN_ID,
    GENERAL_DOMAIN_VERSION,
    GENERAL_MANIFEST_ID,
    GENERAL_OPERATION_IDS,
    GENERAL_PERMISSION_IDS,
    GENERAL_RESOURCE_IDS,
    build_general_domain_definition,
)
from cmm.domains.general.integration import (
    GeneralDomainIntegrationResult,
    register_general_domain,
)
from cmm.domains.general.memory import (
    build_general_goal_binding,
    build_general_goal_proposal,
    build_general_memory_view,
    build_general_memory_view_request,
    build_general_task_binding,
    build_general_task_proposal,
    validate_general_memory_binding,
)
from cmm.domains.general.operations import build_general_operation_definitions
from cmm.domains.general.permissions import (
    GENERAL_PERMISSION_POLICY_ID,
    build_general_permission_policy,
)
from cmm.domains.general.presentation import build_general_presentation_policy
from cmm.domains.general.profile import (
    GENERAL_PROFILE_ID,
    GENERAL_PROFILE_NAME,
    GENERAL_PROHIBITED_ACTIONS,
    build_general_profile,
)
from cmm.domains.general.resources import (
    GENERAL_RESOURCE_KINDS,
    build_general_resource_definitions,
)
from cmm.domains.general.rules import (
    GENERAL_RULE_IDS,
    GeneralAmbiguityRule,
    GeneralDuplicationRule,
    GeneralGoalClarificationRule,
    GeneralPermissionRule,
    GeneralSourceReliabilityRule,
    GeneralTemporalValidityRule,
    build_general_rules,
)
from cmm.domains.general.trace import (
    assemble_general_trace,
    build_general_trace_contribution,
    build_general_trace_reference,
    validate_general_trace,
)
from cmm.domains.general.workflows import (
    GENERAL_WORKFLOW_IDS,
    build_general_workflow_definitions,
)

__all__ = [
    "CANONICAL_GENERAL_OPERATION_IDS",
    "CANONICAL_GENERAL_RESOURCE_IDS",
    "CANONICAL_GENERAL_RULE_IDS",
    "CANONICAL_GENERAL_WORKFLOW_IDS",
    "GENERAL_DOMAIN_ID",
    "GENERAL_DOMAIN_VERSION",
    "GENERAL_MANIFEST_ID",
    "GENERAL_OPERATION_IDS",
    "GENERAL_PERMISSION_IDS",
    "GENERAL_PERMISSION_POLICY_ID",
    "GENERAL_PROFILE_ID",
    "GENERAL_PROFILE_NAME",
    "GENERAL_PROHIBITED_ACTIONS",
    "GENERAL_RESOURCE_IDS",
    "GENERAL_RESOURCE_KINDS",
    "GENERAL_RULE_IDS",
    "GENERAL_WORKFLOW_IDS",
    "HISTORICAL_GENERAL_OPERATION_IDS",
    "GeneralAmbiguityRule",
    "GeneralDomainBootstrap",
    "GeneralDomainIntegrationResult",
    "GeneralDuplicationRule",
    "GeneralGoalClarificationRule",
    "GeneralPermissionRule",
    "GeneralSourceReliabilityRule",
    "GeneralTemporalValidityRule",
    "assemble_general_trace",
    "build_general_domain_definition",
    "build_general_goal_binding",
    "build_general_goal_proposal",
    "build_general_memory_view",
    "build_general_memory_view_request",
    "build_general_operation_definitions",
    "build_general_permission_policy",
    "build_general_presentation_policy",
    "build_general_profile",
    "build_general_resource_definitions",
    "build_general_rules",
    "build_general_task_binding",
    "build_general_task_proposal",
    "build_general_trace_contribution",
    "build_general_trace_reference",
    "build_general_workflow_definitions",
    "build_standard_general_domain_bootstrap",
    "register_general_domain",
    "validate_general_memory_binding",
    "validate_general_trace",
]
