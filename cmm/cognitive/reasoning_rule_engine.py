"""Explicit, provider-independent common reasoning-rule evaluator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from cmm.cognitive.enums import ReasoningRuleResultStatus, ReasoningSeverity
from cmm.cognitive.errors import (
    ReasoningRuleContractError,
    ReasoningRuleExecutionError,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningFinding,
    ReasoningRule,
    ReasoningRuleContext,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)


@runtime_checkable
class ReasoningRuleEngine(Protocol):
    def evaluate(self, rule: ReasoningRule, context: ReasoningRuleContext) -> ReasoningRuleResult: ...


class DefaultReasoningRuleEngine:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        if clock is not None and not callable(clock):
            raise ReasoningRuleContractError("clock must be callable", field="clock")
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ReasoningRuleContractError("clock must return a timezone-aware datetime", field="clock")
        return value

    def evaluate(self, rule: ReasoningRule, context: ReasoningRuleContext) -> ReasoningRuleResult:
        definition = getattr(rule, "definition", None)
        evaluate = getattr(rule, "evaluate", None)
        if definition is None or not callable(evaluate):
            raise ReasoningRuleContractError("rule does not satisfy ReasoningRule", field="rule")
        started_at = self._now()
        try:
            result = evaluate(context)
        except ReasoningRuleExecutionError:
            completed_at = self._now()
            return ReasoningRuleResult(
                rule_id=definition.id,
                rule_name=definition.name,
                rule_version=definition.version,
                domain_id=definition.domain_id,
                status=ReasoningRuleResultStatus.FAILED,
                findings=(ReasoningFinding(
                    code="RULE_CONTROLLED_FAILURE",
                    message="The rule reported a controlled internal failure.",
                    severity=ReasoningSeverity.ERROR,
                    rule_id=definition.id,
                    domain_id=definition.domain_id,
                ),),
                started_at=started_at,
                completed_at=completed_at,
            )
        if not isinstance(result, ReasoningRuleResult):
            raise ReasoningRuleContractError("evaluate must return ReasoningRuleResult", field="result")
        expected = (definition.id, definition.name, definition.version, definition.domain_id)
        actual = (result.rule_id, result.rule_name, result.rule_version, result.domain_id)
        labels = ("rule_id", "rule_name", "rule_version", "domain_id")
        for label, left, right in zip(labels, expected, actual):
            if left != right:
                raise ReasoningRuleContractError(f"result {label} does not match definition", field=label)
        output_count = (
            len(result.findings)
            + len(result.produced_knowledge)
            + len(result.contradictions)
            + len(result.gaps)
            + len(result.recommendations)
            + int(result.escalation is not None)
        )
        return replace(
            result,
            trace_entries=(
                *result.trace_entries,
                ReasoningRuleTraceEntry(
                    code="RULE_EVALUATED",
                    message="Rule evaluation completed with a structured result.",
                    rule_id=definition.id,
                    domain_id=definition.domain_id,
                    status=result.status,
                    occurred_at=result.completed_at,
                    output_count=output_count,
                ),
            ),
        )


__all__ = ["DefaultReasoningRuleEngine", "ReasoningRuleEngine"]
