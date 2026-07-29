"""Phase 9.2 – Goal System Comprehensive Test Suite.

Validates Goal contracts, GoalPriority, SuccessCriterion, GoalConstraint,
GoalDependency, GoalHistoryEntry, InMemoryGoalRepository, GoalManager lifecycle,
state transitions, mandatory invariants, search, and E2E workflow.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.enums import (
    GoalConstraintKind,
    GoalDependencyType,
    GoalKind,
    GoalStatus,
    SuccessCriterionKind,
    SuccessCriterionStatus,
)
from cmm.agent_runtime.errors import (
    DuplicateGoalError,
    GoalCompletionError,
    GoalDependencyError,
    GoalError,
    GoalNotFoundError,
    InvalidGoalContractError,
    InvalidGoalTransitionError,
)
from cmm.agent_runtime.goal_contracts import (
    Goal,
    GoalConstraint,
    GoalDependency,
    GoalPriority,
    GoalQuery,
    SuccessCriterion,
)
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.goal_repository import InMemoryGoalRepository


def _sample_goal(
    goal_id: str = "goal-101",
    title: str = "Reduce technical debt",
    status: GoalStatus = GoalStatus.PROPOSED,
    kind: GoalKind = GoalKind.PROJECT_IMPROVEMENT,
    completed_at: datetime | None = None,
    criteria: list[SuccessCriterion] | None = None,
) -> Goal:
    now = datetime.now(timezone.utc)
    return Goal(
        id=goal_id,
        title=title,
        description="Identify and correct code smells",
        kind=kind,
        status=status,
        priority=GoalPriority(score=80.0, urgency=60.0, importance=90.0),
        urgency=60.0,
        importance=90.0,
        value=85.0,
        confidence=0.9,
        success_criteria=tuple(criteria or []),
        created_at=now,
        updated_at=now,
        completed_at=completed_at,
    )


# ── Contracts and Validation Tests ────────────────────────────────────────────


def test_goal_priority_valid_and_invalid() -> None:
    gp = GoalPriority(score=75.0, urgency=50.0, estimated_cost=12.5)
    assert gp.score == 75.0
    assert gp.estimated_cost == 12.5

    with pytest.raises(InvalidGoalContractError, match="score must be between"):
        GoalPriority(score=150.0)

    with pytest.raises(InvalidGoalContractError, match="estimated_cost must be >= 0.0"):
        GoalPriority(estimated_cost=-5.0)


def test_success_criterion_valid_and_invalid() -> None:
    sc = SuccessCriterion(
        id="sc-1",
        description="All tests pass",
        kind=SuccessCriterionKind.VALIDATION,
        status=SuccessCriterionStatus.PENDING,
    )
    assert sc.id == "sc-1"
    assert sc.required is True

    with pytest.raises(InvalidGoalContractError, match="id must be a non-empty string"):
        SuccessCriterion(id="  ", description="Invalid ID")

    with pytest.raises(
        InvalidGoalContractError, match="Invalid SuccessCriterionStatus"
    ):
        SuccessCriterion(id="sc-2", description="Test", status="invalid_status")


def test_goal_constraint_valid_and_invalid() -> None:
    gc = GoalConstraint(
        id="gc-1",
        description="No API breaking changes",
        kind=GoalConstraintKind.SAFETY,
        severity="blocking",
    )
    assert gc.severity == "blocking"

    with pytest.raises(InvalidGoalContractError, match="Invalid GoalConstraintKind"):
        GoalConstraint(id="gc-2", description="Test", kind="unknown_kind")


def test_goal_dependency_valid_and_invalid() -> None:
    gd = GoalDependency(
        goal_id="goal-2",
        depends_on_goal_id="goal-1",
        dependency_type=GoalDependencyType.REQUIRES_COMPLETION,
    )
    assert gd.blocking is True

    with pytest.raises(GoalDependencyError, match="cannot depend on itself"):
        GoalDependency(goal_id="goal-1", depends_on_goal_id="goal-1")


def test_goal_invariants_parent_and_child_self_referencing() -> None:
    with pytest.raises(InvalidGoalContractError, match="parent of itself"):
        Goal(
            id="g-1",
            title="Goal 1",
            description="Test",
            kind=GoalKind.ANALYSIS,
            status=GoalStatus.PROPOSED,
            priority=GoalPriority(),
            parent_goal_id="g-1",
        )

    with pytest.raises(InvalidGoalContractError, match="child of itself"):
        Goal(
            id="g-2",
            title="Goal 2",
            description="Test",
            kind=GoalKind.ANALYSIS,
            status=GoalStatus.PROPOSED,
            priority=GoalPriority(),
            child_goal_ids=("g-2",),
        )


def test_goal_invariants_completed_at() -> None:
    now = datetime.now(timezone.utc)
    # Non-completed status cannot have completed_at
    with pytest.raises(
        InvalidGoalContractError, match="cannot have completed_at populated"
    ):
        Goal(
            id="g-3",
            title="Goal 3",
            description="Test",
            kind=GoalKind.ANALYSIS,
            status=GoalStatus.ACTIVE,
            priority=GoalPriority(),
            created_at=now,
            completed_at=now,
        )

    # Completed status must have completed_at
    with pytest.raises(
        InvalidGoalContractError, match="must have completed_at populated"
    ):
        Goal(
            id="g-4",
            title="Goal 4",
            description="Test",
            kind=GoalKind.ANALYSIS,
            status=GoalStatus.COMPLETED,
            priority=GoalPriority(),
            completed_at=None,
        )


def test_goal_serialization_round_trip() -> None:
    g = _sample_goal(
        criteria=[
            SuccessCriterion(
                id="sc-1",
                description="Tests green",
                kind=SuccessCriterionKind.VALIDATION,
            )
        ]
    )
    data = g.serialize()
    reconstructed = Goal.from_dict(data)

    assert reconstructed.id == g.id
    assert reconstructed.title == g.title
    assert reconstructed.status == g.status
    assert reconstructed.kind == g.kind
    assert reconstructed.priority.score == g.priority.score
    assert len(reconstructed.success_criteria) == 1
    assert reconstructed.success_criteria[0].id == "sc-1"


# ── Repository Tests ──────────────────────────────────────────────────────────


def test_in_memory_repository_crud_and_mutability_isolation() -> None:
    repo = InMemoryGoalRepository()
    g = _sample_goal("goal-1")

    registered = repo.add(g)
    assert registered.id == "goal-1"

    # Reject duplicate ID
    with pytest.raises(DuplicateGoalError, match="already exists"):
        repo.add(g)

    retrieved = repo.get("goal-1")
    assert retrieved is not None
    assert retrieved.title == g.title

    # Update goal
    now = datetime.now(timezone.utc)
    updated_g = Goal.from_dict(
        {**g.serialize(), "title": "Updated Title", "updated_at": now.isoformat()}
    )
    updated_res = repo.update(updated_g)
    assert updated_res.title == "Updated Title"

    # Ensure internal state immutability
    retrieved_again = repo.get("goal-1")
    assert retrieved_again is not None
    assert retrieved_again.title == "Updated Title"

    # Non-existent goal update/get
    assert repo.get("non-existent") is None
    with pytest.raises(GoalNotFoundError):
        repo.update(_sample_goal("non-existent"))


def test_repository_search_filters_and_pagination() -> None:
    repo = InMemoryGoalRepository()
    repo.add(_sample_goal("g-1", title="Fix bug", kind=GoalKind.REMEDIATION))
    repo.add(_sample_goal("g-2", title="Refactor core", kind=GoalKind.OPTIMIZATION))
    repo.add(_sample_goal("g-3", title="Write docs", kind=GoalKind.DOCUMENTATION))

    # Filter by kind
    res_kind = repo.search(GoalQuery(kinds=(GoalKind.REMEDIATION,)))
    assert len(res_kind.goals) == 1
    assert res_kind.goals[0].id == "g-1"

    # Text search
    res_text = repo.search(GoalQuery(text_search="core"))
    assert len(res_text.goals) == 1
    assert res_text.goals[0].id == "g-2"

    # Pagination
    res_page = repo.search(GoalQuery(limit=2, offset=0))
    assert len(res_page.goals) == 2
    assert res_page.total_count == 3


# ── GoalManager Tests ─────────────────────────────────────────────────────────


def test_goal_manager_registration_and_duplicate_detection() -> None:
    manager = GoalManager()
    g1 = _sample_goal("g-1", title="Clean repository")
    registered = manager.register_goal(g1)
    assert registered.id == "g-1"

    history = manager.get_history("g-1")
    assert len(history) == 1
    assert history[0].new_status == GoalStatus.PROPOSED

    # Duplicate detection by title
    dups = manager.detect_duplicates("Clean repository")
    assert len(dups) == 1
    assert dups[0].id == "g-1"


def test_subgoals_and_dependencies() -> None:
    manager = GoalManager()
    manager.register_goal(_sample_goal("parent-1", title="Parent Goal"))
    child = _sample_goal("child-1", title="Child Goal")

    created_child = manager.create_subgoal("parent-1", child)
    assert created_child.parent_goal_id == "parent-1"

    parent_updated = manager.get_goal("parent-1")
    assert parent_updated is not None
    assert "child-1" in parent_updated.child_goal_ids

    children = manager.get_children("parent-1")
    assert len(children) == 1
    assert children[0].id == "child-1"

    # Dependency addition
    manager.register_goal(_sample_goal("g-2", title="Dependency Target"))
    dep = GoalDependency(
        goal_id="child-1",
        depends_on_goal_id="g-2",
        dependency_type=GoalDependencyType.REQUIRES_COMPLETION,
    )
    updated_child = manager.add_dependency(dep)
    assert len(updated_child.dependencies) == 1
    assert updated_child.dependencies[0].depends_on_goal_id == "g-2"


def test_state_transitions_valid_and_invalid() -> None:
    manager = GoalManager()
    manager.register_goal(_sample_goal("g-1", status=GoalStatus.PROPOSED))

    # Valid transition: proposed -> accepted
    g_acc = manager.change_status("g-1", GoalStatus.ACCEPTED, "user", "Approved")
    assert g_acc.status == GoalStatus.ACCEPTED

    # Invalid transition: completed -> in_progress (via direct invalid change on accepted -> completed without criteria)
    # First active
    manager.change_status("g-1", GoalStatus.ACTIVE, "user", "Activated")
    manager.change_status("g-1", GoalStatus.COMPLETED, "user", "Done")

    with pytest.raises(
        InvalidGoalTransitionError,
        match="cannot move from 'completed' to 'in_progress'",
    ):
        manager.change_status("g-1", GoalStatus.IN_PROGRESS, "user", "Reopen")


def test_pause_and_resume_flow() -> None:
    manager = GoalManager()
    manager.register_goal(_sample_goal("g-1", status=GoalStatus.PROPOSED))
    manager.change_status("g-1", GoalStatus.ACCEPTED, "user", "Accept")
    manager.change_status("g-1", GoalStatus.ACTIVE, "user", "Activate")
    manager.change_status("g-1", GoalStatus.IN_PROGRESS, "user", "Working")

    # Pause
    paused = manager.pause_goal("g-1", "user", "Need rest")
    assert paused.status == GoalStatus.PAUSED

    # Resume restores IN_PROGRESS
    resumed = manager.resume_goal("g-1", "user", "Continue work")
    assert resumed.status == GoalStatus.IN_PROGRESS

    # Resume non-paused goal raises error
    with pytest.raises(InvalidGoalTransitionError, match="not 'paused'"):
        manager.resume_goal("g-1", "user", "Resume again")


def test_cancel_goal_idempotency_and_terminal_restriction() -> None:
    manager = GoalManager()
    manager.register_goal(_sample_goal("g-1", status=GoalStatus.PROPOSED))

    cancelled = manager.cancel_goal("g-1", "user", "Not needed")
    assert cancelled.status == GoalStatus.CANCELLED

    # Idempotent cancel
    cancelled_again = manager.cancel_goal("g-1", "user", "Not needed again")
    assert cancelled_again.status == GoalStatus.CANCELLED

    # Cannot transition cancelled -> active
    with pytest.raises(
        InvalidGoalTransitionError, match="cannot move from 'cancelled' to 'active'"
    ):
        manager.change_status("g-1", GoalStatus.ACTIVE, "user", "Reactivate")


def test_goal_completion_evaluates_required_criteria() -> None:
    manager = GoalManager()
    sc_required = SuccessCriterion(
        id="sc-req",
        description="Must pass suite",
        required=True,
        status=SuccessCriterionStatus.PENDING,
    )
    sc_optional = SuccessCriterion(
        id="sc-opt",
        description="Optional metric",
        required=False,
        status=SuccessCriterionStatus.PENDING,
    )
    goal = _sample_goal(
        "g-1", status=GoalStatus.ACTIVE, criteria=[sc_required, sc_optional]
    )
    manager.register_goal(goal)

    # Attempting to complete with pending required criterion fails
    with pytest.raises(GoalCompletionError, match="unsatisfied"):
        manager.complete_goal("g-1", "user", "Try complete")

    # Evaluate required criterion to satisfied
    manager.evaluate_success_criteria(
        "g-1",
        {
            "sc-req": (SuccessCriterionStatus.SATISFIED, "100% passed"),
        },
    )

    # Now completion succeeds even if optional criterion is pending
    completed = manager.complete_goal("g-1", "user", "Complete goal")
    assert completed.status == GoalStatus.COMPLETED
    assert completed.completed_at is not None


def test_structured_error_hierarchy() -> None:
    assert issubclass(InvalidGoalContractError, GoalError)
    assert issubclass(InvalidGoalContractError, ValueError)
    assert issubclass(GoalNotFoundError, GoalError)
    assert issubclass(GoalNotFoundError, KeyError)
    assert issubclass(DuplicateGoalError, GoalError)
    assert issubclass(InvalidGoalTransitionError, GoalError)
    assert issubclass(GoalCompletionError, GoalError)
    assert issubclass(GoalDependencyError, GoalError)


def test_full_e2e_goal_lifecycle() -> None:
    """Full E2E flow:

    crear objetivo -> aceptar -> activar -> iniciar -> evaluar criterios -> completar -> consultar historial.
    """
    manager = GoalManager()

    # 1. Crear objetivo
    criterion = SuccessCriterion(
        id="sc-e2e",
        description="Code quality benchmark met",
        required=True,
        status=SuccessCriterionStatus.PENDING,
    )
    goal = _sample_goal(
        "goal-e2e",
        title="Phase 9 E2E Goal",
        status=GoalStatus.PROPOSED,
        criteria=[criterion],
    )
    registered = manager.register_goal(
        goal, actor_id="actor-user", reason="Proposal from user"
    )
    assert registered.status == GoalStatus.PROPOSED

    # 2. Aceptar
    accepted = manager.change_status(
        "goal-e2e",
        GoalStatus.ACCEPTED,
        actor_id="actor-system",
        reason="Accepted proposal",
    )
    assert accepted.status == GoalStatus.ACCEPTED

    # 3. Activar
    active = manager.change_status(
        "goal-e2e", GoalStatus.ACTIVE, actor_id="actor-agent", reason="Activated goal"
    )
    assert active.status == GoalStatus.ACTIVE

    # 4. Iniciar (In progress)
    in_progress = manager.change_status(
        "goal-e2e",
        GoalStatus.IN_PROGRESS,
        actor_id="actor-agent",
        reason="Started execution",
    )
    assert in_progress.status == GoalStatus.IN_PROGRESS

    # 5. Evaluar criterios
    evaluated = manager.evaluate_success_criteria(
        "goal-e2e",
        {"sc-e2e": (SuccessCriterionStatus.SATISFIED, "Passed all 1775 tests")},
        actor_id="actor-validator",
        reason="Validated benchmark",
    )
    assert evaluated.success_criteria[0].status == SuccessCriterionStatus.SATISFIED

    # 6. Completar
    completed = manager.complete_goal(
        "goal-e2e", actor_id="actor-agent", reason="Goal satisfied"
    )
    assert completed.status == GoalStatus.COMPLETED
    assert completed.completed_at is not None

    # 7. Consultar historial
    history = manager.get_history("goal-e2e")
    assert len(history) == 6
    statuses = [h.new_status for h in history]
    assert statuses == [
        GoalStatus.PROPOSED,
        GoalStatus.ACCEPTED,
        GoalStatus.ACTIVE,
        GoalStatus.IN_PROGRESS,
        GoalStatus.IN_PROGRESS,  # criteria evaluation entry
        GoalStatus.COMPLETED,
    ]
