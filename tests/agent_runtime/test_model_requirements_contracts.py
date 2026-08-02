"""Phase 9.29 – Model requirements contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from cmm.agent_runtime.model_requirements_contracts import (
    ModelRequirementsSource,
    ResolvedModelRequirements,
    model_requirements_from_dict,
    model_requirements_to_dict,
)
from cmm.agent_runtime.model_requirements_errors import (
    InvalidModelRequirementsContractError,
    ModelRequirementsConflictError,
)
from kernel.llm.model_selection import ModelRequirements


def _requirements() -> ModelRequirements:
    return ModelRequirements(
        minimum_context_window=128_000,
        reasoning=True,
        tool_calling=True,
        structured_output=True,
        privacy="LOCAL_PREFERRED",
        allowed_providers=("local", "remote"),
        excluded_providers=("blocked",),
        maximum_input_cost_per_million=Decimal("1.25"),
        maximum_output_cost_per_million=Decimal("3.50"),
        premium_allowed=False,
    )


def test_model_requirements_round_trip() -> None:
    original = _requirements()

    payload = model_requirements_to_dict(original)
    restored = model_requirements_from_dict(payload)

    assert restored == original
    assert payload["maximum_input_cost_per_million"] == "1.25"
    assert payload["maximum_output_cost_per_million"] == "3.50"


def test_model_requirements_serialization_rejects_wrong_type() -> None:
    with pytest.raises(InvalidModelRequirementsContractError):
        model_requirements_to_dict(object())  # type: ignore[arg-type]


def test_model_requirements_deserialization_rejects_invalid_decimal() -> None:
    with pytest.raises(InvalidModelRequirementsContractError):
        model_requirements_from_dict(
            {"maximum_input_cost_per_million": "not-a-decimal"}
        )


def test_model_requirements_source_is_immutable_and_serializable() -> None:
    source = ModelRequirementsSource(
        source_kind="goal",
        source_id="goal-1",
        requirements=_requirements(),
        priority=20,
        metadata={"policy_version": "1"},
    )

    restored = ModelRequirementsSource.from_dict(source.to_dict())

    assert restored == source
    assert restored.metadata["policy_version"] == "1"

    with pytest.raises(FrozenInstanceError):
        source.priority = 30  # type: ignore[misc]


def test_resolved_requirements_preserve_sources() -> None:
    source = ModelRequirementsSource(
        source_kind="operation",
        source_id="op-1",
        requirements=_requirements(),
    )
    resolved = ResolvedModelRequirements(
        effective=_requirements(),
        sources=(source,),
        requires_premium_approval=True,
        warnings=("premium approval required",),
    )

    restored = ResolvedModelRequirements.from_dict(resolved.to_dict())

    assert restored == resolved
    assert restored.sources[0].source_id == "op-1"
    assert restored.requires_premium_approval is True


def test_source_rejects_untyped_requirements() -> None:
    with pytest.raises(InvalidModelRequirementsContractError):
        ModelRequirementsSource(
            source_kind="goal",
            source_id="goal-1",
            requirements={},  # type: ignore[arg-type]
        )


def test_errors_are_structured() -> None:
    error = ModelRequirementsConflictError(
        "Provider constraints are incompatible",
        {"allowed": ["local"], "excluded": ["local"]},
    )

    assert error.to_dict() == {
        "error_code": "MODEL_REQUIREMENTS_CONFLICT",
        "message": "Provider constraints are incompatible",
        "details": {
            "allowed": ["local"],
            "excluded": ["local"],
        },
    }


def test_operation_descriptor_accepts_typed_model_requirements() -> None:
    from cmm.agent_runtime.operation_execution_contracts import (
        OperationDescriptor,
    )

    requirements = _requirements()
    descriptor = OperationDescriptor(
        name="llm.reason",
        description="Run a model-assisted reasoning operation",
        model_requirements=requirements,
    )

    assert descriptor.model_requirements == requirements


def test_operation_descriptor_rejects_untyped_model_requirements() -> None:
    from cmm.agent_runtime.errors import (
        InvalidAgentOperationContractError,
    )
    from cmm.agent_runtime.operation_execution_contracts import (
        OperationDescriptor,
    )

    with pytest.raises(InvalidAgentOperationContractError):
        OperationDescriptor(
            name="llm.reason",
            description="Run a model-assisted reasoning operation",
            model_requirements={},  # type: ignore[arg-type]
        )


def test_workflow_operation_model_requirements_round_trip() -> None:
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowOperation,
    )

    operation = AgentWorkflowOperation(
        id="workflow-operation-1",
        task_id="task-1",
        operation_name="llm.reason",
        model_requirements=_requirements(),
    )

    restored = AgentWorkflowOperation.from_dict(operation.to_dict())

    assert restored == operation
    assert restored.model_requirements == _requirements()


def test_workflow_operation_remains_backward_compatible() -> None:
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowOperation,
    )

    operation = AgentWorkflowOperation.from_dict(
        {
            "id": "workflow-operation-legacy",
            "task_id": "task-1",
            "operation_name": "filesystem.read_file",
        }
    )

    assert operation.model_requirements is None
    assert operation.to_dict()["model_requirements"] is None


def test_goal_model_requirements_round_trip() -> None:
    from cmm.agent_runtime.enums import GoalKind, GoalStatus
    from cmm.agent_runtime.goal_contracts import Goal, GoalPriority

    goal = Goal(
        id="goal-model-1",
        title="Model-assisted goal",
        description="Goal requiring structured model output",
        kind=GoalKind.ANALYSIS,
        status=GoalStatus.PLANNING,
        priority=GoalPriority(),
        model_requirements=_requirements(),
    )

    restored = Goal.from_dict(goal.to_dict())

    assert restored.model_requirements == _requirements()


def test_goal_remains_backward_compatible_without_model_requirements() -> None:
    from cmm.agent_runtime.enums import GoalKind, GoalStatus
    from cmm.agent_runtime.goal_contracts import Goal, GoalPriority

    goal = Goal(
        id="goal-legacy",
        title="Legacy goal",
        description="Goal without model requirements",
        kind=GoalKind.ANALYSIS,
        status=GoalStatus.PLANNING,
        priority=GoalPriority(),
    )

    restored = Goal.from_dict(goal.to_dict())

    assert restored.model_requirements is None


def test_workflow_plan_model_requirements_round_trip() -> None:
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowPlan,
    )

    plan = AgentWorkflowPlan(
        id="plan-model-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="workflow-1",
        model_requirements=_requirements(),
    )

    restored = AgentWorkflowPlan.from_dict(plan.to_dict())

    assert restored.model_requirements == _requirements()


def test_workflow_plan_rejects_untyped_model_requirements() -> None:
    from cmm.agent_runtime.errors import InvalidAgentPlanningContractError
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowPlan,
    )

    with pytest.raises(InvalidAgentPlanningContractError):
        AgentWorkflowPlan(
            id="plan-invalid",
            goal_id="goal-1",
            agent_run_id="run-1",
            workflow_id="workflow-1",
            model_requirements={},  # type: ignore[arg-type]
        )


def test_agent_descriptor_accepts_and_serializes_model_requirements() -> None:
    from cmm.agent_runtime.agent_registry_contracts import (
        AgentDescriptor,
        AgentVersion,
    )
    from cmm.agent_runtime.agent_registry_enums import (
        AgentKind,
        AgentLifecycle,
    )

    descriptor = AgentDescriptor(
        agent_id="agent.model",
        name="Model Agent",
        version=AgentVersion(1, 0, 0),
        kind=AgentKind.GENERAL,
        lifecycle=AgentLifecycle.ACTIVE,
        description="Agent requiring specific model capabilities",
        capabilities=(),
        factory_id="factory.model",
        model_requirements=_requirements(),
    )

    payload = descriptor.to_dict()

    assert descriptor.model_requirements == _requirements()
    assert payload["model_requirements"] == model_requirements_to_dict(_requirements())


def test_agent_descriptor_lifecycle_preserves_model_requirements() -> None:
    from cmm.agent_runtime.agent_registry_contracts import (
        AgentDescriptor,
        AgentVersion,
    )
    from cmm.agent_runtime.agent_registry_enums import (
        AgentKind,
        AgentLifecycle,
    )

    descriptor = AgentDescriptor(
        agent_id="agent.lifecycle",
        name="Lifecycle Agent",
        version=AgentVersion(1, 0, 0),
        kind=AgentKind.GENERAL,
        lifecycle=AgentLifecycle.EXPERIMENTAL,
        description="Lifecycle preservation test",
        capabilities=(),
        factory_id="factory.lifecycle",
        model_requirements=_requirements(),
    )

    active = descriptor.with_lifecycle(AgentLifecycle.ACTIVE)

    assert active.model_requirements == descriptor.model_requirements


def test_agent_descriptor_rejects_untyped_model_requirements() -> None:
    from cmm.agent_runtime.agent_registry_contracts import (
        AgentDescriptor,
        AgentVersion,
    )
    from cmm.agent_runtime.agent_registry_enums import (
        AgentKind,
        AgentLifecycle,
    )
    from cmm.agent_runtime.agent_registry_errors import (
        AgentRegistryValidationError,
    )

    with pytest.raises(AgentRegistryValidationError):
        AgentDescriptor(
            agent_id="agent.invalid",
            name="Invalid Agent",
            version=AgentVersion(1, 0, 0),
            kind=AgentKind.GENERAL,
            lifecycle=AgentLifecycle.ACTIVE,
            description="Invalid model requirements",
            capabilities=(),
            factory_id="factory.invalid",
            model_requirements={},  # type: ignore[arg-type]
        )
