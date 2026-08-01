from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    InMemoryReasoningRuleRegistry,
    ReasoningFinding,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleExecutionError,
    ReasoningRuleResult,
)
from cmm.domains import (
    DefaultDomainRuleExecutor,
    DomainRuleExecutionError,
    DomainRuleExecutionPlan,
    DomainRuleExecutionStatus,
    DomainRuleSelectionStatus,
    DomainRuleSource,
    DomainRuleSourceRecord,
    SelectedReasoningRule,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


class Rule:
    def __init__(self, rule_id: str, *, outcome: str = "applied") -> None:
        self.calls = 0
        self.outcome = outcome
        self.definition = ReasoningRuleDefinition(
            id=rule_id, name="Rule", version="1.0.0", scope="global",
            category="epistemic", status="enabled", priority=1, risk_level="low",
        )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        self.calls += 1
        if self.outcome == "raise":
            raise ReasoningRuleExecutionError("private detail")
        return ReasoningRuleResult(
            rule_id=self.definition.id, rule_name=self.definition.name,
            rule_version=self.definition.version, status=self.outcome,
            findings=(ReasoningFinding(code="OUTPUT", message="Output.", severity="info", rule_id=self.definition.id),)
            if self.outcome == "applied" else (),
            confidence_delta=0.7 if self.outcome == "applied" else 0.0,
            started_at=context.timestamp, completed_at=context.timestamp,
        )


def plan(*entries: tuple[Rule, bool], status: str = "ready") -> DomainRuleExecutionPlan:
    selected = tuple(
        SelectedReasoningRule(
            definition=rule.definition,
            sources=(DomainRuleSourceRecord(source="profile", reference=rule.definition.id, required=required),),
            group=DomainRuleSource.PRIMARY_DOMAIN,
            required=required,
        ) for rule, required in entries
    )
    blocked = tuple(rule.definition.id for rule, _ in entries) if status == "blocked" else ()
    return DomainRuleExecutionPlan(
        id="plan", status=status, selected_rules=selected, blocked_rule_ids=blocked,
        created_at=NOW,
    )


def registry(*rules: Rule) -> InMemoryReasoningRuleRegistry:
    value = InMemoryReasoningRuleRegistry()
    for rule in rules:
        value.register(rule)
    return value


def test_execution_aggregates_in_plan_order_and_clamps_confidence() -> None:
    first, second = Rule("global.first"), Rule("global.second")
    result = DefaultDomainRuleExecutor(clock=lambda: NOW, id_factory=lambda: "execution").execute(
        plan=plan((first, True), (second, False)),
        context=ReasoningRuleContext(reasoning_id="r", timestamp=NOW),
        registry=registry(first, second),
    )
    assert result.status is DomainRuleExecutionStatus.COMPLETED
    assert result.applied_rule_ids == ("global.first", "global.second")
    assert [f.rule_id for f in result.findings] == ["global.first", "global.second"]
    assert result.confidence_delta == 1.0


def test_required_failure_stops_optional_failure_continues() -> None:
    required, after = Rule("global.required", outcome="raise"), Rule("global.after")
    failed = DefaultDomainRuleExecutor(clock=lambda: NOW, id_factory=lambda: "e").execute(
        plan=plan((required, True), (after, False)),
        context=ReasoningRuleContext(reasoning_id="r", timestamp=NOW),
        registry=registry(required, after),
    )
    assert failed.status is DomainRuleExecutionStatus.FAILED
    assert after.calls == 0

    optional, final = Rule("global.optional", outcome="raise"), Rule("global.final")
    partial = DefaultDomainRuleExecutor(clock=lambda: NOW, id_factory=lambda: "e").execute(
        plan=plan((optional, False), (final, False)),
        context=ReasoningRuleContext(reasoning_id="r", timestamp=NOW),
        registry=registry(optional, final),
    )
    assert partial.status is DomainRuleExecutionStatus.PARTIAL
    assert final.calls == 1


def test_blocked_plan_executes_nothing_and_empty_is_no_applicable() -> None:
    rule = Rule("global.rule")
    blocked = DefaultDomainRuleExecutor(clock=lambda: NOW, id_factory=lambda: "e").execute(
        plan=plan((rule, True), status=DomainRuleSelectionStatus.BLOCKED.value),
        context=ReasoningRuleContext(reasoning_id="r", timestamp=NOW),
        registry=registry(rule),
    )
    assert blocked.status is DomainRuleExecutionStatus.BLOCKED
    assert rule.calls == 0
    empty = DefaultDomainRuleExecutor(clock=lambda: NOW, id_factory=lambda: "e").execute(
        plan=plan(), context=ReasoningRuleContext(reasoning_id="r", timestamp=NOW), registry=registry(),
    )
    assert empty.status is DomainRuleExecutionStatus.NO_APPLICABLE_RULES


def test_executor_rejects_registry_definition_drift() -> None:
    planned = Rule("global.rule")
    registered = Rule("global.rule")
    object.__setattr__(registered, "definition", ReasoningRuleDefinition(
        id="global.rule", name="Changed", version="1.0.0", scope="global",
        category="epistemic", status="enabled", priority=1, risk_level="low",
    ))
    with pytest.raises(DomainRuleExecutionError, match="definition"):
        DefaultDomainRuleExecutor(clock=lambda: NOW, id_factory=lambda: "e").execute(
            plan=plan((planned, True)),
            context=ReasoningRuleContext(reasoning_id="r", timestamp=NOW),
            registry=registry(registered),
        )
