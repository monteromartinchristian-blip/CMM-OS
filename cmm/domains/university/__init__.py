"""Phase 10.22 — University Domain package.

A conservative, proposal-only, fail-closed Domain Pack for academic life.
University never adopts an academic decision, never sends email, never submits
formal procedures, never modifies the official university record, never infers
intellectual capacity from observed performance, and preserves source authority
by attribute.  Academic State is never overridden by Personal Memory.
"""

from __future__ import annotations

from cmm.domains.university.bootstrap import (
    UniversityDomainBootstrap,
    build_standard_university_domain_bootstrap,
)
from cmm.domains.university.catalog import (
    CANONICAL_UNIVERSITY_ENTITY_TYPES,
    CANONICAL_UNIVERSITY_OPERATION_IDS,
    CANONICAL_UNIVERSITY_RESOURCE_IDS,
    CANONICAL_UNIVERSITY_RULE_IDS,
    CANONICAL_UNIVERSITY_WORKFLOW_IDS,
)
from cmm.domains.university.definition import (
    UNIVERSITY_DOMAIN_ID,
    UNIVERSITY_DOMAIN_VERSION,
    UNIVERSITY_MANIFEST_ID,
    UNIVERSITY_OPERATION_IDS,
    UNIVERSITY_PERMISSION_IDS,
    UNIVERSITY_RESOURCE_IDS,
    UNIVERSITY_RULE_IDS,
    UNIVERSITY_WORKFLOW_IDS,
    build_university_domain_definition,
)
from cmm.domains.university.integration import (
    UniversityDomainIntegrationResult,
    register_university_domain,
)
from cmm.domains.university.memory import (
    build_university_memory_binding,
    build_university_memory_proposal,
    build_university_memory_view,
    build_university_memory_view_request,
    validate_university_memory_binding,
)
from cmm.domains.university.operations import (
    build_university_operation_definitions,
)
from cmm.domains.university.permissions import (
    UNIVERSITY_PERMISSION_POLICY_ID,
    build_university_permission_policy,
)
from cmm.domains.university.presentation import (
    build_university_presentation_policy,
)
from cmm.domains.university.profile import (
    UNIVERSITY_PROFILE_ID,
    UNIVERSITY_PROFILE_NAME,
    UNIVERSITY_PROHIBITED_ACTIONS,
    build_university_profile,
)
from cmm.domains.university.resources import (
    UNIVERSITY_RESOURCE_KINDS,
    build_university_resource_definitions,
)
from cmm.domains.university.rules import (
    AcademicContradictionRule,
    AcademicDeadlineRule,
    AcademicDecisionPreservationRule,
    AcademicDependencyRule,
    AcademicIntegrityRule,
    AcademicSourceAuthorityRule,
    AcademicWorkloadRule,
    EctsConsistencyRule,
    ExamAttemptRule,
    ObservedPerformanceCapacityRule,
    build_university_rules,
)
from cmm.domains.university.trace import (
    assemble_university_trace,
    build_university_trace_contribution,
    build_university_trace_reference,
    validate_university_trace,
)
from cmm.domains.university.workflows import (
    build_university_workflow_definitions,
)

__all__ = [
    "CANONICAL_UNIVERSITY_ENTITY_TYPES",
    "CANONICAL_UNIVERSITY_OPERATION_IDS",
    "CANONICAL_UNIVERSITY_RESOURCE_IDS",
    "CANONICAL_UNIVERSITY_RULE_IDS",
    "CANONICAL_UNIVERSITY_WORKFLOW_IDS",
    "UNIVERSITY_DOMAIN_ID",
    "UNIVERSITY_DOMAIN_VERSION",
    "UNIVERSITY_MANIFEST_ID",
    "UNIVERSITY_OPERATION_IDS",
    "UNIVERSITY_PERMISSION_IDS",
    "UNIVERSITY_PERMISSION_POLICY_ID",
    "UNIVERSITY_PROFILE_ID",
    "UNIVERSITY_PROFILE_NAME",
    "UNIVERSITY_PROHIBITED_ACTIONS",
    "UNIVERSITY_RESOURCE_IDS",
    "UNIVERSITY_RESOURCE_KINDS",
    "UNIVERSITY_RULE_IDS",
    "UNIVERSITY_WORKFLOW_IDS",
    "AcademicContradictionRule",
    "AcademicDeadlineRule",
    "AcademicDecisionPreservationRule",
    "AcademicDependencyRule",
    "AcademicIntegrityRule",
    "AcademicSourceAuthorityRule",
    "AcademicWorkloadRule",
    "EctsConsistencyRule",
    "ExamAttemptRule",
    "ObservedPerformanceCapacityRule",
    "UniversityDomainBootstrap",
    "UniversityDomainIntegrationResult",
    "assemble_university_trace",
    "build_standard_university_domain_bootstrap",
    "build_university_domain_definition",
    "build_university_memory_binding",
    "build_university_memory_proposal",
    "build_university_memory_view",
    "build_university_memory_view_request",
    "build_university_operation_definitions",
    "build_university_permission_policy",
    "build_university_presentation_policy",
    "build_university_profile",
    "build_university_resource_definitions",
    "build_university_rules",
    "build_university_trace_contribution",
    "build_university_trace_reference",
    "build_university_workflow_definitions",
    "register_university_domain",
    "validate_university_memory_binding",
    "validate_university_trace",
]
