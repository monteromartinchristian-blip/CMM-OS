"""Phase 9.5 – Cognitive Adapter Test Suite.

Tests for Cognitive Adapter contracts, profile resolution, resource deduplication and permissions,
cognitive session management, result translation, error handling, invariants, and end-to-end flows.
"""

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.cognitive_adapter import (
    AgentCognitiveService,
    DefaultCognitiveRuntimeAdapter,
)
from cmm.agent_runtime.cognitive_adapter_contracts import (
    AgentCognitiveContext,
    AgentCognitiveRequest,
    AgentCognitiveResult,
)
from cmm.agent_runtime.enums import (
    AgentCognitiveDecision,
    AgentCognitiveStatus,
    CognitiveResourceStrategy,
    CognitiveSessionMode,
    GoalKind,
    GoalStatus,
)
from cmm.agent_runtime.errors import (
    CognitiveAdapterExecutionError,
    CognitiveResourceAccessError,
    CognitiveSessionMismatchError,
    CognitiveSessionNotFoundError,
    InvalidAgentCognitiveContractError,
)
from cmm.agent_runtime.goal_contracts import Goal
from cmm.agent_runtime.observation_contracts import (
    Observation,
    ObservationSnapshot,
    ObservationStatus,
)
from cmm.cognitive.contracts import (
    CognitiveFinding,
    CognitiveResult,
    CognitiveStatus,
    Confidence,
)
from cmm.cognitive.enums import ResourceKind, ResourceSourceKind, SensitivityLevel
from cmm.cognitive.resources import Resource, ResourceProvenance


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_sample_snapshot() -> ObservationSnapshot:
    obs = Observation(
        observer="GoalObserver",
        kind="goal",
        subject_id="goal-123",
        statement="Goal goal-123 is ACTIVE",
        value={"goal_id": "goal-123", "status": "active"},
        confidence=1.0,
    )
    return ObservationSnapshot(
        status=ObservationStatus.COMPLETED,
        goal_id="goal-123",
        agent_run_id="run-123",
        observations=(obs,),
    )


def create_sample_resource(
    res_id: str, sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
) -> Resource:
    from cmm.cognitive.resources import ResourceTemporalScope

    prov = ResourceProvenance(
        source_type=ResourceSourceKind.SYSTEM,
        source_id="test_source",
    )
    return Resource(
        id=res_id,
        domain="agent_runtime",
        kind=ResourceKind.STRUCTURED_DATASET,
        source=ResourceSourceKind.SYSTEM,
        content={"data": res_id},
        provenance=prov,
        reliability=Confidence(1.0),
        temporal_scope=ResourceTemporalScope(observed_at=utc_now()),
        sensitivity=sensitivity,
    )


# ── 1. Contracts & Invariants Tests ──────────────────────────────────────────


def test_agent_cognitive_request_validation():
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Analyze current state",
        maximum_questions=2,
        requested_depth="standard",
    )
    assert req.id.startswith("ag-cog-req-")
    assert req.agent_run_id == "run-123"
    assert req.goal_id == "goal-123"
    assert req.maximum_questions == 2

    # Invariant: negative maximum_questions
    with pytest.raises(InvalidAgentCognitiveContractError):
        AgentCognitiveRequest(
            agent_run_id="run-123",
            goal_id="goal-123",
            objective="test",
            maximum_questions=-1,
        )

    # Invariant: invalid requested_depth
    with pytest.raises(InvalidAgentCognitiveContractError):
        AgentCognitiveRequest(
            agent_run_id="run-123",
            goal_id="goal-123",
            objective="test",
            requested_depth="super_deep",
        )

    # Invariant: RESUME session mode without cognitive_session_id
    with pytest.raises(InvalidAgentCognitiveContractError):
        AgentCognitiveRequest(
            agent_run_id="run-123",
            goal_id="goal-123",
            objective="test",
            session_mode=CognitiveSessionMode.RESUME,
            cognitive_session_id=None,
        )


def test_agent_cognitive_result_invariants():
    # Valid result
    res = AgentCognitiveResult(
        request_id="req-123",
        agent_run_id="run-123",
        goal_id="goal-123",
        status=AgentCognitiveStatus.COMPLETED,
        recommended_decision=AgentCognitiveDecision.PLAN,
        reasoning_result_id="reasoning-123",
        confidence=0.85,
    )
    assert res.confidence == 0.85
    assert res.recommended_decision is AgentCognitiveDecision.PLAN

    # Invariant: confidence out of range
    with pytest.raises(InvalidAgentCognitiveContractError):
        AgentCognitiveResult(
            request_id="req-123",
            agent_run_id="run-123",
            goal_id="goal-123",
            status=AgentCognitiveStatus.COMPLETED,
            recommended_decision=AgentCognitiveDecision.PLAN,
            reasoning_result_id="reasoning-123",
            confidence=1.5,
        )

    # Invariant: boolean confidence rejected
    with pytest.raises(InvalidAgentCognitiveContractError):
        AgentCognitiveResult(
            request_id="req-123",
            agent_run_id="run-123",
            goal_id="goal-123",
            status=AgentCognitiveStatus.COMPLETED,
            recommended_decision=AgentCognitiveDecision.PLAN,
            reasoning_result_id="reasoning-123",
            confidence=True,  # bool subclass of int
        )


def test_contract_serialization_round_trip():
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Analyze options",
        reasoning_profile="project",
        resource_ids=("res-1",),
        maximum_questions=3,
        session_mode=CognitiveSessionMode.NEW,
    )
    d = req.to_dict()
    reconstructed = AgentCognitiveRequest.from_dict(d)
    assert reconstructed.agent_run_id == req.agent_run_id
    assert reconstructed.goal_id == req.goal_id
    assert reconstructed.objective == req.objective
    assert reconstructed.reasoning_profile == req.reasoning_profile

    res = AgentCognitiveResult(
        request_id="req-123",
        agent_run_id="run-123",
        goal_id="goal-123",
        status=AgentCognitiveStatus.COMPLETED,
        recommended_decision=AgentCognitiveDecision.PLAN,
        reasoning_result_id="cog-123",
        confidence=0.9,
    )
    res_d = res.to_dict()
    reconstructed_res = AgentCognitiveResult.from_dict(res_d)
    assert reconstructed_res.confidence == 0.9
    assert reconstructed_res.recommended_decision is AgentCognitiveDecision.PLAN


# ── 2. Enums Tests ───────────────────────────────────────────────────────────


def test_enums_completeness():
    assert AgentCognitiveStatus.PENDING.value == "pending"
    assert AgentCognitiveStatus.WAITING_FOR_USER.value == "waiting_for_user"
    assert (
        AgentCognitiveStatus.INSUFFICIENT_INFORMATION.value
        == "insufficient_information"
    )

    assert AgentCognitiveDecision.ASK_USER.value == "ask_user"
    assert AgentCognitiveDecision.LOAD_RESOURCE.value == "load_resource"
    assert AgentCognitiveDecision.PLAN.value == "plan"
    assert (
        AgentCognitiveDecision.COMPLETE_WITHOUT_ACTION.value
        == "complete_without_action"
    )

    assert CognitiveSessionMode.NEW.value == "new"
    assert CognitiveSessionMode.RESUME.value == "resume"
    assert CognitiveSessionMode.FORK.value == "fork"
    assert CognitiveSessionMode.STATELESS.value == "stateless"

    assert CognitiveResourceStrategy.AUTOMATIC.value == "automatic"


# ── 3. Context Preparation & Resources Tests ─────────────────────────────────


def test_context_preparation_resource_deduplication():
    r1 = create_sample_resource("res-1")
    r2 = create_sample_resource("res-2")
    r1_dup = create_sample_resource("res-1")  # duplicate ID

    adapter = DefaultCognitiveRuntimeAdapter()
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Test deduplication",
        resources=(r1, r2, r1_dup),
    )
    ctx = adapter.build_context(req)
    assert len(ctx.combined_resources) == 2
    assert tuple(r.id for r in ctx.combined_resources) == ("res-1", "res-2")


def test_context_preparation_permissions():
    r_restricted = create_sample_resource("res-secret", SensitivityLevel.RESTRICTED)
    adapter = DefaultCognitiveRuntimeAdapter()

    # Request without restricted permissions -> raises CognitiveResourceAccessError
    req_no_perm = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Test permission",
        resources=(r_restricted,),
        permissions=("read",),
    )
    with pytest.raises(CognitiveResourceAccessError):
        adapter.build_context(req_no_perm)

    # Request with restricted_access -> allowed
    req_with_perm = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Test permission",
        resources=(r_restricted,),
        permissions=("restricted_access",),
    )
    ctx = adapter.build_context(req_with_perm)
    assert len(ctx.combined_resources) == 1


def test_context_derived_from_snapshot():
    snapshot = create_sample_snapshot()
    adapter = DefaultCognitiveRuntimeAdapter()
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Derive resources",
        observation_snapshot=snapshot,
    )
    ctx = adapter.build_context(req)
    assert len(ctx.derived_resources) > 0
    assert len(ctx.combined_resources) > 0
    assert ctx.derived_resources[0].provenance.source_type is ResourceSourceKind.SYSTEM


# ── 4. Profile Selection Tests ───────────────────────────────────────────────


def test_profile_resolution_order():
    class DummyGoalManager:
        def get_goal(self, goal_id: str):
            from cmm.agent_runtime.goal_contracts import GoalPriority

            return Goal(
                id=goal_id,
                title="Goal title",
                description="Goal description",
                kind=GoalKind.INFORMATION,
                status=GoalStatus.ACTIVE,
                priority=GoalPriority(0.5),
                metadata={"reasoning_profile": "goal_profile"},
            )

    # 1. Explicit request profile overrides
    adapter1 = DefaultCognitiveRuntimeAdapter(goal_manager=DummyGoalManager())
    req1 = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Test profile",
        reasoning_profile="custom_profile",
    )
    ctx1 = adapter1.build_context(req1)
    assert ctx1.reasoning_profile == "custom_profile"

    # 2. Goal profile used when request profile is default ("general")
    req2 = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Test profile",
        reasoning_profile="general",
    )
    ctx2 = adapter1.build_context(req2)
    assert ctx2.reasoning_profile == "goal_profile"

    # 3. Fallback to default configuration profile ("general")
    adapter3 = DefaultCognitiveRuntimeAdapter()
    ctx3 = adapter3.build_context(req2)
    assert ctx3.reasoning_profile == "general"


# ── 5. Cognitive Sessions Tests ───────────────────────────────────────────────


def test_session_management_new_resume_fork_stateless():
    adapter = DefaultCognitiveRuntimeAdapter()

    # Mode: NEW
    req_new = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Session new",
        session_mode=CognitiveSessionMode.NEW,
    )
    ctx_new = adapter.build_context(req_new)
    assert ctx_new.session_reference is not None
    assert ctx_new.session_reference.mode is CognitiveSessionMode.NEW
    new_s_id = ctx_new.session_reference.session_id

    # Mode: RESUME existing session
    req_resume = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Session resume",
        session_mode=CognitiveSessionMode.RESUME,
        cognitive_session_id=new_s_id,
    )
    ctx_resume = adapter.build_context(req_resume)
    assert ctx_resume.session_reference.session_id == new_s_id
    assert ctx_resume.session_reference.mode is CognitiveSessionMode.RESUME

    # Mode: RESUME non-existent session -> CognitiveSessionNotFoundError
    req_resume_bad = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Session resume bad",
        session_mode=CognitiveSessionMode.RESUME,
        cognitive_session_id="non-existent-session",
    )
    with pytest.raises(CognitiveSessionNotFoundError):
        adapter.build_context(req_resume_bad)

    # Mode: RESUME goal mismatch -> CognitiveSessionMismatchError
    req_resume_mismatch = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="other-goal-999",
        objective="Session resume mismatch",
        session_mode=CognitiveSessionMode.RESUME,
        cognitive_session_id=new_s_id,
    )
    with pytest.raises(CognitiveSessionMismatchError):
        adapter.build_context(req_resume_mismatch)

    # Mode: FORK
    req_fork = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Session fork",
        session_mode=CognitiveSessionMode.FORK,
        cognitive_session_id=new_s_id,
    )
    ctx_fork = adapter.build_context(req_fork)
    assert ctx_fork.session_reference.mode is CognitiveSessionMode.FORK
    assert ctx_fork.session_reference.parent_session_id == new_s_id

    # Mode: STATELESS
    req_stateless = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Session stateless",
        session_mode=CognitiveSessionMode.STATELESS,
    )
    ctx_stateless = adapter.build_context(req_stateless)
    assert ctx_stateless.session_reference is None


# ── 6. Result Translation & Decision Mapping Tests ───────────────────────────


def test_decision_mapping_rules():
    adapter = DefaultCognitiveRuntimeAdapter()
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Test decision mapping",
    )

    # 1. Ask User: blocking question finding
    cog_ask = CognitiveResult(
        objective="Obj",
        status=CognitiveStatus.WAITING_FOR_USER,
        confidence=Confidence(0.9),
        findings=(
            CognitiveFinding(
                code="ask_user_clarification",
                message="User input needed",
                blocking=True,
            ),
        ),
    )
    res_ask = adapter.translate_result(cog_ask, req)
    assert res_ask.recommended_decision is AgentCognitiveDecision.ASK_USER
    assert res_ask.status is AgentCognitiveStatus.WAITING_FOR_USER
    assert res_ask.requires_user_input is True

    # 2. Load Resource: blocking resource gap finding
    cog_res = CognitiveResult(
        objective="Obj",
        status=CognitiveStatus.WAITING_FOR_RESOURCE,
        confidence=Confidence(0.8),
        findings=(
            CognitiveFinding(
                code="missing_resource_load_resource",
                message="Need file resource",
                blocking=True,
            ),
        ),
    )
    res_res = adapter.translate_result(cog_res, req)
    assert res_res.recommended_decision is AgentCognitiveDecision.LOAD_RESOURCE
    assert res_res.status is AgentCognitiveStatus.WAITING_FOR_RESOURCE
    assert res_res.requires_resource is True

    # 3. Insufficient Information
    cog_insuff = CognitiveResult(
        objective="Obj",
        status=CognitiveStatus.INSUFFICIENT_INFORMATION,
        confidence=Confidence(0.3),
        findings=(
            CognitiveFinding(
                code="unresolvable_gap",
                message="Cannot proceed without facts",
                blocking=True,
            ),
        ),
    )
    res_insuff = adapter.translate_result(cog_insuff, req)
    assert (
        res_insuff.recommended_decision
        is AgentCognitiveDecision.INSUFFICIENT_INFORMATION
    )
    assert res_insuff.status is AgentCognitiveStatus.INSUFFICIENT_INFORMATION

    # 4. Plan: Actionable result
    cog_plan = CognitiveResult(
        objective="Obj",
        status=CognitiveStatus.COMPLETED,
        confidence=Confidence(0.95),
    )
    res_plan = adapter.translate_result(cog_plan, req)
    assert res_plan.recommended_decision is AgentCognitiveDecision.PLAN
    assert res_plan.status is AgentCognitiveStatus.COMPLETED

    # 5. Complete Without Action
    cog_no_act = CognitiveResult(
        objective="Obj",
        status=CognitiveStatus.COMPLETED,
        confidence=Confidence(1.0),
        metadata={"complete_without_action": True},
    )
    res_no_act = adapter.translate_result(cog_no_act, req)
    assert (
        res_no_act.recommended_decision
        is AgentCognitiveDecision.COMPLETE_WITHOUT_ACTION
    )

    # 6. Fail: Cognitive failure
    cog_fail = CognitiveResult(
        objective="Obj",
        status=CognitiveStatus.FAILED,
        confidence=Confidence(0.0),
        findings=(
            CognitiveFinding(
                code="cognitive_error",
                message="Engine crash",
                blocking=True,
            ),
        ),
    )
    res_fail = adapter.translate_result(cog_fail, req)
    assert res_fail.recommended_decision is AgentCognitiveDecision.FAIL
    assert res_fail.status is AgentCognitiveStatus.FAILED


# ── 7. Required E2E Mandatory Flows ─────────────────────────────────────────


def test_e2e_flow_planning_prepared():
    """Goal activo -> Snapshot -> Request -> Context -> ReasoningEngine -> Plan decision."""
    snapshot = create_sample_snapshot()
    adapter = DefaultCognitiveRuntimeAdapter()

    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Determine next safe operational step",
        observation_snapshot=snapshot,
    )

    res = adapter.analyze(req)
    assert res.recommended_decision is AgentCognitiveDecision.PLAN
    assert res.status is AgentCognitiveStatus.COMPLETED
    assert res.goal_id == "goal-123"
    assert res.agent_run_id == "run-123"
    assert res.confidence == 1.0


def test_e2e_flow_with_question():
    """Ambiguous goal -> Cognitive Layer detects blocking gap -> ask_user decision."""

    def mock_cognitive_layer(context: AgentCognitiveContext) -> CognitiveResult:
        return CognitiveResult(
            objective=context.goal.title if context.goal else "objective",
            status=CognitiveStatus.WAITING_FOR_USER,
            confidence=Confidence(0.5),
            findings=(
                CognitiveFinding(
                    code="ask_user_clarification",
                    message="Which target environment should be deployed to?",
                    blocking=True,
                ),
            ),
        )

    adapter = DefaultCognitiveRuntimeAdapter(cognitive_layer=mock_cognitive_layer)
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Deploy application",
    )

    res = adapter.analyze(req)
    assert res.recommended_decision is AgentCognitiveDecision.ASK_USER
    assert res.requires_user_input is True
    assert len(res.questions) == 1


def test_e2e_flow_missing_resource():
    """Goal -> gap resolvable by loading internal resource -> load_resource decision."""

    def mock_cognitive_layer(context: AgentCognitiveContext) -> CognitiveResult:
        return CognitiveResult(
            objective="Analyze config",
            status=CognitiveStatus.WAITING_FOR_RESOURCE,
            confidence=Confidence(0.6),
            findings=(
                CognitiveFinding(
                    code="gap_load_resource_config",
                    message="Requires loading application.json",
                    blocking=True,
                ),
            ),
        )

    adapter = DefaultCognitiveRuntimeAdapter(cognitive_layer=mock_cognitive_layer)
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Analyze configuration",
    )

    res = adapter.analyze(req)
    assert res.recommended_decision is AgentCognitiveDecision.LOAD_RESOURCE
    assert res.requires_resource is True
    assert len(res.information_gaps) == 1


def test_e2e_flow_complete_without_action():
    """Information goal -> fully satisfied -> complete_without_action decision."""

    def mock_cognitive_layer(context: AgentCognitiveContext) -> CognitiveResult:
        return CognitiveResult(
            objective="Query system version",
            status=CognitiveStatus.COMPLETED,
            confidence=Confidence(1.0),
            metadata={
                "complete_without_action": True,
                "relevant_facts": ["System version is 1.4.0"],
            },
        )

    adapter = DefaultCognitiveRuntimeAdapter(cognitive_layer=mock_cognitive_layer)
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Query system version",
    )

    res = adapter.analyze(req)
    assert res.recommended_decision is AgentCognitiveDecision.COMPLETE_WITHOUT_ACTION
    assert res.status is AgentCognitiveStatus.COMPLETED
    assert res.relevant_facts == ("System version is 1.4.0",)


def test_e2e_flow_error_handling():
    """Cognitive layer exception -> CognitiveAdapterExecutionError."""

    def faulty_cognitive_layer(context: AgentCognitiveContext):
        raise RuntimeError("Internal LLM connection timeout")

    adapter = DefaultCognitiveRuntimeAdapter(cognitive_layer=faulty_cognitive_layer)
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Unstable query",
    )

    with pytest.raises(CognitiveAdapterExecutionError):
        adapter.analyze(req)


def test_agent_cognitive_service_facade():
    """Verify AgentCognitiveService facade forwards calls properly."""
    service = AgentCognitiveService()
    req = AgentCognitiveRequest(
        agent_run_id="run-123",
        goal_id="goal-123",
        objective="Test facade",
    )
    res = service.analyze(req)
    assert isinstance(res, AgentCognitiveResult)
    assert res.recommended_decision is AgentCognitiveDecision.PLAN
    assert service.cancel(req.id) is True
