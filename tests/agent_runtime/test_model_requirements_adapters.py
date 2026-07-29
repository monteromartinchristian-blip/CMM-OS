"""Phase 9.29 – Policy and approval model requirement adapters."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cmm.agent_runtime.approval_contracts import ApprovalResolution
from cmm.agent_runtime.enums import (
    ApprovalRequestStatus,
    PolicyDecision,
    PolicyEvaluationStatus,
)
from cmm.agent_runtime.model_requirements_approval_adapter import (
    approval_model_requirement_sources,
)
from cmm.agent_runtime.model_requirements_errors import (
    ModelRequirementsResolutionError,
)
from cmm.agent_runtime.model_requirements_policy_adapter import (
    policy_model_requirement_sources,
)
from cmm.agent_runtime.policy_contracts import (
    PolicyEvaluationResult,
    PolicyRestriction,
)


def _policy_result(
    restrictions: tuple[PolicyRestriction, ...],
) -> PolicyEvaluationResult:
    return PolicyEvaluationResult(
        id="policy-eval-1",
        request_id="request-1",
        status=PolicyEvaluationStatus.COMPLETED,
        decision=PolicyDecision.ALLOW,
        allowed=True,
        denied=False,
        requires_approval=False,
        requires_validation=False,
        requires_information=False,
        paused=False,
        restrictions=restrictions,
        policy_trace_id="policy-trace-1",
    )


def test_policy_adapter_reads_explicit_model_requirements() -> None:
    result = _policy_result(
        (
            PolicyRestriction(
                kind="model_requirements",
                description="Require local structured execution",
                parameters={
                    "minimum_context_window": 64_000,
                    "structured_output": True,
                    "privacy": "LOCAL_ONLY",
                    "maximum_input_cost_per_million": "0.80",
                },
                source_policy_id="policy-privacy",
                source_rule_id="rule-local",
            ),
        )
    )

    sources = policy_model_requirement_sources(result)

    assert len(sources) == 1
    assert sources[0].source_kind == "policy"
    assert sources[0].source_id == "policy-privacy:rule-local"
    assert sources[0].priority == 50
    assert sources[0].requirements.minimum_context_window == 64_000
    assert sources[0].requirements.structured_output is True
    assert sources[0].requirements.privacy == "LOCAL_ONLY"
    assert (
        sources[0].requirements.maximum_input_cost_per_million
        == Decimal("0.80")
    )


def test_policy_adapter_ignores_unrelated_restrictions() -> None:
    result = _policy_result(
        (
            PolicyRestriction(
                kind="allowed_hours",
                description="Execute only during working hours",
                parameters={"start": "09:00", "end": "18:00"},
            ),
        )
    )

    assert policy_model_requirement_sources(result) == ()


def test_policy_adapter_does_not_parse_description_text() -> None:
    result = _policy_result(
        (
            PolicyRestriction(
                kind="execution_boundary",
                description="Use a local-only reasoning model",
                parameters={},
            ),
        )
    )

    assert policy_model_requirement_sources(result) == ()


def test_approval_adapter_reads_explicit_approved_parameters() -> None:
    resolution = ApprovalResolution(
        request_id="approval-1",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approved_parameters={
            "model_requirements": {
                "reasoning": True,
                "privacy": "LOCAL_PREFERRED",
                "premium_allowed": True,
            }
        },
    )

    sources = approval_model_requirement_sources(resolution)

    assert len(sources) == 1
    assert sources[0].source_kind == "approval"
    assert sources[0].source_id == "approval-1"
    assert sources[0].priority == 60
    assert sources[0].requirements.reasoning is True
    assert sources[0].requirements.privacy == "LOCAL_PREFERRED"
    assert sources[0].requirements.premium_allowed is True


def test_approval_adapter_returns_empty_without_explicit_key() -> None:
    resolution = ApprovalResolution(
        request_id="approval-2",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approved_parameters={"timeout_seconds": 60},
    )

    assert approval_model_requirement_sources(resolution) == ()


def test_approval_adapter_rejects_non_executable_resolution() -> None:
    resolution = ApprovalResolution(
        request_id="approval-3",
        status=ApprovalRequestStatus.REJECTED,
        satisfied=False,
        may_execute=False,
        approved_parameters={
            "model_requirements": {
                "premium_allowed": True,
            }
        },
    )

    with pytest.raises(
        ModelRequirementsResolutionError,
        match="execution is not approved",
    ):
        approval_model_requirement_sources(resolution)
