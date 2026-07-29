"""Tests for Phase 9.6 – Information Acquisition Strategy.

Verifies contracts, enums, errors, policy evaluation, candidate generation,
deterministic selection, invariants, safety rules, serialization, and E2E flows.
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime import (
    AgentCognitiveResult,
    AgentRun,
    DefaultInformationAcquisitionResolver,
    Goal,
    GoalInformationGap,
    InformationAcquisitionCandidate,
    InformationAcquisitionCost,
    InformationAcquisitionEstimate,
    InformationAcquisitionPolicy,
    InformationAcquisitionRequest,
    InformationAcquisitionRisk,
    InformationAcquisitionService,
    InformationAcquisitionStatus,
    InformationAcquisitionStrategy,
    InvalidInformationAcquisitionContractError,
)
from cmm.agent_runtime.enums import (
    AgentCognitiveDecision,
    AgentCognitiveStatus,
    AgentRuntimeStatus,
    GoalKind,
    GoalStatus,
)

# ── Contract & Invariant Tests ────────────────────────────────────────────────


def test_acquisition_cost_invariants() -> None:
    cost = InformationAcquisitionCost(
        questions=1,
        internal_calls=2,
        monetary_cost=0.5,
        risk=InformationAcquisitionRisk.LOW,
    )
    assert cost.questions == 1
    assert cost.internal_calls == 2
    assert cost.risk == InformationAcquisitionRisk.LOW

    with pytest.raises(InvalidInformationAcquisitionContractError):
        InformationAcquisitionCost(questions=-1)

    with pytest.raises(InvalidInformationAcquisitionContractError):
        InformationAcquisitionCost(monetary_cost=-0.01)

    # Serialization roundtrip
    d = cost.to_dict()
    reconstructed = InformationAcquisitionCost.from_dict(d)
    assert reconstructed == cost


def test_acquisition_estimate_invariants() -> None:
    cost = InformationAcquisitionCost(internal_calls=1)
    estimate = InformationAcquisitionEstimate(
        cost=cost,
        duration_seconds=1.5,
        probability_of_success=0.9,
        confidence_gain=0.8,
    )
    assert estimate.probability_of_success == 0.9

    with pytest.raises(InvalidInformationAcquisitionContractError):
        InformationAcquisitionEstimate(cost=cost, probability_of_success=1.5)

    d = estimate.to_dict()
    reconstructed = InformationAcquisitionEstimate.from_dict(d)
    assert reconstructed == estimate


def test_acquisition_request_invariants() -> None:
    gap = GoalInformationGap(id="gap-1", question="What is the environment?")
    req = InformationAcquisitionRequest(
        id="acq-req-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        gap_id="gap-1",
        gap=gap,
        maximum_questions_remaining=2,
    )
    assert req.id == "acq-req-1"
    assert req.maximum_questions_remaining == 2

    # Invariant: Empty IDs disallowed
    with pytest.raises(InvalidInformationAcquisitionContractError):
        InformationAcquisitionRequest(
            id="",
            agent_run_id="run-1",
            goal_id="goal-1",
            gap_id="gap-1",
            gap=gap,
        )

    # Invariant: Negative limit disallowed
    with pytest.raises(InvalidInformationAcquisitionContractError):
        InformationAcquisitionRequest(
            id="acq-req-1",
            agent_run_id="run-1",
            goal_id="goal-1",
            gap_id="gap-1",
            gap=gap,
            maximum_questions_remaining=-1,
        )

    d = req.to_dict()
    reconstructed = InformationAcquisitionRequest.from_dict(d)
    assert reconstructed.id == req.id
    assert reconstructed.gap_id == req.gap_id


def test_unknown_enum_rejection() -> None:
    with pytest.raises(InvalidInformationAcquisitionContractError):
        InformationAcquisitionCost(risk="unknown_risk_level")

    with pytest.raises(InvalidInformationAcquisitionContractError):
        InformationAcquisitionCandidate(
            strategy="invalid_strategy",
            estimated_cost=InformationAcquisitionCost(),
        )


# ── Decision & Resolver Selection Tests ──────────────────────────────────────


def test_deterministic_candidate_ordering() -> None:
    resolver = DefaultInformationAcquisitionResolver()
    policy = InformationAcquisitionPolicy()

    c1 = InformationAcquisitionCandidate(
        strategy=InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
        estimated_cost=InformationAcquisitionCost(external_calls=1),
        probability_of_resolution=0.6,
        risk=InformationAcquisitionRisk.MEDIUM,
    )
    c2 = InformationAcquisitionCandidate(
        strategy=InformationAcquisitionStrategy.SEARCH_KNOWLEDGE,
        estimated_cost=InformationAcquisitionCost(internal_calls=1),
        probability_of_resolution=0.85,
        risk=InformationAcquisitionRisk.NONE,
    )

    ordered = resolver._order_candidates((c1, c2), policy)
    assert ordered[0].strategy == InformationAcquisitionStrategy.SEARCH_KNOWLEDGE
    assert ordered[1].strategy == InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE


def test_prohibited_strategy_never_selected() -> None:
    service = InformationAcquisitionService()
    gap = GoalInformationGap(id="gap-1", question="Target user?")
    request = InformationAcquisitionRequest(
        id="req-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        gap_id="gap-1",
        gap=gap,
        prohibited_strategies=(InformationAcquisitionStrategy.ASK_USER,),
    )

    result = service.acquire_information(request)
    assert result.decision.strategy != InformationAcquisitionStrategy.ASK_USER


def test_unpermitted_strategy_never_selected() -> None:
    service = InformationAcquisitionService()
    gap = GoalInformationGap(id="gap-1", question="Confidential query?")
    request = InformationAcquisitionRequest(
        id="req-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        gap_id="gap-1",
        gap=gap,
        permissions=(),  # No external search or inference permission
        sensitivity="confidential",
    )

    policy = InformationAcquisitionPolicy(
        allowed_strategies=(
            InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
            InformationAcquisitionStrategy.PAUSE,
        )
    )

    result = service.acquire_information(request, policy)
    # External search is filtered out due to sensitivity & lack of permission
    assert (
        result.decision.strategy
        != InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE
    )


def test_human_review_selected_on_critical_risk() -> None:
    service = InformationAcquisitionService()
    gap = {
        "id": "gap-crit",
        "question": "Critical architectural breaking change",
        "impact": "critical",
        "is_blocking": True,
    }
    request = InformationAcquisitionRequest(
        id="req-crit",
        agent_run_id="run-1",
        goal_id="goal-1",
        gap_id="gap-crit",
        gap=gap,
    )

    result = service.acquire_information(request)
    assert result.decision.strategy in (
        InformationAcquisitionStrategy.REQUEST_HUMAN_REVIEW,
        InformationAcquisitionStrategy.ASK_USER,
    )


# ── Mandatory E2E Flow Tests ─────────────────────────────────────────────────


def test_e2e_flow_ask_user() -> None:
    """Cognitive result -> blocking user gap -> request -> ask_user decision."""
    service = InformationAcquisitionService()
    gap = GoalInformationGap(
        id="gap-user-1",
        question="Which authentication provider should be enabled?",
        required=True,
    )

    request = InformationAcquisitionRequest(
        id="acq-req-user",
        agent_run_id="run-100",
        goal_id="goal-200",
        gap_id="gap-user-1",
        gap=gap,
        maximum_questions_remaining=3,
    )

    result = service.acquire_information(request)
    assert result.status == InformationAcquisitionStatus.SELECTED
    assert result.decision.strategy == InformationAcquisitionStrategy.ASK_USER
    assert result.decision.requires_user_input is True


def test_e2e_flow_internal_resource() -> None:
    """Gap referencing available internal resource -> load_internal_resource decision."""
    service = InformationAcquisitionService()
    gap = {
        "id": "gap-res-1",
        "question": "Need config schema",
        "resource_reference": "res-config-json",
        "is_blocking": True,
    }

    request = InformationAcquisitionRequest(
        id="acq-req-res",
        agent_run_id="run-100",
        goal_id="goal-200",
        gap_id="gap-res-1",
        gap=gap,
        available_resource_ids=("res-config-json",),
        maximum_internal_calls_remaining=10,
    )

    result = service.acquire_information(request)
    assert (
        result.decision.strategy
        == InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE
    )
    assert result.decision.requires_resource is True


def test_e2e_flow_knowledge_search() -> None:
    """Gap resoluble with knowledge store -> search_knowledge decision."""
    service = InformationAcquisitionService()
    gap = {
        "id": "gap-know-1",
        "question": "What is the project naming convention?",
        "is_blocking": False,
    }

    request = InformationAcquisitionRequest(
        id="acq-req-know",
        agent_run_id="run-100",
        goal_id="goal-200",
        gap_id="gap-know-1",
        gap=gap,
    )

    result = service.acquire_information(request)
    assert result.decision.strategy in (
        InformationAcquisitionStrategy.SEARCH_KNOWLEDGE,
        InformationAcquisitionStrategy.SEARCH_REPOSITORY,
    )


def test_e2e_flow_external_search_blocked_by_sensitivity() -> None:
    """High sensitivity gap -> external search blocked -> safe fallback."""
    service = InformationAcquisitionService()
    gap = {
        "id": "gap-ext-sec",
        "question": "Query external secrets provider API",
        "is_blocking": True,
    }

    request = InformationAcquisitionRequest(
        id="acq-req-sec",
        agent_run_id="run-100",
        goal_id="goal-200",
        gap_id="gap-ext-sec",
        gap=gap,
        sensitivity="restricted",
        allowed_strategies=(
            InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
            InformationAcquisitionStrategy.PAUSE,
        ),
    )

    result = service.acquire_information(request)
    assert (
        result.decision.strategy
        != InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE
    )
    assert result.decision.strategy == InformationAcquisitionStrategy.PAUSE


def test_e2e_flow_accept_uncertainty() -> None:
    """Non-blocking gap with high resolution cost -> accept_uncertainty decision."""
    service = InformationAcquisitionService()
    gap = {
        "id": "gap-opt-1",
        "question": "Optional UI theme preference",
        "impact": "low",
        "is_blocking": False,
        "required": False,
    }

    request = InformationAcquisitionRequest(
        id="acq-req-unc",
        agent_run_id="run-100",
        goal_id="goal-200",
        gap_id="gap-opt-1",
        gap=gap,
        prohibited_strategies=(
            InformationAcquisitionStrategy.ASK_USER,
            InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE,
            InformationAcquisitionStrategy.SEARCH_KNOWLEDGE,
            InformationAcquisitionStrategy.SEARCH_REPOSITORY,
        ),
    )

    result = service.acquire_information(request)
    assert result.decision.strategy == InformationAcquisitionStrategy.ACCEPT_UNCERTAINTY


def test_e2e_flow_human_review() -> None:
    """Critical contradiction gap -> request_human_review decision."""
    service = InformationAcquisitionService()
    gap = {
        "id": "gap-human-1",
        "question": "Conflicting security baseline compliance rules",
        "impact": "critical",
        "is_blocking": True,
    }

    request = InformationAcquisitionRequest(
        id="acq-req-hum",
        agent_run_id="run-100",
        goal_id="goal-200",
        gap_id="gap-human-1",
        gap=gap,
        prohibited_strategies=(InformationAcquisitionStrategy.ASK_USER,),
    )

    result = service.acquire_information(request)
    assert (
        result.decision.strategy == InformationAcquisitionStrategy.REQUEST_HUMAN_REVIEW
    )
    assert result.decision.requires_approval is True


# ── Real Integration Test with Cognitive Adapter, Goal, AgentRun ─────────────


from datetime import datetime, timezone

from cmm.agent_runtime import GoalPriority


def test_real_integration_with_cognitive_adapter() -> None:
    """Integration test verifying end-to-end flow from Cognitive Adapter output to Information Acquisition."""
    # 1. Setup Goal & AgentRun
    goal = Goal(
        id="goal-integration-96",
        title="Integrate Information Acquisition",
        description="Integrate Information Acquisition with Agent Runtime",
        kind=GoalKind.MAINTENANCE,
        status=GoalStatus.ACTIVE,
        priority=GoalPriority(),
    )

    agent_run = AgentRun(
        id="run-integration-96",
        agent_id="agent-maintenance",
        goal_id=goal.id,
        status=AgentRuntimeStatus.REASONING,
        autonomy_level=2,
        current_iteration=1,
        started_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    cognitive_result = AgentCognitiveResult(
        id="cog-res-96",
        request_id="cog-req-96",
        agent_run_id=agent_run.id,
        goal_id=goal.id,
        status=AgentCognitiveStatus.WAITING_FOR_USER,
        recommended_decision=AgentCognitiveDecision.ASK_USER,
        reasoning_result_id="rr-96",
        information_gaps=(
            GoalInformationGap(
                id="gap-int-1",
                question="What is the target branch policy?",
                required=True,
            ),
        ),
    )

    # 3. Create Acquisition Request from Cognitive Result
    gap = cognitive_result.information_gaps[0]
    acq_request = InformationAcquisitionRequest(
        id="acq-req-int-96",
        agent_run_id=agent_run.id,
        goal_id=goal.id,
        cognitive_result_id=cognitive_result.id,
        gap_id=gap.id,
        gap=gap,
        maximum_questions_remaining=5,
    )

    # 4. Resolve Acquisition Strategy
    acq_service = InformationAcquisitionService()
    acq_result = acq_service.acquire_information(acq_request)

    # 5. Verify non-mutating, structured result
    assert acq_result.status == InformationAcquisitionStatus.SELECTED
    assert acq_result.decision.strategy == InformationAcquisitionStrategy.ASK_USER
    assert acq_result.request.goal_id == goal.id
    assert acq_result.request.agent_run_id == agent_run.id

    # Verify Goal and AgentRun contracts were NOT mutated
    assert goal.status == GoalStatus.ACTIVE
    assert agent_run.status == AgentRuntimeStatus.REASONING
