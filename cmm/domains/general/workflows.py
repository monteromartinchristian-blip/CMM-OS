"""Phase 10.19 — General Domain Workflows."""

from __future__ import annotations

from cmm.domains.general.catalog import CANONICAL_GENERAL_WORKFLOW_IDS
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

GENERAL_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_GENERAL_WORKFLOW_IDS


def _node(
    node_id: str,
    node_type: WorkflowNodeType,
    name: str,
    *,
    dependencies: tuple[str, ...] = (),
    operation_id: str | None = None,
    approval_gate: str | None = None,
    wait_condition: dict | None = None,
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
    )


def _decision_support() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="general.decision_support",
        domain_id="domain:general",
        version="1.0.0",
        name="DecisionSupport",
        description="Provide prudent decision support without deciding.",
        nodes=(
            _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadOptions"),
            _node("search", WorkflowNodeType.SEARCH_KNOWLEDGE, "SearchKnowledge", dependencies=("load",)),
            _node("profile", WorkflowNodeType.APPLY_PROFILE, "ApplyProfile", dependencies=("search",)),
            _node("reason", WorkflowNodeType.REASON, "ApplyGeneralRules", dependencies=("profile",)),
            _node("compare", WorkflowNodeType.EXECUTE_OPERATION, "CompareItems", dependencies=("reason",), operation_id="general.compare_items"),
            _node("gaps", WorkflowNodeType.DETECT_GAPS, "DetectGaps", dependencies=("compare",)),
            _node("questions", WorkflowNodeType.EXECUTE_OPERATION, "PrepareQuestions", dependencies=("gaps",), operation_id="general.prepare_questions"),
            _node("report", WorkflowNodeType.EXECUTE_OPERATION, "GenerateReport", dependencies=("questions",), operation_id="general.generate_report"),
            _node("complete", WorkflowNodeType.COMPLETE, "Complete", dependencies=("report",)),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Decision support",
        metadata={"phase": "10.19"},
    )


def _goal_clarification() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="general.goal_clarification",
        domain_id="domain:general",
        version="1.0.0",
        name="GoalClarification",
        description="Clarify a general goal before proposing changes.",
        nodes=(
            _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadGoal"),
            _node("profile", WorkflowNodeType.APPLY_PROFILE, "ApplyProfile", dependencies=("load",)),
            _node("reason", WorkflowNodeType.REASON, "ApplyGoalClarificationRule", dependencies=("profile",)),
            _node("ask", WorkflowNodeType.ASK_QUESTION, "AskBlockingQuestions", dependencies=("reason",), wait_condition={"kind": "user_response"}),
            _node("pause", WorkflowNodeType.PAUSE, "PauseWhenUnanswered", dependencies=("ask",)),
            _node("validate", WorkflowNodeType.VALIDATE, "Validate", dependencies=("pause",)),
            _node("memory", WorkflowNodeType.PROPOSE_MEMORY, "ProposeMemory", dependencies=("validate",)),
            _node("complete", WorkflowNodeType.COMPLETE, "Complete", dependencies=("memory",)),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Goal clarification",
        metadata={"phase": "10.19"},
    )


def _information_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="general.information_review",
        domain_id="domain:general",
        version="1.0.0",
        name="InformationReview",
        description="Review general information, detect gaps and contradictions.",
        nodes=(
            _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadResource"),
            _node("search", WorkflowNodeType.SEARCH_KNOWLEDGE, "SearchKnowledge", dependencies=("load",)),
            _node("profile", WorkflowNodeType.APPLY_PROFILE, "ApplyProfile", dependencies=("search",)),
            _node("reason", WorkflowNodeType.REASON, "ApplyGeneralRules", dependencies=("profile",)),
            _node("gaps", WorkflowNodeType.DETECT_GAPS, "DetectGaps", dependencies=("reason",)),
            _node("summary", WorkflowNodeType.EXECUTE_OPERATION, "CreateSummary", dependencies=("gaps",), operation_id="general.create_summary"),
            _node("questions", WorkflowNodeType.EXECUTE_OPERATION, "PrepareQuestions", dependencies=("summary",), operation_id="general.prepare_questions"),
            _node("validate", WorkflowNodeType.VALIDATE, "Validate", dependencies=("questions",)),
            _node("memory", WorkflowNodeType.PROPOSE_MEMORY, "ProposeMemory", dependencies=("validate",)),
            _node("complete", WorkflowNodeType.COMPLETE, "Complete", dependencies=("memory",)),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="General information review",
        metadata={"phase": "10.19"},
    )


def _periodic_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="general.periodic_review",
        domain_id="domain:general",
        version="1.0.0",
        name="PeriodicReview",
        description="Periodically review goals, tasks, and relevant events.",
        nodes=(
            _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadPriorState"),
            _node("search", WorkflowNodeType.SEARCH_KNOWLEDGE, "SearchKnowledge", dependencies=("load",)),
            _node("profile", WorkflowNodeType.APPLY_PROFILE, "ApplyProfile", dependencies=("search",)),
            _node("reason", WorkflowNodeType.REASON, "ApplyGeneralRules", dependencies=("profile",)),
            _node("timeline", WorkflowNodeType.EXECUTE_OPERATION, "BuildTimeline", dependencies=("reason",), operation_id="general.build_timeline"),
            _node("gaps", WorkflowNodeType.DETECT_GAPS, "DetectGaps", dependencies=("timeline",)),
            _node("questions", WorkflowNodeType.EXECUTE_OPERATION, "PrepareQuestions", dependencies=("gaps",), operation_id="general.prepare_questions"),
            _node("validate", WorkflowNodeType.VALIDATE, "Validate", dependencies=("questions",)),
            _node("memory", WorkflowNodeType.PROPOSE_MEMORY, "ProposeMemory", dependencies=("validate",)),
            _node("complete", WorkflowNodeType.COMPLETE, "Complete", dependencies=("memory",)),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Periodic review",
        metadata={"phase": "10.19"},
    )


def build_general_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the four General Domain workflow definitions deterministically in canonical order."""
    by_id = {
        "general.decision_support": _decision_support(),
        "general.goal_clarification": _goal_clarification(),
        "general.information_review": _information_review(),
        "general.periodic_review": _periodic_review(),
    }
    return tuple(by_id[workflow_id] for workflow_id in GENERAL_WORKFLOW_IDS)


__all__ = ["GENERAL_WORKFLOW_IDS", "build_general_workflow_definitions"]