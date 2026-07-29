"""Phase 9.3 – Goal Intake and Goal Normalization Test Suite.

Validates contracts, deterministic normalizer, proposal repository, GoalIntakeService,
Goal conversion, invariants, errors, and end-to-end workflows.
"""

from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from cmm.agent_runtime import (
    DeterministicGoalNormalizer,
    DuplicateGoalError,
    Goal,
    GoalAmbiguity,
    GoalAmbiguityKind,
    GoalConstraint,
    GoalConstraintKind,
    GoalDependency,
    GoalDependencyType,
    GoalInformationGap,
    GoalIntakeDecisionType,
    GoalIntakeService,
    GoalKind,
    GoalManager,
    GoalNormalizationError,
    GoalNormalizationRequest,
    GoalPriority,
    GoalProposal,
    GoalProposalNotFoundError,
    GoalProposalQuery,
    GoalProposalStateError,
    GoalProposalStatus,
    GoalQuery,
    GoalSource,
    GoalStatus,
    InMemoryGoalProposalRepository,
    InMemoryGoalRepository,
    InvalidGoalProposalError,
    SuccessCriterion,
    SuccessCriterionKind,
)

# ── 1. Contract Validation & Invariants Tests ───────────────────────────────────


def test_goal_proposal_valid_creation() -> None:
    now = datetime.now(timezone.utc)
    proposal = GoalProposal(
        id="prop-1",
        source=GoalSource.USER_MESSAGE,
        raw_objective="Implement user authentication module",
        normalized_title="Implement user authentication module",
        normalized_description="Implement user authentication module",
        proposed_kind=GoalKind.TRANSFORMATION,
        proposed_priority=GoalPriority(score=80.0),
        proposed_owner_actor_id="actor-1",
        proposed_autonomy_level=2,
        proposed_sensitivity="restricted",
        proposed_permissions=("read", "write"),
        created_at=now,
    )

    assert proposal.id == "prop-1"
    assert proposal.source == GoalSource.USER_MESSAGE
    assert proposal.raw_objective == "Implement user authentication module"
    assert proposal.proposed_kind == GoalKind.TRANSFORMATION
    assert proposal.proposed_priority.score == 80.0
    assert proposal.proposed_permissions == ("read", "write")
    assert proposal.confidence == 1.0
    assert proposal.status == GoalProposalStatus.CREATED


def test_goal_proposal_invalid_confidence() -> None:
    with pytest.raises(InvalidGoalProposalError, match="confidence"):
        GoalProposal(
            id="prop-1",
            source=GoalSource.USER_MESSAGE,
            raw_objective="Do something",
            normalized_title="Do something",
            normalized_description="Do something",
            proposed_kind=GoalKind.TRANSFORMATION,
            confidence=1.5,
        )


def test_goal_proposal_ambiguity_invariants() -> None:
    amb = GoalAmbiguity(
        id="amb-1",
        kind=GoalAmbiguityKind.SCOPE,
        description="Scope is unclear",
        blocking=True,
    )
    # Invariant #5: Ambiguous proposal requires confirmation
    prop = GoalProposal(
        id="prop-amb",
        source=GoalSource.USER_MESSAGE,
        raw_objective="Clean repo",
        normalized_title="Clean repo",
        normalized_description="Clean repo",
        proposed_kind=GoalKind.MAINTENANCE,
        ambiguities=(amb,),
        requires_confirmation=False,
    )
    assert prop.requires_confirmation is True

    # Invariant #6: READY status cannot have blocking ambiguities
    with pytest.raises(
        InvalidGoalProposalError, match="READY cannot contain blocking ambiguities"
    ):
        GoalProposal(
            id="prop-ready-invalid",
            source=GoalSource.USER_MESSAGE,
            raw_objective="Clean repo",
            normalized_title="Clean repo",
            normalized_description="Clean repo",
            proposed_kind=GoalKind.MAINTENANCE,
            ambiguities=(amb,),
            status=GoalProposalStatus.READY,
        )


def test_goal_proposal_self_dependency_rejected() -> None:
    # Invariant #16: Dependency on the same proposal ID is rejected
    dep = GoalDependency(
        goal_id="g-other",
        depends_on_goal_id="prop-loop",
        dependency_type=GoalDependencyType.REQUIRES_COMPLETION,
    )
    with pytest.raises(
        InvalidGoalProposalError, match="Proposal dependency loop detected"
    ):
        GoalProposal(
            id="prop-loop",
            source=GoalSource.USER_MESSAGE,
            raw_objective="Task loop",
            normalized_title="Task loop",
            normalized_description="Task loop",
            proposed_kind=GoalKind.TRANSFORMATION,
            proposed_dependencies=(dep,),
        )


def test_contracts_immutability_and_collections() -> None:
    # Invariant #17: Collections do not share mutability
    crit = SuccessCriterion(
        id="crit-1",
        description="All tests pass",
        kind=SuccessCriterionKind.VALIDATION,
    )
    constr = GoalConstraint(
        id="constr-1",
        description="No breaking API changes",
        kind=GoalConstraintKind.SAFETY,
    )

    prop = GoalProposal(
        id="prop-immut",
        source=GoalSource.USER_MESSAGE,
        raw_objective="Update API",
        normalized_title="Update API",
        normalized_description="Update API",
        proposed_kind=GoalKind.TRANSFORMATION,
        proposed_success_criteria=[crit],
        proposed_constraints=[constr],
        proposed_permissions=["api:write"],
    )

    assert isinstance(prop.proposed_success_criteria, tuple)
    assert isinstance(prop.proposed_constraints, tuple)
    assert isinstance(prop.proposed_permissions, tuple)
    assert isinstance(prop.metadata, MappingProxyType)

    with pytest.raises(TypeError):
        prop.proposed_permissions[0] = "api:admin"  # type: ignore[index]


def test_contracts_serialization_roundtrip() -> None:
    # Invariant #18: Serialization and reconstruction preserve data
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=7)
    amb = GoalAmbiguity(
        id="amb-1", kind=GoalAmbiguityKind.DEADLINE, description="Deadline tight"
    )
    gap = GoalInformationGap(id="gap-1", question="Who is owner?", topic="owner")

    prop = GoalProposal(
        id="prop-ser",
        source=GoalSource.WORKFLOW,
        raw_objective="Deploy service",
        normalized_title="Deploy service",
        normalized_description="Deploy service",
        proposed_kind=GoalKind.INTEGRATION,
        proposed_priority=GoalPriority(score=90.0, user_priority=100.0),
        proposed_deadline=deadline,
        proposed_owner_actor_id="actor-dev",
        proposed_autonomy_level=2,
        proposed_sensitivity="confidential",
        proposed_permissions=("deploy:stg",),
        ambiguities=(amb,),
        information_gaps=(gap,),
        requires_confirmation=True,
        confidence=0.85,
        status=GoalProposalStatus.REQUIRES_CLARIFICATION,
        created_at=now,
        metadata=MappingProxyType({"env": "staging"}),
    )

    serialized = prop.serialize()
    deserialized = GoalProposal.from_dict(serialized)

    assert deserialized.id == prop.id
    assert deserialized.source == prop.source
    assert deserialized.raw_objective == prop.raw_objective
    assert deserialized.proposed_kind == prop.proposed_kind
    assert deserialized.proposed_priority.score == 90.0
    assert deserialized.proposed_deadline == deadline
    assert deserialized.proposed_permissions == ("deploy:stg",)
    assert deserialized.ambiguities[0].id == amb.id
    assert deserialized.information_gaps[0].id == gap.id
    assert deserialized.metadata["env"] == "staging"


def test_unknown_enums_rejected() -> None:
    # Invariant #19: Unknown enums rejected
    with pytest.raises(InvalidGoalProposalError, match="Invalid GoalSource string"):
        GoalProposal(
            id="prop-bad-enum",
            source="unknown_source_xyz",
            raw_objective="Test",
            normalized_title="Test",
            normalized_description="Test",
            proposed_kind=GoalKind.TRANSFORMATION,
        )


# ── 2. Deterministic Goal Normalizer Tests ─────────────────────────────────────


def test_normalizer_direct_objective() -> None:
    normalizer = DeterministicGoalNormalizer()
    req = GoalNormalizationRequest(
        raw_objective="Build user dashboard UI",
        source=GoalSource.USER_MESSAGE,
        actor_id="actor-alice",
    )
    res = normalizer.normalize(req)

    assert res.status == GoalProposalStatus.READY
    assert res.proposal.normalized_title == "Build user dashboard UI"
    assert res.proposal.normalized_description == "Build user dashboard UI"
    assert res.proposal.proposed_owner_actor_id == "actor-alice"
    assert res.proposal.confidence == 1.0
    assert res.proposal.requires_confirmation is False


def test_normalizer_explicit_kind_priority_deadline_constraints() -> None:
    normalizer = DeterministicGoalNormalizer()
    deadline = datetime.now(timezone.utc) + timedelta(days=2)
    constr = GoalConstraint(
        id="c1",
        description="No external dependencies",
        kind=GoalConstraintKind.TECHNICAL,
    )

    req = GoalNormalizationRequest(
        raw_objective="Refactor authentication pipeline",
        kind_hint=GoalKind.REMEDIATION,
        explicit_priority=GoalPriority(score=75.0),
        explicit_deadline=deadline,
        constraints=(constr,),
        permissions=("auth:read",),
        requested_autonomy_level=3,
    )
    res = normalizer.normalize(req)

    prop = res.proposal
    assert prop.proposed_kind == GoalKind.REMEDIATION
    assert prop.proposed_priority.score == 75.0
    assert prop.proposed_deadline == deadline
    assert prop.proposed_constraints == (constr,)
    assert prop.proposed_permissions == ("auth:read",)
    # Invariant #9: Autonomy level not elevated
    assert prop.proposed_autonomy_level == 3


def test_normalizer_subgoal_parent_id() -> None:
    normalizer = DeterministicGoalNormalizer()
    req = GoalNormalizationRequest(
        raw_objective="Write unit tests for authentication",
        parent_goal_id="goal-parent-123",
    )
    res = normalizer.normalize(req)
    assert res.proposal.metadata.get("parent_goal_id") == "goal-parent-123"


def test_normalizer_recurring_goal() -> None:
    normalizer = DeterministicGoalNormalizer()
    req = GoalNormalizationRequest(
        raw_objective="Run daily database vacuum and backup",
        source=GoalSource.RECURRING_GOAL,
    )
    res = normalizer.normalize(req)
    assert res.proposal.proposed_kind == GoalKind.RECURRING


def test_normalizer_ambiguous_objective() -> None:
    # Invariant #5: Ambiguous objective creates ambiguities & gaps
    normalizer = DeterministicGoalNormalizer()
    req = GoalNormalizationRequest(
        raw_objective="do whatever",
    )
    res = normalizer.normalize(req)

    assert res.status == GoalProposalStatus.REQUIRES_CLARIFICATION
    assert res.proposal.requires_confirmation is True
    assert res.proposal.confidence < 1.0
    assert len(res.proposal.ambiguities) > 0
    assert len(res.proposal.information_gaps) > 0


def test_normalizer_empty_input_rejected() -> None:
    # Invariant #2: Empty input is rejected
    with pytest.raises(GoalNormalizationError, match="raw_objective cannot be empty"):
        GoalNormalizationRequest(raw_objective="    ")


def test_normalizer_does_not_invent_deadlines_or_permissions() -> None:
    # Invariants #7 & #8: No deadline or permission invented
    normalizer = DeterministicGoalNormalizer()
    req = GoalNormalizationRequest(raw_objective="Optimize query execution plan")
    res = normalizer.normalize(req)

    assert res.proposal.proposed_deadline is None
    assert res.proposal.proposed_permissions == ()


# ── 3. Repository Tests ────────────────────────────────────────────────────────


def test_repository_add_get_update_search() -> None:
    repo = InMemoryGoalProposalRepository()
    prop1 = GoalProposal(
        id="prop-10",
        source=GoalSource.USER_MESSAGE,
        raw_objective="Fix login bug",
        normalized_title="Fix login bug",
        normalized_description="Fix login bug",
        proposed_kind=GoalKind.REMEDIATION,
        status=GoalProposalStatus.READY,
    )
    prop2 = GoalProposal(
        id="prop-20",
        source=GoalSource.WORKFLOW,
        raw_objective="Run security scan",
        normalized_title="Run security scan",
        normalized_description="Run security scan",
        proposed_kind=GoalKind.VALIDATION,
        status=GoalProposalStatus.REQUIRES_CLARIFICATION,
        requires_confirmation=True,
    )

    repo.add(prop1)
    repo.add(prop2)

    # Invariant #3: Stable identifier lookup
    assert repo.get("prop-10") == prop1
    assert repo.get("prop-20") == prop2
    assert repo.get("non-existent") is None

    # Duplicate ID check
    with pytest.raises(DuplicateGoalError):
        repo.add(prop1)

    # Update
    updated = GoalProposal.from_dict(
        {**prop1.to_dict(), "status": GoalProposalStatus.ACCEPTED}
    )
    repo.update(updated)
    assert repo.get("prop-10").status == GoalProposalStatus.ACCEPTED

    # Search
    search_res = repo.search(
        GoalProposalQuery(status=GoalProposalStatus.REQUIRES_CLARIFICATION)
    )
    assert len(search_res) == 1
    assert search_res[0].id == "prop-20"


def test_repository_update_non_existent_raises() -> None:
    repo = InMemoryGoalProposalRepository()
    prop = GoalProposal(
        id="prop-missing",
        source=GoalSource.USER_MESSAGE,
        raw_objective="Missing",
        normalized_title="Missing",
        normalized_description="Missing",
        proposed_kind=GoalKind.TRANSFORMATION,
    )
    with pytest.raises(GoalProposalNotFoundError):
        repo.update(prop)


# ── 4. Goal Intake Service & Lifecycle Tests ────────────────────────────────────


def test_service_process_request_and_accept() -> None:
    service = GoalIntakeService()
    req = GoalNormalizationRequest(
        raw_objective="Deploy Phase 9.3 Goal Intake to CMM OS",
        source=GoalSource.USER_MESSAGE,
        actor_id="actor-christian",
    )
    norm_result = service.process_request(req)

    assert norm_result.status == GoalProposalStatus.READY
    prop_id = norm_result.proposal.id

    # Accept proposal
    goal = service.accept_proposal(prop_id)

    # Invariant #14 & #15: Goal references origin proposal and starts as PROPOSED
    assert isinstance(goal, Goal)
    assert goal.status == GoalStatus.PROPOSED
    assert goal.metadata["proposal_id"] == prop_id
    assert goal.metadata["raw_objective"] == "Deploy Phase 9.3 Goal Intake to CMM OS"

    # Invariant #11: Double acceptance prevention
    with pytest.raises(GoalProposalStateError, match="already been accepted"):
        service.accept_proposal(prop_id)


def test_service_reject_proposal() -> None:
    service = GoalIntakeService()
    req = GoalNormalizationRequest(raw_objective="Delete all production tables")
    norm_result = service.process_request(req)

    prop_id = norm_result.proposal.id
    rejected = service.reject_proposal(prop_id, reason="Dangerous operation")

    assert rejected.status == GoalProposalStatus.REJECTED

    # Invariant #10: A rejected proposal cannot be accepted
    with pytest.raises(GoalProposalStateError, match="was rejected"):
        service.accept_proposal(prop_id)


def test_service_duplicate_detection_no_auto_merge() -> None:
    # Set up GoalManager with existing active Goal
    goal_repo = InMemoryGoalRepository()
    manager = GoalManager(repository=goal_repo)
    existing_goal = Goal(
        id="goal-existing-1",
        title="Refactor database schema",
        description="Refactor database schema",
        kind=GoalKind.TRANSFORMATION,
        status=GoalStatus.ACTIVE,
        priority=GoalPriority(),
        owner_actor_id="actor-dev",
    )
    manager.register_goal(existing_goal)

    service = GoalIntakeService(goal_manager=manager)
    req = GoalNormalizationRequest(
        raw_objective="Refactor database schema",
        actor_id="actor-dev",
    )
    res = service.process_request(req)

    # Duplicate detected -> status requires_clarification, decision MERGE_WITH_EXISTING
    assert res.status == GoalProposalStatus.REQUIRES_CLARIFICATION
    assert res.proposal.requires_confirmation is True

    decisions = [
        d
        for d in res.decisions
        if d.decision_type == GoalIntakeDecisionType.MERGE_WITH_EXISTING
    ]
    assert len(decisions) == 1
    assert "goal-existing-1" in decisions[0].candidate_goal_ids

    # GoalManager still has only 1 active goal (no auto-merge or auto-creation)
    assert len(manager.search_goals(GoalQuery()).goals) == 1


# ── 5. End-to-End Integration Workflows ───────────────────────────────────────


def test_e2e_valid_flow() -> None:
    """Flujo válido: entrada -> normalización -> proposal ready -> aceptación -> Goal en GoalManager."""
    goal_repo = InMemoryGoalRepository()
    manager = GoalManager(repository=goal_repo)
    service = GoalIntakeService(goal_manager=manager)

    # 1. Entrada de usuario
    req = GoalNormalizationRequest(
        raw_objective="Add comprehensive logging to agent runtime",
        source=GoalSource.USER_MESSAGE,
        actor_id="actor-lead",
        permissions=("logs:write",),
    )

    # 2. Normalización
    norm_result = service.process_request(req)
    assert norm_result.status == GoalProposalStatus.READY
    proposal_id = norm_result.proposal.id

    # 3. Aceptación
    goal = service.accept_proposal(proposal_id)

    # 4. Conversión y Registro en GoalManager
    assert goal.status == GoalStatus.PROPOSED
    assert goal.permissions == ("logs:write",)

    # 5. Consulta del Goal registrado
    retrieved = manager.get_goal(goal.id)
    assert retrieved is not None
    assert retrieved.title == "Add comprehensive logging to agent runtime"


def test_e2e_ambiguous_flow() -> None:
    """Flujo ambiguo: entrada ambigua -> proposal requires_clarification -> gaps -> no Goal creado."""
    goal_repo = InMemoryGoalRepository()
    manager = GoalManager(repository=goal_repo)
    service = GoalIntakeService(goal_manager=manager)

    # 1. Entrada ambigua
    req = GoalNormalizationRequest(raw_objective="fix it")
    norm_result = service.process_request(req)

    # 2. Propuesta requiere aclaración
    assert norm_result.status == GoalProposalStatus.REQUIRES_CLARIFICATION
    assert len(norm_result.proposal.ambiguities) > 0
    assert len(norm_result.proposal.information_gaps) > 0

    # 3. Intento de aceptar propuesta ambigua bloqueante falla
    with pytest.raises(GoalProposalStateError, match="blocking ambiguities remain"):
        service.accept_proposal(norm_result.proposal.id)

    # 4. No se ha creado ningún Goal en GoalManager
    assert len(manager.search_goals(GoalQuery()).goals) == 0


def test_e2e_duplicate_flow() -> None:
    """Flujo duplicado: entrada -> normalización -> detección de Goal existente -> decision merge_with_existing -> no auto fusión."""
    goal_repo = InMemoryGoalRepository()
    manager = GoalManager(repository=goal_repo)

    # Registramos un objetivo activo previo
    initial_goal = Goal(
        id="goal-prior-auth",
        title="Upgrade JWT security token expiration",
        description="Upgrade JWT security token expiration",
        kind=GoalKind.TRANSFORMATION,
        status=GoalStatus.IN_PROGRESS,
        priority=GoalPriority(),
        owner_actor_id="actor-sec",
    )
    manager.register_goal(initial_goal)

    service = GoalIntakeService(goal_manager=manager)

    # Nueva solicitud idéntica
    req = GoalNormalizationRequest(
        raw_objective="Upgrade JWT security token expiration",
        actor_id="actor-sec",
    )
    res = service.process_request(req)

    # Detección de duplicado
    assert res.status == GoalProposalStatus.REQUIRES_CLARIFICATION
    merge_decisions = [
        d
        for d in res.decisions
        if d.decision_type == GoalIntakeDecisionType.MERGE_WITH_EXISTING
    ]
    assert len(merge_decisions) == 1
    assert "goal-prior-auth" in merge_decisions[0].candidate_goal_ids

    # No se fusionó ni registró automáticamente
    goals = manager.search_goals(GoalQuery()).goals
    assert len(goals) == 1
    assert goals[0].id == "goal-prior-auth"
