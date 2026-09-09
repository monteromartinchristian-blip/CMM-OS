"""Phase 10.46 – Agent Runtime adapter for model-agnostic domain policies.

Translates a ``DomainModelPolicy`` into canonical Agent Runtime contracts. The
adapter never queries provider registries or model catalogs, never selects or
ranks models, never constructs providers, and never invokes inference.
"""

from __future__ import annotations

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
from kernel.llm.model_selection import ModelRequirements

DOMAIN_MODEL_POLICY_PHASE = "10.46"

_DOMAIN_SOURCE_PRIORITY = 25

__all__ = [
    "DOMAIN_MODEL_POLICY_PHASE",
    "domain_model_fallback_policy",
    "domain_model_requirement_source",
    "domain_model_validation_requirements",
]


def _require_domain_model_policy(policy: object) -> DomainModelPolicy:
    if not isinstance(policy, DomainModelPolicy):
        raise ModelRequirementsResolutionError("policy must be a DomainModelPolicy")
    return policy


def domain_model_requirement_source(
    policy: DomainModelPolicy,
    *,
    priority: int = _DOMAIN_SOURCE_PRIORITY,
) -> ModelRequirementsSource:
    """Map objective domain requirements to a canonical requirement source."""

    validated = _require_domain_model_policy(policy)

    requirements = ModelRequirements(
        minimum_context_window=validated.minimum_context_window or 1,
        reasoning=validated.require_reasoning,
        tool_calling=validated.require_tool_calling,
        structured_output=validated.require_structured_output,
        json_mode=validated.require_json_mode,
        json_schema=validated.require_json_schema,
        vision=validated.require_vision,
        audio_input=validated.require_audio_input,
        audio_output=validated.require_audio_output,
        embeddings=validated.require_embeddings,
    )

    return ModelRequirementsSource(
        source_kind="domain",
        source_id=str(validated.domain_id),
        requirements=requirements,
        priority=priority,
    )


def domain_model_validation_requirements(
    policy: DomainModelPolicy,
) -> tuple[ValidationRequirement, ...]:
    """Map domain validation flags to canonical validation requirements."""

    validated = _require_domain_model_policy(policy)
    domain_id = str(validated.domain_id)

    requirements: list[ValidationRequirement] = []

    if validated.require_context_validation:
        requirements.append(
            ValidationRequirement(
                requirement_id=f"domain-model-policy:{domain_id}:context",
                validation_kind=ValidationRequirementKind.CUSTOM,
                stage=AgentValidationStage.PRE_EXECUTION,
                required=True,
                blocking=True,
                metadata={
                    "phase": DOMAIN_MODEL_POLICY_PHASE,
                    "semantic_kind": "context_validation",
                },
            )
        )

    if validated.require_response_validation:
        requirements.append(
            ValidationRequirement(
                requirement_id=f"domain-model-policy:{domain_id}:response",
                validation_kind=ValidationRequirementKind.POST_CONDITION,
                stage=AgentValidationStage.POST_EXECUTION,
                required=True,
                blocking=True,
                metadata={
                    "phase": DOMAIN_MODEL_POLICY_PHASE,
                    "semantic_kind": "response_validation",
                },
            )
        )

    return tuple(requirements)


def domain_model_fallback_policy(
    policy: DomainModelPolicy,
) -> ModelFallbackPolicy | None:
    """Expose the typed canonical fallback policy declared by the domain."""

    return _require_domain_model_policy(policy).fallback_policy
