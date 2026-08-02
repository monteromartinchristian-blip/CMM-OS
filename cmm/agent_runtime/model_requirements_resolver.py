"""Phase 9.29 – Deterministic model requirements resolution."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from cmm.agent_runtime.model_requirements_contracts import (
    ModelRequirementsSource,
    ResolvedModelRequirements,
)
from cmm.agent_runtime.model_requirements_errors import (
    ModelRequirementsConflictError,
    ModelRequirementsResolutionError,
)
from kernel.llm.model_selection import ModelRequirements

_PRIVACY_RANK: dict[str, int] = {
    "REMOTE_ALLOWED": 0,
    "PREMIUM_ALLOWED": 1,
    "LOCAL_PREFERRED": 2,
    "LOCAL_ONLY": 3,
    "SENSITIVE": 4,
}

_CAPABILITY_FIELDS: tuple[str, ...] = (
    "reasoning",
    "tool_calling",
    "structured_output",
    "json_mode",
    "json_schema",
    "vision",
    "audio_input",
    "audio_output",
    "embeddings",
)


def _strictest_privacy(sources: tuple[ModelRequirementsSource, ...]) -> str:
    values = tuple(source.requirements.privacy for source in sources)

    try:
        return max(values, key=lambda value: _PRIVACY_RANK[value])
    except KeyError as exc:
        raise ModelRequirementsResolutionError(
            "Unsupported privacy policy",
            {"privacy": str(exc.args[0])},
        ) from exc


def _minimum_optional_decimal(
    values: Iterable[Decimal | None],
) -> Decimal | None:
    declared = tuple(value for value in values if value is not None)
    return min(declared) if declared else None


def _allowed_provider_intersection(
    sources: tuple[ModelRequirementsSource, ...],
) -> tuple[str, ...]:
    declared = [
        set(source.requirements.allowed_providers)
        for source in sources
        if source.requirements.allowed_providers
    ]

    if not declared:
        return ()

    effective = set.intersection(*declared)
    if not effective:
        raise ModelRequirementsConflictError(
            "Allowed provider constraints have no common provider",
            {
                "allowed_provider_sets": [
                    sorted(provider_set) for provider_set in declared
                ]
            },
        )

    return tuple(sorted(effective))


def resolve_model_requirements(
    sources: Iterable[ModelRequirementsSource],
) -> ResolvedModelRequirements:
    """Resolve requirement layers without weakening inherited constraints."""

    ordered_sources = tuple(
        sorted(
            sources,
            key=lambda source: (
                source.priority,
                source.source_kind,
                source.source_id,
            ),
        )
    )

    if not ordered_sources:
        raise ModelRequirementsResolutionError(
            "At least one model requirements source is required"
        )

    allowed_providers = _allowed_provider_intersection(ordered_sources)
    excluded_providers = tuple(
        sorted(
            {
                provider
                for source in ordered_sources
                for provider in source.requirements.excluded_providers
            }
        )
    )

    overlap = set(allowed_providers) & set(excluded_providers)
    if overlap:
        raise ModelRequirementsConflictError(
            "Effective provider constraints are incompatible",
            {
                "conflicting_providers": sorted(overlap),
                "allowed_providers": list(allowed_providers),
                "excluded_providers": list(excluded_providers),
            },
        )

    capability_values = {
        field_name: any(
            bool(getattr(source.requirements, field_name)) for source in ordered_sources
        )
        for field_name in _CAPABILITY_FIELDS
    }

    premium_allowed = all(
        source.requirements.premium_allowed for source in ordered_sources
    )
    premium_requested = any(
        source.requirements.premium_allowed for source in ordered_sources
    )

    try:
        effective = ModelRequirements(
            minimum_context_window=max(
                source.requirements.minimum_context_window for source in ordered_sources
            ),
            privacy=_strictest_privacy(ordered_sources),
            allowed_providers=allowed_providers,
            excluded_providers=excluded_providers,
            maximum_input_cost_per_million=_minimum_optional_decimal(
                source.requirements.maximum_input_cost_per_million
                for source in ordered_sources
            ),
            maximum_output_cost_per_million=_minimum_optional_decimal(
                source.requirements.maximum_output_cost_per_million
                for source in ordered_sources
            ),
            premium_allowed=premium_allowed,
            **capability_values,
        )
    except ValueError as exc:
        raise ModelRequirementsConflictError(
            "Effective model requirements are invalid",
            {"reason": str(exc)},
        ) from exc

    warnings: tuple[str, ...] = ()
    if premium_requested and not premium_allowed:
        warnings = (
            "Premium execution was requested but is not permitted by every source",
        )

    return ResolvedModelRequirements(
        effective=effective,
        sources=ordered_sources,
        requires_premium_approval=premium_allowed,
        warnings=warnings,
        metadata={
            "source_count": len(ordered_sources),
            "resolution_strategy": "most_restrictive",
        },
    )


def resolve_runtime_model_requirements(
    *,
    agent: object | None = None,
    goal: object | None = None,
    workflow: object | None = None,
    operation: object | None = None,
    policy_result: object | None = None,
    approval_resolution: object | None = None,
) -> ResolvedModelRequirements:
    """Resolve requirements declared by runtime contracts.

    Layers without requirements are ignored. Precedence is represented
    through deterministic priorities while every hard constraint is
    combined using the most-restrictive strategy.
    """

    from cmm.agent_runtime.agent_registry_contracts import AgentDescriptor
    from cmm.agent_runtime.goal_contracts import Goal
    from cmm.agent_runtime.model_requirements_approval_adapter import (
        approval_model_requirement_sources,
    )
    from cmm.agent_runtime.model_requirements_policy_adapter import (
        policy_model_requirement_sources,
    )
    from cmm.agent_runtime.operation_execution_contracts import (
        OperationDescriptor,
    )
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowOperation,
        AgentWorkflowPlan,
    )

    sources: list[ModelRequirementsSource] = []

    if agent is not None:
        if not isinstance(agent, AgentDescriptor):
            raise ModelRequirementsResolutionError(
                "agent must be an AgentDescriptor or None"
            )
        if agent.model_requirements is not None:
            sources.append(
                ModelRequirementsSource(
                    source_kind="agent",
                    source_id=agent.agent_id,
                    requirements=agent.model_requirements,
                    priority=10,
                )
            )

    if goal is not None:
        if not isinstance(goal, Goal):
            raise ModelRequirementsResolutionError("goal must be a Goal or None")
        if goal.model_requirements is not None:
            sources.append(
                ModelRequirementsSource(
                    source_kind="goal",
                    source_id=goal.id,
                    requirements=goal.model_requirements,
                    priority=20,
                )
            )

    if workflow is not None:
        if not isinstance(workflow, AgentWorkflowPlan):
            raise ModelRequirementsResolutionError(
                "workflow must be an AgentWorkflowPlan or None"
            )
        if workflow.model_requirements is not None:
            sources.append(
                ModelRequirementsSource(
                    source_kind="workflow",
                    source_id=workflow.id,
                    requirements=workflow.model_requirements,
                    priority=30,
                )
            )

    if operation is not None:
        if isinstance(operation, AgentWorkflowOperation):
            operation_id = operation.id
        elif isinstance(operation, OperationDescriptor):
            operation_id = operation.name
        else:
            raise ModelRequirementsResolutionError(
                "operation must be an AgentWorkflowOperation, "
                "OperationDescriptor, or None"
            )

        if operation.model_requirements is not None:
            sources.append(
                ModelRequirementsSource(
                    source_kind="operation",
                    source_id=operation_id,
                    requirements=operation.model_requirements,
                    priority=40,
                )
            )

    if policy_result is not None:
        from cmm.agent_runtime.policy_contracts import PolicyEvaluationResult

        if not isinstance(policy_result, PolicyEvaluationResult):
            raise ModelRequirementsResolutionError(
                "policy_result must be a PolicyEvaluationResult or None"
            )
        sources.extend(policy_model_requirement_sources(policy_result))

    if approval_resolution is not None:
        from cmm.agent_runtime.approval_contracts import ApprovalResolution

        if not isinstance(approval_resolution, ApprovalResolution):
            raise ModelRequirementsResolutionError(
                "approval_resolution must be an ApprovalResolution or None"
            )
        sources.extend(approval_model_requirement_sources(approval_resolution))

    if not sources:
        raise ModelRequirementsResolutionError(
            "No runtime layer declares model requirements"
        )

    return resolve_model_requirements(sources)


__all__ = [
    "resolve_model_requirements",
    "resolve_runtime_model_requirements",
]
