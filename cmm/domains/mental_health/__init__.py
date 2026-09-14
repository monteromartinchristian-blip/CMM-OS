"""Phase 10.52 — Mental Health Domain package.

A conservative, proposal-only, fail-closed Domain Pack for ordinary emotional
conversation, therapy continuity, therapy preparation/review, therapy
transcript analysis, longitudinal emotional context and emotionally relevant
decision support.

Mental Health keeps facts, observations, interpretations, hypotheses, fears,
intuitions and uncertainty distinct; it never medicalizes ordinary distress,
never invents a diagnosis or treatment authority, never fabricates a therapist
statement, never persists a sensitive inference without the canonical
proposal/approval path, and never overrides Health's clinical authority.

Public package surface only; no import-time registration or side effects.
"""

from __future__ import annotations

from cmm.domains.mental_health.benchmarks import build_mental_health_benchmark_suites
from cmm.domains.mental_health.bootstrap import (
    MENTAL_HEALTH_BOOTSTRAP_NAME,
    MentalHealthDomainBootstrap,
    build_standard_mental_health_domain_bootstrap,
)
from cmm.domains.mental_health.catalog import (
    CANONICAL_MENTAL_HEALTH_ENTITY_TYPES,
    CANONICAL_MENTAL_HEALTH_OPERATION_IDS,
    CANONICAL_MENTAL_HEALTH_RESOURCE_IDS,
    CANONICAL_MENTAL_HEALTH_RULE_IDS,
    CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS,
    CANONICAL_MENTAL_HEALTH_WORKFLOW_NAMES,
    MENTAL_HEALTH_DOMAIN_ID,
    MENTAL_HEALTH_OPERATION_IDS,
    MENTAL_HEALTH_PROFILE_NAME,
    MENTAL_HEALTH_RESOURCE_IDS,
    MENTAL_HEALTH_RESOURCE_KINDS,
    MENTAL_HEALTH_RULE_IDS,
    MENTAL_HEALTH_WORKFLOW_IDS,
    MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.mental_health.definition import (
    MENTAL_HEALTH_DOMAIN_VERSION,
    MENTAL_HEALTH_MANIFEST_ID,
    MENTAL_HEALTH_PERMISSION_IDS,
    build_mental_health_domain_definition,
)
from cmm.domains.mental_health.integration import (
    MentalHealthDomainIntegrationResult,
    register_mental_health_domain,
)
from cmm.domains.mental_health.knowledge_package import (
    build_mental_health_knowledge_package_schema,
)
from cmm.domains.mental_health.memory import (
    MentalHealthMemoryPolicyError,
    build_mental_health_memory_binding,
    build_mental_health_memory_proposal,
    build_mental_health_memory_view,
    build_mental_health_memory_view_request,
    validate_mental_health_memory_binding,
)
from cmm.domains.mental_health.model_policy import build_mental_health_model_policy
from cmm.domains.mental_health.operations import (
    build_mental_health_operation_definitions,
)
from cmm.domains.mental_health.permissions import (
    MENTAL_HEALTH_CAPABILITY_SEPARATION,
    MENTAL_HEALTH_PERMISSION_POLICY_ID,
    MENTAL_HEALTH_PROHIBITED_CAPABILITIES,
    build_mental_health_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.mental_health.presentation import (
    build_mental_health_presentation_policy,
)
from cmm.domains.mental_health.privacy import build_mental_health_privacy_policy
from cmm.domains.mental_health.profile import (
    MENTAL_HEALTH_PROFILE_ID,
    MENTAL_HEALTH_PROHIBITED_ACTIONS,
    build_mental_health_profile,
)
from cmm.domains.mental_health.quality_metrics import (
    build_mental_health_quality_metrics,
)
from cmm.domains.mental_health.resources import (
    build_mental_health_resource_definitions,
)
from cmm.domains.mental_health.rules import (
    EPISTEMIC_FACT,
    EPISTEMIC_FEAR,
    EPISTEMIC_HYPOTHESIS,
    EPISTEMIC_INTERPRETATION,
    EPISTEMIC_INTUITION,
    EPISTEMIC_OBSERVATION,
    EPISTEMIC_UNCERTAINTY,
    SPEAKER_MODEL,
    SPEAKER_THERAPIST,
    SPEAKER_UNKNOWN,
    SPEAKER_USER,
    AuthorizedLongitudinalContinuityRule,
    EmotionalContextRelevanceRule,
    EmotionalEpistemicSeparationRule,
    HealthAuthorityRule,
    MaterialGapQuestioningRule,
    NonPathologizingDefaultRule,
    ProportionateSafetyEscalationRule,
    PurposeMinimizedCrossDomainRule,
    RepetitionWithoutPathologyRule,
    SensitivePersistenceControlRule,
    TherapySpeakerProvenanceRule,
    TherapyStatementSeparationRule,
    UncertaintyPreservationRule,
    build_mental_health_rules,
    classify_emotional_statement,
    classify_speaker,
    detect_health_owned_clinical_claim,
    evaluate_safety_proportionality,
    is_emotionally_relevant,
    is_persistence_restricted_content,
    persistence_is_authorized,
)
from cmm.domains.mental_health.trace import (
    assemble_mental_health_trace,
    build_mental_health_trace_contribution,
    build_mental_health_trace_reference,
    build_supporting_trace_contribution,
    validate_mental_health_trace,
)
from cmm.domains.mental_health.workflows import (
    build_mental_health_workflow_definitions,
)

__all__ = [
    "CANONICAL_MENTAL_HEALTH_ENTITY_TYPES",
    "CANONICAL_MENTAL_HEALTH_OPERATION_IDS",
    "CANONICAL_MENTAL_HEALTH_RESOURCE_IDS",
    "CANONICAL_MENTAL_HEALTH_RULE_IDS",
    "CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS",
    "CANONICAL_MENTAL_HEALTH_WORKFLOW_NAMES",
    "EPISTEMIC_FACT",
    "EPISTEMIC_FEAR",
    "EPISTEMIC_HYPOTHESIS",
    "EPISTEMIC_INTERPRETATION",
    "EPISTEMIC_INTUITION",
    "EPISTEMIC_OBSERVATION",
    "EPISTEMIC_UNCERTAINTY",
    "MENTAL_HEALTH_BOOTSTRAP_NAME",
    "MENTAL_HEALTH_CAPABILITY_SEPARATION",
    "MENTAL_HEALTH_DOMAIN_ID",
    "MENTAL_HEALTH_DOMAIN_VERSION",
    "MENTAL_HEALTH_MANIFEST_ID",
    "MENTAL_HEALTH_OPERATION_IDS",
    "MENTAL_HEALTH_PERMISSION_IDS",
    "MENTAL_HEALTH_PERMISSION_POLICY_ID",
    "MENTAL_HEALTH_PROFILE_ID",
    "MENTAL_HEALTH_PROFILE_NAME",
    "MENTAL_HEALTH_PROHIBITED_ACTIONS",
    "MENTAL_HEALTH_PROHIBITED_CAPABILITIES",
    "MENTAL_HEALTH_RESOURCE_IDS",
    "MENTAL_HEALTH_RESOURCE_KINDS",
    "MENTAL_HEALTH_RULE_IDS",
    "MENTAL_HEALTH_WORKFLOW_IDS",
    "MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID",
    "SPEAKER_MODEL",
    "SPEAKER_THERAPIST",
    "SPEAKER_UNKNOWN",
    "SPEAKER_USER",
    "AuthorizedLongitudinalContinuityRule",
    "EmotionalContextRelevanceRule",
    "EmotionalEpistemicSeparationRule",
    "HealthAuthorityRule",
    "MaterialGapQuestioningRule",
    "MentalHealthDomainBootstrap",
    "MentalHealthDomainIntegrationResult",
    "MentalHealthMemoryPolicyError",
    "NonPathologizingDefaultRule",
    "ProportionateSafetyEscalationRule",
    "PurposeMinimizedCrossDomainRule",
    "RepetitionWithoutPathologyRule",
    "SensitivePersistenceControlRule",
    "TherapySpeakerProvenanceRule",
    "TherapyStatementSeparationRule",
    "UncertaintyPreservationRule",
    "assemble_mental_health_trace",
    "build_mental_health_benchmark_suites",
    "build_mental_health_domain_definition",
    "build_mental_health_knowledge_package_schema",
    "build_mental_health_memory_binding",
    "build_mental_health_memory_proposal",
    "build_mental_health_memory_view",
    "build_mental_health_memory_view_request",
    "build_mental_health_model_policy",
    "build_mental_health_operation_definitions",
    "build_mental_health_permission_policy",
    "build_mental_health_presentation_policy",
    "build_mental_health_privacy_policy",
    "build_mental_health_profile",
    "build_mental_health_quality_metrics",
    "build_mental_health_resource_definitions",
    "build_mental_health_rules",
    "build_mental_health_trace_contribution",
    "build_mental_health_trace_reference",
    "build_mental_health_workflow_definitions",
    "build_standard_mental_health_domain_bootstrap",
    "build_supporting_trace_contribution",
    "classify_emotional_statement",
    "classify_speaker",
    "detect_health_owned_clinical_claim",
    "evaluate_safety_proportionality",
    "is_emotionally_relevant",
    "is_persistence_restricted_content",
    "permission_authorization_allows",
    "persistence_is_authorized",
    "register_mental_health_domain",
    "validate_mental_health_memory_binding",
    "validate_mental_health_trace",
]
