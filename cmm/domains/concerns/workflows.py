"""Phase 10.25 — Concerns Domain Workflows.

Eight declarative Concerns workflows.  Every workflow loads its context,
applies the conservative ConcernSupportProfile, reasons under the fourteen
Concerns rules, executes analysis/preparation operations, and never acts
autonomously: no action plan is forced, no decision adopted, no risk matrix or
monitoring plan required, no final conclusion demanded, and no external action
performed.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE``
node.  Every workflow explicitly allows successful **unresolved completion**:
finishing still-uncertain, reassured-but-not-certain, or without action is a
success — not a failure (frozen design §10, §47–§55).
"""

from __future__ import annotations

from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_WORKFLOW_IDS,
    CONCERNS_WORKFLOW_NAMES_BY_ID,
)
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

CONCERNS_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_CONCERNS_WORKFLOW_IDS


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
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadConcernSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyConcernSupportProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyConcernsRules",
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
            operation_id="concerns.identify_open_questions",
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
            metadata={
                "final_conclusion_required": False,
                "action_plan_required": False,
                "adopted_decision_required": False,
            },
        ),
    )


def _workflow(
    workflow_id: str,
    *,
    description: str,
    purpose: str,
    core_nodes: tuple[WorkflowNode, ...],
    extra_metadata: dict | None = None,
) -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id=workflow_id,
        domain_id="domain:concerns",
        version="1.0.0",
        name=CONCERNS_WORKFLOW_NAMES_BY_ID[workflow_id],
        description=description,
        nodes=(*_ordered_prefix(), *core_nodes),
        completion_criteria={
            "all_required_nodes_completed": True,
            "no_blocking_failures": True,
        },
        purpose=purpose,
        metadata={
            "phase": "10.25",
            "unresolved_completion_allowed": True,
            "unresolved_completion_valid": True,
            "no_final_conclusion": True,
            "no_action_plan": True,
            "no_monitoring_plan": True,
            # Fail-closed safety defaults: a runtime output that violates any
            # of these (e.g. decision_adopted=True) overrides the safe default
            # and blocks the gate; absence keeps the safe state.
            "decision_adopted": False,
            "external_action_executed": False,
            "external_transmission_performed": False,
            "appointment_booked": False,
            "contact_performed": False,
            "pathology_inferred": False,
            "false_reassurance": False,
            "catastrophic_escalation_present": False,
            "interpretation_promoted_to_fact": False,
            "ritual_questioning_allowed": False,
            "executed": False,
            **(extra_metadata or {}),
        },
    )


def _open_concern_conversation() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.open_concern_conversation",
        description=(
            "Default flexible concern workflow: understand the concern and its "
            "lived significance, resolve the support need, ask a material "
            "question only when needed, run only useful reasoning, propose a "
            "memory update through shared contracts when justified, and finish "
            "without forcing action, risk analysis or a conclusion."
        ),
        purpose="Handle a concern without assuming what type of support is needed.",
        core_nodes=(
            _node(
                "understand",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UnderstandConcern",
                dependencies=("reason",),
                operation_id="concerns.understand_concern",
            ),
            _node(
                "support_need",
                WorkflowNodeType.EXECUTE_OPERATION,
                "InferSupportNeed",
                dependencies=("understand",),
                operation_id="concerns.infer_support_need",
            ),
            _node(
                "lived_experience",
                WorkflowNodeType.EXECUTE_OPERATION,
                "MapLivedExperience",
                dependencies=("support_need",),
                operation_id="concerns.map_lived_experience",
            ),
            _node(
                "gaps",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyMaterialGaps",
                dependencies=("lived_experience",),
                operation_id="concerns.identify_open_questions",
                metadata={"retains_open_questions": True},
            ),
            _node(
                "material_question_gate",
                WorkflowNodeType.VALIDATE,
                "AskOnlyMaterialQuestions",
                dependencies=("gaps",),
                wait_condition={"ritual_questioning_allowed": False},
            ),
            *_questions_and_tail(dependencies=("material_question_gate",)),
        ),
        extra_metadata={
            "preserves_lived_experience": True,
            "support_need_revisable": True,
        },
    )


def _talk_it_through() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.talk_it_through",
        description=(
            "Support open-ended elaboration of a concern: understand, reflect "
            "lived experience, explore, preserve uncertainty, coordinate with "
            "Reflection if helpful, and validate an unresolved completion "
            "(better understood, not necessarily solved)."
        ),
        purpose="Support open-ended elaboration; success may remain unsolved.",
        core_nodes=(
            _node(
                "understand",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UnderstandConcern",
                dependencies=("reason",),
                operation_id="concerns.understand_concern",
            ),
            _node(
                "experience",
                WorkflowNodeType.EXECUTE_OPERATION,
                "MapLivedExperience",
                dependencies=("understand",),
                operation_id="concerns.map_lived_experience",
            ),
            _node(
                "explore",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ExploreHypotheses",
                dependencies=("experience",),
                operation_id="concerns.explore_hypotheses",
            ),
            _node(
                "unresolved_ok",
                WorkflowNodeType.VALIDATE,
                "UnresolvedCompletionIsValid",
                dependencies=("explore",),
                wait_condition={"unresolved_completion_valid": True},
            ),
            *_questions_and_tail(dependencies=("unresolved_ok",)),
        ),
        extra_metadata={
            "no_compulsory_solutions": True,
            "reflection_coordination_allowed": True,
        },
    )


def _reality_check() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.reality_check",
        description=(
            "Compare feared or interpreted meaning with available reality: "
            "separate observations from interpretations, calibrate "
            "uncertainty, and give a grounded assessment that may reassure or "
            "may acknowledge a real basis for concern."
        ),
        purpose="Compare interpretation with evidence; no forced verdict.",
        core_nodes=(
            _node(
                "understand",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UnderstandConcern",
                dependencies=("reason",),
                operation_id="concerns.understand_concern",
            ),
            _node(
                "separation",
                WorkflowNodeType.EXECUTE_OPERATION,
                "SeparateRealityInterpretation",
                dependencies=("understand",),
                operation_id="concerns.separate_reality_interpretation",
            ),
            _node(
                "uncertainty",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CalibrateUncertainty",
                dependencies=("separation",),
                operation_id="concerns.calibrate_uncertainty",
            ),
            _node(
                "epistemic_gate",
                WorkflowNodeType.VALIDATE,
                "LevelsStayDistinct",
                dependencies=("uncertainty",),
                wait_condition={"interpretation_promoted_to_fact": False},
            ),
            *_questions_and_tail(dependencies=("epistemic_gate",)),
        ),
        extra_metadata={"fact_interpretation_separated": True},
    )


def _reassurance_review() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.reassurance_review",
        description=(
            "Evaluate whether reassurance is justified and communicate the "
            "semantic basis: no false reassurance, no catastrophic escalation, "
            "and no presumption that reassurance itself is good or harmful."
        ),
        purpose="Evidence-calibrated reassurance with honesty gates.",
        core_nodes=(
            _node(
                "understand",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UnderstandConcern",
                dependencies=("reason",),
                operation_id="concerns.understand_concern",
            ),
            _node(
                "reassurance",
                WorkflowNodeType.EXECUTE_OPERATION,
                "EvaluateReassurance",
                dependencies=("understand",),
                operation_id="concerns.evaluate_reassurance",
            ),
            _node(
                "honesty_gate",
                WorkflowNodeType.VALIDATE,
                "NoFalseReassurance",
                dependencies=("reassurance",),
                wait_condition={"false_reassurance": False},
            ),
            _node(
                "proportionality_gate",
                WorkflowNodeType.VALIDATE,
                "NoCatastrophicEscalation",
                dependencies=("honesty_gate",),
                wait_condition={"catastrophic_escalation_present": False},
            ),
            *_questions_and_tail(dependencies=("proportionality_gate",)),
        ),
        extra_metadata={
            "reassurance_allowed_when_supported": True,
            "absolute_certainty_forbidden": True,
        },
    )


def _practical_problem_solving() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.practical_problem_solving",
        description=(
            "Help improve a situation when action is desired: understand the "
            "problem, identify the desired outcome, generate options, propose "
            "a proportionate next step through the agency gate.  No option is "
            "adopted and nothing external is executed."
        ),
        purpose="Practical options with agency preserved.",
        core_nodes=(
            _node(
                "understand",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UnderstandConcern",
                dependencies=("reason",),
                operation_id="concerns.understand_concern",
            ),
            _node(
                "options",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ExploreOptions",
                dependencies=("understand",),
                operation_id="concerns.explore_options",
            ),
            _node(
                "next_step",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareNextStep",
                dependencies=("options",),
                operation_id="concerns.prepare_next_step",
            ),
            _node(
                "agency_gate",
                WorkflowNodeType.VALIDATE,
                "NoAdoptionWithoutUserDecision",
                dependencies=("options", "next_step"),
                wait_condition={"decision_adopted": False},
            ),
            _node(
                "no_execution_gate",
                WorkflowNodeType.VALIDATE,
                "NothingExecuted",
                dependencies=("agency_gate",),
                wait_condition={"external_action_executed": False},
            ),
            *_questions_and_tail(dependencies=("no_execution_gate",)),
        ),
        extra_metadata={
            "options_are_candidates": True,
            "user_decision_required_for_adoption": True,
        },
    )


def _decision_under_uncertainty() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.decision_under_uncertainty",
        description=(
            "Help make sense of a decision when uncertainty and concern "
            "coexist: clarify the decision, separate known from unknown, "
            "structure options and trade-offs, preserve remaining uncertainty, "
            "and keep the personal decision with the user."
        ),
        purpose="Decision support; the user decides.",
        core_nodes=(
            _node(
                "understand",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UnderstandConcern",
                dependencies=("reason",),
                operation_id="concerns.understand_concern",
            ),
            _node(
                "uncertainty",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CalibrateUncertainty",
                dependencies=("understand",),
                operation_id="concerns.calibrate_uncertainty",
            ),
            _node(
                "options",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ExploreOptions",
                dependencies=("uncertainty",),
                operation_id="concerns.explore_options",
            ),
            _node(
                "decision_gate",
                WorkflowNodeType.VALIDATE,
                "UserKeepsTheDecision",
                dependencies=("options",),
                wait_condition={"decision_adopted": False},
            ),
            *_questions_and_tail(dependencies=("decision_gate",)),
        ),
        extra_metadata={
            "no_automatic_personal_decision": True,
            "tradeoffs_surfaced": True,
        },
    )


def _recurring_concern_review() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.recurring_concern_review",
        description=(
            "Revisit an ongoing concern without treating repetition as "
            "pathology: load authorized prior context, compare evidence and "
            "interpretations, update the reassurance assessment, and pass the "
            "non-pathologizing gate.  Reassurance remains allowed."
        ),
        purpose="Recurring-concern review; repetition is not pathology.",
        core_nodes=(
            _node(
                "recurrence",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewRecurringConcern",
                dependencies=("reason",),
                operation_id="concerns.review_recurring_concern",
            ),
            _node(
                "reassurance",
                WorkflowNodeType.EXECUTE_OPERATION,
                "EvaluateReassurance",
                dependencies=("recurrence",),
                operation_id="concerns.evaluate_reassurance",
            ),
            _node(
                "non_pathology_gate",
                WorkflowNodeType.VALIDATE,
                "RepetitionIsNotPathology",
                dependencies=("recurrence", "reassurance"),
                wait_condition={"pathology_inferred": False},
            ),
            *_questions_and_tail(dependencies=("non_pathology_gate",)),
        ),
        extra_metadata={
            "authorized_prior_context_only": True,
            "psychiatric_labels_forbidden": True,
        },
    )


def _professional_discussion_preparation() -> DomainWorkflowDefinition:
    return _workflow(
        "concerns.professional_discussion_preparation",
        description=(
            "Turn a concern into a useful professional discussion: understand, "
            "identify material open questions, and prepare structured content. "
            " The preparation-only gate guarantees nothing was sent, booked or "
            "transmitted."
        ),
        purpose="Preparation only; no external transmission.",
        core_nodes=(
            _node(
                "understand",
                WorkflowNodeType.EXECUTE_OPERATION,
                "UnderstandConcern",
                dependencies=("reason",),
                operation_id="concerns.understand_concern",
            ),
            _node(
                "prepare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareProfessionalDiscussion",
                dependencies=("understand",),
                operation_id="concerns.prepare_professional_discussion",
            ),
            _node(
                "preparation_only_gate",
                WorkflowNodeType.VALIDATE,
                "PreparationOnlyNoTransmission",
                dependencies=("prepare",),
                wait_condition={
                    "external_transmission_performed": False,
                    "appointment_booked": False,
                    "contact_performed": False,
                },
            ),
            *_questions_and_tail(dependencies=("preparation_only_gate",)),
        ),
        extra_metadata={
            "preparation_is_not_transmission": True,
        },
    )


def build_concerns_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the eight Concerns Domain workflow definitions deterministically."""
    by_id = {
        "concerns.open_concern_conversation": _open_concern_conversation(),
        "concerns.talk_it_through": _talk_it_through(),
        "concerns.reality_check": _reality_check(),
        "concerns.reassurance_review": _reassurance_review(),
        "concerns.practical_problem_solving": _practical_problem_solving(),
        "concerns.decision_under_uncertainty": _decision_under_uncertainty(),
        "concerns.recurring_concern_review": _recurring_concern_review(),
        "concerns.professional_discussion_preparation": (
            _professional_discussion_preparation()
        ),
    }
    return tuple(by_id[workflow_id] for workflow_id in CONCERNS_WORKFLOW_IDS)


__all__ = [
    "CONCERNS_WORKFLOW_IDS",
    "build_concerns_workflow_definitions",
]
