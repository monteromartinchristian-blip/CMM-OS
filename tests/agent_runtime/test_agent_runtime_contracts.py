"""Unit tests for Phase 9.1 Agent Runtime contracts, enums, and invariants."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from cmm.agent_runtime import (
    AgentDefinition,
    AgentResult,
    AgentResultOutcome,
    AgentRun,
    AgentRuntimeStatus,
    InvalidAgentContractError,
    RuntimeDecision,
    RuntimeDecisionType,
)


def test_agent_definition_valid_construction() -> None:
    agent = AgentDefinition(
        id="agent-project-maintenance",
        name="Project Maintenance Agent",
        version="1.0.0",
        description="Maintains project structure and quality",
        reasoning_profile="project",
        runtime_policy="project-maintenance",
        observation_profile="repository",
        autonomy_level=2,
        allowed_goal_types=("project_improvement", "maintenance"),
        allowed_operations=("clean", "lint"),
        prohibited_operations=("delete_repo",),
        budget_policy="default-budget",
        approval_policy="project-approval",
        recovery_policy="safe-recovery",
        enabled=True,
        metadata={"key": "value"},
    )

    assert agent.id == "agent-project-maintenance"
    assert agent.autonomy_level == 2
    assert agent.allowed_goal_types == ("project_improvement", "maintenance")
    assert isinstance(agent.metadata, MappingProxyType)
    assert agent.metadata["key"] == "value"


def test_agent_definition_invariants_no_execution_logic() -> None:
    """Invariant 1: AgentDefinition configures runtime but does not execute logic."""
    agent = AgentDefinition(
        id="agent-1",
        name="Test Agent",
        version="1",
        description="Desc",
        reasoning_profile="prof",
        runtime_policy="pol",
        observation_profile="obs",
        autonomy_level=1,
    )
    # Verify no execution or AI provider methods exist on contract
    assert not hasattr(agent, "execute")
    assert not hasattr(agent, "run")
    assert not hasattr(agent, "query_llm")


def test_agent_definition_invalid_autonomy_level() -> None:
    """Invariant 3: Autonomy level cannot be negative or invalid."""
    with pytest.raises(
        InvalidAgentContractError, match="autonomy_level cannot be negative"
    ):
        AgentDefinition(
            id="agent-1",
            name="Agent",
            version="1",
            description="d",
            reasoning_profile="r",
            runtime_policy="p",
            observation_profile="o",
            autonomy_level=-1,
        )

    with pytest.raises(
        InvalidAgentContractError, match="autonomy_level must be an integer"
    ):
        AgentDefinition(
            id="agent-1",
            name="Agent",
            version="1",
            description="d",
            reasoning_profile="r",
            runtime_policy="p",
            observation_profile="o",
            autonomy_level="high",  # type: ignore[arg-type]
        )


def test_agent_run_valid_construction() -> None:
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id="agent-run-123",
        agent_id="agent-project-maintenance",
        goal_id="goal-123",
        status=AgentRuntimeStatus.EXECUTING,
        autonomy_level=2,
        current_iteration=3,
        started_at=now,
        updated_at=now,
    )

    assert run.id == "agent-run-123"
    assert run.agent_id == "agent-project-maintenance"
    assert run.goal_id == "goal-123"
    assert run.status == AgentRuntimeStatus.EXECUTING
    assert run.current_iteration == 3


def test_agent_run_invariant_references_one_agent_and_goal() -> None:
    """Invariant 2: AgentRun references exactly one agent and one goal."""
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id="agent-run-1",
        agent_id="agent-1",
        goal_id="goal-1",
        status="executing",
        autonomy_level=1,
        current_iteration=0,
        started_at=now,
        updated_at=now,
    )
    assert isinstance(run.agent_id, str) and run.agent_id == "agent-1"
    assert isinstance(run.goal_id, str) and run.goal_id == "goal-1"

    with pytest.raises(
        InvalidAgentContractError, match="agent_id must be a non-empty string"
    ):
        AgentRun(
            id="run-1",
            agent_id="",
            goal_id="goal-1",
            status="executing",
            autonomy_level=1,
            current_iteration=0,
            started_at=now,
            updated_at=now,
        )


def test_agent_run_iteration_counter_non_negative() -> None:
    """Invariant 4: Iteration counters cannot be negative."""
    now = datetime.now(timezone.utc)
    with pytest.raises(
        InvalidAgentContractError, match="current_iteration cannot be negative"
    ):
        AgentRun(
            id="run-1",
            agent_id="agent-1",
            goal_id="goal-1",
            status=AgentRuntimeStatus.EXECUTING,
            autonomy_level=1,
            current_iteration=-1,
            started_at=now,
            updated_at=now,
        )


def test_agent_run_timestamp_coherence() -> None:
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(seconds=10)
    with pytest.raises(
        InvalidAgentContractError, match="completed_at cannot be prior to started_at"
    ):
        AgentRun(
            id="run-1",
            agent_id="agent-1",
            goal_id="goal-1",
            status=AgentRuntimeStatus.COMPLETED,
            autonomy_level=1,
            current_iteration=1,
            started_at=now,
            updated_at=now,
            completed_at=earlier,
        )


def test_runtime_decision_valid_construction() -> None:
    now = datetime.now(timezone.utc)
    decision = RuntimeDecision(
        id="decision-123",
        run_id="agent-run-123",
        decision=RuntimeDecisionType.EXECUTE,
        confidence=0.95,
        created_at=now,
        reason_codes=("info_complete", "budget_ok"),
        inputs=({"step": 1},),
        requires_approval=False,
    )

    assert decision.id == "decision-123"
    assert decision.decision == RuntimeDecisionType.EXECUTE
    assert decision.confidence == 0.95
    assert decision.reason_codes == ("info_complete", "budget_ok")


def test_runtime_decision_invalid_confidence() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(
        InvalidAgentContractError, match="confidence must be between 0.0 and 1.0"
    ):
        RuntimeDecision(
            id="dec-1",
            run_id="run-1",
            decision=RuntimeDecisionType.PLAN,
            confidence=1.5,
            created_at=now,
        )


def test_agent_result_valid_construction() -> None:
    start = datetime.now(timezone.utc) - timedelta(seconds=5)
    end = datetime.now(timezone.utc)
    result = AgentResult(
        id="result-123",
        agent_run_id="agent-run-123",
        goal_id="goal-123",
        status=AgentRuntimeStatus.COMPLETED,
        outcome=AgentResultOutcome.SUCCESS,
        confidence=0.98,
        trace_id="trace-abc",
        started_at=start,
        completed_at=end,
        duration_ms=5000,
        completed_workflows=("wf-1",),
        completed_operations=("op-1", "op-2"),
    )

    assert result.id == "result-123"
    assert result.status == AgentRuntimeStatus.COMPLETED
    assert result.outcome == AgentResultOutcome.SUCCESS
    assert result.duration_ms == 5000


def test_agent_result_invariant_timestamp_coherence() -> None:
    """Invariant 5: Completed result must contain coherent timestamps."""
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(seconds=100)
    with pytest.raises(
        InvalidAgentContractError, match="completed_at cannot be prior to started_at"
    ):
        AgentResult(
            id="res-1",
            agent_run_id="run-1",
            goal_id="goal-1",
            status=AgentRuntimeStatus.COMPLETED,
            outcome="success",
            confidence=0.9,
            trace_id="t-1",
            started_at=now,
            completed_at=earlier,
            duration_ms=100,
        )


def test_collections_mutability_isolation() -> None:
    """Invariant 6: Internal collections must not share mutability between instances."""
    input_list = ["type_a", "type_b"]
    input_meta = {"env": "test"}

    agent = AgentDefinition(
        id="agent-1",
        name="Agent",
        version="1",
        description="d",
        reasoning_profile="r",
        runtime_policy="p",
        observation_profile="o",
        autonomy_level=1,
        allowed_goal_types=input_list,  # type: ignore[arg-type]
        metadata=input_meta,
    )

    # Mutating original inputs should not mutate contract
    input_list.append("type_c")
    input_meta["env"] = "production"

    assert agent.allowed_goal_types == ("type_a", "type_b")
    assert agent.metadata["env"] == "test"

    # Attempting mutation on contract properties should fail
    with pytest.raises((AttributeError, TypeError)):
        agent.allowed_goal_types.append("type_d")  # type: ignore[attr-defined]

    with pytest.raises((TypeError, AttributeError)):
        agent.metadata["env"] = "hacked"  # type: ignore[index]


def test_serialization_and_deserialization_roundtrip() -> None:
    """Invariant 7: Contracts convert to structured representation and reconstruct without data loss."""
    now = datetime.now(timezone.utc)
    original_def = AgentDefinition(
        id="agent-123",
        name="Test Agent",
        version="2.0",
        description="Desc",
        reasoning_profile="profile-1",
        runtime_policy="policy-1",
        observation_profile="obs-1",
        autonomy_level=3,
        allowed_goal_types=("goal_a",),
        metadata={"owner": "team"},
    )
    def_dict = original_def.to_dict()
    reconstructed_def = AgentDefinition.from_dict(def_dict)
    assert reconstructed_def == original_def

    original_run = AgentRun(
        id="run-1",
        agent_id="agent-123",
        goal_id="goal-456",
        status=AgentRuntimeStatus.REASONING,
        autonomy_level=3,
        current_iteration=2,
        started_at=now,
        updated_at=now,
        metadata={"step": 5},
    )
    run_dict = original_run.serialize()
    reconstructed_run = AgentRun.from_dict(run_dict)
    assert reconstructed_run == original_run

    original_dec = RuntimeDecision(
        id="dec-1",
        run_id="run-1",
        decision=RuntimeDecisionType.SEARCH,
        confidence=0.88,
        created_at=now,
        reason_codes=("code1",),
        inputs=("query",),
    )
    dec_dict = original_dec.to_dict()
    reconstructed_dec = RuntimeDecision.from_dict(dec_dict)
    assert reconstructed_dec == original_dec

    original_res = AgentResult(
        id="res-1",
        agent_run_id="run-1",
        goal_id="goal-456",
        status=AgentRuntimeStatus.COMPLETED,
        outcome=AgentResultOutcome.SUCCESS,
        confidence=0.99,
        trace_id="trace-123",
        started_at=now,
        completed_at=now + timedelta(seconds=10),
        duration_ms=10000,
    )
    res_dict = original_res.to_dict()
    reconstructed_res = AgentResult.from_dict(res_dict)
    assert reconstructed_res == original_res


def test_enum_rejection_for_unknown_values() -> None:
    """Invariant 8: Unknown values of enums must be rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(
        InvalidAgentContractError, match="Invalid AgentRuntimeStatus string"
    ):
        AgentRun(
            id="run-1",
            agent_id="agent-1",
            goal_id="goal-1",
            status="super_running",  # invalid
            autonomy_level=1,
            current_iteration=0,
            started_at=now,
            updated_at=now,
        )

    with pytest.raises(
        InvalidAgentContractError, match="Invalid RuntimeDecisionType string"
    ):
        RuntimeDecision(
            id="dec-1",
            run_id="run-1",
            decision="quantum_teleport",  # invalid
            confidence=0.5,
            created_at=now,
        )


def test_metadata_does_not_alter_public_fields() -> None:
    """Invariant 9: Metadata does not alter the semantics of public fields."""
    agent = AgentDefinition(
        id="agent-1",
        name="Agent 1",
        version="1",
        description="d",
        reasoning_profile="r",
        runtime_policy="p",
        observation_profile="o",
        autonomy_level=1,
        metadata={"autonomy_level": 999, "id": "override-id"},
    )
    assert agent.id == "agent-1"
    assert agent.autonomy_level == 1
    assert agent.metadata["id"] == "override-id"


def test_metadata_key_validation() -> None:
    with pytest.raises(
        InvalidAgentContractError, match="Metadata keys must be strings"
    ):
        AgentDefinition(
            id="agent-1",
            name="Agent 1",
            version="1",
            description="d",
            reasoning_profile="r",
            runtime_policy="p",
            observation_profile="o",
            autonomy_level=1,
            metadata={123: "value"},  # type: ignore[dict-item]
        )


def test_no_infrastructure_or_llm_dependencies() -> None:
    """Invariant 10: No contract directly depends on LLM model, executor, or backend."""
    from cmm.agent_runtime import contracts

    # Inspect imported modules in contracts.py module scope
    module_dict = contracts.__dict__
    forbidden_terms = (
        "openai",
        "anthropic",
        "langchain",
        "llama",
        "executor",
        "sql",
        "sqlite",
    )
    for key in module_dict:
        for term in forbidden_terms:
            assert term not in key.lower(), (
                f"Found infrastructure term '{term}' in contract module key '{key}'"
            )
