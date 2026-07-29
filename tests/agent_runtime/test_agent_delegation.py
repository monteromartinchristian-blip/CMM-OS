"""Phase 9.24 Agent Delegation Tests.

Unit and integration tests for the Agent Delegation subsystem.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.agent_runtime import (
    AgentDelegationService,
    AgentRegistryService,
    AgentRuntimeEventBus,
    DelegatedGoal,
    DelegationEventType,
    DelegationProposal,
    DelegationResult,
    DelegationStatus,
    InMemoryAgentDelegationStore,
    InMemoryAgentRegistryStore,
    InMemoryGoalRepository,
)
from cmm.agent_runtime.agent_delegation_errors import (
    AgentDelegationValidationError,
)
from cmm.agent_runtime.agent_registry_contracts import (
    AgentCapability,
    AgentDescriptor,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentCapabilityKind,
    AgentKind,
    AgentLifecycle,
)
from cmm.agent_runtime.enums import GoalKind, GoalStatus
from cmm.agent_runtime.errors import AgentRuntimeError
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
from cmm.agent_runtime.goal_manager import GoalManager

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def agent_store() -> InMemoryAgentRegistryStore:
    return InMemoryAgentRegistryStore()


@pytest.fixture
def goal_repo() -> InMemoryGoalRepository:
    return InMemoryGoalRepository()


@pytest.fixture
def event_bus() -> AgentRuntimeEventBus:
    return AgentRuntimeEventBus()


@pytest.fixture
def registry_service(agent_store: InMemoryAgentRegistryStore) -> AgentRegistryService:
    from cmm.agent_runtime.agent_registry import AgentRegistry

    return AgentRegistryService(registry=AgentRegistry(store=agent_store))


@pytest.fixture
def goal_manager(goal_repo: InMemoryGoalRepository) -> GoalManager:
    return GoalManager(repository=goal_repo)


@pytest.fixture
def source_agent_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="agent-general",
        version=AgentVersion(major=1, minor=0, patch=0),
        name="General Agent",
        description="General purpose agent",
        kind=AgentKind.GENERAL,
        factory_id="default",
        capabilities=(
            AgentCapability(
                name="delegate",
                kind=AgentCapabilityKind.OPERATION,
                description="Can delegate tasks",
                metadata={"supported_goal_kinds": ["task", "analysis"]},
            ),
        ),
        lifecycle=AgentLifecycle.ACTIVE,
        created_at=datetime.now(timezone.utc),
        required_permissions=("read", "write", "delegate"),
        metadata=MappingProxyType({"autonomy_level": 3}),
    )


@pytest.fixture
def target_agent_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="agent-project",
        version=AgentVersion(major=1, minor=0, patch=0),
        name="Project Agent",
        description="Project-specific agent",
        kind=AgentKind.DOMAIN,
        factory_id="default",
        capabilities=(
            AgentCapability(
                name="execute_task",
                kind=AgentCapabilityKind.OPERATION,
                description="Can execute project tasks",
                metadata={
                    "supported_goal_kinds": ["transformation", "task", "analysis"]
                },
            ),
        ),
        lifecycle=AgentLifecycle.ACTIVE,
        created_at=datetime.now(timezone.utc),
        required_permissions=("read", "write"),
        metadata=MappingProxyType({"autonomy_level": 2}),
    )


@pytest.fixture
def parent_goal() -> Goal:
    return Goal(
        id="goal-123",
        title="Parent Goal",
        description="Main goal to delegate from",
        kind=GoalKind.TRANSFORMATION,
        status=GoalStatus.IN_PROGRESS,
        priority=GoalPriority(score=75, urgency=50, importance=70),
        urgency=50,
        importance=70,
        value=80,
        confidence=0.9,
        assigned_agent_id="agent-general",
        autonomy_level=3,
        permissions=("read", "write", "delegate"),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def delegation_service(
    agent_store: InMemoryAgentRegistryStore,
    goal_repo: InMemoryGoalRepository,
    event_bus: AgentRuntimeEventBus,
    registry_service: AgentRegistryService,
    goal_manager: GoalManager,
    source_agent_descriptor: AgentDescriptor,
    target_agent_descriptor: AgentDescriptor,
) -> AgentDelegationService:
    # Register agents in registry
    registry_service.register_agent(source_agent_descriptor)
    registry_service.register_agent(target_agent_descriptor)

    store = InMemoryAgentDelegationStore()
    return AgentDelegationService(
        store=store,
        registry_service=registry_service,
        goal_manager=goal_manager,
        goal_repository=goal_repo,
        event_bus=event_bus,
    )


@pytest.fixture
def delegation_proposal() -> DelegationProposal:
    return DelegationProposal(
        parent_goal_id="goal-123",
        target_agent_id="agent-project",
        child_goal_kind=GoalKind.TRANSFORMATION,
        child_goal_title="Sub-task for project",
        child_goal_description="Execute project sub-task",
        expected_result=MappingProxyType({"output": "completed"}),
        source_agent_id="agent-general",
        depth=0,
    )


# ── Contract Tests ───────────────────────────────────────────────────────────


class TestDelegationStatus:
    """Test DelegationStatus enum."""

    def test_all_statuses_exist(self) -> None:
        expected = {
            "proposed",
            "accepted",
            "active",
            "waiting",
            "completed",
            "failed",
            "cancelled",
            "rejected",
            "expired",
        }
        actual = {s.value for s in DelegationStatus}
        assert actual == expected

    def test_is_terminal_property(self) -> None:
        assert DelegationStatus.COMPLETED.is_terminal
        assert DelegationStatus.FAILED.is_terminal
        assert DelegationStatus.CANCELLED.is_terminal
        assert DelegationStatus.REJECTED.is_terminal
        assert DelegationStatus.EXPIRED.is_terminal
        assert not DelegationStatus.PROPOSED.is_terminal
        assert not DelegationStatus.ACCEPTED.is_terminal
        assert not DelegationStatus.ACTIVE.is_terminal
        assert not DelegationStatus.WAITING.is_terminal

    def test_is_active_property(self) -> None:
        assert DelegationStatus.ACCEPTED.is_active
        assert DelegationStatus.ACTIVE.is_active
        assert DelegationStatus.WAITING.is_active
        assert not DelegationStatus.PROPOSED.is_active
        assert not DelegationStatus.COMPLETED.is_active
        assert not DelegationStatus.FAILED.is_active


class TestDelegationEventType:
    """Test DelegationEventType enum."""

    def test_all_event_types_exist(self) -> None:
        expected = {
            "agent.delegation.proposed",
            "agent.delegation.accepted",
            "agent.delegation.rejected",
            "agent.delegation.started",
            "agent.delegation.waiting",
            "agent.delegation.completed",
            "agent.delegation.failed",
            "agent.delegation.cancelled",
            "agent.delegation.result_received",
        }
        actual = {e.value for e in DelegationEventType}
        assert actual == expected


class TestDelegatedGoalContract:
    """Test DelegatedGoal contract validation."""

    def test_valid_delegation(self, parent_goal: Goal) -> None:
        child_goal = Goal(
            id=f"goal-{uuid.uuid4().hex[:12]}",
            title="Child Goal",
            description="Child goal for delegation",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.PROPOSED,
            priority=parent_goal.priority,
            parent_goal_id=parent_goal.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        now = datetime.now(timezone.utc)
        delegation = DelegatedGoal(
            id=f"del-{uuid.uuid4().hex[:12]}",
            parent_goal_id=parent_goal.id,
            child_goal_id=child_goal.id,
            source_agent_id="agent-general",
            target_agent_id="agent-project",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.PROPOSED,
            created_at=now,
            updated_at=now,
            depth=0,
        )
        assert delegation.id.startswith("del-")
        assert delegation.parent_goal_id == parent_goal.id
        assert delegation.child_goal_id == child_goal.id
        assert delegation.status == DelegationStatus.PROPOSED
        assert not delegation.is_terminal
        assert delegation.is_active == False  # PROPOSED is not active

    def test_self_reference_rejected(self) -> None:
        """Delegation with same parent and child goal ID should be rejected."""
        with pytest.raises(AgentDelegationValidationError):
            DelegatedGoal(
                id="del-123",
                parent_goal_id="goal-123",
                child_goal_id="goal-123",  # Same as parent
                source_agent_id="agent-general",
                target_agent_id="agent-project",
                source_agent_run_id=None,
                target_agent_run_id=None,
                expected_result=MappingProxyType({}),
                constraints=(),
                status=DelegationStatus.PROPOSED,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_same_agent_rejected(self) -> None:
        """Delegation to same agent should be rejected."""
        with pytest.raises(AgentDelegationValidationError):
            DelegatedGoal(
                id="del-123",
                parent_goal_id="goal-123",
                child_goal_id="goal-456",
                source_agent_id="agent-general",
                target_agent_id="agent-general",  # Same as source
                source_agent_run_id=None,
                target_agent_run_id=None,
                expected_result=MappingProxyType({}),
                constraints=(),
                status=DelegationStatus.PROPOSED,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

    def test_depth_limit(self) -> None:
        """Delegation depth exceeding max should be rejected."""
        with pytest.raises(AgentDelegationValidationError):
            DelegatedGoal(
                id="del-123",
                parent_goal_id="goal-123",
                child_goal_id="goal-456",
                source_agent_id="agent-general",
                target_agent_id="agent-project",
                source_agent_run_id=None,
                target_agent_run_id=None,
                expected_result=MappingProxyType({}),
                constraints=(),
                status=DelegationStatus.PROPOSED,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                depth=11,  # Exceeds max of 10
            )


class TestDelegationProposalContract:
    """Test DelegationProposal contract validation."""

    def test_valid_proposal(self) -> None:
        proposal = DelegationProposal(
            parent_goal_id="goal-123",
            target_agent_id="agent-project",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task",
            child_goal_description="Execute sub-task",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-general",
            depth=0,
        )
        assert proposal.parent_goal_id == "goal-123"
        assert proposal.target_agent_id == "agent-project"
        assert proposal.child_goal_kind == GoalKind.TRANSFORMATION

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(AgentRuntimeError):
            DelegationProposal(
                parent_goal_id="goal-123",
                target_agent_id="agent-project",
                child_goal_kind=GoalKind.TRANSFORMATION,
                child_goal_title="",  # Empty
                child_goal_description="Execute sub-task",
                expected_result=MappingProxyType({}),
            )


class TestDelegationResultContract:
    """Test DelegationResult contract."""

    def test_is_success_property(self) -> None:
        result = DelegationResult(
            delegation_id="del-123",
            parent_goal_id="goal-123",
            child_goal_id="goal-456",
            delegated_run_id="run-123",
            status=DelegationStatus.COMPLETED,
            agent_result_id="ar-123",
            outputs=("result1",),
            knowledge_ids=("k1",),
            artifacts=("a1",),
            warnings=(),
            errors=(),
            completed_at=datetime.now(timezone.utc),
        )
        assert result.is_success
        assert not result.is_partial
        assert not result.is_failure
        assert not result.is_cancelled
        assert not result.is_invalid
        assert not result.is_pending

    def test_is_partial_with_warnings(self) -> None:
        result = DelegationResult(
            delegation_id="del-123",
            parent_goal_id="goal-123",
            child_goal_id="goal-456",
            delegated_run_id="run-123",
            status=DelegationStatus.COMPLETED,
            agent_result_id="ar-123",
            outputs=("result1",),
            knowledge_ids=(),
            artifacts=(),
            warnings=("warning1",),  # Has warning
            errors=(),
            completed_at=datetime.now(timezone.utc),
        )
        assert result.is_partial
        assert result.is_success

    def test_is_invalid_with_errors(self) -> None:
        result = DelegationResult(
            delegation_id="del-123",
            parent_goal_id="goal-123",
            child_goal_id="goal-456",
            delegated_run_id="run-123",
            status=DelegationStatus.COMPLETED,
            agent_result_id="ar-123",
            outputs=(),
            knowledge_ids=(),
            artifacts=(),
            warnings=(),
            errors=("error1",),  # Has error
            completed_at=datetime.now(timezone.utc),
        )
        assert result.is_invalid


# ── Store Tests ──────────────────────────────────────────────────────────────


class TestInMemoryAgentDelegationStore:
    """Test InMemoryAgentDelegationStore."""

    def test_add_and_get(self, parent_goal: Goal) -> None:
        store = InMemoryAgentDelegationStore()
        child_goal = Goal(
            id="goal-456",
            title="Child Goal",
            description="Child goal",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.PROPOSED,
            priority=parent_goal.priority,
            parent_goal_id=parent_goal.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        now = datetime.now(timezone.utc)
        delegation = DelegatedGoal(
            id="del-123",
            parent_goal_id=parent_goal.id,
            child_goal_id=child_goal.id,
            source_agent_id="agent-general",
            target_agent_id="agent-project",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        store.add(delegation)
        retrieved = store.get("del-123")
        assert retrieved is not None
        assert retrieved.id == "del-123"
        assert retrieved.parent_goal_id == parent_goal.id

    def test_duplicate_rejected(self, parent_goal: Goal) -> None:
        store = InMemoryAgentDelegationStore()
        child_goal = Goal(
            id="goal-456",
            title="Child Goal",
            description="Child goal",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.PROPOSED,
            priority=parent_goal.priority,
            parent_goal_id=parent_goal.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        now = datetime.now(timezone.utc)
        delegation = DelegatedGoal(
            id="del-123",
            parent_goal_id=parent_goal.id,
            child_goal_id=child_goal.id,
            source_agent_id="agent-general",
            target_agent_id="agent-project",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        store.add(delegation)
        with pytest.raises(ValueError):
            store.add(delegation)

    def test_list_by_parent_goal(self, parent_goal: Goal) -> None:
        store = InMemoryAgentDelegationStore()
        now = datetime.now(timezone.utc)
        for i in range(3):
            delegation = DelegatedGoal(
                id=f"del-{i}",
                parent_goal_id=parent_goal.id,
                child_goal_id=f"goal-{456 + i}",
                source_agent_id="agent-general",
                target_agent_id="agent-project",
                source_agent_run_id=None,
                target_agent_run_id=None,
                expected_result=MappingProxyType({}),
                constraints=(),
                status=DelegationStatus.PROPOSED,
                created_at=now,
                updated_at=now,
            )
            store.add(delegation)
        result = store.list_by_parent_goal(parent_goal.id)
        assert len(result) == 3

    def test_list_active_by_parent_goal(self, parent_goal: Goal) -> None:
        store = InMemoryAgentDelegationStore()
        child_goal = Goal(
            id="goal-456",
            title="Child Goal",
            description="Child goal",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.PROPOSED,
            priority=parent_goal.priority,
            parent_goal_id=parent_goal.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        now = datetime.now(timezone.utc)
        # Active delegation
        active = DelegatedGoal(
            id="del-active",
            parent_goal_id=parent_goal.id,
            child_goal_id=child_goal.id,
            source_agent_id="agent-general",
            target_agent_id="agent-project",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        # Completed delegation
        completed = DelegatedGoal(
            id="del-completed",
            parent_goal_id=parent_goal.id,
            child_goal_id="goal-789",
            source_agent_id="agent-general",
            target_agent_id="agent-project",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.COMPLETED,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        store.add(active)
        store.add(completed)
        active_list = store.list_active_by_parent_goal(parent_goal.id)
        assert len(active_list) == 1
        assert active_list[0].id == "del-active"

    def test_exists_delegation_between(self, parent_goal: Goal) -> None:
        store = InMemoryAgentDelegationStore()
        child_goal = Goal(
            id="goal-456",
            title="Child Goal",
            description="Child goal",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.PROPOSED,
            priority=parent_goal.priority,
            parent_goal_id=parent_goal.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        now = datetime.now(timezone.utc)
        delegation = DelegatedGoal(
            id="del-123",
            parent_goal_id=parent_goal.id,
            child_goal_id=child_goal.id,
            source_agent_id="agent-general",
            target_agent_id="agent-project",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        store.add(delegation)
        assert store.exists_delegation_between(
            "agent-general", "agent-project", parent_goal.id
        )
        assert not store.exists_delegation_between(
            "agent-project", "agent-general", parent_goal.id
        )


# ── Service Integration Tests ────────────────────────────────────────────────


class TestAgentDelegationService:
    """Integration tests for AgentDelegationService."""

    def test_propose_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        # Setup parent goal
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        assert delegation is not None
        assert delegation.id.startswith("del-")
        assert delegation.status == DelegationStatus.PROPOSED
        assert delegation.parent_goal_id == "goal-123"
        assert delegation.target_agent_id == "agent-project"
        assert delegation.child_goal_id is not None
        # Check child goal was created
        child = goal_repo.get(delegation.child_goal_id)
        assert child is not None
        assert child.parent_goal_id == "goal-123"
        assert child.assigned_agent_id == "agent-project"

    def test_accept_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        accepted = delegation_service.accept(delegation.id)
        assert accepted.status == DelegationStatus.ACCEPTED
        assert accepted.target_agent_run_id is None  # Not provided

    def test_reject_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        rejected = delegation_service.reject(delegation.id, "Target unavailable")
        assert rejected.status == DelegationStatus.REJECTED
        # Child goal should be cancelled
        child = goal_repo.get(delegation.child_goal_id)
        assert child is not None
        assert child.status == GoalStatus.CANCELLED

    def test_start_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        delegation_service.accept(delegation.id)
        started = delegation_service.start(delegation.id)
        assert started.status == DelegationStatus.ACTIVE
        assert started.target_agent_run_id is not None
        assert started.target_agent_run_id.startswith("del-del-")

    def test_complete_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        delegation_service.accept(delegation.id)
        started = delegation_service.start(delegation.id)

        result = DelegationResult(
            delegation_id=delegation.id,
            parent_goal_id=delegation.parent_goal_id,
            child_goal_id=delegation.child_goal_id,
            delegated_run_id=started.target_agent_run_id,
            status=DelegationStatus.COMPLETED,
            agent_result_id=None,
            outputs=("result1",),
            knowledge_ids=("k1",),
            artifacts=("a1",),
            warnings=(),
            errors=(),
            completed_at=datetime.now(timezone.utc),
        )
        completed = delegation_service.complete(delegation.id, result)
        assert completed.status == DelegationStatus.COMPLETED
        # Child goal should be completed
        child = goal_repo.get(delegation.child_goal_id)
        assert child is not None
        assert child.status == GoalStatus.COMPLETED

    def test_fail_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        delegation_service.accept(delegation.id)
        delegation_service.start(delegation.id)

        failed = delegation_service.fail(delegation.id, "Execution error")
        assert failed.status == DelegationStatus.FAILED
        # Child goal should be failed
        child = goal_repo.get(delegation.child_goal_id)
        assert child is not None
        assert child.status == GoalStatus.FAILED

    def test_cancel_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        delegation_service.accept(delegation.id)
        delegation_service.start(delegation.id)

        cancelled = delegation_service.cancel(delegation.id, "User cancelled")
        assert cancelled.status == DelegationStatus.CANCELLED
        # Child goal should be cancelled
        child = goal_repo.get(delegation.child_goal_id)
        assert child is not None
        assert child.status == GoalStatus.CANCELLED

    def test_get_delegation(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        retrieved = delegation_service.get(delegation.id)
        assert retrieved is not None
        assert retrieved.id == delegation.id
        # Non-existent
        assert delegation_service.get("non-existent") is None

    def test_list_for_parent_goal(
        self,
        delegation_service: AgentDelegationService,
        goal_repo: InMemoryGoalRepository,
        source_agent_descriptor: AgentDescriptor,
        target_agent_descriptor: AgentDescriptor,
    ) -> None:
        # Register additional target agents

        target2 = AgentDescriptor(
            agent_id="agent-target-2",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Target 2",
            description="Second target",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="Can execute",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
        )
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)
        delegation_service._registry.register_agent(target2)

        # Create multiple delegations for same parent to different targets
        targets = ["agent-project", "agent-target-2"]
        for i in range(2):
            proposal = DelegationProposal(
                parent_goal_id="goal-123",
                target_agent_id=targets[i],
                child_goal_kind=GoalKind.TRANSFORMATION,
                child_goal_title=f"Sub-task {i}",
                child_goal_description=f"Execute sub-task {i}",
                expected_result=MappingProxyType({"output": "completed"}),
                source_agent_id="agent-general",
                depth=0,
            )
            delegation_service.propose(proposal)

        delegations = delegation_service.list_for_parent_goal("goal-123")
        assert len(delegations) == 2

    def test_waiting_status(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        delegation_service.accept(delegation.id)
        delegation_service.start(delegation.id)

        waiting = delegation_service.waiting(delegation.id)
        assert waiting.status == DelegationStatus.WAITING

    def test_invalid_state_transitions(
        self,
        delegation_service: AgentDelegationService,
        delegation_proposal: DelegationProposal,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        delegation = delegation_service.propose(delegation_proposal)
        # Cannot accept already accepted delegation
        delegation_service.accept(delegation.id)
        with pytest.raises(AgentRuntimeError):
            delegation_service.accept(delegation.id)

        # Cannot start non-accepted delegation (use a new parent goal to avoid duplicate)
        parent_goal2 = Goal(
            id="goal-456",
            title="Parent Goal 2",
            description="Another goal",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal2)
        proposal2 = DelegationProposal(
            parent_goal_id="goal-456",
            target_agent_id="agent-project",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task",
            child_goal_description="Execute sub-task",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-general",
            depth=0,
        )
        delegation2 = delegation_service.propose(proposal2)
        with pytest.raises(AgentRuntimeError):
            delegation_service.start(delegation2.id)

    def test_max_depth_exceeded(
        self,
        goal_repo: InMemoryGoalRepository,
        source_agent_descriptor: AgentDescriptor,
        target_agent_descriptor: AgentDescriptor,
    ) -> None:
        # Create a fresh service with its own registry
        from cmm.agent_runtime.agent_registry import AgentRegistry

        agent_store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=agent_store)
        reg_svc = AgentRegistryService(registry=registry)
        reg_svc.register_agent(source_agent_descriptor)
        reg_svc.register_agent(target_agent_descriptor)

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_repository=goal_repo,
        )

        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        # Create first delegation at depth 0
        proposal0 = DelegationProposal(
            parent_goal_id="goal-123",
            target_agent_id="agent-project",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task 0",
            child_goal_description="Execute sub-task 0",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-general",
            depth=0,
        )
        del0 = svc.propose(proposal0)
        assert del0.depth == 0

        # Try to create delegation at depth 11 (exceeds max of 10)
        with pytest.raises(AgentDelegationValidationError):
            DelegationProposal(
                parent_goal_id=del0.child_goal_id,
                target_agent_id="agent-project",
                child_goal_kind=GoalKind.TRANSFORMATION,
                child_goal_title="Sub-task 11",
                child_goal_description="Execute sub-task 11",
                expected_result=MappingProxyType({"output": "completed"}),
                source_agent_id="agent-general",
                depth=11,
            )

    def test_cycle_detection(
        self,
        goal_repo: InMemoryGoalRepository,
        source_agent_descriptor: AgentDescriptor,
        target_agent_descriptor: AgentDescriptor,
    ) -> None:
        """Test that delegation cycles are detected and rejected."""
        from cmm.agent_runtime.agent_registry import AgentRegistry

        agent_store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=agent_store)
        reg_svc = AgentRegistryService(registry=registry)
        reg_svc.register_agent(source_agent_descriptor)
        reg_svc.register_agent(target_agent_descriptor)

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_repository=goal_repo,
        )

        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        # Create first delegation: general -> project
        proposal1 = DelegationProposal(
            parent_goal_id="goal-123",
            target_agent_id="agent-project",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task 1",
            child_goal_description="Execute sub-task 1",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-general",
            depth=0,
        )
        del1 = svc.propose(proposal1)

        # Try to create reverse delegation: project -> general (would create cycle)
        proposal2 = DelegationProposal(
            parent_goal_id=del1.child_goal_id,
            target_agent_id="agent-general",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task 2",
            child_goal_description="Execute sub-task 2",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-project",
            depth=1,
        )
        with pytest.raises(AgentRuntimeError):
            svc.propose(proposal2)

    def test_duplicate_delegation_rejected(
        self,
        goal_repo: InMemoryGoalRepository,
        source_agent_descriptor: AgentDescriptor,
        target_agent_descriptor: AgentDescriptor,
    ) -> None:
        """Test that duplicate active delegations are rejected."""
        from cmm.agent_runtime.agent_registry import AgentRegistry

        agent_store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=agent_store)
        reg_svc = AgentRegistryService(registry=registry)
        reg_svc.register_agent(source_agent_descriptor)
        reg_svc.register_agent(target_agent_descriptor)

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_repository=goal_repo,
        )

        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        proposal = DelegationProposal(
            parent_goal_id="goal-123",
            target_agent_id="agent-project",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task",
            child_goal_description="Execute sub-task",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-general",
            depth=0,
        )
        svc.propose(proposal)

        # Try to create duplicate delegation
        with pytest.raises(AgentRuntimeError):
            svc.propose(proposal)

    def test_permission_escalation_rejected(
        self,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        """Test that delegating to agent with higher permissions is rejected."""
        from cmm.agent_runtime.agent_registry import AgentRegistry

        agent_store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=agent_store)
        reg_svc = AgentRegistryService(registry=registry)

        # Source has only "read" permission
        source_desc = AgentDescriptor(
            agent_id="agent-general",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="General Agent",
            description="General purpose agent",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="Can delegate tasks",
                    metadata={"supported_goal_kinds": ["task", "analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read",),  # Only read
            metadata=MappingProxyType({"autonomy_level": 3}),
        )
        reg_svc.register_agent(source_desc)

        # Target has more permissions
        target_desc = AgentDescriptor(
            agent_id="agent-project",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Project Agent",
            description="Project-specific agent",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="Can execute project tasks",
                    metadata={"supported_goal_kinds": ["task"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write", "admin"),  # More permissions
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        reg_svc.register_agent(target_desc)

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_repository=goal_repo,
        )

        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=3,
            permissions=("read",),  # Only read permission
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        proposal = DelegationProposal(
            parent_goal_id="goal-123",
            target_agent_id="agent-project",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task",
            child_goal_description="Execute sub-task",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-general",
            depth=0,
        )
        with pytest.raises(AgentRuntimeError):
            svc.propose(proposal)

    def test_autonomy_escalation_rejected(
        self,
        goal_repo: InMemoryGoalRepository,
    ) -> None:
        """Test that delegating to agent with higher autonomy is rejected."""
        from cmm.agent_runtime.agent_registry import AgentRegistry

        agent_store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=agent_store)
        reg_svc = AgentRegistryService(registry=registry)

        # Source has lower autonomy
        source_desc = AgentDescriptor(
            agent_id="agent-general",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="General Agent",
            description="General purpose agent",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="Can delegate tasks",
                    metadata={"supported_goal_kinds": ["task", "analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write", "delegate"),
            metadata=MappingProxyType({"autonomy_level": 2}),  # Lower autonomy
        )
        reg_svc.register_agent(source_desc)

        # Target has higher autonomy
        target_desc = AgentDescriptor(
            agent_id="agent-project",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Project Agent",
            description="Project-specific agent",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="Can execute project tasks",
                    metadata={"supported_goal_kinds": ["task"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 4}),  # Higher autonomy
        )
        reg_svc.register_agent(target_desc)

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_repository=goal_repo,
        )

        parent_goal = Goal(
            id="goal-123",
            title="Parent Goal",
            description="Main goal to delegate from",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-general",
            autonomy_level=2,  # Lower autonomy
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        goal_repo.add(parent_goal)

        proposal = DelegationProposal(
            parent_goal_id="goal-123",
            target_agent_id="agent-project",
            child_goal_kind=GoalKind.TRANSFORMATION,
            child_goal_title="Sub-task",
            child_goal_description="Execute sub-task",
            expected_result=MappingProxyType({"output": "completed"}),
            source_agent_id="agent-general",
            depth=0,
        )
        with pytest.raises(AgentRuntimeError):
            svc.propose(proposal)
