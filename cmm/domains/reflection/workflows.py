"""Phase 10.24 — Reflection Domain Workflows.

Six declarative Reflection workflows.  Every workflow loads its context,
applies the conservative ReflectionProfile, reasons under the six Reflection
rules, executes reflection operations, retains open questions, and never acts
autonomously: no decision is adopted, no identity is classified, no memory is
written without confirmation, and no external write occurs.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE``
node.  Personal Question Exploration and Structured Reflection explicitly
allow successful **unresolved completion**: a workflow that finishes with open
questions and no conclusion is a success, not a failure (spec §21, §43).
"""

from __future__ import annotations

from cmm.domains.reflection.catalog import (
    CANONICAL_REFLECTION_WORKFLOW_IDS,
    REFLECTION_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

REFLECTION_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_REFLECTION_WORKFLOW_IDS


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
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadReflectionSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyReflectionProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyReflectionRules",
            dependencies=("profile",),
        ),
    )


def _questions_and_tail(*, dependencies: tuple[str, ...]) -> tuple[WorkflowNode, ...]:
    return (
        _node(
            "questions",
            WorkflowNodeType.EXECUTE_OPERATION,
            "IdentifyOpenQuestions",
            dependencies=dependencies,
            operation_id="reflection.identify_open_questions",
            metadata={"retains_open_questions": True},
        ),
        _node(
            "validate",
            WorkflowNodeType.VALIDATE,
            "ValidateUnresolvedCompletion",
            dependencies=("questions",),
            wait_condition={"unresolved_completion_allowed": True},
        ),
        _node(
            "complete",
            WorkflowNodeType.COMPLETE,
            "Complete",
            dependencies=("validate",),
            metadata={"final_conclusion_required": False},
        ),
    )


def _workflow(
    workflow_id: str,
    *,
    description: str,
    purpose: str,
    core_nodes: tuple[WorkflowNode, ...],
    metadata: dict,
) -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id=workflow_id,
        domain_id="domain:reflection",
        version="1.0.0",
        name=REFLECTION_WORKFLOW_NAMES_BY_ID[workflow_id],
        description=description,
        nodes=(*_ordered_prefix(), *core_nodes),
        completion_criteria={
            "all_required_nodes_completed": True,
            "no_blocking_failures": True,
        },
        purpose=purpose,
        metadata={"phase": "10.24", **metadata},
    )


def _structured_reflection() -> DomainWorkflowDefinition:
    return _workflow(
        "reflection.structured_reflection",
        description=(
            "Organize a complex reflection without forcing convergence: "
            "collect grounded material, separate observation from "
            "interpretation, extract beliefs/values/emotions/needs, identify "
            "tensions, generate prudent hypotheses when justified, retain "
            "open questions, and produce a structured result."
        ),
        purpose="Structured reflection (no forced conclusion)",
        core_nodes=(
            _node(
                "structure",
                WorkflowNodeType.EXECUTE_OPERATION,
                "StructureReflection",
                dependencies=("reason",),
                operation_id="reflection.structure_reflection",
            ),
            *_questions_and_tail(dependencies=("structure",)),
        ),
        metadata={
            "unresolved_completion_allowed": True,
            "preserves_ambivalence": True,
            "preserves_open_questions": True,
            "no_final_conclusion": True,
        },
    )


def _belief_review() -> DomainWorkflowDefinition:
    return _workflow(
        "reflection.belief_review",
        description=(
            "Review a belief against evidence, counterevidence, experience "
            "and interpretation.  Absence of counterevidence is never proof."
        ),
        purpose="Belief review against the five epistemic dimensions",
        core_nodes=(
            _node(
                "beliefs",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ExtractBeliefs",
                dependencies=("reason",),
                operation_id="reflection.extract_beliefs",
            ),
            _node(
                "no_proof",
                WorkflowNodeType.VALIDATE,
                "AbsenceOfCounterevidenceIsNotProof",
                dependencies=("beliefs",),
                wait_condition={"absence_of_counterevidence_not_proof": True},
            ),
            *_questions_and_tail(dependencies=("no_proof",)),
        ),
        metadata={
            "unresolved_completion_allowed": True,
            "absence_of_counterevidence_not_proof": True,
            "no_final_conclusion": True,
        },
    )


def _personal_question_exploration() -> DomainWorkflowDefinition:
    return _workflow(
        "reflection.personal_question_exploration",
        description=(
            "Explore an unresolved personal question using multiple prudent "
            "hypotheses.  Successful completion may have no answer: open "
            "questions are retained as a valid outcome."
        ),
        purpose="Personal question exploration (success may be unanswered)",
        core_nodes=(
            _node(
                "hypotheses",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateHypotheses",
                dependencies=("reason",),
                operation_id="reflection.generate_hypotheses",
            ),
            *_questions_and_tail(dependencies=("hypotheses",)),
        ),
        metadata={
            "unresolved_completion_allowed": True,
            "no_final_conclusion": True,
            "no_invented_answer": True,
        },
    )


def _decision_reflection() -> DomainWorkflowDefinition:
    return _workflow(
        "reflection.decision_reflection",
        description=(
            "Review a decision candidate, values, tensions, alternatives and "
            "uncertainty.  Never adopts the decision: analysis is proposal-only."
        ),
        purpose="Decision reflection (analysis only, no adoption)",
        core_nodes=(
            _node(
                "decision",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewDecision",
                dependencies=("reason",),
                operation_id="reflection.review_decision",
            ),
            _node(
                "no_adoption",
                WorkflowNodeType.VALIDATE,
                "NoDecisionAdoption",
                dependencies=("decision",),
                wait_condition={"decision_adopted": False},
            ),
            *_questions_and_tail(dependencies=("no_adoption",)),
        ),
        metadata={
            "unresolved_completion_allowed": True,
            "decision_never_adopted": True,
            "proposal_only": True,
            "no_final_conclusion": True,
        },
    )


def _identity_narrative_review() -> DomainWorkflowDefinition:
    return _workflow(
        "reflection.identity_narrative_review",
        description=(
            "Compare and structure user-provided identity narratives.  "
            "Restricted identity inference applies: no identity diagnosis or "
            "classification is ever produced."
        ),
        purpose="Identity narrative review (structure only, no classification)",
        core_nodes=(
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareVersions",
                dependencies=("reason",),
                operation_id="reflection.compare_versions",
            ),
            _node(
                "no_classification",
                WorkflowNodeType.VALIDATE,
                "NoIdentityClassification",
                dependencies=("compare",),
                wait_condition={"identity_not_classified": True},
            ),
            *_questions_and_tail(dependencies=("no_classification",)),
        ),
        metadata={
            "unresolved_completion_allowed": True,
            "identity_not_classified": True,
            "restricted_inference": True,
            "no_final_conclusion": True,
        },
    )


def _longitudinal_review() -> DomainWorkflowDefinition:
    return _workflow(
        "reflection.longitudinal_review",
        description=(
            "Compare reflection versions over time with grounded chronology "
            "only: no input-order timeline, no persistence claim from "
            "repetition alone."
        ),
        purpose="Longitudinal review (grounded chronology only)",
        core_nodes=(
            _node(
                "timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildPersonalTimeline",
                dependencies=("reason",),
                operation_id="reflection.build_personal_timeline",
            ),
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareVersions",
                dependencies=("timeline",),
                operation_id="reflection.compare_versions",
            ),
            _node(
                "grounded_chronology",
                WorkflowNodeType.VALIDATE,
                "GroundedChronologyOnly",
                dependencies=("compare",),
                wait_condition={"grounded_chronology_required": True},
            ),
            *_questions_and_tail(dependencies=("grounded_chronology",)),
        ),
        metadata={
            "unresolved_completion_allowed": True,
            "grounded_chronology_required": True,
            "no_input_order_timeline": True,
            "no_repetition_persistence": True,
            "no_final_conclusion": True,
        },
    )


def build_reflection_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the six Reflection Domain workflow definitions deterministically."""
    by_id = {
        "reflection.structured_reflection": _structured_reflection(),
        "reflection.belief_review": _belief_review(),
        "reflection.personal_question_exploration": _personal_question_exploration(),
        "reflection.decision_reflection": _decision_reflection(),
        "reflection.identity_narrative_review": _identity_narrative_review(),
        "reflection.longitudinal_review": _longitudinal_review(),
    }
    return tuple(by_id[workflow_id] for workflow_id in REFLECTION_WORKFLOW_IDS)


__all__ = ["REFLECTION_WORKFLOW_IDS", "build_reflection_workflow_definitions"]
