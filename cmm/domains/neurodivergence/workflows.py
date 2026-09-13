"""Phase 10.53 — Neurodivergence Domain Workflows.

Eight declarative Neurodivergence workflows.  Every workflow loads its context,
applies ``NeurodivergenceProfile``, reasons under the fourteen Neurodivergence
rules, executes evidence-organization/preparation operations, and never acts
autonomously: no diagnosis is produced, no clinical status is created, no
medication or treatment is touched, and no sensitive memory is written.

These workflows use the existing shared Workflow Engine contract only.  No
Neurodivergence workflow engine exists.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE``
node.  The sensitive-memory workflow stops at a ``PROPOSE_MEMORY`` node behind
a real ``REQUEST_APPROVAL`` gate, so a proposal can never become a mutation
without the canonical approval path.
"""

from __future__ import annotations

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.domains.neurodivergence.catalog import (
    CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS,
    NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

NEURODIVERGENCE_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_NEURODIVERGENCE_WORKFLOW_IDS

DOMAIN_ID = "domain:neurodivergence"

#: The canonical approval gate for sensitive-memory proposals.
SENSITIVE_MEMORY_APPROVAL_GATE = "neurodivergence.sensitive_memory_persistence"


def _node(
    node_id: str,
    node_type: WorkflowNodeType,
    name: str,
    *,
    dependencies: tuple[str, ...] = (),
    operation_id: str | None = None,
    approval_gate: str | None = None,
    wait_condition: dict | None = None,
    metadata: dict | None = None,
) -> WorkflowNode:
    return WorkflowNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        dependencies=dependencies,
        operation_id=operation_id,
        operation_version="1.0.0" if operation_id else None,
        approval_gate=approval_gate,
        wait_condition=wait_condition,
        metadata=metadata or {},
    )


def _ordered_prefix() -> tuple[WorkflowNode, ...]:
    """Strict safety prefix: load -> profile -> reason (enforced as deps)."""
    return (
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadNeurodivergenceSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyNeurodivergenceProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyNeurodivergenceRules",
            dependencies=("profile",),
        ),
    )


def _validate_only_tail(*, depends_on: str) -> tuple[WorkflowNode, ...]:
    return (
        _node(
            "validate",
            WorkflowNodeType.VALIDATE,
            "Validate",
            dependencies=(depends_on,),
        ),
        _node(
            "complete",
            WorkflowNodeType.COMPLETE,
            "Complete",
            dependencies=("validate",),
        ),
    )


def _developmental_history_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.developmental_history_review",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.developmental_history_review"
        ],
        description=(
            "Build a referenced developmental timeline that keeps historical and "
            "current evidence distinct and never invents a developmental history."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildDevelopmentalTimeline",
                dependencies=("reason",),
                operation_id="neurodivergence.build_developmental_timeline",
            ),
            *_validate_only_tail(depends_on="timeline"),
        ),
        required_resources=(
            "neurodivergence.developmental_history",
            "neurodivergence.longitudinal_evidence",
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Developmental history organization (references only)",
        sensitivity=SensitivityLevel.RESTRICTED,
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "chronology_required": True,
            "retrospective_reports_distinguished_from_observation": True,
        },
    )


def _evidence_consolidation_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.evidence_consolidation_review",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.evidence_consolidation_review"
        ],
        description=(
            "Consolidate referenced evidence by source and period, then map its "
            "certainty states without promoting any of them."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewEvidence",
                dependencies=("reason",),
                operation_id="neurodivergence.review_evidence",
            ),
            _node(
                "map_certainty",
                WorkflowNodeType.EXECUTE_OPERATION,
                "MapCertaintyStates",
                dependencies=("review",),
                operation_id="neurodivergence.map_certainty_states",
            ),
            *_validate_only_tail(depends_on="map_certainty"),
        ),
        required_resources=(
            "neurodivergence.assessment_records",
            "neurodivergence.developmental_history",
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Evidence consolidation with certainty mapping",
        sensitivity=SensitivityLevel.RESTRICTED,
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "certainty_promotion_performed": False,
        },
    )


def _diagnostic_status_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.diagnostic_status_review",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.diagnostic_status_review"
        ],
        description=(
            "Review the current certainty status of documented information and "
            "apply Health clinical authority; Neurodivergence never creates or "
            "removes a clinical status."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "map_certainty",
                WorkflowNodeType.EXECUTE_OPERATION,
                "MapCertaintyStates",
                dependencies=("reason",),
                operation_id="neurodivergence.map_certainty_states",
            ),
            _node(
                "health_authority",
                WorkflowNodeType.REASON,
                "ApplyHealthClinicalAuthority",
                dependencies=("map_certainty",),
                metadata={"health_authority_applied": True},
            ),
            *_validate_only_tail(depends_on="health_authority"),
        ),
        required_resources=("neurodivergence.assessment_records",),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Diagnostic-status review under Health authority",
        sensitivity=SensitivityLevel.RESTRICTED,
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "health_authority_applied": True,
            "clinical_status_created": False,
            "diagnosis_created": False,
        },
    )


def _neuropsychological_assessment_preparation() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.neuropsychological_assessment_preparation",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.neuropsychological_assessment_preparation"
        ],
        description=(
            "Prepare a structured evidence summary and useful questions for a "
            "professional assessment; preparation is never a diagnosis and the "
            "summary is approval-gated."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewEvidence",
                dependencies=("reason",),
                operation_id="neurodivergence.review_evidence",
            ),
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareAssessmentSources",
                dependencies=("review",),
                operation_id="neurodivergence.compare_assessment_sources",
            ),
            _node(
                "summary",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareAssessmentSummary",
                dependencies=("compare",),
                operation_id="neurodivergence.prepare_assessment_summary",
            ),
            *_validate_only_tail(depends_on="summary"),
        ),
        required_resources=(
            "neurodivergence.assessment_records",
            "neurodivergence.psychometric_results",
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Neuropsychological assessment preparation",
        sensitivity=SensitivityLevel.RESTRICTED,
        approval_gates=("neurodivergence.assessment_summary_preparation",),
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "preparation_only": True,
            "clinical_status_created": False,
        },
    )


def _assessment_result_integration() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.assessment_result_integration",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.assessment_result_integration"
        ],
        description=(
            "Integrate user-provided assessment results: compare sources, keep "
            "each source's owner, and map the resulting certainty states."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareAssessmentSources",
                dependencies=("reason",),
                operation_id="neurodivergence.compare_assessment_sources",
            ),
            _node(
                "map_certainty",
                WorkflowNodeType.EXECUTE_OPERATION,
                "MapCertaintyStates",
                dependencies=("compare",),
                operation_id="neurodivergence.map_certainty_states",
            ),
            *_validate_only_tail(depends_on="map_certainty"),
        ),
        required_resources=(
            "neurodivergence.assessment_records",
            "neurodivergence.psychometric_results",
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Assessment result integration (source authority preserved)",
        sensitivity=SensitivityLevel.RESTRICTED,
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "source_authority_preserved": True,
            "screening_promoted_to_diagnosis": False,
        },
    )


def _differential_overlap_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.differential_overlap_review",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.differential_overlap_review"
        ],
        description=(
            "Explore why a hypothesis may fit, why it may not, what overlaps and "
            "what evidence would clarify the picture — balanced, never adversarial."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewEvidence",
                dependencies=("reason",),
                operation_id="neurodivergence.review_evidence",
            ),
            _node(
                "differential",
                WorkflowNodeType.EXECUTE_OPERATION,
                "AnalyzeDifferentialOverlap",
                dependencies=("review",),
                operation_id="neurodivergence.analyze_differential_overlap",
            ),
            _node(
                "questions",
                WorkflowNodeType.DETECT_GAPS,
                "IdentifyClarifyingEvidence",
                dependencies=("differential",),
            ),
            *_validate_only_tail(depends_on="questions"),
        ),
        required_resources=("neurodivergence.differential_overlap_context",),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Differential and overlap review (exploratory)",
        sensitivity=SensitivityLevel.RESTRICTED,
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "differential_reasoning": "balanced_not_adversarial",
            "negative_evidence_required": False,
            "co_diagnosis_created": False,
        },
    )


def _functional_impact_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.functional_impact_review",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.functional_impact_review"
        ],
        description=(
            "Review everyday functional context across executive, sensory and "
            "academic domains without turning a trait into an impairment."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "impact",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewFunctionalImpact",
                dependencies=("reason",),
                operation_id="neurodivergence.review_functional_impact",
            ),
            *_validate_only_tail(depends_on="impact"),
        ),
        required_resources=(
            "neurodivergence.functional_impact",
            "neurodivergence.executive_function_context",
            "neurodivergence.sensory_context",
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Functional impact review",
        sensitivity=SensitivityLevel.RESTRICTED,
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "trait_treated_as_impairment": False,
        },
    )


def _sensitive_memory_proposal_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="neurodivergence.sensitive_memory_proposal_review",
        domain_id=DOMAIN_ID,
        version="1.0.0",
        name=NEURODIVERGENCE_WORKFLOW_NAMES_BY_ID[
            "neurodivergence.sensitive_memory_proposal_review"
        ],
        description=(
            "Propose a sensitive memory update behind a canonical approval gate; "
            "the proposal preserves hypothesis status and never implies mutation."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateProposal",
                dependencies=("reason",),
            ),
            _node(
                "approval",
                WorkflowNodeType.REQUEST_APPROVAL,
                "RequestPersistenceApproval",
                dependencies=("validate",),
                approval_gate=SENSITIVE_MEMORY_APPROVAL_GATE,
            ),
            _node(
                "propose",
                WorkflowNodeType.PROPOSE_MEMORY,
                "ProposeMemoryUpdate",
                dependencies=("approval",),
                operation_id="neurodivergence.propose_memory_update",
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("propose",),
            ),
        ),
        required_resources=("neurodivergence.longitudinal_evidence",),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Sensitive memory proposal review (proposal only)",
        sensitivity=SensitivityLevel.RESTRICTED,
        approval_gates=(SENSITIVE_MEMORY_APPROVAL_GATE,),
        metadata={
            "phase": "10.53",
            "cross_domain_support_required": False,
            "proposal_only": True,
            "direct_mutation": False,
            "certainty_state_preserved": True,
        },
    )


def build_neurodivergence_workflow_definitions() -> tuple[
    DomainWorkflowDefinition, ...
]:
    """Build the eight Neurodivergence workflows deterministically in catalog order."""
    by_id = {
        "neurodivergence.developmental_history_review": (
            _developmental_history_review()
        ),
        "neurodivergence.evidence_consolidation_review": (
            _evidence_consolidation_review()
        ),
        "neurodivergence.diagnostic_status_review": _diagnostic_status_review(),
        "neurodivergence.neuropsychological_assessment_preparation": (
            _neuropsychological_assessment_preparation()
        ),
        "neurodivergence.assessment_result_integration": (
            _assessment_result_integration()
        ),
        "neurodivergence.differential_overlap_review": (_differential_overlap_review()),
        "neurodivergence.functional_impact_review": _functional_impact_review(),
        "neurodivergence.sensitive_memory_proposal_review": (
            _sensitive_memory_proposal_review()
        ),
    }
    return tuple(by_id[workflow_id] for workflow_id in NEURODIVERGENCE_WORKFLOW_IDS)
