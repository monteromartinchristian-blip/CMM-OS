"""Phase 10.21 — Relationships Domain Workflows.

Six declarative Relationships workflows.  Every workflow loads its context,
applies the conservative Relationships profile, reasons under the eight
Relationships rules, detects gaps, optionally executes one or more
Relationships operations, and never acts on a relationship autonomously.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain
(an analytical operation can never run before reasoning, and reasoning never
before the profile/context are loaded).  A terminal ``COMPLETE`` node always
transitively depends on a ``VALIDATE`` node, so completion cannot bypass
validation.

Relational-safety posture (spec §1, §8, §26):
- **No memory write**: the domain memory policy is read-only (``allow_write=False``),
  so no workflow proposes memory.  All tails are validate-only.
- **No autonomous relational action**: ``relationships.conversation_preparation``
  only *prepares* material and carries a real ``REQUEST_APPROVAL`` gate; it never
  sends, contacts, or initiates communication on its own.
- **Decision Support Mode A**: ``relationships.decision_support`` compares options
  against explicit user criteria and never adopts a relational decision.
- **Boundary review is review-only**: ``relationships.boundary_review`` never
  modifies, enforces, communicates, or withdraws a boundary.
"""

from __future__ import annotations

from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_WORKFLOW_IDS
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

RELATIONSHIPS_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_RELATIONSHIPS_WORKFLOW_IDS


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


def _ordered_prefix() -> tuple[WorkflowNode, ...]:
    """Strict safety prefix: load -> profile -> reason (enforced as deps)."""
    return (
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadRelationshipSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyRelationshipsProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyRelationshipsRules",
            dependencies=("profile",),
        ),
    )


def _validate_only_tail() -> tuple[WorkflowNode, ...]:
    # Tail that completes without proposing memory (memory policy is read-only).
    return (
        _node(
            "validate",
            WorkflowNodeType.VALIDATE,
            "Validate",
            dependencies=("questions",),
        ),
        _node(
            "complete",
            WorkflowNodeType.COMPLETE,
            "Complete",
            dependencies=("validate",),
        ),
    )


def _timeline_analysis() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="relationships.timeline_analysis",
        domain_id="domain:relationships",
        version="1.0.0",
        name="TimelineAnalysis",
        description="Build a traceable relationship timeline and detect patterns as hypotheses.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildTimeline",
                dependencies=("reason",),
                operation_id="relationships.build_timeline",
            ),
            _node(
                "patterns",
                WorkflowNodeType.EXECUTE_OPERATION,
                "DetectPatterns",
                dependencies=("timeline",),
                operation_id="relationships.detect_patterns",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackOpenQuestions",
                dependencies=("patterns",),
                operation_id="relationships.track_open_questions",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Relationship timeline analysis (patterns as hypotheses)",
        metadata={"phase": "10.21"},
    )


def _boundary_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="relationships.boundary_review",
        domain_id="domain:relationships",
        version="1.0.0",
        name="BoundaryReview",
        description="Review boundary consistency without modifying or enforcing any boundary.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "separate",
                WorkflowNodeType.EXECUTE_OPERATION,
                "SeparateFactsInterpretations",
                dependencies=("reason",),
                operation_id="relationships.separate_facts_interpretations",
            ),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewBoundaries",
                dependencies=("separate",),
                operation_id="relationships.review_boundaries",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackOpenQuestions",
                dependencies=("review",),
                operation_id="relationships.track_open_questions",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Boundary review (review-only, no boundary action)",
        metadata={"phase": "10.21"},
    )


def _conflict_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="relationships.conflict_review",
        domain_id="domain:relationships",
        version="1.0.0",
        name="ConflictReview",
        description="Review a conflict/rupture without diagnosing a third party or collapsing ambivalence.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "events",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ExtractEvents",
                dependencies=("reason",),
                operation_id="relationships.extract_events",
            ),
            _node(
                "separate",
                WorkflowNodeType.EXECUTE_OPERATION,
                "SeparateFactsInterpretations",
                dependencies=("events",),
                operation_id="relationships.separate_facts_interpretations",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackOpenQuestions",
                dependencies=("separate",),
                operation_id="relationships.track_open_questions",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Conflict review (no third-party diagnosis)",
        metadata={"phase": "10.21"},
    )


def _conversation_preparation() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="relationships.conversation_preparation",
        domain_id="domain:relationships",
        version="1.0.0",
        name="ConversationPreparation",
        description="Prepare material for a conversation without sending or contacting anyone.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "prepare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "PrepareConversation",
                dependencies=("reason",),
                operation_id="relationships.prepare_conversation",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackOpenQuestions",
                dependencies=("prepare",),
                operation_id="relationships.track_open_questions",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "Validate",
                dependencies=("questions",),
            ),
            _node(
                "approve",
                WorkflowNodeType.REQUEST_APPROVAL,
                "ApproveConversationPreparation",
                dependencies=("validate",),
                approval_gate="relationships.conversation_preparation",
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("approve",),
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Conversation preparation (never sends or contacts)",
        metadata={"phase": "10.21"},
    )


def _decision_support() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="relationships.decision_support",
        domain_id="domain:relationships",
        version="1.0.0",
        name="DecisionSupport",
        description="Compare options against explicit user criteria without adopting any decision (Mode A).",
        nodes=(
            *_ordered_prefix(),
            _node(
                "needs",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyNeeds",
                dependencies=("reason",),
                operation_id="relationships.identify_needs",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackOpenQuestions",
                dependencies=("needs",),
                operation_id="relationships.track_open_questions",
            ),
            _node(
                "validate",
                WorkflowNodeType.VALIDATE,
                "Validate",
                dependencies=("questions",),
            ),
            _node(
                "approve",
                WorkflowNodeType.REQUEST_APPROVAL,
                "ConfirmDecisionPath",
                dependencies=("validate",),
                approval_gate="relationships.decision_support",
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("approve",),
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Decision support (Mode A: never adopts a decision)",
        metadata={"phase": "10.21"},
    )


def _pattern_evolution_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="relationships.pattern_evolution_review",
        domain_id="domain:relationships",
        version="1.0.0",
        name="PatternEvolutionReview",
        description="Compare relationship periods and review pattern evolution without certainty.",
        nodes=(
            *_ordered_prefix(),
            _node(
                "timeline",
                WorkflowNodeType.EXECUTE_OPERATION,
                "BuildTimeline",
                dependencies=("reason",),
                operation_id="relationships.build_timeline",
            ),
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ComparePeriods",
                dependencies=("timeline",),
                operation_id="relationships.compare_periods",
            ),
            _node(
                "patterns",
                WorkflowNodeType.EXECUTE_OPERATION,
                "DetectPatterns",
                dependencies=("compare",),
                operation_id="relationships.detect_patterns",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackOpenQuestions",
                dependencies=("patterns",),
                operation_id="relationships.track_open_questions",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Pattern evolution review (patterns remain hypotheses)",
        metadata={"phase": "10.21"},
    )


def build_relationships_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the six Relationships Domain workflow definitions deterministically in canonical order."""
    by_id = {
        "relationships.boundary_review": _boundary_review(),
        "relationships.conflict_review": _conflict_review(),
        "relationships.conversation_preparation": _conversation_preparation(),
        "relationships.decision_support": _decision_support(),
        "relationships.pattern_evolution_review": _pattern_evolution_review(),
        "relationships.timeline_analysis": _timeline_analysis(),
    }
    return tuple(by_id[workflow_id] for workflow_id in RELATIONSHIPS_WORKFLOW_IDS)


__all__ = ["RELATIONSHIPS_WORKFLOW_IDS", "build_relationships_workflow_definitions"]
