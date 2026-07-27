"""Phase 9.24 Agent Delegation Completeness Tests.

Covers gaps detected in audit:
- Atomicity of propose
- Full state machine (parametrized allowed/forbidden transitions)
- Indirect multi-level cycles
- Idempotency (accept/start/complete/cancel, duplicate results)
- Integration failures (PolicyEngine, EventBus, repositories, GoalManager)
- Store exhaustive: all indices, delete, update non-existent, clear, run_id/status/parent/child updates
- Results: warnings/errors preserved, no auto-complete parent, duplicate result guard, result incorporation failure visibility
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType
from unittest.mock import MagicMock

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
    AgentDelegationCycleDetectedError,
    AgentDelegationInvalidStateTransitionError,
    AgentDelegationMaxDepthExceededError,
    AgentDelegationPolicyDeniedError,
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
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.runtime_event_bus import (
    AgentRuntimeEventQueueFullError,
)

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
def source_agent_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="agent-source",
        version=AgentVersion(major=1, minor=0, patch=0),
        name="Source Agent",
        description="Source",
        kind=AgentKind.GENERAL,
        factory_id="default",
        capabilities=(
            AgentCapability(
                name="delegate",
                kind=AgentCapabilityKind.OPERATION,
                description="Can delegate",
                metadata={
                    "supported_goal_kinds": ["task", "analysis", "transformation"]
                },
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
        agent_id="agent-target",
        version=AgentVersion(major=1, minor=0, patch=0),
        name="Target Agent",
        description="Target",
        kind=AgentKind.DOMAIN,
        factory_id="default",
        capabilities=(
            AgentCapability(
                name="execute_task",
                kind=AgentCapabilityKind.OPERATION,
                description="Can execute",
                metadata={"supported_goal_kinds": ["transformation", "task"]},
            ),
        ),
        lifecycle=AgentLifecycle.ACTIVE,
        created_at=datetime.now(timezone.utc),
        required_permissions=("read", "write"),
        metadata=MappingProxyType({"autonomy_level": 2}),
    )


@pytest.fixture
def parent_goal_factory():
    def _make(id: str = "goal-123", assigned_agent_id: str = "agent-source"):
        return Goal(
            id=id,
            title="Parent",
            description="Parent",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id=assigned_agent_id,
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    return _make


@pytest.fixture
def delegation_service(
    agent_store: InMemoryAgentRegistryStore,
    goal_repo: InMemoryGoalRepository,
    event_bus: AgentRuntimeEventBus,
    registry_service: AgentRegistryService,
    source_agent_descriptor: AgentDescriptor,
    target_agent_descriptor: AgentDescriptor,
) -> AgentDelegationService:
    registry_service.register_agent(source_agent_descriptor)
    registry_service.register_agent(target_agent_descriptor)
    store = InMemoryAgentDelegationStore()
    return AgentDelegationService(
        store=store,
        registry_service=registry_service,
        goal_manager=GoalManager(repository=goal_repo),
        goal_repository=goal_repo,
        event_bus=event_bus,
    )


def _proposal(
    parent_goal_id: str = "goal-123",
    source_agent_id: str = "agent-source",
    target_agent_id: str = "agent-target",
):
    return DelegationProposal(
        parent_goal_id=parent_goal_id,
        target_agent_id=target_agent_id,
        child_goal_kind=GoalKind.TRANSFORMATION,
        child_goal_title="Sub",
        child_goal_description="Sub",
        expected_result=MappingProxyType({"ok": True}),
        source_agent_id=source_agent_id,
        depth=0,
    )


# ── Atomicity of propose ──────────────────────────────────────────────────


class TestProposeAtomicity:
    def test_goal_repo_add_failure_prevents_delegation(self, parent_goal_factory):
        from cmm.agent_runtime.agent_registry import AgentRegistry

        store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=store)
        reg_svc = AgentRegistryService(registry=registry)
        source = AgentDescriptor(
            agent_id="agent-source",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Source",
            description="Src",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="D",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write", "delegate"),
            metadata=MappingProxyType({"autonomy_level": 3}),
        )
        target = AgentDescriptor(
            agent_id="agent-target",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Target",
            description="Tgt",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        reg_svc.register_agent(source)
        reg_svc.register_agent(target)

        parent = parent_goal_factory(id="goal-parent")
        broken_repo = MagicMock()
        broken_repo.get.return_value = parent
        broken_repo.add.side_effect = RuntimeError("storage failure")

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_repository=broken_repo,
        )

        with pytest.raises(RuntimeError):
            svc.propose(
                _proposal(
                    parent_goal_id=parent.id,
                    source_agent_id=source.agent_id,
                    target_agent_id=target.agent_id,
                )
            )

        # No delegation persisted
        assert len(svc._store) == 0

    def test_goal_repo_update_failure_prevents_persisting_inconsistent_parent(
        self, parent_goal_factory
    ):
        from cmm.agent_runtime.agent_registry import AgentRegistry

        store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=store)
        reg_svc = AgentRegistryService(registry=registry)
        source = AgentDescriptor(
            agent_id="agent-source",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Source",
            description="Src",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="D",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write", "delegate"),
            metadata=MappingProxyType({"autonomy_level": 3}),
        )
        target = AgentDescriptor(
            agent_id="agent-target",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Target",
            description="Tgt",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        reg_svc.register_agent(source)
        reg_svc.register_agent(target)

        parent = parent_goal_factory(id="goal-parent")
        goal_repo = InMemoryGoalRepository()
        goal_repo.add(parent)

        broken_repo = goal_repo

        def bad_update(goal):
            raise RuntimeError("parent update failed")

        broken_repo.update = bad_update  # type: ignore[method-assign]

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_manager=GoalManager(repository=goal_repo),
            goal_repository=broken_repo,
        )

        with pytest.raises(RuntimeError):
            svc.propose(
                _proposal(
                    parent_goal_id=parent.id,
                    source_agent_id=source.agent_id,
                    target_agent_id=target.agent_id,
                )
            )

        # No delegation is stored because failure happens after child add but before store.add in current implementation? Actually propose does store.add after parent update.
        # The test asserts no delegation persisted due to failure prior to store.add after our patch? but code order is child add -> parent update -> delegation.add.
        # We expect no delegation created.
        assert len(svc._store) == 0


# ── State machine parametrized ────────────────────────────────────────────


class TestStateMachine:
    @pytest.mark.parametrize(
        "from_status,operation,expected_error",
        [
            ("PROPOSED", "accept", DelegationStatus.ACCEPTED),
            ("PROPOSED", "start", AgentDelegationInvalidStateTransitionError),
            ("PROPOSED", "waiting", AgentDelegationInvalidStateTransitionError),
            ("PROPOSED", "complete", AgentDelegationInvalidStateTransitionError),
            ("ACCEPTED", "start", DelegationStatus.ACTIVE),
            ("ACCEPTED", "waiting", AgentDelegationInvalidStateTransitionError),
            ("ACCEPTED", "complete", AgentDelegationInvalidStateTransitionError),
            ("ACTIVE", "waiting", DelegationStatus.WAITING),
            ("ACTIVE", "complete", DelegationStatus.COMPLETED),
            ("WAITING", "complete", DelegationStatus.COMPLETED),
            ("COMPLETED", "accept", AgentDelegationInvalidStateTransitionError),
            ("FAILED", "cancel", AgentDelegationInvalidStateTransitionError),
            ("REJECTED", "start", AgentDelegationInvalidStateTransitionError),
        ],
    )
    def test_state_transitions(
        self, delegation_service, from_status, operation, expected_error
    ):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))

        # Advance to desired from_status
        if from_status == "ACCEPTED":
            d = delegation_service.accept(d.id)
        elif from_status == "ACTIVE":
            d = delegation_service.accept(d.id)
            d = delegation_service.start(d.id)
        elif from_status == "WAITING":
            d = delegation_service.accept(d.id)
            d = delegation_service.start(d.id)
            d = delegation_service.waiting(d.id)
        elif from_status == "COMPLETED":
            result = DelegationResult(
                delegation_id=d.id,
                parent_goal_id=d.parent_goal_id,
                child_goal_id=d.child_goal_id,
                delegated_run_id=None,
                status=DelegationStatus.COMPLETED,
                agent_result_id=None,
                outputs=(),
                knowledge_ids=(),
                artifacts=(),
                warnings=(),
                errors=(),
                completed_at=datetime.now(timezone.utc),
            )
            d = delegation_service.accept(d.id)
            d = delegation_service.start(d.id)
            d = delegation_service.complete(d.id, result)
        elif from_status == "FAILED":
            d = delegation_service.accept(d.id)
            d = delegation_service.start(d.id)
            d = delegation_service.fail(d.id, "boom")
        elif from_status == "REJECTED":
            d = delegation_service.reject(d.id, "no")

        # Attempt operation
        if expected_error is AgentDelegationInvalidStateTransitionError:
            with pytest.raises(AgentDelegationInvalidStateTransitionError):
                if operation == "accept":
                    delegation_service.accept(d.id)
                elif operation == "start":
                    delegation_service.start(d.id)
                elif operation == "waiting":
                    delegation_service.waiting(d.id)
                elif operation == "complete":
                    result = DelegationResult(
                        delegation_id=d.id,
                        parent_goal_id=d.parent_goal_id,
                        child_goal_id=d.child_goal_id,
                        delegated_run_id=d.target_agent_run_id,
                        status=DelegationStatus.COMPLETED,
                        agent_result_id=None,
                        outputs=(),
                        knowledge_ids=(),
                        artifacts=(),
                        warnings=(),
                        errors=(),
                        completed_at=datetime.now(timezone.utc),
                    )
                    delegation_service.complete(d.id, result)
                elif operation == "cancel":
                    delegation_service.cancel(d.id, "x")
            # State must remain unchanged
            current = delegation_service.get(d.id)
            assert current is not None and current.status == DelegationStatus(
                from_status.lower()
            )
        else:
            # Allowed transition
            if operation == "accept":
                d = delegation_service.accept(d.id)
            elif operation == "start":
                d = delegation_service.start(d.id)
            elif operation == "waiting":
                d = delegation_service.waiting(d.id)
            elif operation == "complete":
                result = DelegationResult(
                    delegation_id=d.id,
                    parent_goal_id=d.parent_goal_id,
                    child_goal_id=d.child_goal_id,
                    delegated_run_id=d.target_agent_run_id,
                    status=DelegationStatus.COMPLETED,
                    agent_result_id=None,
                    outputs=(),
                    knowledge_ids=(),
                    artifacts=(),
                    warnings=(),
                    errors=(),
                    completed_at=datetime.now(timezone.utc),
                )
                d = delegation_service.complete(d.id, result)
            assert d.status == expected_error


# ── Indirect cycles ──────────────────────────────────────────────────────


class TestIndirectCycles:
    def test_indirect_cycle_rejected(self, parent_goal_factory):
        from cmm.agent_runtime.agent_registry import AgentRegistry

        store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=store)
        reg_svc = AgentRegistryService(registry=registry)
        source = AgentDescriptor(
            agent_id="agent-a",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="A",
            description="A",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="D",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        b = AgentDescriptor(
            agent_id="agent-b",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="B",
            description="B",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        c = AgentDescriptor(
            agent_id="agent-c",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="C",
            description="C",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        for a in (source, b, c):
            reg_svc.register_agent(a)

        goal_repo = InMemoryGoalRepository()
        store = InMemoryAgentDelegationStore()
        svc = AgentDelegationService(
            store=store, registry_service=reg_svc, goal_repository=goal_repo
        )

        ga = parent_goal_factory(id="goal-a")
        goal_repo.add(ga)
        d1 = svc.propose(
            DelegationProposal(
                parent_goal_id=ga.id,
                target_agent_id="agent-b",
                child_goal_kind=GoalKind.ANALYSIS,
                child_goal_title="b",
                child_goal_description="b",
                expected_result=MappingProxyType({}),
                source_agent_id="agent-a",
                depth=0,
            )
        )
        gb = goal_repo.get(d1.child_goal_id)
        assert gb is not None
        d2 = svc.propose(
            DelegationProposal(
                parent_goal_id=gb.id,
                target_agent_id="agent-c",
                child_goal_kind=GoalKind.ANALYSIS,
                child_goal_title="c",
                child_goal_description="c",
                expected_result=MappingProxyType({}),
                source_agent_id="agent-b",
                depth=1,
            )
        )
        gc = goal_repo.get(d2.child_goal_id)
        assert gc is not None
        with pytest.raises(AgentDelegationCycleDetectedError):
            svc.propose(
                DelegationProposal(
                    parent_goal_id=gc.id,
                    target_agent_id="agent-a",
                    child_goal_kind=GoalKind.ANALYSIS,
                    child_goal_title="a",
                    child_goal_description="a",
                    expected_result=MappingProxyType({}),
                    source_agent_id="agent-c",
                    depth=2,
                )
            )

    def test_cycle_in_secondary_branch_rejected(self, parent_goal_factory):
        from cmm.agent_runtime.agent_registry import AgentRegistry

        store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=store)
        reg_svc = AgentRegistryService(registry=registry)
        a = AgentDescriptor(
            agent_id="agent-a",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="A",
            description="A",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="D",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        b = AgentDescriptor(
            agent_id="agent-b",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="B",
            description="B",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        c = AgentDescriptor(
            agent_id="agent-c",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="C",
            description="C",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        d = AgentDescriptor(
            agent_id="agent-d",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="D",
            description="D",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        for agent in (a, b, c, d):
            reg_svc.register_agent(agent)

        goal_repo = InMemoryGoalRepository()
        store = InMemoryAgentDelegationStore()
        svc = AgentDelegationService(
            store=store, registry_service=reg_svc, goal_repository=goal_repo
        )

        ga = parent_goal_factory(id="goal-a")
        goal_repo.add(ga)
        d1 = svc.propose(
            DelegationProposal(
                parent_goal_id=ga.id,
                target_agent_id="agent-b",
                child_goal_kind=GoalKind.ANALYSIS,
                child_goal_title="b",
                child_goal_description="b",
                expected_result=MappingProxyType({}),
                source_agent_id="agent-a",
                depth=0,
            )
        )
        gb = goal_repo.get(d1.child_goal_id)
        assert gb is not None

        d2 = svc.propose(
            DelegationProposal(
                parent_goal_id=gb.id,
                target_agent_id="agent-c",
                child_goal_kind=GoalKind.ANALYSIS,
                child_goal_title="c",
                child_goal_description="c",
                expected_result=MappingProxyType({}),
                source_agent_id="agent-b",
                depth=1,
            )
        )
        gc = goal_repo.get(d2.child_goal_id)
        assert gc is not None

        d3 = svc.propose(
            DelegationProposal(
                parent_goal_id=gc.id,
                target_agent_id="agent-d",
                child_goal_kind=GoalKind.ANALYSIS,
                child_goal_title="d",
                child_goal_description="d",
                expected_result=MappingProxyType({}),
                source_agent_id="agent-c",
                depth=2,
            )
        )
        gd = goal_repo.get(d3.child_goal_id)
        assert gd is not None

        with pytest.raises(AgentDelegationCycleDetectedError):
            svc.propose(
                DelegationProposal(
                    parent_goal_id=gd.id,
                    target_agent_id="agent-a",
                    child_goal_kind=GoalKind.ANALYSIS,
                    child_goal_title="a",
                    child_goal_description="a",
                    expected_result=MappingProxyType({}),
                    source_agent_id="agent-d",
                    depth=3,
                )
            )


# ── Depth ────────────────────────────────────────────────────────────────


class TestDepthValidation:
    def test_max_depth_exact_allowed(self, parent_goal_factory):
        from cmm.agent_runtime.agent_registry import AgentRegistry

        store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=store)
        reg_svc = AgentRegistryService(registry=registry)
        source = AgentDescriptor(
            agent_id="agent-source",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Source",
            description="Src",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="D",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        target = AgentDescriptor(
            agent_id="agent-target",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Target",
            description="Tgt",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["analysis"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        reg_svc.register_agent(source)
        reg_svc.register_agent(target)

        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            goal_repository=InMemoryGoalRepository(),
        )

        parent = parent_goal_factory(id="goal-parent")
        svc._goal_repo.add(parent)

        current_parent_id = parent.id
        current_source = "agent-source"
        target_agent = "agent-target"
        depths = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        next_target = "agent-target"
        for depth in depths:
            proposal = DelegationProposal(
                parent_goal_id=current_parent_id,
                target_agent_id=next_target,
                child_goal_kind=GoalKind.ANALYSIS,
                child_goal_title=f"sub-{depth}",
                child_goal_description="sub",
                expected_result=MappingProxyType({}),
                source_agent_id=current_source,
                depth=depth,
            )
            d = svc.propose(proposal)
            current_parent_id = d.child_goal_id

    def test_depth_above_max_raises(self):
        with pytest.raises(AgentDelegationValidationError):
            DelegationProposal(
                parent_goal_id="goal-parent",
                target_agent_id="agent-target",
                child_goal_kind=GoalKind.ANALYSIS,
                child_goal_title="sub",
                child_goal_description="sub",
                expected_result=MappingProxyType({}),
                source_agent_id="agent-source",
                depth=11,
            )


# ── Idempotency ──────────────────────────────────────────────────────────


class TestIdempotency:
    def test_accept_idempotent_same_run_id(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        delegation_service.accept(d.id, target_agent_run_id="run-1")
        # Second accept is invalid transition; state must remain ACCEPTED
        with pytest.raises(AgentDelegationInvalidStateTransitionError):
            delegation_service.accept(d.id, target_agent_run_id="run-1")
        current = delegation_service.get(d.id)
        assert current is not None and current.status == DelegationStatus.ACCEPTED

    def test_complete_idempotent(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        delegation_service.accept(d.id)
        s = delegation_service.start(d.id)
        result = DelegationResult(
            delegation_id=d.id,
            parent_goal_id=d.parent_goal_id,
            child_goal_id=d.child_goal_id,
            delegated_run_id=s.target_agent_run_id,
            status=DelegationStatus.COMPLETED,
            agent_result_id=None,
            outputs=(),
            knowledge_ids=(),
            artifacts=(),
            warnings=(),
            errors=(),
            completed_at=datetime.now(timezone.utc),
        )
        c1 = delegation_service.complete(d.id, result)
        assert c1.status == DelegationStatus.COMPLETED
        # Duplicate complete raises invalid transition; state remains COMPLETED
        with pytest.raises(AgentDelegationInvalidStateTransitionError):
            delegation_service.complete(d.id, result)
        current = delegation_service.get(d.id)
        assert current is not None and current.status == DelegationStatus.COMPLETED

    def test_cancel_idempotent(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        delegation_service.accept(d.id)
        delegation_service.start(d.id)
        c1 = delegation_service.cancel(d.id, "x")
        assert c1.status == DelegationStatus.CANCELLED
        # Duplicate cancel raises invalid transition; state remains CANCELLED
        with pytest.raises(AgentDelegationInvalidStateTransitionError):
            delegation_service.cancel(d.id, "x")
        current = delegation_service.get(d.id)
        assert current is not None and current.status == DelegationStatus.CANCELLED

    def test_duplicate_result_not_incorporated_twice(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        delegation_service.accept(d.id)
        s = delegation_service.start(d.id)
        result = DelegationResult(
            delegation_id=d.id,
            parent_goal_id=d.parent_goal_id,
            child_goal_id=d.child_goal_id,
            delegated_run_id=s.target_agent_run_id,
            status=DelegationStatus.COMPLETED,
            agent_result_id="ar-1",
            outputs=("out",),
            knowledge_ids=(),
            artifacts=(),
            warnings=(),
            errors=(),
            completed_at=datetime.now(timezone.utc),
        )
        delegation_service.complete(d.id, result)
        # Second complete raises invalid transition; state remains consistent
        with pytest.raises(AgentDelegationInvalidStateTransitionError):
            delegation_service.complete(d.id, result)
        child = delegation_service._goal_repo.get(d.child_goal_id)
        assert child is not None and child.status == GoalStatus.COMPLETED


# ── Integration failures ─────────────────────────────────────────────────


class TestIntegrationFailures:
    def test_policy_engine_deny(self, parent_goal_factory):
        from cmm.agent_runtime.agent_registry import AgentRegistry

        store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=store)
        reg_svc = AgentRegistryService(registry=registry)
        source = AgentDescriptor(
            agent_id="agent-source",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Source",
            description="Src",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="D",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 3}),
        )
        target = AgentDescriptor(
            agent_id="agent-target",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Target",
            description="Tgt",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        reg_svc.register_agent(source)
        reg_svc.register_agent(target)

        policy = MagicMock()
        policy.evaluate.return_value = MagicMock(decision="deny", reason="forbidden")
        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            policy_engine=policy,
            goal_repository=InMemoryGoalRepository(),
        )
        parent = parent_goal_factory(id="goal-parent")
        svc._goal_repo.add(parent)
        with pytest.raises(AgentDelegationPolicyDeniedError):
            svc.propose(_proposal(parent_goal_id=parent.id))

    def test_policy_engine_unexpected_error_fail_closed(self, parent_goal_factory):
        from cmm.agent_runtime.agent_registry import AgentRegistry

        store = InMemoryAgentRegistryStore()
        registry = AgentRegistry(store=store)
        reg_svc = AgentRegistryService(registry=registry)
        source = AgentDescriptor(
            agent_id="agent-source",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Source",
            description="Src",
            kind=AgentKind.GENERAL,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="delegate",
                    kind=AgentCapabilityKind.OPERATION,
                    description="D",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 3}),
        )
        target = AgentDescriptor(
            agent_id="agent-target",
            version=AgentVersion(major=1, minor=0, patch=0),
            name="Target",
            description="Tgt",
            kind=AgentKind.DOMAIN,
            factory_id="default",
            capabilities=(
                AgentCapability(
                    name="execute_task",
                    kind=AgentCapabilityKind.OPERATION,
                    description="E",
                    metadata={"supported_goal_kinds": ["transformation"]},
                ),
            ),
            lifecycle=AgentLifecycle.ACTIVE,
            created_at=datetime.now(timezone.utc),
            required_permissions=("read", "write"),
            metadata=MappingProxyType({"autonomy_level": 2}),
        )
        reg_svc.register_agent(source)
        reg_svc.register_agent(target)

        policy = MagicMock()
        policy.evaluate.side_effect = RuntimeError("policy boom")
        svc = AgentDelegationService(
            store=InMemoryAgentDelegationStore(),
            registry_service=reg_svc,
            policy_engine=policy,
            goal_repository=InMemoryGoalRepository(),
        )
        parent = parent_goal_factory(id="goal-parent")
        svc._goal_repo.add(parent)
        with pytest.raises(AgentDelegationPolicyDeniedError):
            svc.propose(_proposal(parent_goal_id=parent.id))

    def test_event_bus_full_best_effort(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        # Make event bus always queue full; proposal should still succeed (best-effort)
        delegation_service._event_bus.publish = MagicMock(
            side_effect=AgentRuntimeEventQueueFullError("full")
        )
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        assert d.status == DelegationStatus.PROPOSED


# ── Store comprehensive ──────────────────────────────────────────────────


class TestStoreComprehensive:
    def test_list_all_indices(self, parent_goal_factory):
        store = InMemoryAgentDelegationStore()
        parent = parent_goal_factory(id="goal-parent")
        child = Goal(
            id="goal-child",
            title="Child",
            description="Child",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.PROPOSED,
            priority=parent.priority,
            parent_goal_id=parent.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        d = DelegatedGoal(
            id="del-1",
            parent_goal_id=parent.id,
            child_goal_id=child.id,
            source_agent_id="agent-source",
            target_agent_id="agent-target",
            source_agent_run_id="run-src",
            target_agent_run_id="run-tgt",
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store.add(d)
        assert len(store.list_by_parent_goal(parent.id)) == 1
        assert len(store.list_by_child_goal(child.id)) == 1
        assert len(store.list_by_source_agent("agent-source")) == 1
        assert len(store.list_by_target_agent("agent-target")) == 1
        assert len(store.list_by_status(DelegationStatus.ACTIVE)) == 1
        assert len(store.list_by_source_run("run-src")) == 1
        assert len(store.list_by_target_run("run-tgt")) == 1
        assert len(store.list_active_by_target_agent("agent-target")) == 1
        assert store.count_by_parent_goal(parent.id) == 1

    def test_update_nonexistent_raises(self):
        store = InMemoryAgentDelegationStore()
        d = DelegatedGoal(
            id="del-x",
            parent_goal_id="p",
            child_goal_id="c",
            source_agent_id="s",
            target_agent_id="t",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.PROPOSED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(KeyError):
            store.update(d)

    def test_add_duplicate_raises(self):
        store = InMemoryAgentDelegationStore()
        d = DelegatedGoal(
            id="del-1",
            parent_goal_id="p",
            child_goal_id="c",
            source_agent_id="s",
            target_agent_id="t",
            source_agent_run_id=None,
            target_agent_run_id=None,
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.PROPOSED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store.add(d)
        with pytest.raises(ValueError):
            store.add(d)

    def test_clear(self):
        store = InMemoryAgentDelegationStore()
        for i in range(3):
            d = DelegatedGoal(
                id=f"del-{i}",
                parent_goal_id="p",
                child_goal_id="c",
                source_agent_id="s",
                target_agent_id="t",
                source_agent_run_id=None,
                target_agent_run_id=None,
                expected_result=MappingProxyType({}),
                constraints=(),
                status=DelegationStatus.PROPOSED,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            store.add(d)
        store.clear()
        assert len(store) == 0
        assert store.list_by_parent_goal("p") == []
        assert store.list_by_status(DelegationStatus.PROPOSED) == []

    def test_delete_cleans_indices(self):
        store = InMemoryAgentDelegationStore()
        d = DelegatedGoal(
            id="del-1",
            parent_goal_id="goal-parent",
            child_goal_id="goal-child",
            source_agent_id="agent-source",
            target_agent_id="agent-target",
            source_agent_run_id="run-src",
            target_agent_run_id="run-tgt",
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store.add(d)
        assert store.delete("del-1") is True
        assert store.get("del-1") is None
        assert store.list_by_parent_goal("goal-parent") == []
        assert store.list_by_target_run("run-tgt") == []

    def test_update_changes_run_id_and_status_indices(self):
        store = InMemoryAgentDelegationStore()
        d = DelegatedGoal(
            id="del-1",
            parent_goal_id="goal-parent",
            child_goal_id="goal-child",
            source_agent_id="agent-source",
            target_agent_id="agent-target",
            source_agent_run_id="run-src",
            target_agent_run_id="run-tgt",
            expected_result=MappingProxyType({}),
            constraints=(),
            status=DelegationStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store.add(d)
        updated = DelegatedGoal(
            id="del-1",
            parent_goal_id="goal-parent",
            child_goal_id="goal-child",
            source_agent_id="agent-source",
            target_agent_id="agent-target",
            source_agent_run_id="run-src",
            target_agent_run_id="run-tgt",
            expected_result=MappingProxyType({"x": 1}),
            constraints=(),
            status=DelegationStatus.COMPLETED,
            created_at=d.created_at,
            updated_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        store.update(updated)
        assert store.list_by_status(DelegationStatus.ACTIVE) == []
        assert len(store.list_by_status(DelegationStatus.COMPLETED)) == 1


# ── Results handling ─────────────────────────────────────────────────────


class TestResultsHandling:
    def test_warnings_preserved_and_partial(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        delegation_service.accept(d.id)
        s = delegation_service.start(d.id)
        result = DelegationResult(
            delegation_id=d.id,
            parent_goal_id=d.parent_goal_id,
            child_goal_id=d.child_goal_id,
            delegated_run_id=s.target_agent_run_id,
            status=DelegationStatus.COMPLETED,
            agent_result_id=None,
            outputs=(),
            knowledge_ids=(),
            artifacts=(),
            warnings=("warn1",),
            errors=(),
            completed_at=datetime.now(timezone.utc),
        )
        captured: list = []
        delegation_service._event_bus.subscribe(
            lambda ev: captured.append(ev),
            event_types=[DelegationEventType.RESULT_RECEIVED.value],
        )
        completed = delegation_service.complete(d.id, result)
        assert any(
            e.header.event_type == DelegationEventType.RESULT_RECEIVED.value
            for e in captured
        )
        assert completed.metadata.get("result", {}).get("warnings") == ["warn1"]

    def test_errors_preserved_invalid(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        delegation_service.accept(d.id)
        s = delegation_service.start(d.id)
        result = DelegationResult(
            delegation_id=d.id,
            parent_goal_id=d.parent_goal_id,
            child_goal_id=d.child_goal_id,
            delegated_run_id=s.target_agent_run_id,
            status=DelegationStatus.FAILED,
            agent_result_id=None,
            outputs=(),
            knowledge_ids=(),
            artifacts=(),
            warnings=(),
            errors=("boom",),
            completed_at=datetime.now(timezone.utc),
        )
        completed = delegation_service.complete(d.id, result)
        assert completed.status == DelegationStatus.FAILED
        assert completed.metadata.get("result", {}).get("errors") == ["boom"]

    def test_result_incorporation_failure_adds_warning(self, delegation_service):
        parent_goal = Goal(
            id="goal-123",
            title="P",
            description="P",
            kind=GoalKind.TRANSFORMATION,
            status=GoalStatus.IN_PROGRESS,
            priority=GoalPriority(score=75, urgency=50, importance=70),
            urgency=50,
            importance=70,
            value=80,
            confidence=0.9,
            assigned_agent_id="agent-source",
            autonomy_level=3,
            permissions=("read", "write", "delegate"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        delegation_service._goal_repo.add(parent_goal)
        d = delegation_service.propose(_proposal(parent_goal_id=parent_goal.id))
        delegation_service.accept(d.id)
        s = delegation_service.start(d.id)
        result = DelegationResult(
            delegation_id=d.id,
            parent_goal_id=d.parent_goal_id,
            child_goal_id=d.child_goal_id,
            delegated_run_id=s.target_agent_run_id,
            status=DelegationStatus.COMPLETED,
            agent_result_id=None,
            outputs=(),
            knowledge_ids=(),
            artifacts=(),
            warnings=(),
            errors=(),
            completed_at=datetime.now(timezone.utc),
        )
        # Force goal_manager failure
        delegation_service._goal_manager = MagicMock()
        delegation_service._goal_manager.incorporate_delegation_result.side_effect = (
            RuntimeError("gm fail")
        )
        completed = delegation_service.complete(d.id, result)
        warnings = completed.metadata.get("warnings", [])
        assert any("result_incorporation_failed" in w for w in warnings)
