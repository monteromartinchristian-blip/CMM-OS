"""Phase 9.29 – Policy evaluation adapter for model requirements."""

from __future__ import annotations

from cmm.agent_runtime.model_requirements_contracts import (
    ModelRequirementsSource,
    model_requirements_from_dict,
)
from cmm.agent_runtime.model_requirements_errors import (
    ModelRequirementsResolutionError,
)
from cmm.agent_runtime.policy_contracts import (
    PolicyEvaluationResult,
    PolicyRestriction,
)

MODEL_REQUIREMENTS_RESTRICTION_KIND = "model_requirements"


def policy_model_requirement_sources(
    result: PolicyEvaluationResult,
) -> tuple[ModelRequirementsSource, ...]:
    """Translate explicit policy restrictions into requirement sources."""

    if not isinstance(result, PolicyEvaluationResult):
        raise ModelRequirementsResolutionError(
            "result must be a PolicyEvaluationResult"
        )

    sources: list[ModelRequirementsSource] = []

    for index, restriction in enumerate(result.restrictions):
        if not isinstance(restriction, PolicyRestriction):
            raise ModelRequirementsResolutionError(
                "Policy restrictions must contain PolicyRestriction values"
            )

        if restriction.kind != MODEL_REQUIREMENTS_RESTRICTION_KIND:
            continue

        source_policy_id = restriction.source_policy_id or "policy"
        source_rule_id = restriction.source_rule_id or f"restriction-{index}"
        source_id = f"{source_policy_id}:{source_rule_id}"

        sources.append(
            ModelRequirementsSource(
                source_kind="policy",
                source_id=source_id,
                requirements=model_requirements_from_dict(
                    restriction.parameters
                ),
                priority=50,
                metadata={
                    "evaluation_id": result.id,
                    "policy_trace_id": result.policy_trace_id,
                    "restriction_kind": restriction.kind,
                },
            )
        )

    return tuple(sources)


__all__ = [
    "MODEL_REQUIREMENTS_RESTRICTION_KIND",
    "policy_model_requirement_sources",
]
