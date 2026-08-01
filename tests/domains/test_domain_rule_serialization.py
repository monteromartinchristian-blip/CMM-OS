from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    Confidence,
    KnowledgeItem,
    KnowledgeKind,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
)
from cmm.domains import (
    DomainRuleContractError,
    DomainRuleExecutionPlan,
    DomainRuleExecutionResult,
    DomainRuleSelectionDecision,
    DomainRuleSelectionStatus,
    DomainRuleSerializationError,
    DomainRuleSource,
    DomainRuleSourceRecord,
    SelectedReasoningRule,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _definition() -> ReasoningRuleDefinition:
    return ReasoningRuleDefinition(
        id="global.rule", name="Rule", version="1.0.0", scope="global",
        category="epistemic", status="enabled", priority=1, risk_level="low",
    )


def test_selection_contracts_round_trip_and_are_json_safe() -> None:
    source = DomainRuleSourceRecord(
        source=DomainRuleSource.GLOBAL_MANDATORY,
        reference="global.rule",
        required=True,
    )
    selected = SelectedReasoningRule(
        definition=_definition(), sources=(source,), group=DomainRuleSource.GLOBAL_MANDATORY,
        required=True,
    )
    decision = DomainRuleSelectionDecision(
        code="rule_selected", rule_id="global.rule", included=True,
        message="Rule selected.", sources=(source,),
    )
    plan = DomainRuleExecutionPlan(
        id="plan-1", status=DomainRuleSelectionStatus.READY,
        selected_rules=(selected,), decisions=(decision,), created_at=NOW,
    )
    payload = plan.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert DomainRuleExecutionPlan.from_dict(payload) == plan


def test_selection_from_dict_rejects_unknown_fields() -> None:
    with pytest.raises(DomainRuleSerializationError):
        DomainRuleSourceRecord.from_dict(
            {"source": "optional", "reference": "global.rule", "required": False, "x": 1}
        )


def test_execution_result_round_trip_preserves_phase8_knowledge() -> None:
    knowledge = KnowledgeItem(
        id="knowledge-1", statement="A verified proposition.", kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.8), created_at=NOW, updated_at=NOW,
    )
    rule_result = ReasoningRuleResult(
        rule_id="global.rule", rule_name="Rule", rule_version="1.0.0", status="applied",
        produced_knowledge=(knowledge,), started_at=NOW, completed_at=NOW,
    )
    result = DomainRuleExecutionResult(
        id="execution", plan_id="plan", status="completed", rule_results=(rule_result,),
        produced_knowledge=(knowledge,), applied_rule_ids=("global.rule",),
        confidence_delta=0.75,
        started_at=NOW, completed_at=NOW,
    )
    restored = DomainRuleExecutionResult.from_dict(result.to_dict())
    assert restored == result
    assert restored.confidence_delta == 0.75
    with pytest.raises(DomainRuleContractError, match="produced_knowledge"):
        DomainRuleExecutionResult(
            id="execution", plan_id="plan", status="completed",
            produced_knowledge=("not-knowledge",), started_at=NOW, completed_at=NOW,
        )


@pytest.mark.parametrize("confidence_delta", (-1.000001, 1.000001, float("nan"), float("inf")))
def test_execution_result_from_dict_rejects_invalid_aggregate_confidence_delta(
    confidence_delta: float,
) -> None:
    payload = DomainRuleExecutionResult(
        id="execution",
        plan_id="plan",
        status="completed",
        started_at=NOW,
        completed_at=NOW,
    ).to_dict()
    payload["confidence_delta"] = confidence_delta

    with pytest.raises(DomainRuleSerializationError, match="confidence_delta"):
        DomainRuleExecutionResult.from_dict(payload)
