"""Deterministic execution and aggregation of a Domain Rule execution plan."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.cognitive.reasoning_rule_engine import DefaultReasoningRuleEngine
from cmm.cognitive.reasoning_rule_registry import ReasoningRuleRegistry
from cmm.domains.enums import DomainRuleExecutionStatus, DomainRuleSelectionStatus
from cmm.domains.errors import DomainRuleConfigurationError, DomainRuleExecutionError
from cmm.domains.rule_contracts import (
    MAX_AGGREGATE_CONFIDENCE_DELTA,
    DomainRuleExecutionPlan,
    DomainRuleExecutionPolicy,
    DomainRuleExecutionResult,
)


@runtime_checkable
class DomainRuleExecutor(Protocol):
    def execute(
        self,
        *,
        plan: DomainRuleExecutionPlan,
        context: ReasoningRuleContext,
        registry: ReasoningRuleRegistry,
        policy: DomainRuleExecutionPolicy | None = None,
    ) -> DomainRuleExecutionResult: ...


class DefaultDomainRuleExecutor:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise DomainRuleConfigurationError("clock must be callable", field="clock")
        if id_factory is not None and not callable(id_factory):
            raise DomainRuleConfigurationError("id_factory must be callable", field="id_factory")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: f"domain-rule-execution-{uuid.uuid4()}")
        self._engine = DefaultReasoningRuleEngine(clock=self._clock)

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise DomainRuleExecutionError("clock must return a timezone-aware datetime", field="clock")
        return value

    def _id(self) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise DomainRuleExecutionError("id_factory must return a non-empty string", field="id_factory")
        return value.strip()

    def execute(
        self,
        *,
        plan: DomainRuleExecutionPlan,
        context: ReasoningRuleContext,
        registry: ReasoningRuleRegistry,
        policy: DomainRuleExecutionPolicy | None = None,
    ) -> DomainRuleExecutionResult:
        if not isinstance(plan, DomainRuleExecutionPlan):
            raise DomainRuleExecutionError("plan must be a DomainRuleExecutionPlan", field="plan")
        if not isinstance(context, ReasoningRuleContext):
            raise DomainRuleExecutionError("context must be a ReasoningRuleContext", field="context")
        if not isinstance(registry, ReasoningRuleRegistry):
            raise DomainRuleExecutionError("registry must satisfy ReasoningRuleRegistry", field="registry")
        policy = policy or DomainRuleExecutionPolicy()
        if not isinstance(policy, DomainRuleExecutionPolicy):
            raise DomainRuleExecutionError("policy must be a DomainRuleExecutionPolicy", field="policy")

        started_at = self._now()
        execution_id = self._id()
        if plan.status is DomainRuleSelectionStatus.BLOCKED:
            return DomainRuleExecutionResult(
                id=execution_id, plan_id=plan.id, status=DomainRuleExecutionStatus.BLOCKED,
                blocked_rule_ids=plan.blocked_rule_ids, decisions=plan.decisions,
                started_at=started_at, completed_at=self._now(),
            )
        if plan.status is DomainRuleSelectionStatus.FAILED:
            return DomainRuleExecutionResult(
                id=execution_id, plan_id=plan.id, status=DomainRuleExecutionStatus.FAILED,
                failed_rule_ids=plan.blocked_rule_ids, decisions=plan.decisions,
                started_at=started_at, completed_at=self._now(),
            )

        results = []
        applied: list[str] = []
        skipped: list[str] = []
        blocked: list[str] = []
        failed: list[str] = []
        degraded = plan.status is DomainRuleSelectionStatus.PARTIAL
        required_failed = False

        for selected in plan.selected_rules:
            definition = selected.definition
            rule = registry.get(definition.id, definition.version)
            if rule is None:
                raise DomainRuleExecutionError(
                    "planned rule implementation is unavailable", field="registry",
                    details={"rule_id": definition.id, "version": definition.version},
                )
            registered = rule.definition
            if registered != definition:
                raise DomainRuleExecutionError(
                    "planned definition does not match registered implementation", field="definition",
                    details={"rule_id": definition.id, "version": definition.version},
                )
            result = self._engine.evaluate(rule, context)
            results.append(result)
            if result.status is ReasoningRuleResultStatus.APPLIED:
                applied.append(definition.id)
            elif result.status in {ReasoningRuleResultStatus.NOT_APPLICABLE, ReasoningRuleResultStatus.SKIPPED}:
                skipped.append(definition.id)
            elif result.status is ReasoningRuleResultStatus.BLOCKED:
                blocked.append(definition.id)
                if selected.required:
                    required_failed = True
                else:
                    degraded = True
            elif result.status is ReasoningRuleResultStatus.FAILED:
                failed.append(definition.id)
                if selected.required:
                    required_failed = True
                else:
                    degraded = True
            if required_failed and policy.stop_on_required_failure:
                break

        if required_failed:
            status = DomainRuleExecutionStatus.FAILED
        elif degraded:
            status = DomainRuleExecutionStatus.PARTIAL
        elif not results or not applied:
            status = DomainRuleExecutionStatus.NO_APPLICABLE_RULES
        else:
            status = DomainRuleExecutionStatus.COMPLETED

        findings = tuple(item for result in results for item in result.findings)
        knowledge = tuple(item for result in results for item in result.produced_knowledge)
        contradictions = tuple(item for result in results for item in result.contradictions)
        gaps = tuple(item for result in results for item in result.gaps)
        recommendations = tuple(item for result in results for item in result.recommendations)
        escalations = tuple(result.escalation for result in results if result.escalation is not None)
        traces = tuple(item for result in results for item in result.trace_entries)
        raw_delta = sum(result.confidence_delta for result in results)
        limit = min(
            policy.aggregate_confidence_limit,
            MAX_AGGREGATE_CONFIDENCE_DELTA,
        )
        delta = max(-limit, min(limit, raw_delta))
        return DomainRuleExecutionResult(
            id=execution_id, plan_id=plan.id, status=status, rule_results=tuple(results),
            findings=findings, produced_knowledge=knowledge, contradictions=contradictions,
            gaps=gaps, recommendations=recommendations, escalations=escalations,
            confidence_delta=delta, applied_rule_ids=tuple(applied), skipped_rule_ids=tuple(skipped),
            blocked_rule_ids=tuple(blocked), failed_rule_ids=tuple(failed), trace_entries=traces,
            decisions=plan.decisions, started_at=started_at, completed_at=self._now(),
            metadata={"selected_rule_count": len(plan.selected_rules), "executed_rule_count": len(results)},
        )


__all__ = ["DefaultDomainRuleExecutor", "DomainRuleExecutor"]
