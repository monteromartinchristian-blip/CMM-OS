"""Phase 9.29 – Approval resolution adapter for model requirements."""

from __future__ import annotations

from cmm.agent_runtime.approval_contracts import ApprovalResolution
from cmm.agent_runtime.model_requirements_contracts import (
    ModelRequirementsSource,
    model_requirements_from_dict,
)
from cmm.agent_runtime.model_requirements_errors import (
    ModelRequirementsResolutionError,
)

MODEL_REQUIREMENTS_APPROVAL_KEY = "model_requirements"


def approval_model_requirement_sources(
    resolution: ApprovalResolution,
) -> tuple[ModelRequirementsSource, ...]:
    """Translate explicit approved parameters into requirement sources."""

    if not isinstance(resolution, ApprovalResolution):
        raise ModelRequirementsResolutionError(
            "resolution must be an ApprovalResolution"
        )

    payload = resolution.approved_parameters.get(
        MODEL_REQUIREMENTS_APPROVAL_KEY
    )
    if payload is None:
        return ()

    if not resolution.satisfied or not resolution.may_execute:
        raise ModelRequirementsResolutionError(
            "Approval model requirements cannot be applied when "
            "execution is not approved",
            {
                "request_id": resolution.request_id,
                "satisfied": resolution.satisfied,
                "may_execute": resolution.may_execute,
            },
        )

    return (
        ModelRequirementsSource(
            source_kind="approval",
            source_id=resolution.request_id,
            requirements=model_requirements_from_dict(payload),
            priority=60,
            metadata={
                "approval_status": resolution.status.value,
                "reason_codes": list(resolution.reason_codes),
            },
        ),
    )


__all__ = [
    "MODEL_REQUIREMENTS_APPROVAL_KEY",
    "approval_model_requirement_sources",
]
