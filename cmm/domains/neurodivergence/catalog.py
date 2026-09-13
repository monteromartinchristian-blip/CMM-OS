"""Phase 10.53 — Canonical Neurodivergence Domain Catalog.

Single source of truth for the structural IDs of the Neurodivergence Domain.

All other modules (definition, resources, profile, rules, operations,
workflows, bootstrap, integration) must import from this module rather than
re-declaring the same tuples.  This prevents catalog divergence.

Canonical identity (frozen design §3):

    domain:neurodivergence / namespace ``neurodivergence.*`` / version ``1.0.0``

Counts are frozen acceptance criteria (plan "Frozen inventories"): 14 rules,
10 resource families, 8 operations, 8 workflows.
"""

from __future__ import annotations

# ── Canonical neurodivergence entity semantics ────────────────────────────────
# Semantic vocabulary surfaced through shared Entity / KnowledgeItem bindings
# and the ``entity_types`` field of Neurodivergence resource definitions.  They
# are not new persistent classes and never become a second epistemic taxonomy:
# the canonical Cognitive Layer kinds remain authoritative (frozen design §7).

CANONICAL_NEURODIVERGENCE_ENTITY_TYPES: tuple[str, ...] = (
    "developmental_milestone",
    "developmental_observation",
    "assessment_record",
    "psychometric_result",
    "screening_result",
    "observation",
    "self_report",
    "third_party_report",
    "functional_observation",
    "executive_function_context",
    "sensory_context",
    "social_context",
    "academic_function_context",
    "working_hypothesis",
    "differential_hypothesis",
    "overlap_hypothesis",
    "uncertainty",
    "contradiction",
    "assessment_question",
)

# ── Canonical resource IDs ───────────────────────────────────────────────────
# ``domain:neurodivergence`` yields slug ``neurodivergence``; the shared
# resource and operation contracts require the domain prefix on the canonical
# IDs.  Source-domain projections are authorized read-only boundaries: they are
# never rewritten by Neurodivergence.

CANONICAL_NEURODIVERGENCE_RESOURCE_IDS: tuple[str, ...] = (
    "neurodivergence.developmental_history",
    "neurodivergence.assessment_records",
    "neurodivergence.psychometric_results",
    "neurodivergence.executive_function_context",
    "neurodivergence.sensory_context",
    "neurodivergence.academic_function_context",
    "neurodivergence.social_function_context",
    "neurodivergence.functional_impact",
    "neurodivergence.longitudinal_evidence",
    "neurodivergence.differential_overlap_context",
)

NEURODIVERGENCE_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1]
    for resource_id in CANONICAL_NEURODIVERGENCE_RESOURCE_IDS
)

# ── Canonical rule IDs ───────────────────────────────────────────────────────
# Exactly the fourteen required semantic responsibilities (spec §11).

CANONICAL_NEURODIVERGENCE_RULE_IDS: tuple[str, ...] = (
    "neurodivergence.certainty_state_preservation",
    "neurodivergence.clinical_status_authority",
    "neurodivergence.source_authority",
    "neurodivergence.developmental_temporality",
    "neurodivergence.observation_report_separation",
    "neurodivergence.screening_diagnosis_separation",
    "neurodivergence.trait_function_separation",
    "neurodivergence.longitudinal_corroboration",
    "neurodivergence.contradiction_preservation",
    "neurodivergence.differential_explanations",
    "neurodivergence.overlap_reasoning",
    "neurodivergence.purpose_minimized_cross_domain",
    "neurodivergence.global_attribution_guard",
    "neurodivergence.sensitive_label_persistence",
)

# ── Canonical operation IDs ──────────────────────────────────────────────────

CANONICAL_NEURODIVERGENCE_OPERATION_IDS: tuple[str, ...] = (
    "neurodivergence.analyze_differential_overlap",
    "neurodivergence.build_developmental_timeline",
    "neurodivergence.compare_assessment_sources",
    "neurodivergence.map_certainty_states",
    "neurodivergence.prepare_assessment_summary",
    "neurodivergence.propose_memory_update",
    "neurodivergence.review_evidence",
    "neurodivergence.review_functional_impact",
)

# ── Canonical workflow IDs ───────────────────────────────────────────────────
# Stable IDs under the ``neurodivergence.`` namespace; display titles are never
# used as identifiers (plan "Frozen inventories").

CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS: tuple[str, ...] = (
    "neurodivergence.developmental_history_review",
    "neurodivergence.evidence_consolidation_review",
    "neurodivergence.diagnostic_status_review",
    "neurodivergence.neuropsychological_assessment_preparation",
    "neurodivergence.assessment_result_integration",
    "neurodivergence.differential_overlap_review",
    "neurodivergence.functional_impact_review",
    "neurodivergence.sensitive_memory_proposal_review",
)

# Canonical workflow display names keyed by workflow ID.
NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
    "neurodivergence.developmental_history_review": (
        "Neurodivergence — Developmental History Review"
    ),
    "neurodivergence.evidence_consolidation_review": (
        "Neurodivergence — Evidence Consolidation Review"
    ),
    "neurodivergence.diagnostic_status_review": (
        "Neurodivergence — Diagnostic-Status Review"
    ),
    "neurodivergence.neuropsychological_assessment_preparation": (
        "Neurodivergence — Neuropsychological Assessment Preparation"
    ),
    "neurodivergence.assessment_result_integration": (
        "Neurodivergence — Assessment Result Integration"
    ),
    "neurodivergence.differential_overlap_review": (
        "Neurodivergence — Differential and Overlap Review"
    ),
    "neurodivergence.functional_impact_review": (
        "Neurodivergence — Functional Impact Review"
    ),
    "neurodivergence.sensitive_memory_proposal_review": (
        "Neurodivergence — Sensitive Memory Proposal Review"
    ),
}

CANONICAL_NEURODIVERGENCE_WORKFLOW_NAMES: tuple[str, ...] = tuple(
    NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[workflow_id]
    for workflow_id in CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS
)

NEURODIVERGENCE_DOMAIN_ID = "domain:neurodivergence"
NEURODIVERGENCE_PROFILE_NAME = "NeurodivergenceProfile"

# Convenience aliases (single source of truth stays the CANONICAL_* tuples).
NEURODIVERGENCE_RESOURCE_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_RESOURCE_IDS
NEURODIVERGENCE_RULE_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_RULE_IDS
NEURODIVERGENCE_OPERATION_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_OPERATION_IDS
NEURODIVERGENCE_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS

__all__ = [
    "CANONICAL_NEURODIVERGENCE_ENTITY_TYPES",
    "CANONICAL_NEURODIVERGENCE_OPERATION_IDS",
    "CANONICAL_NEURODIVERGENCE_RESOURCE_IDS",
    "CANONICAL_NEURODIVERGENCE_RULE_IDS",
    "CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS",
    "CANONICAL_NEURODIVERGENCE_WORKFLOW_NAMES",
    "NEURODIVERGENCE_DOMAIN_ID",
    "NEURODIVERGENCE_OPERATION_IDS",
    "NEURODIVERGENCE_PROFILE_NAME",
    "NEURODIVERGENCE_RESOURCE_IDS",
    "NEURODIVERGENCE_RESOURCE_KINDS",
    "NEURODIVERGENCE_RULE_IDS",
    "NEURODIVERGENCE_WORKFLOW_IDS",
    "NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID",
]
