"""Phase 10.46 – Agent Runtime adapter for ``DomainModelPolicy``."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.domain_model_policy_adapter import (
    domain_model_fallback_policy,
    domain_model_requirement_source,
    domain_model_validation_requirements,
)
from cmm.agent_runtime.enums import (
    AgentValidationStage,
    ValidationRequirementKind,
)
from cmm.agent_runtime.model_fallback_contracts import ModelFallbackPolicy
from cmm.agent_runtime.model_requirements_contracts import ModelRequirementsSource
from cmm.agent_runtime.model_requirements_errors import (
    ModelRequirementsResolutionError,
)
from cmm.agent_runtime.validation_integration_contracts import ValidationRequirement
from cmm.domains.model_policy_contracts import DomainModelPolicy

_CAPABILITY_FIELDS = (
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


def _policy(**overrides: object) -> DomainModelPolicy:
    data: dict[str, object] = {"domain_id": "domain:health"}
    data.update(overrides)
    return DomainModelPolicy(**data)  # type: ignore[arg-type]


def test_domain_policy_maps_to_neutral_provider_independent_requirements() -> None:
    policy = DomainModelPolicy(
        domain_id="domain:health",
        require_reasoning=True,
        require_structured_output=True,
        minimum_context_window=64_000,
    )

    source = domain_model_requirement_source(policy)

    assert isinstance(source, ModelRequirementsSource)
    assert source.source_kind == "domain"
    assert source.source_id == "domain:health"
    assert source.priority == 25
    assert source.requirements.reasoning is True
    assert source.requirements.structured_output is True
    assert source.requirements.minimum_context_window == 64_000
    assert source.requirements.allowed_providers == ()
    assert source.requirements.excluded_providers == ()
    assert source.requirements.privacy == "REMOTE_ALLOWED"
    assert source.requirements.premium_allowed is False
    assert source.requirements.maximum_input_cost_per_million is None
    assert source.requirements.maximum_output_cost_per_million is None


def test_domain_policy_maps_every_objective_capability_boolean() -> None:
    policy = _policy(
        require_reasoning=True,
        require_tool_calling=True,
        require_structured_output=True,
        require_json_mode=True,
        require_json_schema=True,
        require_vision=True,
        require_audio_input=True,
        require_audio_output=True,
        require_embeddings=True,
    )

    requirements = domain_model_requirement_source(policy).requirements

    for field_name in _CAPABILITY_FIELDS:
        assert getattr(requirements, field_name) is True


def test_domain_policy_absent_context_maps_to_canonical_neutral_one() -> None:
    source = domain_model_requirement_source(_policy())

    assert source.requirements.minimum_context_window == 1


def test_domain_policy_source_priority_is_configurable() -> None:
    source = domain_model_requirement_source(_policy(), priority=7)

    assert source.priority == 7


def test_domain_policy_context_validation_requirement() -> None:
    requirements = domain_model_validation_requirements(
        _policy(require_context_validation=True)
    )

    assert len(requirements) == 1
    requirement = requirements[0]
    assert isinstance(requirement, ValidationRequirement)
    assert requirement.requirement_id == "domain-model-policy:domain:health:context"
    assert requirement.validation_kind is ValidationRequirementKind.CUSTOM
    assert requirement.stage is AgentValidationStage.PRE_EXECUTION
    assert requirement.required is True
    assert requirement.blocking is True
    assert requirement.metadata["phase"] == "10.46"
    assert requirement.metadata["semantic_kind"] == "context_validation"


def test_domain_policy_response_validation_requirement() -> None:
    requirements = domain_model_validation_requirements(
        _policy(require_response_validation=True)
    )

    assert len(requirements) == 1
    requirement = requirements[0]
    assert isinstance(requirement, ValidationRequirement)
    assert requirement.requirement_id == "domain-model-policy:domain:health:response"
    assert requirement.validation_kind is ValidationRequirementKind.POST_CONDITION
    assert requirement.stage is AgentValidationStage.POST_EXECUTION
    assert requirement.required is True
    assert requirement.blocking is True
    assert requirement.metadata["phase"] == "10.46"
    assert requirement.metadata["semantic_kind"] == "response_validation"


def test_domain_policy_false_validation_flags_produce_no_requirements() -> None:
    assert domain_model_validation_requirements(_policy()) == ()


def test_domain_policy_both_validation_flags_produce_two_requirements() -> None:
    requirements = domain_model_validation_requirements(
        _policy(
            require_context_validation=True,
            require_response_validation=True,
        )
    )

    assert tuple(r.requirement_id for r in requirements) == (
        "domain-model-policy:domain:health:context",
        "domain-model-policy:domain:health:response",
    )


def test_domain_policy_fallback_reuses_existing_typed_policy() -> None:
    fallback = ModelFallbackPolicy(id="domain-health-fallback", maximum_attempts=2)

    assert domain_model_fallback_policy(_policy(fallback_policy=fallback)) is fallback


def test_domain_policy_fallback_defaults_to_none() -> None:
    assert domain_model_fallback_policy(_policy()) is None


@pytest.mark.parametrize(
    "function",
    (
        domain_model_requirement_source,
        domain_model_validation_requirements,
        domain_model_fallback_policy,
    ),
)
def test_adapter_rejects_non_policy_objects(function: object) -> None:
    with pytest.raises(ModelRequirementsResolutionError):
        function("domain:health")  # type: ignore[operator]


def test_adapter_functions_are_exported_from_agent_runtime() -> None:
    import cmm.agent_runtime as runtime

    for function in (
        domain_model_fallback_policy,
        domain_model_requirement_source,
        domain_model_validation_requirements,
    ):
        assert getattr(runtime, function.__name__) is function
        assert function.__name__ in runtime.__all__
