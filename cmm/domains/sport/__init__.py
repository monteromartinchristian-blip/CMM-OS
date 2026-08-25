"""Phase 10.28 — Sport Domain package.

Domain Pack for athletic training, physical activity goals, progression analysis,
load management, recovery tracking, body measurements, injury risk signals,
and controlled Health coordination.

Public package surface only; no import-time registration or side effects.
"""

from __future__ import annotations

from cmm.domains.sport.bootstrap import (
    SPORT_BOOTSTRAP_NAME,
    SportDomainBootstrap,
    build_standard_sport_domain_bootstrap,
)
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_ENTITY_IDS,
    CANONICAL_SPORT_ENTITY_TYPES,
    CANONICAL_SPORT_OPERATION_IDS,
    CANONICAL_SPORT_RESOURCE_IDS,
    CANONICAL_SPORT_RULE_IDS,
    CANONICAL_SPORT_RULE_NAMES,
    CANONICAL_SPORT_WORKFLOW_IDS,
    SPORT_ENTITY_IDS,
    SPORT_OPERATION_IDS,
    SPORT_RESOURCE_IDS,
    SPORT_RESOURCE_KINDS,
    SPORT_RULE_IDS,
    SPORT_WORKFLOW_IDS,
)
from cmm.domains.sport.definition import (
    SPORT_DOMAIN_ID,
    SPORT_DOMAIN_VERSION,
    SPORT_MANIFEST_ID,
    SPORT_OPERATION_IDS as DEF_SPORT_OPERATION_IDS,
    SPORT_PERMISSION_IDS,
    SPORT_PROFILE_NAME,
    SPORT_RESOURCE_IDS as DEF_SPORT_RESOURCE_IDS,
    SPORT_RULE_IDS as DEF_SPORT_RULE_IDS,
    SPORT_WORKFLOW_IDS as DEF_SPORT_WORKFLOW_IDS,
    build_sport_domain_definition,
)
from cmm.domains.sport.integration import (
    SportDomainIntegrationResult,
    register_sport_domain,
)
from cmm.domains.sport.memory import (
    CANDIDATE_SPORT_LONGITUDINAL_KINDS,
    build_sport_memory_binding,
    build_sport_memory_proposal,
    build_sport_memory_view,
    build_sport_memory_view_request,
    validate_sport_memory_binding,
    validate_sport_memory_proposal_content,
)
from cmm.domains.sport.operations import (
    adjust_training_load_result,
    build_sport_operation_definitions,
    create_training_plan_result,
    generate_workout_result,
    identify_risks_result,
    review_progress_result,
    review_recovery_result,
    schedule_sessions_result,
    track_measurements_result,
)
from cmm.domains.sport.permissions import (
    SPORT_PERMISSION_POLICY_ID,
    SPORT_PROHIBITED_CAPABILITIES,
    build_sport_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.sport.presentation import (
    build_sport_presentation_policy,
    present_sport_result,
)
from cmm.domains.sport.profile import (
    SPORT_PROFILE_ID,
    SPORT_PROFILE_NAME as PROF_SPORT_PROFILE_NAME,
    SPORT_PROHIBITED_ACTIONS,
    build_sport_profile,
)
from cmm.domains.sport.resources import (
    build_sport_resource_definitions,
)
from cmm.domains.sport.rules import (
    HealthConstraintRule,
    InjurySignalRule,
    MeasurementTrendRule,
    ProgressiveOverloadRule,
    RecoveryRule,
    TrainingLoadRule,
    build_sport_rules,
    evaluate_health_constraint,
    evaluate_injury_signal,
    evaluate_measurement_trend,
    evaluate_progressive_overload,
    evaluate_recovery,
    evaluate_training_load,
)
from cmm.domains.sport.trace import (
    assemble_sport_trace,
    build_sport_trace_contribution,
    build_sport_trace_reference,
    build_supporting_trace_contribution,
    validate_sport_trace,
)
from cmm.domains.sport.workflows import (
    SPORT_WORKFLOW_NAMES_BY_ID,
    build_sport_workflow_definitions,
    execute_return_to_training_workflow,
)

__all__ = [
    "CANDIDATE_SPORT_LONGITUDINAL_KINDS",
    "CANONICAL_SPORT_ENTITY_IDS",
    "CANONICAL_SPORT_ENTITY_TYPES",
    "CANONICAL_SPORT_OPERATION_IDS",
    "CANONICAL_SPORT_RESOURCE_IDS",
    "CANONICAL_SPORT_RULE_IDS",
    "CANONICAL_SPORT_RULE_NAMES",
    "CANONICAL_SPORT_WORKFLOW_IDS",
    "HealthConstraintRule",
    "InjurySignalRule",
    "MeasurementTrendRule",
    "ProgressiveOverloadRule",
    "RecoveryRule",
    "SPORT_BOOTSTRAP_NAME",
    "SPORT_DOMAIN_ID",
    "SPORT_DOMAIN_VERSION",
    "SPORT_ENTITY_IDS",
    "SPORT_MANIFEST_ID",
    "SPORT_OPERATION_IDS",
    "SPORT_PERMISSION_IDS",
    "SPORT_PERMISSION_POLICY_ID",
    "SPORT_PROFILE_ID",
    "SPORT_PROFILE_NAME",
    "SPORT_PROHIBITED_ACTIONS",
    "SPORT_PROHIBITED_CAPABILITIES",
    "SPORT_RESOURCE_IDS",
    "SPORT_RESOURCE_KINDS",
    "SPORT_RULE_IDS",
    "SPORT_WORKFLOW_IDS",
    "SPORT_WORKFLOW_NAMES_BY_ID",
    "SportDomainBootstrap",
    "SportDomainIntegrationResult",
    "TrainingLoadRule",
    "adjust_training_load_result",
    "assemble_sport_trace",
    "build_sport_domain_definition",
    "build_sport_memory_binding",
    "build_sport_memory_proposal",
    "build_sport_memory_view",
    "build_sport_memory_view_request",
    "build_sport_operation_definitions",
    "build_sport_permission_policy",
    "build_sport_presentation_policy",
    "build_sport_profile",
    "build_sport_resource_definitions",
    "build_sport_rules",
    "build_sport_trace_contribution",
    "build_sport_trace_reference",
    "build_sport_workflow_definitions",
    "build_standard_sport_domain_bootstrap",
    "build_supporting_trace_contribution",
    "create_training_plan_result",
    "evaluate_health_constraint",
    "evaluate_injury_signal",
    "evaluate_measurement_trend",
    "evaluate_progressive_overload",
    "evaluate_recovery",
    "evaluate_training_load",
    "execute_return_to_training_workflow",
    "generate_workout_result",
    "identify_risks_result",
    "permission_authorization_allows",
    "present_sport_result",
    "register_sport_domain",
    "review_progress_result",
    "review_recovery_result",
    "schedule_sessions_result",
    "track_measurements_result",
    "validate_sport_memory_binding",
    "validate_sport_memory_proposal_content",
    "validate_sport_trace",
]
