from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    ReasoningFinding,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleSerializationError,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_definition_round_trip_is_exact_and_detached() -> None:
    original = ReasoningRuleDefinition(
        id="global.rule",
        name="GlobalRule",
        version="1.2.10",
        scope="global",
        category="epistemic",
        status="enabled",
        priority=20,
        risk_level="low",
        metadata={"nested": [1, {"x": True}]},
    )
    payload = original.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    restored = ReasoningRuleDefinition.from_dict(payload)
    assert restored == original
    payload["metadata"]["nested"].append(3)
    assert original.metadata["nested"] == (1, {"x": True})


def test_context_and_result_round_trip_nested_contracts() -> None:
    context = ReasoningRuleContext(
        reasoning_id="r-1",
        gaps=(
            {
                "code": "MISSING",
                "message": "Missing evidence.",
                "severity": "warning",
                "rule_id": "global.rule",
            },
        ),
        timestamp=NOW,
    )
    result = ReasoningRuleResult(
        rule_id="global.rule",
        rule_name="GlobalRule",
        rule_version="1.2.10",
        status="applied",
        findings=(
            ReasoningFinding(
                code="FOUND",
                message="Found evidence.",
                severity="info",
                rule_id="global.rule",
            ),
        ),
        gaps=context.gaps,
        started_at=NOW,
        completed_at=NOW,
    )
    assert ReasoningRuleContext.from_dict(context.to_dict()) == context
    assert ReasoningRuleResult.from_dict(result.to_dict()) == result


@pytest.mark.parametrize(
    ("contract", "payload"),
    [
        (ReasoningRuleDefinition, {"unexpected": True}),
        (ReasoningRuleContext, {"reasoning_id": "r", "timestamp": NOW.isoformat(), "x": 1}),
        (ReasoningRuleResult, {"rule_id": "x", "unknown": 1}),
    ],
)
def test_from_dict_rejects_unknown_and_missing_fields(contract: type, payload: dict) -> None:
    with pytest.raises(ReasoningRuleSerializationError):
        contract.from_dict(payload)
