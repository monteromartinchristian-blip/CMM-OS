"""Phase 9.29 – Model requirements resolver tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cmm.agent_runtime.model_requirements_contracts import (
    ModelRequirementsSource,
)
from cmm.agent_runtime.model_requirements_errors import (
    ModelRequirementsConflictError,
    ModelRequirementsResolutionError,
)
from cmm.agent_runtime.model_requirements_resolver import (
    resolve_model_requirements,
)
from kernel.llm.model_selection import ModelRequirements


def _source(
    source_kind: str,
    source_id: str,
    *,
    priority: int = 0,
    requirements: ModelRequirements | None = None,
) -> ModelRequirementsSource:
    return ModelRequirementsSource(
        source_kind=source_kind,
        source_id=source_id,
        priority=priority,
        requirements=requirements or ModelRequirements(),
    )


def test_resolution_combines_most_restrictive_requirements() -> None:
    resolved = resolve_model_requirements(
        (
            _source(
                "agent",
                "agent-1",
                priority=10,
                requirements=ModelRequirements(
                    minimum_context_window=32_000,
                    reasoning=True,
                    privacy="REMOTE_ALLOWED",
                    allowed_providers=("local", "remote"),
                    maximum_input_cost_per_million=Decimal("2.00"),
                    premium_allowed=True,
                ),
            ),
            _source(
                "goal",
                "goal-1",
                priority=20,
                requirements=ModelRequirements(
                    minimum_context_window=128_000,
                    tool_calling=True,
                    privacy="LOCAL_PREFERRED",
                    allowed_providers=("local",),
                    excluded_providers=("blocked",),
                    maximum_input_cost_per_million=Decimal("0.75"),
                    premium_allowed=False,
                ),
            ),
        )
    )

    effective = resolved.effective

    assert effective.minimum_context_window == 128_000
    assert effective.reasoning is True
    assert effective.tool_calling is True
    assert effective.privacy == "LOCAL_PREFERRED"
    assert effective.allowed_providers == ("local",)
    assert effective.excluded_providers == ("blocked",)
    assert effective.maximum_input_cost_per_million == Decimal("0.75")
    assert effective.premium_allowed is False
    assert resolved.requires_premium_approval is False
    assert resolved.warnings


def test_resolution_uses_union_for_capabilities_and_exclusions() -> None:
    resolved = resolve_model_requirements(
        (
            _source(
                "workflow",
                "workflow-1",
                requirements=ModelRequirements(
                    structured_output=True,
                    excluded_providers=("provider-a",),
                ),
            ),
            _source(
                "operation",
                "operation-1",
                requirements=ModelRequirements(
                    vision=True,
                    excluded_providers=("provider-b",),
                ),
            ),
        )
    )

    assert resolved.effective.structured_output is True
    assert resolved.effective.vision is True
    assert resolved.effective.excluded_providers == (
        "provider-a",
        "provider-b",
    )


def test_resolution_preserves_deterministic_source_order() -> None:
    resolved = resolve_model_requirements(
        (
            _source("operation", "operation-2", priority=30),
            _source("agent", "agent-1", priority=10),
            _source("goal", "goal-1", priority=20),
        )
    )

    assert tuple(source.source_kind for source in resolved.sources) == (
        "agent",
        "goal",
        "operation",
    )


def test_resolution_rejects_empty_sources() -> None:
    with pytest.raises(ModelRequirementsResolutionError):
        resolve_model_requirements(())


def test_resolution_rejects_disjoint_allowed_providers() -> None:
    with pytest.raises(ModelRequirementsConflictError):
        resolve_model_requirements(
            (
                _source(
                    "goal",
                    "goal-1",
                    requirements=ModelRequirements(allowed_providers=("provider-a",)),
                ),
                _source(
                    "operation",
                    "operation-1",
                    requirements=ModelRequirements(allowed_providers=("provider-b",)),
                ),
            )
        )


def test_resolution_rejects_allowed_excluded_overlap() -> None:
    with pytest.raises(ModelRequirementsConflictError):
        resolve_model_requirements(
            (
                _source(
                    "goal",
                    "goal-1",
                    requirements=ModelRequirements(allowed_providers=("provider-a",)),
                ),
                _source(
                    "policy",
                    "policy-1",
                    requirements=ModelRequirements(excluded_providers=("provider-a",)),
                ),
            )
        )


def test_sensitive_privacy_is_strictest() -> None:
    resolved = resolve_model_requirements(
        (
            _source(
                "agent",
                "agent-1",
                requirements=ModelRequirements(privacy="PREMIUM_ALLOWED"),
            ),
            _source(
                "policy",
                "policy-1",
                requirements=ModelRequirements(privacy="SENSITIVE"),
            ),
        )
    )

    assert resolved.effective.privacy == "SENSITIVE"


def test_premium_requires_every_source_to_allow_it() -> None:
    resolved = resolve_model_requirements(
        (
            _source(
                "agent",
                "agent-1",
                requirements=ModelRequirements(premium_allowed=True),
            ),
            _source(
                "goal",
                "goal-1",
                requirements=ModelRequirements(premium_allowed=True),
            ),
        )
    )

    assert resolved.effective.premium_allowed is True
    assert resolved.requires_premium_approval is True


def test_runtime_resolution_combines_all_declared_layers() -> None:
    from cmm.agent_runtime.agent_registry_contracts import (
        AgentDescriptor,
        AgentVersion,
    )
    from cmm.agent_runtime.agent_registry_enums import (
        AgentKind,
        AgentLifecycle,
    )
    from cmm.agent_runtime.enums import GoalKind, GoalStatus
    from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
    from cmm.agent_runtime.model_requirements_resolver import (
        resolve_runtime_model_requirements,
    )
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowOperation,
        AgentWorkflowPlan,
    )

    agent = AgentDescriptor(
        agent_id="agent.runtime",
        name="Runtime Agent",
        version=AgentVersion(1, 0, 0),
        kind=AgentKind.GENERAL,
        lifecycle=AgentLifecycle.ACTIVE,
        description="Runtime model requirements test",
        capabilities=(),
        factory_id="factory.runtime",
        model_requirements=ModelRequirements(
            minimum_context_window=16_000,
            reasoning=True,
            allowed_providers=("local", "remote"),
            premium_allowed=True,
        ),
    )
    goal = Goal(
        id="goal-runtime",
        title="Runtime goal",
        description="Runtime resolution test",
        kind=GoalKind.ANALYSIS,
        status=GoalStatus.PLANNING,
        priority=GoalPriority(),
        model_requirements=ModelRequirements(
            minimum_context_window=64_000,
            tool_calling=True,
            allowed_providers=("local",),
            premium_allowed=True,
        ),
    )
    workflow = AgentWorkflowPlan(
        id="plan-runtime",
        goal_id=goal.id,
        agent_run_id="run-runtime",
        workflow_id="workflow-runtime",
        model_requirements=ModelRequirements(
            structured_output=True,
            maximum_input_cost_per_million=Decimal("1.50"),
            premium_allowed=True,
        ),
    )
    operation = AgentWorkflowOperation(
        id="operation-runtime",
        task_id="task-runtime",
        operation_name="llm.reason",
        model_requirements=ModelRequirements(
            minimum_context_window=128_000,
            privacy="LOCAL_ONLY",
            maximum_input_cost_per_million=Decimal("0.75"),
            premium_allowed=False,
        ),
    )

    resolved = resolve_runtime_model_requirements(
        agent=agent,
        goal=goal,
        workflow=workflow,
        operation=operation,
    )

    assert resolved.effective.minimum_context_window == 128_000
    assert resolved.effective.reasoning is True
    assert resolved.effective.tool_calling is True
    assert resolved.effective.structured_output is True
    assert resolved.effective.privacy == "LOCAL_ONLY"
    assert resolved.effective.allowed_providers == ("local",)
    assert resolved.effective.maximum_input_cost_per_million == Decimal("0.75")
    assert resolved.effective.premium_allowed is False
    assert tuple(source.source_kind for source in resolved.sources) == (
        "agent",
        "goal",
        "workflow",
        "operation",
    )


def test_runtime_resolution_ignores_layers_without_requirements() -> None:
    from cmm.agent_runtime.model_requirements_resolver import (
        resolve_runtime_model_requirements,
    )
    from cmm.agent_runtime.operation_execution_contracts import (
        OperationDescriptor,
    )

    operation = OperationDescriptor(
        name="llm.summarize",
        description="Summarize content",
        model_requirements=ModelRequirements(reasoning=True),
    )

    resolved = resolve_runtime_model_requirements(operation=operation)

    assert resolved.effective.reasoning is True
    assert len(resolved.sources) == 1
    assert resolved.sources[0].source_id == "llm.summarize"


def test_runtime_resolution_rejects_missing_requirements() -> None:
    from cmm.agent_runtime.model_requirements_resolver import (
        resolve_runtime_model_requirements,
    )
    from cmm.agent_runtime.operation_execution_contracts import (
        OperationDescriptor,
    )

    operation = OperationDescriptor(
        name="filesystem.read",
        description="Read a local file",
    )

    with pytest.raises(
        ModelRequirementsResolutionError,
        match="No runtime layer declares",
    ):
        resolve_runtime_model_requirements(operation=operation)


def test_runtime_resolution_rejects_invalid_contract_type() -> None:
    from cmm.agent_runtime.model_requirements_resolver import (
        resolve_runtime_model_requirements,
    )

    with pytest.raises(
        ModelRequirementsResolutionError,
        match="agent must be",
    ):
        resolve_runtime_model_requirements(agent=object())


def test_phase_9_29_public_exports() -> None:
    import cmm.agent_runtime as runtime

    expected = (
        "ModelRequirementsSource",
        "ResolvedModelRequirements",
        "ModelRequirementsError",
        "ModelRequirementsConflictError",
        "ModelRequirementsResolutionError",
        "InvalidModelRequirementsContractError",
        "model_requirements_to_dict",
        "model_requirements_from_dict",
        "resolve_model_requirements",
        "resolve_runtime_model_requirements",
    )

    for name in expected:
        assert hasattr(runtime, name)
        assert name in runtime.__all__


def test_runtime_resolution_combines_policy_and_approval_sources() -> None:
    from cmm.agent_runtime.approval_contracts import ApprovalResolution
    from cmm.agent_runtime.enums import (
        ApprovalRequestStatus,
        PolicyDecision,
        PolicyEvaluationStatus,
    )
    from cmm.agent_runtime.model_requirements_resolver import (
        resolve_runtime_model_requirements,
    )
    from cmm.agent_runtime.operation_execution_contracts import (
        OperationDescriptor,
    )
    from cmm.agent_runtime.policy_contracts import (
        PolicyEvaluationResult,
        PolicyRestriction,
    )

    operation = OperationDescriptor(
        name="llm.generate",
        description="Generate structured output",
        model_requirements=ModelRequirements(
            reasoning=True,
            allowed_providers=("local", "remote"),
            premium_allowed=True,
        ),
    )

    policy_result = PolicyEvaluationResult(
        id="policy-eval-runtime",
        request_id="request-runtime",
        status=PolicyEvaluationStatus.COMPLETED,
        decision=PolicyDecision.ALLOW,
        allowed=True,
        denied=False,
        requires_approval=True,
        requires_validation=False,
        requires_information=False,
        paused=False,
        restrictions=(
            PolicyRestriction(
                kind="model_requirements",
                description="Require local execution",
                parameters={
                    "privacy": "LOCAL_ONLY",
                    "allowed_providers": ["local"],
                },
                source_policy_id="policy-local",
                source_rule_id="rule-local",
            ),
        ),
    )

    approval = ApprovalResolution(
        request_id="approval-runtime",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approved_parameters={
            "model_requirements": {
                "minimum_context_window": 128_000,
                "premium_allowed": False,
            }
        },
    )

    resolved = resolve_runtime_model_requirements(
        operation=operation,
        policy_result=policy_result,
        approval_resolution=approval,
    )

    assert resolved.effective.reasoning is True
    assert resolved.effective.privacy == "LOCAL_ONLY"
    assert resolved.effective.allowed_providers == ("local",)
    assert resolved.effective.minimum_context_window == 128_000
    assert resolved.effective.premium_allowed is False
    assert tuple(source.source_kind for source in resolved.sources) == (
        "operation",
        "policy",
        "approval",
    )


def test_runtime_resolution_ignores_empty_policy_and_approval_sources() -> None:
    from cmm.agent_runtime.approval_contracts import ApprovalResolution
    from cmm.agent_runtime.enums import (
        ApprovalRequestStatus,
        PolicyDecision,
        PolicyEvaluationStatus,
    )
    from cmm.agent_runtime.model_requirements_resolver import (
        resolve_runtime_model_requirements,
    )
    from cmm.agent_runtime.operation_execution_contracts import (
        OperationDescriptor,
    )
    from cmm.agent_runtime.policy_contracts import PolicyEvaluationResult

    operation = OperationDescriptor(
        name="llm.reason",
        description="Reason over content",
        model_requirements=ModelRequirements(reasoning=True),
    )

    policy_result = PolicyEvaluationResult(
        id="policy-eval-empty",
        request_id="request-empty",
        status=PolicyEvaluationStatus.COMPLETED,
        decision=PolicyDecision.ALLOW,
        allowed=True,
        denied=False,
        requires_approval=False,
        requires_validation=False,
        requires_information=False,
        paused=False,
    )

    approval = ApprovalResolution(
        request_id="approval-empty",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
    )

    resolved = resolve_runtime_model_requirements(
        operation=operation,
        policy_result=policy_result,
        approval_resolution=approval,
    )

    assert len(resolved.sources) == 1
    assert resolved.sources[0].source_kind == "operation"


def test_phase_9_29_adapter_exports() -> None:
    import cmm.agent_runtime as runtime

    expected = (
        "MODEL_REQUIREMENTS_APPROVAL_KEY",
        "MODEL_REQUIREMENTS_RESTRICTION_KIND",
        "approval_model_requirement_sources",
        "policy_model_requirement_sources",
    )

    for name in expected:
        assert hasattr(runtime, name)
        assert name in runtime.__all__
