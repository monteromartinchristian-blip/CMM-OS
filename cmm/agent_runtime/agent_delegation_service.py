"""Phase 9.24 Agent Delegation Service."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

from cmm.agent_runtime.agent_delegation_contracts import (
    DelegatedGoal,
    DelegationProposal,
    DelegationResult,
    create_delegation,
)
from cmm.agent_runtime.agent_delegation_enums import (
    DelegationEventType,
    DelegationStatus,
)
from cmm.agent_runtime.agent_delegation_errors import (
    AgentDelegationAgentsIncompatibleError,
    AgentDelegationAutonomyEscalationError,
    AgentDelegationChildGoalIncompatibleError,
    AgentDelegationCycleDetectedError,
    AgentDelegationDuplicateError,
    AgentDelegationInvalidStateTransitionError,
    AgentDelegationMaxDepthExceededError,
    AgentDelegationParentGoalNotFoundError,
    AgentDelegationParentGoalTerminalError,
    AgentDelegationPermissionEscalationError,
    AgentDelegationPolicyDeniedError,
    AgentDelegationSourceAgentNotFoundError,
    AgentDelegationTargetAgentNotFoundError,
    AgentDelegationTargetUnsupportedGoalError,
    AgentDelegationValidationError,
)
from cmm.agent_runtime.agent_delegation_store import (
    AgentDelegationStore,
    InMemoryAgentDelegationStore,
)
from cmm.agent_runtime.agent_registry_contracts import AgentDescriptor, AgentInstance
from cmm.agent_runtime.agent_registry_enums import AgentLifecycle
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import GoalConstraintKind, GoalKind, GoalStatus
from cmm.agent_runtime.goal_contracts import Goal, GoalConstraint
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.runtime_event_bus import (
    AgentRuntimeEventBus,
    AgentRuntimeEventBusClosedError,
    AgentRuntimeEventQueueFullError,
)
from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
)


@runtime_checkable
class AgentFactoryProtocol(Protocol):
    def create(self, descriptor: AgentDescriptor, context: Any) -> AgentInstance: ...


@runtime_checkable
class GoalRepositoryProtocol(Protocol):
    def get(self, goal_id: str) -> Goal | None: ...
    def update(self, goal: Goal) -> None: ...


@runtime_checkable
class AgentRunRepositoryProtocol(Protocol):
    def get(self, run_id: str) -> AgentRun | None: ...
    def add(self, run: AgentRun) -> None: ...
    def update(self, run: AgentRun) -> None: ...


@runtime_checkable
class PolicyEngineProtocol(Protocol):
    def evaluate(
        self,
        subject: str,
        action: str,
        resource: str,
        context: Mapping[str, Any],
    ) -> Any: ...


@runtime_checkable
class ApprovalServiceProtocol(Protocol):
    def request_approval(
        self,
        request_id: str,
        subject: str,
        action: str,
        context: Mapping[str, Any],
    ) -> Any: ...


@runtime_checkable
class ActionBudgetProtocol(Protocol):
    def reserve(
        self,
        agent_id: str,
        action_type: str,
        estimated_cost: float,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class AgentDelegationServiceConfig:
    max_delegation_depth: int = 10
    default_delegation_timeout_seconds: float = 300.0
    require_acceptance: bool = True
    allow_self_delegation: bool = False
    enforce_goal_constraints: bool = True
    emit_events: bool = True


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _generate_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


class AgentDelegationService:
    """
    Service for managing agent-to-agent delegations.

    Provides the full delegation lifecycle: propose, accept, reject, start,
    complete, fail, cancel. Integrates with registry, factory, goals, policies,
    and event bus.
    """

    def __init__(
        self,
        *,
        store: AgentDelegationStore | None = None,
        registry_service: AgentRegistryService | None = None,
        agent_resolver: AgentResolver | None = None,
        goal_manager: GoalManager | None = None,
        goal_repository: GoalRepositoryProtocol | None = None,
        agent_run_repository: AgentRunRepositoryProtocol | None = None,
        factory: AgentFactoryProtocol | None = None,
        policy_engine: PolicyEngineProtocol | None = None,
        approval_service: ApprovalServiceProtocol | None = None,
        action_budget: ActionBudgetProtocol | None = None,
        event_bus: AgentRuntimeEventBus | None = None,
        config: AgentDelegationServiceConfig | None = None,
    ) -> None:
        self._store = store or InMemoryAgentDelegationStore()
        self._registry = registry_service
        self._resolver = agent_resolver
        self._goal_manager = goal_manager
        self._goal_repo = goal_repository
        self._run_repo = agent_run_repository
        self._factory = factory
        self._policy_engine = policy_engine
        self._approval_service = approval_service
        self._action_budget = action_budget
        self._event_bus = event_bus
        self._config = config or AgentDelegationServiceConfig()

    def _validate_source_agent(
        self, agent_id: str, run_id: str | None = None
    ) -> AgentDescriptor:
        """Validate source agent exists and is resolvable."""
        if self._registry is None:
            raise AgentDelegationSourceAgentNotFoundError(
                f"Source agent {agent_id} not found: no registry configured",
                details={"agent_id": agent_id},
            )

        descriptor = self._registry.registry.get(agent_id)
        if descriptor is None:
            raise AgentDelegationSourceAgentNotFoundError(
                f"Source agent {agent_id} not found",
                details={"agent_id": agent_id},
            )

        if descriptor.lifecycle != AgentLifecycle.ACTIVE:
            raise AgentDelegationAgentsIncompatibleError(
                f"Source agent {agent_id} is not active",
                details={"agent_id": agent_id, "lifecycle": descriptor.lifecycle.value},
            )

        if run_id and self._run_repo:
            run = self._run_repo.get(run_id)
            if run is None or run.agent_id != agent_id:
                raise AgentDelegationValidationError(
                    f"Source agent run {run_id} not found or mismatched",
                    {"run_id": run_id, "agent_id": agent_id},
                )

        return descriptor

    def _validate_target_agent(self, agent_id: str) -> AgentDescriptor:
        """Validate target agent exists and is resolvable."""
        if self._registry is None:
            raise AgentDelegationTargetAgentNotFoundError(
                f"Target agent {agent_id} not found: no registry configured",
                details={"agent_id": agent_id},
            )

        descriptor = self._registry.registry.get(agent_id)
        if descriptor is None:
            raise AgentDelegationTargetAgentNotFoundError(
                f"Target agent {agent_id} not found",
                details={"agent_id": agent_id},
            )

        if descriptor.lifecycle not in {AgentLifecycle.ACTIVE, AgentLifecycle.EXPERIMENTAL}:
            raise AgentDelegationTargetUnsupportedGoalError(
                f"Target agent {agent_id} is not available",
                details={"agent_id": agent_id, "lifecycle": descriptor.lifecycle.value},
            )

        return descriptor

    def _validate_parent_goal(self, goal_id: str) -> Goal:
        """Validate parent goal exists and is not terminal."""
        if self._goal_repo is None:
            raise AgentDelegationParentGoalNotFoundError(
                f"Parent goal {goal_id} not found: no goal repository configured",
                details={"goal_id": goal_id},
            )

        goal = self._goal_repo.get(goal_id)
        if goal is None:
            raise AgentDelegationParentGoalNotFoundError(
                f"Parent goal {goal_id} not found",
                details={"goal_id": goal_id},
            )

        if goal.status in {GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED}:
            raise AgentDelegationParentGoalTerminalError(
                f"Parent goal {goal_id} is in terminal state {goal.status.value}",
                details={"goal_id": goal_id, "status": goal.status.value},
            )

        return goal

    def _validate_agents_compatible(
        self, source: AgentDescriptor, target: AgentDescriptor
    ) -> None:
        """Validate agents are compatible for delegation."""
        if (
            not self._config.allow_self_delegation
            and source.agent_id == target.agent_id
        ):
            raise AgentDelegationAgentsIncompatibleError(
                "Self-delegation is not allowed",
                details={
                    "source_agent_id": source.agent_id,
                    "target_agent_id": target.agent_id,
                },
            )

        source_can_delegate = any(
            c.kind.value in {"operation", "permission"} for c in source.capabilities
        )
        target_can_receive = any(
            c.kind.value in {"operation", "permission"} for c in target.capabilities
        )

        if not source_can_delegate:
            raise AgentDelegationAgentsIncompatibleError(
                f"Source agent {source.agent_id} lacks delegation capability",
                details={"agent_id": source.agent_id},
            )

        if not target_can_receive:
            raise AgentDelegationAgentsIncompatibleError(
                f"Target agent {target.agent_id} cannot receive delegations",
                details={"agent_id": target.agent_id},
            )

    def _validate_target_supports_goal(
        self, target: AgentDescriptor, goal_kind: GoalKind
    ) -> None:
        """Validate target agent supports the goal kind."""
        supported_kinds = set()
        for cap in target.capabilities:
            if cap.kind.value == "operation":
                kinds = cap.metadata.get("supported_goal_kinds", [])
                if isinstance(kinds, list):
                    supported_kinds.update(kinds)

        if goal_kind.value not in supported_kinds and supported_kinds:
            raise AgentDelegationTargetUnsupportedGoalError(
                f"Target agent {target.agent_id} does not support goal kind {goal_kind.value}",
                details={
                    "agent_id": target.agent_id,
                    "goal_kind": goal_kind.value,
                    "supported_kinds": list(supported_kinds),
                },
            )

    def _validate_permissions_and_policies(
        self,
        source: AgentDescriptor,
        target: AgentDescriptor,
        parent_goal: Goal,
        proposal: DelegationProposal,
    ) -> None:
        """Validate permissions and evaluate policies."""
        source_perms = (
            set(source.required_permissions) if source.required_permissions else set()
        )
        target_perms = (
            set(target.required_permissions) if target.required_permissions else set()
        )

        if not target_perms.issubset(source_perms):
            extra = target_perms - source_perms
            raise AgentDelegationPermissionEscalationError(
                f"Target agent has permissions not held by source: {extra}",
                details={"extra_permissions": list(extra)},
            )

        source_autonomy = (
            source.metadata.get("autonomy_level", 0) if source.metadata else 0
        )
        target_autonomy = (
            target.metadata.get("autonomy_level", 0) if target.metadata else 0
        )
        if target_autonomy > source_autonomy:
            raise AgentDelegationAutonomyEscalationError(
                f"Target agent autonomy level {target_autonomy} exceeds source {source_autonomy}",
                details={"source_autonomy": source_autonomy, "target_autonomy": target_autonomy},
            )

        if self._policy_engine:
            try:
                result = self._policy_engine.evaluate(
                    subject=f"agent:{source.agent_id}",
                    action="delegate",
                    resource=f"agent:{target.agent_id}",
                    context={
                        "parent_goal_id": parent_goal.id,
                        "child_goal_kind": proposal.child_goal_kind.value,
                        "target_agent_id": target.agent_id,
                        "depth": proposal.depth,
                    },
                )
                if hasattr(result, "decision") and result.decision == "deny":
                    raise AgentDelegationPolicyDeniedError(
                        f"Policy denied delegation: {getattr(result, 'reason', 'unknown')}",
                        details={"policy_decision": getattr(result, "decision", "deny")},
                    )
            except AgentDelegationPolicyDeniedError:
                raise
            except Exception as exc:
                raise AgentDelegationPolicyDeniedError(
                    f"Policy evaluation failed: {exc}"
                ) from exc

    def _validate_no_cycle(
        self, source_agent_id: str, target_agent_id: str, parent_goal_id: str
    ) -> None:
        """Validate that delegation won't create a cycle.

        Detecta ciclos indirectos multi-nivel comprobando si ya existe un
        camino desde ''target_agent_id'' hasta ''source_agent_id'' en el
        grafo de delegaciones activas. Si existe, al añadir la nueva arista
        ''target_agent_id -> source_agent_id'' se cerraría un ciclo.
        """
        if self._store.exists_delegation_between(
            target_agent_id, source_agent_id, parent_goal_id
        ):
            raise AgentDelegationCycleDetectedError(
                f"Delegation would create a cycle between {source_agent_id} and {target_agent_id}",
                details={"source_agent_id": source_agent_id, "target_agent_id": target_agent_id, "parent_goal_id": parent_goal_id},
            )

        adjacency: dict[str, list[str]] = {}
        for dep in self._store:
            if dep.is_terminal:
                continue
            adjacency.setdefault(dep.source_agent_id, []).append(dep.target_agent_id)

        visited_agents: set[str] = set()
        stack = [target_agent_id]

        while stack:
            current_agent = stack.pop()
            if current_agent in visited_agents:
                continue
            visited_agents.add(current_agent)

            if current_agent == source_agent_id:
                raise AgentDelegationCycleDetectedError(
                    "Delegation would create an indirect cycle",
                    details={"source_agent_id": source_agent_id, "target_agent_id": target_agent_id, "parent_goal_id": parent_goal_id},
                )

            for next_agent in adjacency.get(current_agent, []):
                stack.append(next_agent)

    def _validate_no_duplicate(
        self, source_agent_id: str, target_agent_id: str, parent_goal_id: str
    ) -> None:
        """Validate no active duplicate delegation exists."""
        if self._store.exists_delegation_between(
            source_agent_id, target_agent_id, parent_goal_id
        ):
            raise AgentDelegationDuplicateError(
                f"Active delegation already exists between {source_agent_id} and {target_agent_id} for goal {parent_goal_id}",
                details={"source_agent_id": source_agent_id, "target_agent_id": target_agent_id, "parent_goal_id": parent_goal_id},
            )

    def _validate_depth(self, depth: int) -> None:
        """Validate delegation depth."""
        if depth > self._config.max_delegation_depth:
            raise AgentDelegationMaxDepthExceededError(
                f"Delegation depth {depth} exceeds maximum {self._config.max_delegation_depth}",
                details={"depth": depth, "max_depth": self._config.max_delegation_depth},
            )

    def _validate_child_goal_constraints(
        self, parent_goal: Goal, child_goal: Goal
    ) -> None:
        """Validate child goal is compatible with parent constraints."""
        if not self._config.enforce_goal_constraints:
            return

        for parent_constraint in parent_goal.constraints:
            for child_constraint in child_goal.constraints:
                if parent_constraint.kind == child_constraint.kind and not self._constraints_compatible(
                    parent_constraint, child_constraint
                ):
                    raise AgentDelegationChildGoalIncompatibleError(
                        f"Child goal constraint {child_constraint.kind.value} incompatible with parent constraint {parent_constraint.kind.value}",
                        details={"parent_constraint": parent_constraint.to_dict(), "child_constraint": child_constraint.to_dict()},
                    )

    def _constraints_compatible(
        self, parent: GoalConstraint, child: GoalConstraint
    ) -> bool:
        """Check if child constraint is compatible with (more restrictive than) parent."""
        if parent.kind != child.kind:
            return True

        if parent.kind == GoalConstraintKind.TIME:
            try:
                return float(child.condition.get("value", 0)) <= float(parent.condition.get("value", 0))
            except (ValueError, TypeError):
                return True

        if parent.kind == GoalConstraintKind.COST:
            try:
                return float(child.condition.get("value", 0)) <= float(parent.condition.get("value", 0))
            except (ValueError, TypeError):
                return True

        if parent.kind == GoalConstraintKind.QUALITY:
            try:
                return float(child.condition.get("value", 0)) >= float(parent.condition.get("value", 0))
            except (ValueError, TypeError):
                return True

        return child.condition == parent.condition

    def _emit_event(
        self,
        event_type: DelegationEventType,
        delegation: DelegatedGoal,
        *,
        payload: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> None:
        """Emit a delegation event."""
        if not self._config.emit_events or self._event_bus is None:
            return

        try:
            event = AgentRuntimeEvent(
                header=AgentRuntimeEventHeader(
                    event_id=f"evt-{uuid.uuid4().hex[:12]}",
                    event_type=event_type.value,
                    agent_id=delegation.source_agent_id,
                    agent_run_id=delegation.source_agent_run_id,
                    goal_id=delegation.parent_goal_id,
                    correlation_id=correlation_id or delegation.correlation_id,
                    causation_id=causation_id,
                    metadata={
                        "delegation_id": delegation.id,
                        "parent_goal_id": delegation.parent_goal_id,
                        "child_goal_id": delegation.child_goal_id,
                        "source_agent_id": delegation.source_agent_id,
                        "target_agent_id": delegation.target_agent_id,
                        "delegation_status": delegation.status.value,
                    },
                ),
                payload=AgentRuntimeEventPayload(data=dict(payload or {})),
            )
            self._event_bus.publish(event)
        except (AgentRuntimeEventBusClosedError, AgentRuntimeEventQueueFullError):
            logger.exception(
                "Failed to emit delegation event %s (best-effort)",
                event_type.value,
            )

    def propose(self, proposal: DelegationProposal) -> DelegatedGoal:
        """Create a delegation proposal."""
        now = _now_utc()

        parent_goal = self._validate_parent_goal(proposal.parent_goal_id)

        source_agent_id = proposal.source_agent_id or parent_goal.assigned_agent_id
        if not source_agent_id:
            raise AgentDelegationValidationError(
                "Source agent ID is required",
                details={"proposal": proposal.to_dict()},
            )

        source_agent = self._validate_source_agent(
            source_agent_id, proposal.source_agent_run_id
        )
        target_agent = self._validate_target_agent(proposal.target_agent_id)

        self._validate_agents_compatible(source_agent, target_agent)
        self._validate_target_supports_goal(target_agent, proposal.child_goal_kind)
        self._validate_depth(proposal.depth)
        self._validate_no_cycle(
            source_agent_id, target_agent.agent_id, proposal.parent_goal_id
        )
        self._validate_no_duplicate(
            source_agent_id, target_agent.agent_id, proposal.parent_goal_id
        )
        self._validate_permissions_and_policies(
            source_agent, target_agent, parent_goal, proposal
        )

        child_goal = Goal(
            id=f"goal-{uuid.uuid4().hex[:12]}",
            title=proposal.child_goal_title,
            description=proposal.child_goal_description,
            kind=proposal.child_goal_kind,
            status=GoalStatus.PROPOSED,
            priority=parent_goal.priority,
            urgency=parent_goal.urgency,
            importance=parent_goal.importance,
            value=parent_goal.value,
            confidence=parent_goal.confidence,
            success_criteria=parent_goal.success_criteria,
            constraints=proposal.constraints,
            requirements=parent_goal.requirements,
            dependencies=parent_goal.dependencies,
            parent_goal_id=parent_goal.id,
            child_goal_ids=(),
            source=parent_goal.source,
            owner_actor_id=parent_goal.owner_actor_id,
            assigned_agent_id=target_agent.agent_id,
            autonomy_level=min(
                target_agent.metadata.get("autonomy_level", 0) if target_agent.metadata else 0,
                source_agent.metadata.get("autonomy_level", 0) if source_agent.metadata else 0,
            ),
            deadline=parent_goal.deadline,
            temporal_scope=parent_goal.temporal_scope,
            sensitivity=parent_goal.sensitivity,
            permissions=tuple(
                p for p in (target_agent.required_permissions or ()) if p in parent_goal.permissions
            ),
            created_at=now,
            updated_at=now,
            metadata=MappingProxyType(dict(proposal.metadata)),
        )

        if self._goal_repo:
            self._goal_repo.add(child_goal)

        updated_parent = Goal(
            id=parent_goal.id,
            title=parent_goal.title,
            description=parent_goal.description,
            kind=parent_goal.kind,
            status=parent_goal.status,
            priority=parent_goal.priority,
            urgency=parent_goal.urgency,
            importance=parent_goal.importance,
            value=parent_goal.value,
            confidence=parent_goal.confidence,
            success_criteria=parent_goal.success_criteria,
            constraints=parent_goal.constraints,
            requirements=parent_goal.requirements,
            dependencies=parent_goal.dependencies,
            parent_goal_id=parent_goal.parent_goal_id,
            child_goal_ids=(*parent_goal.child_goal_ids, child_goal.id),
            source=parent_goal.source,
            owner_actor_id=parent_goal.owner_actor_id,
            assigned_agent_id=parent_goal.assigned_agent_id,
            autonomy_level=parent_goal.autonomy_level,
            deadline=parent_goal.deadline,
            temporal_scope=parent_goal.temporal_scope,
            sensitivity=parent_goal.sensitivity,
            permissions=parent_goal.permissions,
            created_at=parent_goal.created_at,
            updated_at=now,
            completed_at=parent_goal.completed_at,
            metadata=parent_goal.metadata,
        )
        if self._goal_repo:
            self._goal_repo.update(updated_parent)

        delegation = create_delegation(
            parent_goal=updated_parent,
            child_goal=child_goal,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent.agent_id,
            source_agent_run_id=proposal.source_agent_run_id,
            expected_result=proposal.expected_result,
            constraints=proposal.constraints,
            depth=proposal.depth,
            correlation_id=proposal.correlation_id,
            metadata=proposal.metadata,
        )

        self._store.add(delegation)

        self._emit_event(
            DelegationEventType.PROPOSED,
            delegation,
            payload={"proposal": proposal.to_dict()},
        )

        return delegation

    def accept(self, delegation_id: str, target_agent_run_id: str | None = None) -> DelegatedGoal:
        """Accept a proposed delegation."""
        delegation = self._store.get(delegation_id)
        if delegation is None:
            raise AgentDelegationValidationError(
                f"Delegation {delegation_id} not found",
                details={"delegation_id": delegation_id},
            )

        if delegation.status != DelegationStatus.PROPOSED:
            raise AgentDelegationInvalidStateTransitionError(
                f"Cannot accept delegation in status {delegation.status.value}",
                details={"delegation_id": delegation_id, "current_status": delegation.status.value},
            )

        if target_agent_run_id and self._run_repo:
            run = self._run_repo.get(target_agent_run_id)
            if run is None or run.agent_id != delegation.target_agent_id:
                raise AgentDelegationValidationError(
                    f"Target agent run {target_agent_run_id} does not match delegation target",
                    details={"target_agent_run_id": target_agent_run_id, "expected_agent_id": delegation.target_agent_id},
                )

        now = _now_utc()
        updated = DelegatedGoal(
            id=delegation.id,
            parent_goal_id=delegation.parent_goal_id,
            child_goal_id=delegation.child_goal_id,
            source_agent_id=delegation.source_agent_id,
            target_agent_id=delegation.target_agent_id,
            source_agent_run_id=delegation.source_agent_run_id,
            target_agent_run_id=target_agent_run_id,
            expected_result=delegation.expected_result,
            constraints=delegation.constraints,
            status=DelegationStatus.ACCEPTED,
            created_at=delegation.created_at,
            updated_at=now,
            completed_at=delegation.completed_at,
            depth=delegation.depth,
            correlation_id=delegation.correlation_id,
            metadata=delegation.metadata,
        )
        self._store.update(updated)

        if self._goal_repo:
            child_goal = self._goal_repo.get(delegation.child_goal_id)
            if child_goal:
                updated_child = Goal(
                    id=child_goal.id,
                    title=child_goal.title,
                    description=child_goal.description,
                    kind=child_goal.kind,
                    status=GoalStatus.ACCEPTED,
                    priority=child_goal.priority,
                    urgency=child_goal.urgency,
                    importance=child_goal.importance,
                    value=child_goal.value,
                    confidence=child_goal.confidence,
                    success_criteria=child_goal.success_criteria,
                    constraints=child_goal.constraints,
                    requirements=child_goal.requirements,
                    dependencies=child_goal.dependencies,
                    parent_goal_id=child_goal.parent_goal_id,
                    child_goal_ids=child_goal.child_goal_ids,
                    source=child_goal.source,
                    owner_actor_id=child_goal.owner_actor_id,
                    assigned_agent_id=child_goal.assigned_agent_id,
                    autonomy_level=child_goal.autonomy_level,
                    deadline=child_goal.deadline,
                    temporal_scope=child_goal.temporal_scope,
                    sensitivity=child_goal.sensitivity,
                    permissions=child_goal.permissions,
                    created_at=child_goal.created_at,
                    updated_at=now,
                    completed_at=None,
                    metadata=child_goal.metadata,
                )
                self._goal_repo.update(updated_child)

        self._emit_event(
            DelegationEventType.ACCEPTED,
            updated,
            payload={"target_agent_run_id": target_agent_run_id},
            causation_id=delegation.id,
        )

        return updated

    def reject(self, delegation_id: str, reason: str) -> DelegatedGoal:
        """Reject a proposed delegation."""
        delegation = self._store.get(delegation_id)
        if delegation is None:
            raise AgentDelegationValidationError(
                f"Delegation {delegation_id} not found",
                details={"delegation_id": delegation_id},
            )

        if delegation.status not in {DelegationStatus.PROPOSED, DelegationStatus.ACCEPTED}:
            raise AgentDelegationInvalidStateTransitionError(
                f"Cannot reject delegation in status {delegation.status.value}",
                details={"delegation_id": delegation_id, "current_status": delegation.status.value},
            )

        now = _now_utc()
        updated = DelegatedGoal(
            id=delegation.id,
            parent_goal_id=delegation.parent_goal_id,
            child_goal_id=delegation.child_goal_id,
            source_agent_id=delegation.source_agent_id,
            target_agent_id=delegation.target_agent_id,
            source_agent_run_id=delegation.source_agent_run_id,
            target_agent_run_id=delegation.target_agent_run_id,
            expected_result=delegation.expected_result,
            constraints=delegation.constraints,
            status=DelegationStatus.REJECTED,
            created_at=delegation.created_at,
            updated_at=now,
            completed_at=now,
            depth=delegation.depth,
            correlation_id=delegation.correlation_id,
            metadata=MappingProxyType({**dict(delegation.metadata), "rejection_reason": reason}),
        )
        self._store.update(updated)

        if self._goal_repo:
            child_goal = self._goal_repo.get(delegation.child_goal_id)
            if child_goal:
                updated_child = Goal(
                    id=child_goal.id,
                    title=child_goal.title,
                    description=child_goal.description,
                    kind=child_goal.kind,
                    status=GoalStatus.CANCELLED,
                    priority=child_goal.priority,
                    urgency=child_goal.urgency,
                    importance=child_goal.importance,
                    value=child_goal.value,
                    confidence=child_goal.confidence,
                    success_criteria=child_goal.success_criteria,
                    constraints=child_goal.constraints,
                    requirements=child_goal.requirements,
                    dependencies=child_goal.dependencies,
                    parent_goal_id=child_goal.parent_goal_id,
                    child_goal_ids=child_goal.child_goal_ids,
                    source=child_goal.source,
                    owner_actor_id=child_goal.owner_actor_id,
                    assigned_agent_id=child_goal.assigned_agent_id,
                    autonomy_level=child_goal.autonomy_level,
                    deadline=child_goal.deadline,
                    temporal_scope=child_goal.temporal_scope,
                    sensitivity=child_goal.sensitivity,
                    permissions=child_goal.permissions,
                    created_at=child_goal.created_at,
                    updated_at=now,
                    completed_at=None,
                    metadata=child_goal.metadata,
                )
                self._goal_repo.update(updated_child)

        self._emit_event(
            DelegationEventType.REJECTED,
            updated,
            payload={"reason": reason},
            causation_id=delegation.id,
        )

        return updated

    def start(self, delegation_id: str) -> DelegatedGoal:
        """Start the delegated agent run."""
        delegation = self._store.get(delegation_id)
        if delegation is None:
            raise AgentDelegationValidationError(
                f"Delegation {delegation_id} not found",
                details={"delegation_id": delegation_id},
            )

        if delegation.status != DelegationStatus.ACCEPTED:
            raise AgentDelegationInvalidStateTransitionError(
                f"Cannot start delegation in status {delegation.status.value}",
                details={"delegation_id": delegation_id, "current_status": delegation.status.value},
            )

        from cmm.agent_runtime.enums import AgentRuntimeStatus

        run_id = _generate_run_id(f"del-{delegation.id}")
        agent_run = AgentRun(
            id=run_id,
            agent_id=delegation.target_agent_id,
            goal_id=delegation.child_goal_id,
            status=AgentRuntimeStatus.EXECUTING,
            autonomy_level=delegation.metadata.get("autonomy_level", 1),
            current_iteration=0,
            started_at=_now_utc(),
            updated_at=_now_utc(),
            metadata=MappingProxyType({"delegation_id": delegation.id}),
        )

        if self._run_repo:
            self._run_repo.add(agent_run)

        now = _now_utc()
        updated = DelegatedGoal(
            id=delegation.id,
            parent_goal_id=delegation.parent_goal_id,
            child_goal_id=delegation.child_goal_id,
            source_agent_id=delegation.source_agent_id,
            target_agent_id=delegation.target_agent_id,
            source_agent_run_id=delegation.source_agent_run_id,
            target_agent_run_id=run_id,
            expected_result=delegation.expected_result,
            constraints=delegation.constraints,
            status=DelegationStatus.ACTIVE,
            created_at=delegation.created_at,
            updated_at=now,
            completed_at=delegation.completed_at,
            depth=delegation.depth,
            correlation_id=delegation.correlation_id,
            metadata=delegation.metadata,
        )
        self._store.update(updated)

        if self._goal_repo:
            child_goal = self._goal_repo.get(delegation.child_goal_id)
            if child_goal:
                updated_child = Goal(
                    id=child_goal.id,
                    title=child_goal.title,
                    description=child_goal.description,
                    kind=child_goal.kind,
                    status=GoalStatus.IN_PROGRESS,
                    priority=child_goal.priority,
                    urgency=child_goal.urgency,
                    importance=child_goal.importance,
                    value=child_goal.value,
                    confidence=child_goal.confidence,
                    success_criteria=child_goal.success_criteria,
                    constraints=child_goal.constraints,
                    requirements=child_goal.requirements,
                    dependencies=child_goal.dependencies,
                    parent_goal_id=child_goal.parent_goal_id,
                    child_goal_ids=child_goal.child_goal_ids,
                    source=child_goal.source,
                    owner_actor_id=child_goal.owner_actor_id,
                    assigned_agent_id=child_goal.assigned_agent_id,
                    autonomy_level=child_goal.autonomy_level,
                    deadline=child_goal.deadline,
                    temporal_scope=child_goal.temporal_scope,
                    sensitivity=child_goal.sensitivity,
                    permissions=child_goal.permissions,
                    created_at=child_goal.created_at,
                    updated_at=now,
                    completed_at=None,
                    metadata=child_goal.metadata,
                )
                self._goal_repo.update(updated_child)

        self._emit_event(
            DelegationEventType.STARTED,
            updated,
            payload={"delegated_run_id": run_id},
            causation_id=delegation.id,
        )

        return updated

    def complete(self, delegation_id: str, result: DelegationResult) -> DelegatedGoal:
        """Complete a delegation with a result."""
        delegation = self._store.get(delegation_id)
        if delegation is None:
            raise AgentDelegationValidationError(
                f"Delegation {delegation_id} not found",
                details={"delegation_id": delegation_id},
            )

        if delegation.status not in {DelegationStatus.ACTIVE, DelegationStatus.WAITING}:
            raise AgentDelegationInvalidStateTransitionError(
                f"Cannot complete delegation in status {delegation.status.value}",
                details={"delegation_id": delegation_id, "current_status": delegation.status.value},
            )

        if result.delegation_id != delegation_id:
            raise AgentDelegationValidationError(
                "Result delegation_id does not match",
                details={"expected": delegation_id, "got": result.delegation_id},
            )

        if result.parent_goal_id != delegation.parent_goal_id:
            raise AgentDelegationValidationError(
                "Result parent_goal_id does not match",
                details={"expected": delegation.parent_goal_id, "got": result.parent_goal_id},
            )

        if result.child_goal_id != delegation.child_goal_id:
            raise AgentDelegationValidationError(
                "Result child_goal_id does not match",
                details={"expected": delegation.child_goal_id, "got": result.child_goal_id},
            )

        now = _now_utc()
        final_status = (
            DelegationStatus.COMPLETED if result.status == DelegationStatus.COMPLETED else DelegationStatus.FAILED
        )

        updated = replace(
            delegation,
            status=final_status,
            completed_at=result.completed_at,
            updated_at=now,
            metadata=MappingProxyType({**dict(delegation.metadata), "result": result.to_dict()}),
        )
        self._store.update(updated)

        if self._goal_repo:
            child_goal = self._goal_repo.get(delegation.child_goal_id)
            if child_goal:
                child_status = GoalStatus.COMPLETED if result.status == DelegationStatus.COMPLETED else GoalStatus.FAILED
                updated_child = replace(
                    child_goal,
                    status=child_status,
                    completed_at=result.completed_at if result.status == DelegationStatus.COMPLETED else None,
                    updated_at=now,
                )
                self._goal_repo.update(updated_child)

        if self._goal_manager and self._goal_repo:
            parent_goal = self._goal_repo.get(delegation.parent_goal_id)
            if parent_goal and hasattr(self._goal_manager, "incorporate_delegation_result"):
                try:
                    self._goal_manager.incorporate_delegation_result(
                        parent_goal_id=delegation.parent_goal_id,
                        delegation_result=result,
                    )
                except Exception as exc:
                    logger.exception(
                        "Failed to incorporate result into parent %s",
                        delegation.parent_goal_id,
                    )
                    current_metadata = dict(delegation.metadata)
                    current_metadata.setdefault("warnings", []).append(f"result_incorporation_failed: {exc}")
                    updated = replace(updated, metadata=MappingProxyType(current_metadata))

        event_type = (
            DelegationEventType.COMPLETED if result.status == DelegationStatus.COMPLETED else DelegationEventType.FAILED
        )
        self._emit_event(
            event_type,
            updated,
            payload={"result": result.to_dict()},
            causation_id=delegation.id,
        )
        self._emit_event(
            DelegationEventType.RESULT_RECEIVED,
            updated,
            payload={"result": result.to_dict()},
            causation_id=delegation.id,
        )

        return updated

    def fail(self, delegation_id: str, error: str) -> DelegatedGoal:
        """Fail a delegation."""
        delegation = self._store.get(delegation_id)
        if delegation is None:
            raise AgentDelegationValidationError(
                f"Delegation {delegation_id} not found",
                details={"delegation_id": delegation_id},
            )

        if delegation.is_terminal:
            raise AgentDelegationInvalidStateTransitionError(
                f"Cannot fail delegation in terminal status {delegation.status.value}",
                details={"delegation_id": delegation_id, "current_status": delegation.status.value},
            )

        now = _now_utc()
        updated = replace(
            delegation,
            status=DelegationStatus.FAILED,
            completed_at=now,
            updated_at=now,
            metadata=MappingProxyType({**dict(delegation.metadata), "error": error}),
        )
        self._store.update(updated)

        if self._goal_repo:
            child_goal = self._goal_repo.get(delegation.child_goal_id)
            if child_goal:
                updated_child = replace(
                    child_goal,
                    status=GoalStatus.FAILED,
                    completed_at=None,
                    updated_at=now,
                )
                self._goal_repo.update(updated_child)

        self._emit_event(
            DelegationEventType.FAILED,
            updated,
            payload={"error": error},
            causation_id=delegation.id,
        )

        return updated

    def cancel(self, delegation_id: str, reason: str = "Cancelled by user") -> DelegatedGoal:
        """Cancel a delegation."""
        delegation = self._store.get(delegation_id)
        if delegation is None:
            raise AgentDelegationValidationError(
                f"Delegation {delegation_id} not found",
                details={"delegation_id": delegation_id},
            )

        if delegation.is_terminal:
            raise AgentDelegationInvalidStateTransitionError(
                f"Cannot cancel delegation in terminal status {delegation.status.value}",
                details={"delegation_id": delegation_id, "current_status": delegation.status.value},
            )

        now = _now_utc()
        updated = replace(
            delegation,
            status=DelegationStatus.CANCELLED,
            completed_at=now,
            updated_at=now,
            metadata=MappingProxyType({**dict(delegation.metadata), "cancellation_reason": reason}),
        )
        self._store.update(updated)

        if self._goal_repo:
            child_goal = self._goal_repo.get(delegation.child_goal_id)
            if child_goal:
                updated_child = replace(
                    child_goal,
                    status=GoalStatus.CANCELLED,
                    completed_at=None,
                    updated_at=now,
                )
                self._goal_repo.update(updated_child)

        self._emit_event(
            DelegationEventType.CANCELLED,
            updated,
            payload={"reason": reason},
            causation_id=delegation.id,
        )

        return updated

    def get(self, delegation_id: str) -> DelegatedGoal | None:
        """Get a delegation by ID."""
        return self._store.get(delegation_id)

    def list_for_parent_goal(self, parent_goal_id: str) -> list[DelegatedGoal]:
        """List all delegations for a parent goal."""
        return self._store.list_by_parent_goal(parent_goal_id)

    def waiting(self, delegation_id: str) -> DelegatedGoal:
        """Mark delegation as waiting for result."""
        delegation = self._store.get(delegation_id)
        if delegation is None:
            raise AgentDelegationValidationError(
                f"Delegation {delegation_id} not found",
                details={"delegation_id": delegation_id},
            )

        if delegation.status != DelegationStatus.ACTIVE:
            raise AgentDelegationInvalidStateTransitionError(
                f"Cannot set waiting on delegation in status {delegation.status.value}",
                details={"delegation_id": delegation_id, "current_status": delegation.status.value},
            )

        now = _now_utc()
        updated = replace(
            delegation,
            status=DelegationStatus.WAITING,
            updated_at=now,
        )
        self._store.update(updated)

        self._emit_event(
            DelegationEventType.WAITING,
            updated,
            causation_id=delegation.id,
        )

        return updated
