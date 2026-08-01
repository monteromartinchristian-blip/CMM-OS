from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    DefaultReasoningRuleEngine,
    ReasoningRuleContext,
    ReasoningRuleContractError,
    ReasoningRuleDefinition,
    ReasoningRuleExecutionError,
    ReasoningRuleResult,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


class Rule:
    def __init__(self, *, result_id: str = "global.rule", controlled: bool = False) -> None:
        self.definition = ReasoningRuleDefinition(
            id="global.rule",
            name="Rule",
            version="1.0.0",
            scope="global",
            category="epistemic",
            status="enabled",
            priority=1,
            risk_level="low",
        )
        self.result_id = result_id
        self.controlled = controlled

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        if self.controlled:
            raise ReasoningRuleExecutionError("unsafe internal detail")
        return ReasoningRuleResult(
            rule_id=self.result_id,
            rule_name="Rule",
            rule_version="1.0.0",
            status="applied",
            started_at=context.timestamp,
            completed_at=context.timestamp,
        )


def test_engine_evaluates_explicit_rule_with_original_context() -> None:
    context = ReasoningRuleContext(reasoning_id="r", timestamp=NOW)
    result = DefaultReasoningRuleEngine(clock=lambda: NOW).evaluate(Rule(), context)
    assert result.status.value == "applied"
    assert result.trace_entries[-1].code == "RULE_EVALUATED"
    assert result.trace_entries[-1].status is result.status


def test_controlled_failure_is_safe_and_structured() -> None:
    context = ReasoningRuleContext(reasoning_id="r", timestamp=NOW)
    result = DefaultReasoningRuleEngine(clock=lambda: NOW).evaluate(
        Rule(controlled=True), context
    )
    assert result.status.value == "failed"
    assert result.findings[0].code == "RULE_CONTROLLED_FAILURE"
    assert "unsafe internal detail" not in result.findings[0].message


def test_engine_rejects_mismatched_result() -> None:
    with pytest.raises(ReasoningRuleContractError, match="rule_id"):
        DefaultReasoningRuleEngine(clock=lambda: NOW).evaluate(
            Rule(result_id="global.other"),
            ReasoningRuleContext(reasoning_id="r", timestamp=NOW),
        )


def test_programming_errors_propagate() -> None:
    class Broken(Rule):
        def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
            raise RuntimeError("programming bug")

    with pytest.raises(RuntimeError, match="programming bug"):
        DefaultReasoningRuleEngine(clock=lambda: NOW).evaluate(
            Broken(), ReasoningRuleContext(reasoning_id="r", timestamp=NOW)
        )
