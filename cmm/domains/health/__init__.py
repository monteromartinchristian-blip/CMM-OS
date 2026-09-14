"""Phase 10.20 — Health Domain package.

A conservative, proposal-only, fail-closed Domain Pack for personal health
information.  Health never provides definitive diagnoses, never modifies
medication, never takes treatment decisions, and never communicates
externally without the required approval path.
"""

from __future__ import annotations

from cmm.domains.health.bootstrap import (
    HealthDomainBootstrap,
    build_standard_health_domain_bootstrap,
)
from cmm.domains.health.catalog import (
    CANONICAL_HEALTH_ENTITY_TYPES,
    CANONICAL_HEALTH_OPERATION_IDS,
    CANONICAL_HEALTH_RESOURCE_IDS,
    CANONICAL_HEALTH_RULE_IDS,
    CANONICAL_HEALTH_WORKFLOW_IDS,
)
from cmm.domains.health.definition import (
    HEALTH_DOMAIN_ID,
    HEALTH_DOMAIN_VERSION,
    HEALTH_MANIFEST_ID,
    HEALTH_OPERATION_IDS,
    HEALTH_PERMISSION_IDS,
    HEALTH_RESOURCE_IDS,
    HEALTH_RULE_IDS,
    HEALTH_WORKFLOW_IDS,
    build_health_domain_definition,
)
from cmm.domains.health.integration import (
    HealthDomainIntegrationResult,
    register_health_domain,
)
from cmm.domains.health.memory import (
    build_health_memory_view,
    build_health_memory_view_request,
    build_health_symptom_binding,
    build_health_symptom_proposal,
    validate_health_memory_binding,
)
from cmm.domains.health.operations import (
    build_health_operation_definitions,
)
from cmm.domains.health.permissions import (
    HEALTH_PERMISSION_POLICY_ID,
    build_health_permission_policy,
)
from cmm.domains.health.presentation import build_health_presentation_policy
from cmm.domains.health.profile import (
    HEALTH_PROFILE_ID,
    HEALTH_PROFILE_NAME,
    HEALTH_PROHIBITED_ACTIONS,
    build_health_profile,
)
from cmm.domains.health.resources import (
    HEALTH_RESOURCE_KINDS,
    build_health_resource_definitions,
)
from cmm.domains.health.rules import (
    HealthClinicalSourcePriorityRule,
    HealthMedicalRedFlagRule,
    HealthMedicalTemporalValidityRule,
    HealthMedicationConsistencyRule,
    HealthMedicationTemporalRelationshipRule,
    HealthNoDefinitiveDiagnosisRule,
    HealthProfessionalEscalationRule,
    HealthSymptomDiagnosisHypothesisRule,
    build_health_rules,
)
from cmm.domains.health.trace import (
    assemble_health_trace,
    build_health_trace_contribution,
    build_health_trace_reference,
    validate_health_trace,
)
from cmm.domains.health.workflows import (
    build_health_workflow_definitions,
)

__all__ = [
    "CANONICAL_HEALTH_ENTITY_TYPES",
    "CANONICAL_HEALTH_OPERATION_IDS",
    "CANONICAL_HEALTH_RESOURCE_IDS",
    "CANONICAL_HEALTH_RULE_IDS",
    "CANONICAL_HEALTH_WORKFLOW_IDS",
    "HEALTH_DOMAIN_ID",
    "HEALTH_DOMAIN_VERSION",
    "HEALTH_MANIFEST_ID",
    "HEALTH_OPERATION_IDS",
    "HEALTH_PERMISSION_IDS",
    "HEALTH_PERMISSION_POLICY_ID",
    "HEALTH_PROFILE_ID",
    "HEALTH_PROFILE_NAME",
    "HEALTH_PROHIBITED_ACTIONS",
    "HEALTH_RESOURCE_IDS",
    "HEALTH_RESOURCE_KINDS",
    "HEALTH_RULE_IDS",
    "HEALTH_WORKFLOW_IDS",
    "HealthClinicalSourcePriorityRule",
    "HealthDomainBootstrap",
    "HealthDomainIntegrationResult",
    "HealthMedicalRedFlagRule",
    "HealthMedicalTemporalValidityRule",
    "HealthMedicationConsistencyRule",
    "HealthMedicationTemporalRelationshipRule",
    "HealthNoDefinitiveDiagnosisRule",
    "HealthProfessionalEscalationRule",
    "HealthSymptomDiagnosisHypothesisRule",
    "assemble_health_trace",
    "build_health_domain_definition",
    "build_health_memory_view",
    "build_health_memory_view_request",
    "build_health_operation_definitions",
    "build_health_permission_policy",
    "build_health_presentation_policy",
    "build_health_profile",
    "build_health_resource_definitions",
    "build_health_rules",
    "build_health_symptom_binding",
    "build_health_symptom_proposal",
    "build_health_trace_contribution",
    "build_health_trace_reference",
    "build_health_workflow_definitions",
    "build_standard_health_domain_bootstrap",
    "register_health_domain",
    "validate_health_memory_binding",
    "validate_health_trace",
]
