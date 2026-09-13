"""Phase 10.53 — Neurodivergence Domain package.

An exploration-friendly, certainty-preserving, fail-closed Domain Pack for
exploratory and longitudinal neurodevelopmental reasoning: developmental
history, assessment-evidence organization, differential and overlap reasoning,
functional-impact review and preparation for professional assessment.

Neurodivergence keeps observations, self-report, third-party report, screening
results, model interpretation, working hypotheses and negative or insufficient
evidence distinct.  It may explore freely and hold useful working hypotheses,
but it never promotes a model inference, a screening result, self-report or an
isolated trait into a confirmed diagnosis, never overwrites Health's clinical
authority, never claims a sibling domain's facts as its own, and never persists
a sensitive label without the canonical proposal/approval path.

Public package surface only; no import-time registration or side effects.
"""

from __future__ import annotations

from cmm.domains.neurodivergence.benchmarks import (
    NEURODIVERGENCE_BENCHMARK_AREAS,
    build_neurodivergence_benchmark_suites,
)
from cmm.domains.neurodivergence.bootstrap import (
    NEURODIVERGENCE_BOOTSTRAP_NAME,
    NeurodivergenceDomainBootstrap,
    build_standard_neurodivergence_domain_bootstrap,
)
from cmm.domains.neurodivergence.catalog import (
    CANONICAL_NEURODIVERGENCE_ENTITY_TYPES,
    CANONICAL_NEURODIVERGENCE_OPERATION_IDS,
    CANONICAL_NEURODIVERGENCE_RESOURCE_IDS,
    CANONICAL_NEURODIVERGENCE_RULE_IDS,
    CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS,
    CANONICAL_NEURODIVERGENCE_WORKFLOW_NAMES,
    NEURODIVERGENCE_DOMAIN_ID,
    NEURODIVERGENCE_OPERATION_IDS,
    NEURODIVERGENCE_PROFILE_NAME,
    NEURODIVERGENCE_RESOURCE_IDS,
    NEURODIVERGENCE_RESOURCE_KINDS,
    NEURODIVERGENCE_RULE_IDS,
    NEURODIVERGENCE_WORKFLOW_IDS,
    NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.neurodivergence.definition import (
    NEURODIVERGENCE_DOMAIN_VERSION,
    NEURODIVERGENCE_MANIFEST_ID,
    NEURODIVERGENCE_PERMISSION_IDS,
    build_neurodivergence_domain_definition,
)
from cmm.domains.neurodivergence.integration import (
    NeurodivergenceDomainIntegrationResult,
    register_neurodivergence_domain,
)
from cmm.domains.neurodivergence.knowledge_package import (
    build_neurodivergence_knowledge_package_schema,
)
from cmm.domains.neurodivergence.memory import (
    NeurodivergenceMemoryPolicyError,
    build_neurodivergence_memory_binding,
    build_neurodivergence_memory_proposal,
    build_neurodivergence_memory_view,
    build_neurodivergence_memory_view_request,
    validate_neurodivergence_memory_binding,
)
from cmm.domains.neurodivergence.model_policy import (
    build_neurodivergence_model_policy,
)
from cmm.domains.neurodivergence.operations import (
    build_neurodivergence_operation_definitions,
)
from cmm.domains.neurodivergence.permissions import (
    NEURODIVERGENCE_CAPABILITY_SEPARATION,
    NEURODIVERGENCE_PERMISSION_POLICY_ID,
    NEURODIVERGENCE_PROHIBITED_CAPABILITIES,
    build_neurodivergence_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.neurodivergence.presentation import (
    build_neurodivergence_presentation_policy,
)
from cmm.domains.neurodivergence.privacy import (
    build_neurodivergence_privacy_policy,
)
from cmm.domains.neurodivergence.profile import (
    NEURODIVERGENCE_ALLOWED_INFERENCES,
    NEURODIVERGENCE_PROFILE_ID,
    NEURODIVERGENCE_PROHIBITED_ACTIONS,
    NEURODIVERGENCE_PROHIBITED_INFERENCES,
    build_neurodivergence_profile,
)
from cmm.domains.neurodivergence.quality_metrics import (
    NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES,
    build_neurodivergence_quality_metrics,
)
from cmm.domains.neurodivergence.resources import (
    build_neurodivergence_resource_definitions,
)
from cmm.domains.neurodivergence.rules import (
    CERTAINTY_CONFIRMED,
    CERTAINTY_HYPOTHESIS,
    CERTAINTY_IN_EVALUATION,
    CERTAINTY_INSUFFICIENTLY_SUPPORTED,
    CERTAINTY_NOT_CONFIRMED,
    CERTAINTY_RULED_OUT,
    CERTAINTY_UNKNOWN,
    HEALTH_DOMAIN_ID,
    CertaintyStatePreservationRule,
    ClinicalStatusAuthorityRule,
    ContradictionPreservationRule,
    DevelopmentalTemporalityRule,
    DifferentialExplanationsRule,
    GlobalAttributionGuardRule,
    LongitudinalCorroborationRule,
    ObservationReportSeparationRule,
    OverlapReasoningRule,
    PurposeMinimizedCrossDomainRule,
    ScreeningDiagnosisSeparationRule,
    SensitiveLabelPersistenceRule,
    SourceAuthorityRule,
    TraitFunctionSeparationRule,
    build_neurodivergence_rules,
    classify_development_period,
    classify_evidence_source,
    describe_certainty_state,
    detect_health_owned_clinical_status,
    evaluate_certainty_transition,
    evaluate_contradiction_preservation,
    evaluate_developmental_temporality,
    evaluate_longitudinal_corroboration,
    is_persistence_restricted_content,
    persistence_is_authorized,
    persistence_requires_proposal,
    proposal_preserves_hypothesis_status,
)
from cmm.domains.neurodivergence.trace import (
    assemble_neurodivergence_trace,
    build_neurodivergence_trace_contribution,
    build_neurodivergence_trace_reference,
    build_supporting_trace_contribution,
    validate_neurodivergence_trace,
)
from cmm.domains.neurodivergence.workflows import (
    build_neurodivergence_workflow_definitions,
)

__all__ = [
    "CANONICAL_NEURODIVERGENCE_ENTITY_TYPES",
    "CANONICAL_NEURODIVERGENCE_OPERATION_IDS",
    "CANONICAL_NEURODIVERGENCE_RESOURCE_IDS",
    "CANONICAL_NEURODIVERGENCE_RULE_IDS",
    "CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS",
    "CANONICAL_NEURODIVERGENCE_WORKFLOW_NAMES",
    "CERTAINTY_CONFIRMED",
    "CERTAINTY_HYPOTHESIS",
    "CERTAINTY_INSUFFICIENTLY_SUPPORTED",
    "CERTAINTY_IN_EVALUATION",
    "CERTAINTY_NOT_CONFIRMED",
    "CERTAINTY_RULED_OUT",
    "CERTAINTY_UNKNOWN",
    "HEALTH_DOMAIN_ID",
    "NEURODIVERGENCE_ALLOWED_INFERENCES",
    "NEURODIVERGENCE_BENCHMARK_AREAS",
    "NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES",
    "NEURODIVERGENCE_BOOTSTRAP_NAME",
    "NEURODIVERGENCE_CAPABILITY_SEPARATION",
    "NEURODIVERGENCE_DOMAIN_ID",
    "NEURODIVERGENCE_DOMAIN_VERSION",
    "NEURODIVERGENCE_MANIFEST_ID",
    "NEURODIVERGENCE_OPERATION_IDS",
    "NEURODIVERGENCE_PERMISSION_IDS",
    "NEURODIVERGENCE_PERMISSION_POLICY_ID",
    "NEURODIVERGENCE_PROFILE_ID",
    "NEURODIVERGENCE_PROFILE_NAME",
    "NEURODIVERGENCE_PROHIBITED_ACTIONS",
    "NEURODIVERGENCE_PROHIBITED_CAPABILITIES",
    "NEURODIVERGENCE_PROHIBITED_INFERENCES",
    "NEURODIVERGENCE_RESOURCE_IDS",
    "NEURODIVERGENCE_RESOURCE_KINDS",
    "NEURODIVERGENCE_RULE_IDS",
    "NEURODIVERGENCE_WORKFLOW_IDS",
    "NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID",
    "CertaintyStatePreservationRule",
    "ClinicalStatusAuthorityRule",
    "ContradictionPreservationRule",
    "DevelopmentalTemporalityRule",
    "DifferentialExplanationsRule",
    "GlobalAttributionGuardRule",
    "LongitudinalCorroborationRule",
    "NeurodivergenceDomainBootstrap",
    "NeurodivergenceDomainIntegrationResult",
    "NeurodivergenceMemoryPolicyError",
    "ObservationReportSeparationRule",
    "OverlapReasoningRule",
    "PurposeMinimizedCrossDomainRule",
    "ScreeningDiagnosisSeparationRule",
    "SensitiveLabelPersistenceRule",
    "SourceAuthorityRule",
    "TraitFunctionSeparationRule",
    "assemble_neurodivergence_trace",
    "build_neurodivergence_benchmark_suites",
    "build_neurodivergence_domain_definition",
    "build_neurodivergence_knowledge_package_schema",
    "build_neurodivergence_memory_binding",
    "build_neurodivergence_memory_proposal",
    "build_neurodivergence_memory_view",
    "build_neurodivergence_memory_view_request",
    "build_neurodivergence_model_policy",
    "build_neurodivergence_operation_definitions",
    "build_neurodivergence_permission_policy",
    "build_neurodivergence_presentation_policy",
    "build_neurodivergence_privacy_policy",
    "build_neurodivergence_profile",
    "build_neurodivergence_quality_metrics",
    "build_neurodivergence_resource_definitions",
    "build_neurodivergence_rules",
    "build_neurodivergence_trace_contribution",
    "build_neurodivergence_trace_reference",
    "build_neurodivergence_workflow_definitions",
    "build_standard_neurodivergence_domain_bootstrap",
    "build_supporting_trace_contribution",
    "classify_development_period",
    "classify_evidence_source",
    "describe_certainty_state",
    "detect_health_owned_clinical_status",
    "evaluate_certainty_transition",
    "evaluate_contradiction_preservation",
    "evaluate_developmental_temporality",
    "evaluate_longitudinal_corroboration",
    "is_persistence_restricted_content",
    "permission_authorization_allows",
    "persistence_is_authorized",
    "persistence_requires_proposal",
    "proposal_preserves_hypothesis_status",
    "register_neurodivergence_domain",
    "validate_neurodivergence_memory_binding",
    "validate_neurodivergence_trace",
]
