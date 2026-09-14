"""Phase 10.25 — Concerns Domain package.

A conservative, proposal-only, fail-closed Domain Pack for supporting the user
through problems, worries, fears, uncertainty, recurring concerns, difficult
decisions, requests for reassurance or perspective, and open-ended
talk-it-through conversations.  Concerns understands first, keeps epistemic
levels distinct, offers evidence-calibrated reassurance when justified,
acknowledges material concerns when justified, avoids catastrophic escalation
and false reassurance, never pathologizes repetition, never forces action or
closure, never adopts a personal decision, never writes semantic memory, and
never performs an external action: prepared content is preparation only
(``PREPARATION != SEND``, ``PROPOSAL != MUTATION``).

Public package surface only; no import-time registration or side effects.
"""

from __future__ import annotations

from cmm.domains.concerns.bootstrap import (
    CONCERNS_BOOTSTRAP_NAME,
    ConcernsDomainBootstrap,
    build_standard_concerns_domain_bootstrap,
)
from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_ENTITY_TYPES,
    CANONICAL_CONCERNS_OPERATION_IDS,
    CANONICAL_CONCERNS_RESOURCE_IDS,
    CANONICAL_CONCERNS_RULE_IDS,
    CANONICAL_CONCERNS_RULE_NAMES,
    CANONICAL_CONCERNS_WORKFLOW_IDS,
    CANONICAL_CONCERNS_WORKFLOW_NAMES,
    CONCERNS_RESOURCE_KINDS,
    CONCERNS_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.concerns.definition import (
    CONCERNS_DOMAIN_ID,
    CONCERNS_DOMAIN_VERSION,
    CONCERNS_MANIFEST_ID,
    CONCERNS_OPERATION_IDS,
    CONCERNS_PERMISSION_IDS,
    CONCERNS_PROFILE_NAME,
    CONCERNS_RESOURCE_IDS,
    CONCERNS_RULE_IDS,
    CONCERNS_WORKFLOW_IDS,
    build_concerns_domain_definition,
)
from cmm.domains.concerns.integration import (
    ConcernsDomainIntegrationResult,
    register_concerns_domain,
)
from cmm.domains.concerns.memory import (
    build_concerns_memory_binding,
    build_concerns_memory_proposal,
    build_concerns_memory_view,
    build_concerns_memory_view_request,
    validate_concerns_memory_binding,
)
from cmm.domains.concerns.operations import (
    build_concerns_operation_definitions,
    calibrate_uncertainty_result,
    evaluate_reassurance_result,
    evaluate_risk_result,
    explore_hypotheses_result,
    explore_options_result,
    identify_open_questions_result,
    infer_support_need_result,
    prepare_next_step_result,
    prepare_professional_discussion_result,
    review_recurring_concern_result,
    separate_reality_interpretation_result,
    understand_concern_result,
)
from cmm.domains.concerns.permissions import (
    CONCERNS_PERMISSION_POLICY_ID,
    build_concerns_permission_policy,
    is_persistence_restricted_content,
    permission_authorization_allows,
    persistence_confirmation_accepted,
)
from cmm.domains.concerns.presentation import (
    build_concerns_presentation_policy,
    present_concerns_result,
)
from cmm.domains.concerns.profile import (
    CONCERNS_PROFILE_ID,
    CONCERNS_PROHIBITED_ACTIONS,
    build_concerns_profile,
)
from cmm.domains.concerns.resources import (
    build_concerns_resource_definitions,
)
from cmm.domains.concerns.rules import (
    AgencyWithoutPressureRule,
    ContextualQuestionRule,
    DirectnessWithoutHarshnessRule,
    EmotionalValidationRule,
    EvidenceCalibratedReassuranceRule,
    ExperienceRealitySeparationRule,
    ImmediateRiskEscalationRule,
    NoCatastrophicEscalationRule,
    NoFalseReassuranceRule,
    ProportionalRiskRule,
    RepetitionWithoutPathologizingRule,
    SupportNeedCalibrationRule,
    UncertaintyPreservationRule,
    UnderstandBeforeInterveneRule,
    build_concerns_rules,
    classify_concern_statement,
    detect_catastrophic_escalation,
    detect_false_reassurance,
    evaluate_action_state,
    evaluate_grounded_directness,
    evaluate_immediate_risk_escalation,
    evaluate_proportional_risk,
    evaluate_question_materiality,
    evaluate_reassurance,
    evaluate_repetitive_certainty_pattern,
    evaluate_uncertainty,
    infer_support_need,
    map_lived_experience,
    normalize_json_value,
    review_recurring_concern_state,
    understand_concern,
)
from cmm.domains.concerns.trace import (
    assemble_concerns_trace,
    build_concerns_trace_contribution,
    build_concerns_trace_reference,
    build_supporting_trace_contribution,
    validate_concerns_trace,
)
from cmm.domains.concerns.workflows import (
    build_concerns_workflow_definitions,
)

__all__ = [
    "CANONICAL_CONCERNS_ENTITY_TYPES",
    "CANONICAL_CONCERNS_OPERATION_IDS",
    "CANONICAL_CONCERNS_RESOURCE_IDS",
    "CANONICAL_CONCERNS_RULE_IDS",
    "CANONICAL_CONCERNS_RULE_NAMES",
    "CANONICAL_CONCERNS_WORKFLOW_IDS",
    "CANONICAL_CONCERNS_WORKFLOW_NAMES",
    "CONCERNS_BOOTSTRAP_NAME",
    "CONCERNS_DOMAIN_ID",
    "CONCERNS_DOMAIN_VERSION",
    "CONCERNS_MANIFEST_ID",
    "CONCERNS_OPERATION_IDS",
    "CONCERNS_PERMISSION_IDS",
    "CONCERNS_PERMISSION_POLICY_ID",
    "CONCERNS_PROFILE_ID",
    "CONCERNS_PROFILE_NAME",
    "CONCERNS_PROHIBITED_ACTIONS",
    "CONCERNS_RESOURCE_IDS",
    "CONCERNS_RESOURCE_KINDS",
    "CONCERNS_RULE_IDS",
    "CONCERNS_WORKFLOW_IDS",
    "CONCERNS_WORKFLOW_NAMES_BY_ID",
    "AgencyWithoutPressureRule",
    "ConcernsDomainBootstrap",
    "ConcernsDomainIntegrationResult",
    "ContextualQuestionRule",
    "DirectnessWithoutHarshnessRule",
    "EmotionalValidationRule",
    "EvidenceCalibratedReassuranceRule",
    "ExperienceRealitySeparationRule",
    "ImmediateRiskEscalationRule",
    "NoCatastrophicEscalationRule",
    "NoFalseReassuranceRule",
    "ProportionalRiskRule",
    "RepetitionWithoutPathologizingRule",
    "SupportNeedCalibrationRule",
    "UncertaintyPreservationRule",
    "UnderstandBeforeInterveneRule",
    "assemble_concerns_trace",
    "build_concerns_domain_definition",
    "build_concerns_memory_binding",
    "build_concerns_memory_proposal",
    "build_concerns_memory_view",
    "build_concerns_memory_view_request",
    "build_concerns_operation_definitions",
    "build_concerns_permission_policy",
    "build_concerns_presentation_policy",
    "build_concerns_profile",
    "build_concerns_resource_definitions",
    "build_concerns_rules",
    "build_concerns_trace_contribution",
    "build_concerns_trace_reference",
    "build_concerns_workflow_definitions",
    "build_standard_concerns_domain_bootstrap",
    "build_supporting_trace_contribution",
    "calibrate_uncertainty_result",
    "classify_concern_statement",
    "detect_catastrophic_escalation",
    "detect_false_reassurance",
    "evaluate_action_state",
    "evaluate_grounded_directness",
    "evaluate_immediate_risk_escalation",
    "evaluate_proportional_risk",
    "evaluate_question_materiality",
    "evaluate_reassurance",
    "evaluate_reassurance_result",
    "evaluate_repetitive_certainty_pattern",
    "evaluate_risk_result",
    "evaluate_uncertainty",
    "explore_hypotheses_result",
    "explore_options_result",
    "identify_open_questions_result",
    "infer_support_need",
    "infer_support_need_result",
    "is_persistence_restricted_content",
    "map_lived_experience",
    "normalize_json_value",
    "permission_authorization_allows",
    "persistence_confirmation_accepted",
    "prepare_next_step_result",
    "prepare_professional_discussion_result",
    "present_concerns_result",
    "register_concerns_domain",
    "review_recurring_concern_result",
    "review_recurring_concern_state",
    "separate_reality_interpretation_result",
    "understand_concern",
    "understand_concern_result",
    "validate_concerns_memory_binding",
    "validate_concerns_trace",
]
