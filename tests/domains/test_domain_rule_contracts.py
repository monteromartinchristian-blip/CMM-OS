from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import ReasoningRuleDefinition, ReasoningRuleResult
from cmm.domains import (
    DomainReasoningRuleDefinition,
    DomainRuleContractError,
    DomainRuleExecutionPolicy,
    DomainRuleExecutionResult,
    DomainRuleResult,
    DomainRuleSelectionPolicy,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_domain_definition_and_result_specialize_common_contracts() -> None:
    definition = DomainReasoningRuleDefinition(
        id="health.red_flags",
        name="HealthRedFlags",
        version="1.0.0",
        scope="domain",
        domain_id="domain:health",
        category="safety",
        status="enabled",
        priority=900,
        required_permissions=("knowledge.health.read",),
        risk_level="high",
    )
    result = DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status="not_applicable",
        started_at=NOW,
        completed_at=NOW,
    )
    assert isinstance(definition, ReasoningRuleDefinition)
    assert isinstance(result, ReasoningRuleResult)
    assert DomainReasoningRuleDefinition.from_dict(definition.to_dict()) == definition
    assert DomainRuleResult.from_dict(result.to_dict()) == result


def test_domain_specializations_require_domain_identity() -> None:
    with pytest.raises(DomainRuleContractError, match="domain"):
        DomainReasoningRuleDefinition(
            id="global.rule", name="Rule", version="1.0.0", scope="global",
            category="epistemic", status="enabled", priority=1, risk_level="low",
        )


def test_selection_and_execution_policies_are_strict() -> None:
    assert DomainRuleSelectionPolicy().include_optional is True
    assert DomainRuleExecutionPolicy().stop_on_required_failure is True
    with pytest.raises(DomainRuleContractError):
        DomainRuleSelectionPolicy(include_optional=1)  # type: ignore[arg-type]
    with pytest.raises(DomainRuleContractError):
        DomainRuleExecutionPolicy(aggregate_confidence_limit=float("nan"))


@pytest.mark.parametrize("confidence_delta", (-1.000001, 1.000001, float("nan"), float("inf")))
def test_execution_result_rejects_invalid_aggregate_confidence_delta(
    confidence_delta: float,
) -> None:
    with pytest.raises(DomainRuleContractError, match="confidence_delta"):
        DomainRuleExecutionResult(
            id="execution",
            plan_id="plan",
            status="completed",
            confidence_delta=confidence_delta,
            started_at=NOW,
            completed_at=NOW,
        )
