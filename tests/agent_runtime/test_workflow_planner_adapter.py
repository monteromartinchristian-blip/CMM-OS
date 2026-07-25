"""Unit and integration tests for Phase 9.7 Workflow Planner Adapter."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentPlanningDecision,
    AgentPlanningStatus,
    WorkflowPlanChangeReason,
    WorkflowPlanStatus,
)
from cmm.agent_runtime.errors import (
    InvalidAgentPlanningContractError,
    PlannerUnavailableError,
)
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
from cmm.agent_runtime.goal_repository import InMemoryGoalRepository
from cmm.agent_runtime.workflow_planner_adapter import (
    AgentPlanningService,
    DefaultWorkflowPlannerAdapter,
)
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentReplanningRequest,
    AgentWorkflowBudgetEstimate,
    AgentWorkflowDependency,
    AgentWorkflowOperation,
    AgentWorkflowPlan,
    AgentWorkflowTask,
)
from cmm.agent_runtime.workflow_planner_store import InMemoryWorkflowPlanStore
from cmm.agent_runtime.workflow_planner_validator import AgentWorkflowPlanValidator
from cmm.memory.technical_reasoner import TechnicalReasoner
from cmm.planner.task_planner import TaskPlanner

# ── Dummy Technical Reasoner Facade ───────────────────────────────────────────


class DummySymbol:
    def __init__(
        self, title: str, identifier: str = "sym-1", kind: str = "Class"
    ) -> None:
        self.title = title
        self.identifier = identifier
        self.kind = kind


class DummyTechnicalReasoner(TechnicalReasoner):
    """Deterministically mocks technical reasoner responses without external dependencies."""

    def __init__(self) -> None:
        pass

    def locate_feature(self, query: str) -> list[object]:
        return [DummySymbol(title="TechnicalReasoner", identifier="sym-reasoner")]

    def impact_analysis(self, feature_name: str) -> dict[str, object] | None:
        return {
            "risk": "low",
            "direct_dependents": [
                DummySymbol(title="TaskPlanner", identifier="sym-planner")
            ],
            "callers": [],
            "callees": [],
        }

    def explain_dependencies(self, feature_name: str) -> dict[str, list[object]] | None:
        return {"uses": [], "imports": [], "inherits_from": []}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def dummy_reasoner() -> TechnicalReasoner:
    return DummyTechnicalReasoner()


@pytest.fixture
def task_planner(dummy_reasoner: TechnicalReasoner) -> TaskPlanner:
    return TaskPlanner(reasoner=dummy_reasoner)


@pytest.fixture
def goal_repo() -> InMemoryGoalRepository:
    repo = InMemoryGoalRepository()
    g = Goal(
        id="goal-100",
        title="Refactor technical reasoning planner",
        description="Refactor technical reasoning planner",
        kind="transformation",
        status="active",
        priority=GoalPriority(),
    )
    repo.add(g)
    return repo


from datetime import datetime, timezone

from cmm.agent_runtime.enums import AgentRuntimeStatus


@pytest.fixture
def sample_agent_run() -> AgentRun:
    now = datetime.now(timezone.utc)
    return AgentRun(
        id="run-100",
        agent_id="agent-1",
        goal_id="goal-100",
        status=AgentRuntimeStatus.PLANNING,
        autonomy_level=1,
        current_iteration=1,
        started_at=now,
        updated_at=now,
    )


@pytest.fixture
def planning_request() -> AgentPlanningRequest:
    return AgentPlanningRequest(
        id="req-100",
        goal_id="goal-100",
        agent_run_id="run-100",
        objective="Refactor technical reasoning planner",
        allowed_operations=[
            "python.find_symbol",
            "python.list_imports",
            "python.describe_module",
            "filesystem.read_file",
            "filesystem.exists",
        ],
        prohibited_operations=["filesystem.delete_file"],
        required_validations=["structural_check"],
        timeout_seconds=60.0,
    )


# ── Contract & Invariant Tests ────────────────────────────────────────────────


def test_planning_request_invariants() -> None:
    """Validate AgentPlanningRequest contract invariants."""
    req = AgentPlanningRequest(
        id="req-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        objective="Test objective",
    )
    assert req.id == "req-1"
    assert req.goal_id == "goal-1"
    assert req.agent_run_id == "run-1"

    with pytest.raises(InvalidAgentPlanningContractError):
        AgentPlanningRequest(id="", goal_id="g", agent_run_id="r", objective="o")

    with pytest.raises(InvalidAgentPlanningContractError):
        AgentPlanningRequest(id="r", goal_id="", agent_run_id="r", objective="o")

    with pytest.raises(InvalidAgentPlanningContractError):
        AgentPlanningRequest(
            id="r", goal_id="g", agent_run_id="r", objective="o", timeout_seconds=-5.0
        )


def test_workflow_plan_serialization_roundtrip(
    planning_request: AgentPlanningRequest,
) -> None:
    """Verify AgentWorkflowPlan serialization and reconstruction retain all fields."""
    plan = AgentWorkflowPlan(
        id="wf-plan-1",
        goal_id=planning_request.goal_id,
        agent_run_id=planning_request.agent_run_id,
        workflow_id="wf-1",
        version=1,
        status=WorkflowPlanStatus.VALID,
        objective="Test objective",
        confidence=0.95,
        estimated_budget=AgentWorkflowBudgetEstimate(
            estimated_cost=1.5, estimated_tokens=1000
        ),
    )
    d = plan.to_dict()
    reconstructed = AgentWorkflowPlan.from_dict(d)

    assert reconstructed.id == plan.id
    assert reconstructed.goal_id == plan.goal_id
    assert reconstructed.version == plan.version
    assert reconstructed.confidence == plan.confidence
    assert reconstructed.estimated_budget.estimated_cost == 1.5


def test_dependency_self_dependency_prohibited() -> None:
    """Verify self-dependency raises InvalidAgentPlanningContractError."""
    with pytest.raises(InvalidAgentPlanningContractError):
        AgentWorkflowDependency(
            id="dep-1",
            source_task_id="task-1",
            target_task_id="task-1",
        )


def test_budget_estimate_non_negative_invariants() -> None:
    """Verify budget estimates reject negative values."""
    with pytest.raises(InvalidAgentPlanningContractError):
        AgentWorkflowBudgetEstimate(estimated_cost=-10.0)


# ── Structural Validator Tests ────────────────────────────────────────────────


def test_validator_detects_cycle() -> None:
    """Validator must detect cycle in task dependencies."""
    validator = AgentWorkflowPlanValidator()

    t1 = AgentWorkflowTask(id="t1", workflow_id="wf1", name="Task 1", description="")
    t2 = AgentWorkflowTask(id="t2", workflow_id="wf1", name="Task 2", description="")

    dep1 = AgentWorkflowDependency(id="d1", source_task_id="t1", target_task_id="t2")
    dep2 = AgentWorkflowDependency(id="d2", source_task_id="t2", target_task_id="t1")

    plan = AgentWorkflowPlan(
        id="plan-cycle",
        goal_id="g1",
        agent_run_id="r1",
        workflow_id="wf1",
        tasks=[t1, t2],
        dependencies=[dep1, dep2],
    )

    val = validator.validate(plan)
    assert not val.is_valid
    assert any("Circular dependency" in err for err in val.blocking_errors)


def test_validator_prohibited_operation(planning_request: AgentPlanningRequest) -> None:
    """Validator must block prohibited operations."""
    validator = AgentWorkflowPlanValidator()

    t1 = AgentWorkflowTask(id="t1", workflow_id="wf1", name="Delete", description="")
    op1 = AgentWorkflowOperation(
        id="op1",
        task_id="t1",
        operation_name="filesystem.delete_file",
    )

    plan = AgentWorkflowPlan(
        id="plan-prohibited",
        goal_id=planning_request.goal_id,
        agent_run_id=planning_request.agent_run_id,
        workflow_id="wf1",
        tasks=[t1],
        operations=[op1],
    )

    val = validator.validate(plan, request=planning_request)
    assert not val.is_valid
    assert any("prohibited_operations" in err for err in val.blocking_errors)


def test_validator_unregistered_operation() -> None:
    """Validator must detect unregistered operation when registry is provided."""
    registry = ["filesystem.read_file"]
    validator = AgentWorkflowPlanValidator(operation_registry=registry)

    t1 = AgentWorkflowTask(id="t1", workflow_id="wf1", name="T", description="")
    op1 = AgentWorkflowOperation(
        id="op1", task_id="t1", operation_name="unknown.operation"
    )

    plan = AgentWorkflowPlan(
        id="plan-unregistered",
        goal_id="g1",
        agent_run_id="r1",
        workflow_id="wf1",
        tasks=[t1],
        operations=[op1],
    )

    val = validator.validate(plan)
    assert not val.is_valid
    assert any("not registered" in err for err in val.blocking_errors)


# ── Store & Versioning Tests ──────────────────────────────────────────────────


def test_store_versioning_and_supersede() -> None:
    """InMemoryWorkflowPlanStore must preserve version history and track superseded plans."""
    store = InMemoryWorkflowPlanStore()

    v1 = AgentWorkflowPlan(
        id="p1",
        goal_id="g1",
        agent_run_id="r1",
        workflow_id="wf1",
        version=1,
        status=WorkflowPlanStatus.VALID,
    )
    store.add(v1)

    assert store.get_latest("wf1").id == "p1"

    v2 = AgentWorkflowPlan(
        id="p2",
        goal_id="g1",
        agent_run_id="r1",
        workflow_id="wf1",
        version=2,
        previous_version_id="p1",
        status=WorkflowPlanStatus.VALID,
    )
    store.supersede("p1", "p2")
    store.add(v2)

    p1_updated = store.get("p1")
    assert p1_updated.status == WorkflowPlanStatus.SUPERSEDED
    assert p1_updated.metadata["superseded_by"] == "p2"

    assert store.get_latest("wf1").id == "p2"
    assert len(store.list_versions("wf1")) == 2


# ── E2E Required Flows ────────────────────────────────────────────────────────


def test_e2e_flow_valid_project_plan(
    task_planner: TaskPlanner,
    goal_repo: InMemoryGoalRepository,
    sample_agent_run: AgentRun,
    planning_request: AgentPlanningRequest,
) -> None:
    """Flow 1: Valid project plan with TaskPlanner translation, validation, and no execution."""
    adapter = DefaultWorkflowPlannerAdapter(
        planner=task_planner,
        goal_repository=goal_repo,
        agent_run_provider=lambda rid: sample_agent_run,
    )

    plan = adapter.plan(planning_request)

    assert plan.id is not None
    assert plan.status in (WorkflowPlanStatus.VALID, WorkflowPlanStatus.READY)
    assert plan.goal_id == planning_request.goal_id
    assert len(plan.tasks) > 0
    assert len(plan.dependencies) == len(plan.tasks) - 1
    assert len(plan.operations) == len(plan.tasks)
    assert plan.validation.is_valid


def test_e2e_flow_complete_without_workflow(
    goal_repo: InMemoryGoalRepository,
    planning_request: AgentPlanningRequest,
) -> None:
    """Flow 2: Complete without workflow when Goal is already satisfied."""
    g = goal_repo.get("goal-100")
    now = datetime.now(timezone.utc)
    goal_repo._goals["goal-100"] = Goal(
        id="goal-100",
        title=g.title,
        description=g.description,
        kind=g.kind,
        status="completed",
        priority=g.priority,
        created_at=g.created_at,
        completed_at=now,
    ).serialize()

    adapter = DefaultWorkflowPlannerAdapter(
        goal_repository=goal_repo,
    )

    plan = adapter.plan(planning_request)

    assert plan.status == WorkflowPlanStatus.COMPLETED
    assert len(plan.tasks) == 0
    assert (
        plan.metadata.get("decision")
        == AgentPlanningDecision.COMPLETE_WITHOUT_WORKFLOW.value
    )


def test_e2e_flow_replanning(
    task_planner: TaskPlanner,
    goal_repo: InMemoryGoalRepository,
    sample_agent_run: AgentRun,
    planning_request: AgentPlanningRequest,
) -> None:
    """Flow 3: Replanning creates version 2, preserving version 1 as superseded."""
    service = AgentPlanningService(
        adapter=DefaultWorkflowPlannerAdapter(
            planner=task_planner,
            goal_repository=goal_repo,
            agent_run_provider=lambda rid: sample_agent_run,
        )
    )

    v1_plan = service.plan(planning_request)
    assert v1_plan.version == 1

    replan_req = AgentReplanningRequest(
        id="replan-req-1",
        plan_id=v1_plan.id,
        reason=WorkflowPlanChangeReason.NEW_INFORMATION,
        reason_details="Detected new architectural constraint",
    )

    replan_res = service.replan(replan_req)

    assert replan_res.status == AgentPlanningStatus.COMPLETED
    assert replan_res.decision == AgentPlanningDecision.REPLAN
    assert replan_res.version == 2

    # Verify version 1 is preserved and marked superseded
    v1_fetched = service.get_plan(v1_plan.id)
    assert v1_fetched.status == WorkflowPlanStatus.SUPERSEDED

    v2_fetched = service.get_latest_plan(v1_plan.workflow_id)
    assert v2_fetched.version == 2
    assert v2_fetched.previous_version_id == v1_plan.id


def test_planner_unavailable_error() -> None:
    """Adapter must raise PlannerUnavailableError if planner is missing when needed."""
    adapter = DefaultWorkflowPlannerAdapter(planner=None)
    req = AgentPlanningRequest(
        id="r1", goal_id="g1", agent_run_id="run1", objective="Do work"
    )

    with pytest.raises(PlannerUnavailableError):
        adapter.plan(req)
