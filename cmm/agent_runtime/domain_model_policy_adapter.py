"""Phase 10.46 – Agent Runtime adapter for model-agnostic domain policies.

The adapter consumes the canonical ``DomainModelPolicy`` attribute surface
structurally, so this package never imports the Domain Intelligence package and
the approved one-way dependency (domains → Agent Runtime → kernel.llm) holds.

It never queries provider registries or model catalogs, never selects or ranks
models, never constructs providers, and never invokes inference.
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
from kernel.llm.model_selection import ModelRequirements

DOMAIN_MODEL_POLICY_PHASE = "10.46"

_DOMAIN_SOURCE_PRIORITY = 25

_POLICY_ATTRIBUTE_SURFACE = (
    "domain_id",
    "require_reasoning",
    "require_tool_calling",
    "require_structured_output",
    "require_json_mode",
    "require_json_schema",
    "require_vision",
    "require_audio_input",
    "require_audio_output",
    "require_embeddings",
    "minimum_context_window",
    "require_context_validation",
    "require_response_validation",
    "fallback_policy",
    "metadata",
)

__all__ = [
    "DOMAIN_MODEL_POLICY_PHASE",
    "domain_model_fallback_policy",
    "domain_model_requirement_source",
    "domain_model_validation_requirements",
]


def _require_domain_model_policy(policy: object) -> object:
    """Fail closed unless the object exposes the canonical policy surface."""

    if not all(hasattr(policy, name) for name in _POLICY_ATTRIBUTE_SURFACE):
        raise ModelRequirementsResolutionError(
            "policy must expose the canonical DomainModelPolicy attribute surface"
        )
    return policy


def domain_model_requirement_source(
    policy: object,
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
        contributes_premium_permission=False,
    )


def domain_model_validation_requirements(
    policy: object,
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
    policy: object,
) -> ModelFallbackPolicy | None:
    """Expose the typed canonical fallback policy declared by the domain."""

    return _require_domain_model_policy(policy).fallback_policy
