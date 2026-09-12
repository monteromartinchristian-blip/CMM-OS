"""Phase 10.52 — Mental Health Domain Workflows.

Eight declarative Mental Health workflows.  Every workflow loads its context,
applies ``MentalHealthProfile``, reasons under the thirteen Mental Health
rules, executes analysis/preparation operations, and never acts autonomously:
no clinical presentation is forced, no diagnosis is produced, no treatment is
changed, and no sensitive memory is written.

These workflows use the existing shared Workflow Engine contract only.  No
Mental Health workflow engine exists.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE``
node.  The sensitive-memory workflow stops at a ``PROPOSE_MEMORY`` node behind
a real ``REQUEST_APPROVAL`` gate, so a proposal can never become a mutation
without the canonical approval path.  The safety-escalation workflow is a
*coordination* flow: it requests the existing canonical escalation/approval
mechanism and never becomes a crisis decision engine.
"""

from __future__ import annotations

from cmm.domains.mental_health.catalog import (
    CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS,
    MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

MENTAL_HEALTH_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS


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
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadEmotionalSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyMentalHealthProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyMentalHealthRules",
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


def _emotional_context_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.emotional_context_review",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.emotional_context_review"
        ],
        description=(
            "Review ordinary emotional context without clinical presentation."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewEmotionalContext",
                dependencies=("reason",),
                operation_id="mental_health.review_emotional_context",
            ),
            _node(
                "detect_gaps",
                WorkflowNodeType.DETECT_GAPS,
                "DetectMaterialGaps",
                dependencies=("review",),
            ),
            *_validate_only_tail(depends_on="detect_gaps"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Ordinary emotional context review (non-clinical)",
        metadata={"phase": "10.52", "clinical_presentation_default": False},
    )


def _therapy_session_preparation() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.therapy_session_preparation",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.therapy_session_preparation"
        ],
        description=(
            "Prepare themes, questions and unresolved items for a future "
            "therapy session; never fabricates therapist guidance."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "prepare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareTherapySession",
                dependencies=("reason",),
                operation_id="mental_health.prepare_therapy_session",
            ),
            _node(
                "questions",
                WorkflowNodeType.DETECT_GAPS,
                "IdentifyMaterialQuestions",
                dependencies=("prepare",),
            ),
            *_validate_only_tail(depends_on="questions"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Therapy session preparation (preparation only)",
        metadata={"phase": "10.52", "fabricates_therapist_guidance": False},
    )


def _therapy_session_post_processing() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.therapy_session_post_processing",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.therapy_session_post_processing"
        ],
        description="Review user-provided session notes preserving attribution.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewTherapySession",
                dependencies=("reason",),
                operation_id="mental_health.review_therapy_session",
            ),
            *_validate_only_tail(depends_on="review"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Therapy session post-processing",
        metadata={"phase": "10.52", "speaker_attribution_required": True},
    )


def _therapy_transcript_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.therapy_transcript_review",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.therapy_transcript_review"
        ],
        description=(
            "Analyze an authorized transcript preserving speaker identity, "
            "source identity, verbatim-vs-summary and uncertainty."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "analyze",
                WorkflowNodeType.EXECUTE_OPERATION,
                "AnalyzeTherapyTranscript",
                dependencies=("reason",),
                operation_id="mental_health.analyze_therapy_transcript",
            ),
            _node(
                "map",
                WorkflowNodeType.EXECUTE_OPERATION,
                "MapFactInterpretationUncertainty",
                dependencies=("analyze",),
                operation_id="mental_health.map_fact_interpretation_uncertainty",
            ),
            *_validate_only_tail(depends_on="map"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Therapy transcript review (provenance-preserving)",
        metadata={
            "phase": "10.52",
            "speaker_provenance_required": True,
            "source_identity_required": True,
        },
    )


def _longitudinal_emotional_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.longitudinal_emotional_review",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.longitudinal_emotional_review"
        ],
        description=(
            "Compare authorized longitudinal emotional periods using canonical "
            "memory/temporal references; no independent timeline store."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareEmotionalPeriods",
                dependencies=("reason",),
                operation_id="mental_health.compare_emotional_periods",
            ),
            *_validate_only_tail(depends_on="compare"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Longitudinal emotional review (authorized references only)",
        metadata={"phase": "10.52", "independent_timeline_store": False},
    )


def _emotionally_relevant_decision_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.emotionally_relevant_decision_review",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.emotionally_relevant_decision_review"
        ],
        description=(
            "Support a decision with emotional content while preserving "
            "preference, uncertainty and trade-offs."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewEmotionalDecision",
                dependencies=("reason",),
                operation_id="mental_health.review_emotional_decision",
            ),
            *_validate_only_tail(depends_on="review"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Emotionally relevant decision review",
        metadata={"phase": "10.52", "adopts_decision": False},
    )


def _sensitive_memory_proposal_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.sensitive_memory_proposal_review",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.sensitive_memory_proposal_review"
        ],
        description=(
            "Propose a sensitive memory update behind a canonical approval gate; "
            "proposal never implies mutation."
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
                approval_gate="mental_health.sensitive_memory_persistence",
            ),
            _node(
                "propose",
                WorkflowNodeType.PROPOSE_MEMORY,
                "ProposeMemoryUpdate",
                dependencies=("approval",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("propose",),
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Sensitive memory proposal review (proposal only)",
        metadata={
            "phase": "10.52",
            "proposal_only": True,
            "direct_mutation": False,
        },
    )


def _safety_escalation_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="mental_health.safety_escalation_review",
        domain_id="domain:mental-health",
        version="1.0.0",
        name=MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[
            "mental_health.safety_escalation_review"
        ],
        description=(
            "Coordinate a proportionate safety review through the existing "
            "canonical escalation/policy mechanism; never a crisis engine."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "detect",
                WorkflowNodeType.DETECT_GAPS,
                "AssessMaterialRisk",
                dependencies=("reason",),
            ),
            _node(
                "escalate",
                WorkflowNodeType.ESCALATE,
                "RouteExistingEscalation",
                dependencies=("detect",),
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "ValidateProportionality",
                dependencies=("escalate",),
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("validate",),
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Safety escalation coordination (existing mechanism only)",
        metadata={
            "phase": "10.52",
            "own_crisis_engine": False,
            "emotion_triggered_escalation": False,
        },
    )


def build_mental_health_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the eight Mental Health workflows deterministically in catalog order."""
    by_id = {
        "mental_health.emotional_context_review": _emotional_context_review(),
        "mental_health.emotionally_relevant_decision_review": (
            _emotionally_relevant_decision_review()
        ),
        "mental_health.longitudinal_emotional_review": (
            _longitudinal_emotional_review()
        ),
        "mental_health.safety_escalation_review": _safety_escalation_review(),
        "mental_health.sensitive_memory_proposal_review": (
            _sensitive_memory_proposal_review()
        ),
        "mental_health.therapy_session_post_processing": (
            _therapy_session_post_processing()
        ),
        "mental_health.therapy_session_preparation": _therapy_session_preparation(),
        "mental_health.therapy_transcript_review": _therapy_transcript_review(),
    }
    return tuple(by_id[workflow_id] for workflow_id in MENTAL_HEALTH_WORKFLOW_IDS)
