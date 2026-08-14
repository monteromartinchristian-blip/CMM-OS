"""Phase 10.23 — Opposition Domain Workflows.

Seven declarative Opposition workflows.  Every workflow loads its context,
applies the conservative Opposition profile, reasons under the six Opposition
rules, detects gaps, optionally executes one or more Opposition operations,
and never acts on official public-body systems autonomously.

Safety ordering: ``load -> profile -> reason`` is a strict dependency chain.
A terminal ``COMPLETE`` node always transitively depends on a ``VALIDATE`` node.

Safety posture (spec §20, §22):
- **No memory write**: memory policy is read-only; all tails are validate-only.
- **No autonomous external action**: planning workflows produce *proposals*
  and carry a real ``REQUEST_APPROVAL`` gate; they never register, submit,
  pay, sign, or switch the target.  ``review_call`` is read-only analysis.
- **Call monitoring** is represented as a review concern node; no scheduler is
  introduced.
"""

from __future__ import annotations

from cmm.domains.oppositions.catalog import CANONICAL_OPPOSITION_WORKFLOW_IDS
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType

OPPOSITIONS_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_OPPOSITION_WORKFLOW_IDS


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
        _node("load", WorkflowNodeType.LOAD_RESOURCE, "LoadOppositionSources"),
        _node(
            "profile",
            WorkflowNodeType.APPLY_PROFILE,
            "ApplyOppositionProfile",
            dependencies=("load",),
        ),
        _node(
            "reason",
            WorkflowNodeType.REASON,
            "ApplyOppositionRules",
            dependencies=("profile",),
        ),
    )


def _validate_only_tail() -> tuple[WorkflowNode, ...]:
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


def _planning_tail(approval_gate: str) -> tuple[WorkflowNode, ...]:
    return (
        _node(
            "validate",
            WorkflowNodeType.VALIDATE,
            "Validate",
            dependencies=("questions",),
        ),
        _node(
            "approve",
            WorkflowNodeType.REQUEST_APPROVAL,
            "ConfirmStrategyProposal",
            dependencies=("validate",),
            approval_gate=approval_gate,
        ),
        _node(
            "complete",
            WorkflowNodeType.COMPLETE,
            "Complete",
            dependencies=("approve",),
        ),
    )


def _opposition_setup() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="oppositions.setup",
        domain_id="domain:oppositions",
        version="1.0.0",
        name="OppositionSetup",
        description=(
            "Set up an opposition target/body: known call state, verification "
            "needs, syllabus baseline, requirements, constraints, milestones and "
            "an initial strategy proposal.  Long-term preparation may exist "
            "without a currently open call, but call uncertainty stays explicit."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "check_call",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewCall",
                dependencies=("reason",),
                operation_id="oppositions.review_call",
            ),
            _node(
                "divide",
                WorkflowNodeType.EXECUTE_OPERATION,
                "DivideSyllabus",
                dependencies=("check_call",),
                operation_id="oppositions.divide_syllabus",
            ),
            _node(
                "plan",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CreateStudyPlan",
                dependencies=("divide",),
                operation_id="oppositions.create_study_plan",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyRisks",
                dependencies=("plan",),
                operation_id="oppositions.identify_risks",
            ),
            *_planning_tail("oppositions.setup"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Opposition setup (initial strategy proposal only)",
        metadata={"phase": "10.23"},
    )


def _weekly_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="oppositions.weekly_review",
        domain_id="domain:oppositions",
        version="1.0.0",
        name="WeeklyStudyReview",
        description=(
            "Weekly study review: monitoring state (call monitoring is a "
            "required concern for active goals), progress, coverage/revision, "
            "mocks, capacity/constraints, and risks, producing a next-week "
            "proposal.  No scheduler is introduced."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "monitor",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewCall",
                dependencies=("reason",),
                operation_id="oppositions.review_call",
            ),
            _node(
                "progress",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackProgress",
                dependencies=("monitor",),
                operation_id="oppositions.track_progress",
            ),
            _node(
                "review",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateWeeklyReview",
                dependencies=("progress",),
                operation_id="oppositions.generate_weekly_review",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyRisks",
                dependencies=("review",),
                operation_id="oppositions.identify_risks",
            ),
            *_planning_tail("oppositions.weekly_review"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Weekly study review (proposal only)",
        metadata={"phase": "10.23"},
    )


def _mock_exam_review() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="oppositions.mock_exam_review",
        domain_id="domain:oppositions",
        version="1.0.0",
        name="MockExamReview",
        description=(
            "Grounded mock interpretation and revision recommendation.  A "
            "single mock is an observation, not a trend; no capacity or exam-"
            "success guarantee is inferred."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "mock",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewMockExam",
                dependencies=("reason",),
                operation_id="oppositions.review_mock_exam",
            ),
            _node(
                "revision",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateRevisionPlan",
                dependencies=("mock",),
                operation_id="oppositions.generate_revision_plan",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyRisks",
                dependencies=("revision",),
                operation_id="oppositions.identify_risks",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Mock exam review (analysis + revision proposal)",
        metadata={"phase": "10.23"},
    )


def _call_analysis() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="oppositions.call_analysis",
        domain_id="domain:oppositions",
        version="1.0.0",
        name="CallAnalysis",
        description=(
            "Analyse an official call: authority by attribute/scope, temporal "
            "validity, requirements/deadlines, contradictions/gaps, and an "
            "OFFICIAL_ONLY read-only verification need.  Never registers or "
            "submits."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "call",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewCall",
                dependencies=("reason",),
                operation_id="oppositions.review_call",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyRisks",
                dependencies=("call",),
                operation_id="oppositions.identify_risks",
            ),
            _node(
                "verify",
                WorkflowNodeType.VALIDATE,
                "VerifyOfficialReadOnly",
                dependencies=("questions",),
                wait_condition={"official_only": True, "read_only": True},
            ),
            _node(
                "complete",
                WorkflowNodeType.COMPLETE,
                "Complete",
                dependencies=("verify",),
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Official call analysis (read-only, no submission)",
        metadata={"phase": "10.23"},
    )


def _syllabus_revision() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="oppositions.syllabus_revision",
        domain_id="domain:oppositions",
        version="1.0.0",
        name="SyllabusRevision",
        description=(
            "Syllabus revision: coverage + review/retention risk + pending "
            "topics + available time -> a revision proposal.  Forgetfulness is "
            "never inferred from elapsed time alone."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "divide",
                WorkflowNodeType.EXECUTE_OPERATION,
                "DivideSyllabus",
                dependencies=("reason",),
                operation_id="oppositions.divide_syllabus",
            ),
            _node(
                "revision",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateRevisionPlan",
                dependencies=("divide",),
                operation_id="oppositions.generate_revision_plan",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyRisks",
                dependencies=("revision",),
                operation_id="oppositions.identify_risks",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Syllabus revision (proposal only)",
        metadata={"phase": "10.23"},
    )


def _alternative_route_comparison() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="oppositions.alternative_route_comparison",
        domain_id="domain:oppositions",
        version="1.0.0",
        name="AlternativeRouteComparison",
        description=(
            "Compare the primary target with alternatives: grounded comparison, "
            "trade-offs, uncertainty and a proposal.  Never abandons or changes "
            "the target silently."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "compare",
                WorkflowNodeType.EXECUTE_OPERATION,
                "CompareBodies",
                dependencies=("reason",),
                operation_id="oppositions.compare_bodies",
            ),
            _node(
                "strategy",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewCall",
                dependencies=("compare",),
                operation_id="oppositions.review_call",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyRisks",
                dependencies=("strategy",),
                operation_id="oppositions.identify_risks",
            ),
            *_planning_tail("oppositions.alternative_route_comparison"),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Alternative route comparison (trade-offs/proposal only)",
        metadata={"phase": "10.23"},
    )


def _exam_readiness() -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id="oppositions.exam_readiness",
        domain_id="domain:oppositions",
        version="1.0.0",
        name="ExamReadinessReview",
        description=(
            "Exam readiness assessment consuming call/exam temporal state, "
            "syllabus identity, coverage, revision, mock evidence, feasibility "
            "and risks.  Returns explicit uncertainty; never guarantees passing "
            "or judges personal capacity."
        ),
        nodes=(
            *_ordered_prefix(),
            _node(
                "monitor",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewCall",
                dependencies=("reason",),
                operation_id="oppositions.review_call",
            ),
            _node(
                "progress",
                WorkflowNodeType.EXECUTE_OPERATION,
                "TrackProgress",
                dependencies=("monitor",),
                operation_id="oppositions.track_progress",
            ),
            _node(
                "mock",
                WorkflowNodeType.EXECUTE_OPERATION,
                "ReviewMockExam",
                dependencies=("progress",),
                operation_id="oppositions.review_mock_exam",
            ),
            _node(
                "readiness",
                WorkflowNodeType.EXECUTE_OPERATION,
                "GenerateWeeklyReview",
                dependencies=("mock",),
                operation_id="oppositions.generate_weekly_review",
            ),
            _node(
                "questions",
                WorkflowNodeType.EXECUTE_OPERATION,
                "IdentifyRisks",
                dependencies=("readiness",),
                operation_id="oppositions.identify_risks",
            ),
            *_validate_only_tail(),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="Exam readiness review (explicit uncertainty, no guarantee)",
        metadata={"phase": "10.23"},
    )


def build_oppositions_workflow_definitions() -> tuple[DomainWorkflowDefinition, ...]:
    """Build the seven Opposition Domain workflow definitions deterministically."""
    by_id = {
        "oppositions.alternative_route_comparison": _alternative_route_comparison(),
        "oppositions.call_analysis": _call_analysis(),
        "oppositions.exam_readiness": _exam_readiness(),
        "oppositions.mock_exam_review": _mock_exam_review(),
        "oppositions.setup": _opposition_setup(),
        "oppositions.syllabus_revision": _syllabus_revision(),
        "oppositions.weekly_review": _weekly_review(),
    }
    return tuple(by_id[workflow_id] for workflow_id in OPPOSITIONS_WORKFLOW_IDS)


__all__ = ["OPPOSITIONS_WORKFLOW_IDS", "build_oppositions_workflow_definitions"]