"""Phase 10.24 — Reflection Domain package.

A conservative, proposal-only, fail-closed Domain Pack for complex reflection,
hypothesis exploration, organization of ideas, longitudinal comparison,
decision review, and preservation of genuine ambivalence without forcing a
single conclusion.  Reflection never classifies identity, never presents a
psychological hypothesis as a diagnosis, never adopts a personal decision,
never writes semantic memory without a valid confirmation, and never performs
an external write: prepared content is preparation only (``PREPARATION !=
EXTERNAL COMMUNICATION``, ``PROPOSAL != MUTATION``).

Public package surface only; no import-time registration or side effects.
"""

from __future__ import annotations

from cmm.domains.reflection.bootstrap import (
    REFLECTION_BOOTSTRAP_NAME,
    ReflectionDomainBootstrap,
    build_standard_reflection_domain_bootstrap,
)
from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_ENTITY_TYPES,
    CANONICAL_REFLECTION_OPERATION_IDS,
    CANONICAL_REFLECTION_RESOURCE_IDS,
    CANONICAL_REFLECTION_RULE_IDS,
    CANONICAL_REFLECTION_RULE_NAMES,
    CANONICAL_REFLECTION_WORKFLOW_IDS,
    CANONICAL_REFLECTION_WORKFLOW_NAMES,
    REFLECTION_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.reflection.definition import (
    REFLECTION_DOMAIN_ID,
    REFLECTION_DOMAIN_VERSION,
    REFLECTION_MANIFEST_ID,
    REFLECTION_OPERATION_IDS,
    REFLECTION_PERMISSION_IDS,
    REFLECTION_RESOURCE_IDS,
    REFLECTION_RULE_IDS,
    build_reflection_domain_definition,
)
from cmm.domains.reflection.integration import (
    ReflectionDomainIntegrationResult,
    register_reflection_domain,
)
from cmm.domains.reflection.memory import (
    build_reflection_memory_binding,
    build_reflection_memory_proposal,
    build_reflection_memory_view,
    build_reflection_memory_view_request,
    validate_reflection_memory_binding,
)
from cmm.domains.reflection.operations import (
    build_personal_timeline_result,
    build_reflection_operation_definitions,
    compare_versions_result,
    extract_beliefs_result,
    generate_hypotheses_result,
    generate_summary_result,
    identify_open_questions_result,
    prepare_notion_entry_result,
    review_decision_result,
    structure_reflection_result,
)
from cmm.domains.reflection.permissions import (
    REFLECTION_PERMISSION_POLICY_ID,
    build_reflection_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.reflection.presentation import (
    build_reflection_presentation_policy,
    present_reflection_result,
    present_state,
)
from cmm.domains.reflection.profile import (
    REFLECTION_PROFILE_ID,
    REFLECTION_PROFILE_NAME,
    REFLECTION_PROHIBITED_ACTIONS,
    build_reflection_profile,
)
from cmm.domains.reflection.resources import (
    REFLECTION_RESOURCE_KINDS,
    build_reflection_resource_definitions,
)
from cmm.domains.reflection.rules import (
    BeliefEvidenceRule,
    MultipleHypothesesRule,
    NoForcedConclusionRule,
    OpenQuestionRule,
    PreserveAmbivalenceRule,
    ReflectionTemporalEvolutionRule,
    authorizes_confirmation,
    build_reflection_rules,
    classify_belief_evidence,
    classify_persistence,
    classify_statement_level,
    compare_reflection_versions,
    evaluate_ambivalence,
    evaluate_hypotheses,
    evaluate_open_questions,
    evaluate_persistence_basis,
    map_interests,
    no_forced_conclusion_policy,
)
from cmm.domains.reflection.trace import (
    assemble_reflection_trace,
    build_reflection_trace_contribution,
    build_reflection_trace_reference,
    validate_reflection_trace,
)
from cmm.domains.reflection.workflows import (
    REFLECTION_WORKFLOW_IDS,
    build_reflection_workflow_definitions,
)

__all__ = [
    "CANONICAL_REFLECTION_ENTITY_TYPES",
    "CANONICAL_REFLECTION_OPERATION_IDS",
    "CANONICAL_REFLECTION_RESOURCE_IDS",
    "CANONICAL_REFLECTION_RULE_IDS",
    "CANONICAL_REFLECTION_RULE_NAMES",
    "CANONICAL_REFLECTION_WORKFLOW_IDS",
    "CANONICAL_REFLECTION_WORKFLOW_NAMES",
    "REFLECTION_BOOTSTRAP_NAME",
    "REFLECTION_DOMAIN_ID",
    "REFLECTION_DOMAIN_VERSION",
    "REFLECTION_MANIFEST_ID",
    "REFLECTION_OPERATION_IDS",
    "REFLECTION_PERMISSION_IDS",
    "REFLECTION_PERMISSION_POLICY_ID",
    "REFLECTION_PROFILE_ID",
    "REFLECTION_PROFILE_NAME",
    "REFLECTION_PROHIBITED_ACTIONS",
    "REFLECTION_RESOURCE_IDS",
    "REFLECTION_RESOURCE_KINDS",
    "REFLECTION_RULE_IDS",
    "REFLECTION_WORKFLOW_IDS",
    "REFLECTION_WORKFLOW_NAMES_BY_ID",
    "BeliefEvidenceRule",
    "MultipleHypothesesRule",
    "NoForcedConclusionRule",
    "OpenQuestionRule",
    "PreserveAmbivalenceRule",
    "ReflectionDomainBootstrap",
    "ReflectionDomainIntegrationResult",
    "ReflectionTemporalEvolutionRule",
    "assemble_reflection_trace",
    "authorizes_confirmation",
    "build_personal_timeline_result",
    "build_reflection_domain_definition",
    "build_reflection_memory_binding",
    "build_reflection_memory_proposal",
    "build_reflection_memory_view",
    "build_reflection_memory_view_request",
    "build_reflection_operation_definitions",
    "build_reflection_permission_policy",
    "build_reflection_presentation_policy",
    "build_reflection_profile",
    "build_reflection_resource_definitions",
    "build_reflection_rules",
    "build_reflection_trace_contribution",
    "build_reflection_trace_reference",
    "build_reflection_workflow_definitions",
    "build_standard_reflection_domain_bootstrap",
    "classify_belief_evidence",
    "classify_persistence",
    "classify_statement_level",
    "compare_reflection_versions",
    "compare_versions_result",
    "evaluate_ambivalence",
    "evaluate_hypotheses",
    "evaluate_open_questions",
    "evaluate_persistence_basis",
    "extract_beliefs_result",
    "generate_hypotheses_result",
    "generate_summary_result",
    "identify_open_questions_result",
    "map_interests",
    "no_forced_conclusion_policy",
    "permission_authorization_allows",
    "prepare_notion_entry_result",
    "present_reflection_result",
    "present_state",
    "register_reflection_domain",
    "review_decision_result",
    "structure_reflection_result",
    "validate_reflection_memory_binding",
    "validate_reflection_trace",
]