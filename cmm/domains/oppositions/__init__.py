"""Phase 10.23 — Opposition Domain package.

A conservative, proposal-only, fail-closed Domain Pack for public competitive
examinations/oppositions.  Opposition never registers, submits an application,
pays a fee, signs, modifies official public-body records, abandons or switches
the target, adopts a strategy without an explicit user decision, or infers
capacity / guaranteed exam success from mock performance.  Source authority is
preserved by attribute and scope; a single mock is not a trend; Official
Opposition State is never overridden by Personal Memory.
"""

from __future__ import annotations

from cmm.domains.oppositions.bootstrap import (
    OppositionsDomainBootstrap,
    build_standard_oppositions_domain_bootstrap,
)
from cmm.domains.oppositions.catalog import (
    CANONICAL_OPPOSITION_ENTITY_TYPES,
    CANONICAL_OPPOSITION_OPERATION_IDS,
    CANONICAL_OPPOSITION_RESOURCE_IDS,
    CANONICAL_OPPOSITION_RULE_IDS,
    CANONICAL_OPPOSITION_WORKFLOW_IDS,
)
from cmm.domains.oppositions.definition import (
    OPPOSITIONS_DOMAIN_ID,
    OPPOSITIONS_DOMAIN_VERSION,
    OPPOSITIONS_MANIFEST_ID,
    OPPOSITIONS_OPERATION_IDS,
    OPPOSITIONS_PERMISSION_IDS,
    OPPOSITIONS_RESOURCE_IDS,
    OPPOSITIONS_RULE_IDS,
    OPPOSITIONS_WORKFLOW_IDS,
    build_oppositions_domain_definition,
)
from cmm.domains.oppositions.integration import (
    OppositionsDomainIntegrationResult,
    register_oppositions_domain,
)
from cmm.domains.oppositions.memory import (
    build_oppositions_memory_binding,
    build_oppositions_memory_proposal,
    build_oppositions_memory_view,
    build_oppositions_memory_view_request,
    validate_oppositions_memory_binding,
)
from cmm.domains.oppositions.operations import (
    build_oppositions_operation_definitions,
)
from cmm.domains.oppositions.permissions import (
    OPPOSITIONS_PERMISSION_POLICY_ID,
    build_oppositions_permission_policy,
)
from cmm.domains.oppositions.presentation import (
    build_oppositions_presentation_policy,
)
from cmm.domains.oppositions.profile import (
    OPPOSITIONS_PROFILE_ID,
    OPPOSITIONS_PROFILE_NAME,
    OPPOSITIONS_PROHIBITED_ACTIONS,
    build_oppositions_profile,
)
from cmm.domains.oppositions.resources import (
    OPPOSITIONS_RESOURCE_KINDS,
    build_oppositions_resource_definitions,
)
from cmm.domains.oppositions.rules import (
    AlternativeRouteRule,
    MockExamInterpretationRule,
    OfficialCallPriorityRule,
    OppositionTemporalValidityRule,
    StudyFeasibilityRule,
    SyllabusCoverageRule,
    build_oppositions_rules,
)
from cmm.domains.oppositions.trace import (
    assemble_oppositions_trace,
    build_oppositions_trace_contribution,
    build_oppositions_trace_reference,
    validate_oppositions_trace,
)
from cmm.domains.oppositions.workflows import (
    build_oppositions_workflow_definitions,
)

__all__ = [
    "CANONICAL_OPPOSITION_ENTITY_TYPES",
    "CANONICAL_OPPOSITION_OPERATION_IDS",
    "CANONICAL_OPPOSITION_RESOURCE_IDS",
    "CANONICAL_OPPOSITION_RULE_IDS",
    "CANONICAL_OPPOSITION_WORKFLOW_IDS",
    "OPPOSITIONS_DOMAIN_ID",
    "OPPOSITIONS_DOMAIN_VERSION",
    "OPPOSITIONS_MANIFEST_ID",
    "OPPOSITIONS_OPERATION_IDS",
    "OPPOSITIONS_PERMISSION_IDS",
    "OPPOSITIONS_PERMISSION_POLICY_ID",
    "OPPOSITIONS_PROFILE_ID",
    "OPPOSITIONS_PROFILE_NAME",
    "OPPOSITIONS_PROHIBITED_ACTIONS",
    "OPPOSITIONS_RESOURCE_IDS",
    "OPPOSITIONS_RESOURCE_KINDS",
    "OPPOSITIONS_RULE_IDS",
    "OPPOSITIONS_WORKFLOW_IDS",
    "AlternativeRouteRule",
    "MockExamInterpretationRule",
    "OfficialCallPriorityRule",
    "OppositionTemporalValidityRule",
    "OppositionsDomainBootstrap",
    "OppositionsDomainIntegrationResult",
    "StudyFeasibilityRule",
    "SyllabusCoverageRule",
    "assemble_oppositions_trace",
    "build_oppositions_domain_definition",
    "build_oppositions_memory_binding",
    "build_oppositions_memory_proposal",
    "build_oppositions_memory_view",
    "build_oppositions_memory_view_request",
    "build_oppositions_operation_definitions",
    "build_oppositions_permission_policy",
    "build_oppositions_presentation_policy",
    "build_oppositions_profile",
    "build_oppositions_resource_definitions",
    "build_oppositions_rules",
    "build_oppositions_trace_contribution",
    "build_oppositions_trace_reference",
    "build_oppositions_workflow_definitions",
    "build_standard_oppositions_domain_bootstrap",
    "register_oppositions_domain",
    "validate_oppositions_memory_binding",
    "validate_oppositions_trace",
]