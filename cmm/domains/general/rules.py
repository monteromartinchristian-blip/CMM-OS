"""Phase 10.19 — General Domain Rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.domains.general.catalog import CANONICAL_GENERAL_RULE_IDS
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

GENERAL_RULE_IDS: tuple[str, ...] = CANONICAL_GENERAL_RULE_IDS


def _definition(
    rule_id: str,
    name: str,
    category: str,
    priority: int,
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:general",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description=f"Conservative structural rule for {rule_id}.",
        metadata={"phase": "10.19"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
    code: str,
    message: str,
) -> ReasoningRuleResult:
    return DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status=status,
        findings=findings,
        gaps=gaps,
        escalation=escalation,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps) + int(escalation is not None),
            ),
        ),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


@dataclass(frozen=True, slots=True)
class GeneralTemporalValidityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        temporal = context.metadata.get("temporal")
        if not isinstance(temporal, Mapping):
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No temporal metadata supplied.",
            )
        kind = temporal.get("kind", "unknown")
        if kind == "unknown":
            gap = ReasoningGap(
                code="TEMPORAL_UNKNOWN",
                message="Temporal status is unknown; cannot treat as current.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition, context, ReasoningRuleResultStatus.APPLIED,
                gaps=(gap,), code="TEMPORAL_UNKNOWN_RECORDED",
                message="Unknown temporality recorded as gap.",
            )
        if kind == "expired":
            finding = ReasoningFinding(
                code="TEMPORAL_EXPIRED",
                message="Temporal data is expired; not treated as current.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
            return _result(
                self.definition, context, ReasoningRuleResultStatus.APPLIED,
                findings=(finding,), code="TEMPORAL_EXPIRED_RECORDED",
                message="Expired temporality recorded.",
            )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            code="TEMPORAL_VALID",
            message="Temporal validity confirmed.",
        )


@dataclass(frozen=True, slots=True)
class GeneralSourceReliabilityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        sources = context.metadata.get("sources")
        if not isinstance(sources, (list, tuple)):
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No source metadata supplied.",
            )
        findings: list[ReasoningFinding] = []
        gaps: list[ReasoningGap] = []
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            source_id = source.get("id", "unknown")
            source_type = source.get("type", "unknown")
            has_provenance = source.get("provenance") is not None
            if source_type == "external_source" and not has_provenance:
                gap = ReasoningGap(
                    code="EXTERNAL_SOURCE_NO_PROVENANCE",
                    message="External source lacks provenance; not trusted.",
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=(source_id,),
                )
                gaps.append(gap)
            elif not has_provenance:
                finding = ReasoningFinding(
                    code="SOURCE_NO_PROVENANCE",
                    message="Source lacks provenance.",
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=(source_id,),
                )
                findings.append(finding)
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings), gaps=tuple(gaps),
            code="SOURCE_RELIABILITY_EVALUATED",
            message="Source reliability evaluated.",
        )


@dataclass(frozen=True, slots=True)
class GeneralAmbiguityRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        ambiguous = context.metadata.get("ambiguous_terms")
        if not isinstance(ambiguous, (list, tuple)) or not ambiguous:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No ambiguous terms supplied.",
            )
        gaps = tuple(
            ReasoningGap(
                code="AMBIGUOUS_TERM",
                message=f"Ambiguous term: {term}",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=(str(term),),
            )
            for term in ambiguous
        )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            gaps=gaps, code="AMBIGUITY_DETECTED",
            message="Ambiguity detected; clarification required.",
        )


@dataclass(frozen=True, slots=True)
class GeneralPermissionRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        requested = context.metadata.get("requested_permissions")
        if not isinstance(requested, (list, tuple)):
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No requested permissions supplied.",
            )
        missing = tuple(
            permission
            for permission in requested
            if permission not in context.effective_permissions
        )
        if missing:
            finding = ReasoningFinding(
                code="PERMISSION_MISSING",
                message="Required permissions are missing.",
                severity=ReasoningSeverity.ERROR,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=missing,
            )
            escalation = ReasoningEscalation(
                code="PERMISSION_ESCALATION",
                message="Permission escalation recommended.",
                severity=ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
                references=missing,
            )
            return _result(
                self.definition, context, ReasoningRuleResultStatus.BLOCKED,
                findings=(finding,), escalation=escalation,
                code="RULE_BLOCKED",
                message="Permission check failed; blocked.",
            )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            code="PERMISSIONS_OK",
            message="All required permissions present.",
        )


@dataclass(frozen=True, slots=True)
class GeneralGoalClarificationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        goal = context.metadata.get("goal")
        if not isinstance(goal, Mapping):
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="No goal metadata supplied.",
            )
        gaps: list[ReasoningGap] = []
        if not goal.get("expected_outcome"):
            gaps.append(
                ReasoningGap(
                    code="GOAL_NO_OUTCOME",
                    message="Goal lacks expected outcome.",
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                )
            )
        if not goal.get("constraints"):
            gaps.append(
                ReasoningGap(
                    code="GOAL_NO_CONSTRAINTS",
                    message="Goal lacks relevant constraints.",
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                )
            )
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            gaps=tuple(gaps), code="GOAL_CLARIFICATION_EVALUATED",
            message="Goal clarification evaluated.",
        )


@dataclass(frozen=True, slots=True)
class GeneralDuplicationRule:
    definition: DomainReasoningRuleDefinition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        items = context.metadata.get("items")
        if not isinstance(items, (list, tuple)) or len(items) < 2:
            return _result(
                self.definition, context, ReasoningRuleResultStatus.NOT_APPLICABLE,
                code="RULE_NOT_APPLICABLE",
                message="Insufficient items for duplication check.",
            )
        seen: dict[str, str] = {}
        findings: list[ReasoningFinding] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            item_id = item.get("id", "unknown")
            canonical = item.get("canonical_id") or item.get("digest") or item_id
            if canonical in seen:
                finding = ReasoningFinding(
                    code="DUPLICATE_DETECTED",
                    message=f"Potential duplicate: {seen[canonical]} and {item_id}",
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                    references=(seen[canonical], item_id),
                )
                findings.append(finding)
            else:
                seen[canonical] = item_id
        return _result(
            self.definition, context, ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings), code="DUPLICATION_EVALUATED",
            message="Duplication evaluated.",
        )


def build_general_rules() -> tuple[Any, ...]:
    """Build the six General Domain rules deterministically in canonical order."""
    by_id = {
        "general.ambiguity": GeneralAmbiguityRule(
            definition=_definition(
                "general.ambiguity", "GeneralAmbiguityRule",
                ReasoningRuleCategory.INFERENCE.value, 780,
            )
        ),
        "general.duplication": GeneralDuplicationRule(
            definition=_definition(
                "general.duplication", "GeneralDuplicationRule",
                ReasoningRuleCategory.CONSISTENCY.value, 750,
            )
        ),
        "general.goal_clarification": GeneralGoalClarificationRule(
            definition=_definition(
                "general.goal_clarification", "GeneralGoalClarificationRule",
                ReasoningRuleCategory.INFERENCE.value, 760,
            )
        ),
        "general.permission": GeneralPermissionRule(
            definition=_definition(
                "general.permission", "GeneralPermissionRule",
                ReasoningRuleCategory.SAFETY.value, 770,
            )
        ),
        "general.source_reliability": GeneralSourceReliabilityRule(
            definition=_definition(
                "general.source_reliability", "GeneralSourceReliabilityRule",
                ReasoningRuleCategory.EPISTEMIC.value, 790,
            )
        ),
        "general.temporal_validity": GeneralTemporalValidityRule(
            definition=_definition(
                "general.temporal_validity", "GeneralTemporalValidityRule",
                ReasoningRuleCategory.TEMPORALITY.value, 800,
            )
        ),
    }
    return tuple(by_id[rule_id] for rule_id in GENERAL_RULE_IDS)


__all__ = [
    "GENERAL_RULE_IDS",
    "GeneralAmbiguityRule",
    "GeneralDuplicationRule",
    "GeneralGoalClarificationRule",
    "GeneralPermissionRule",
    "GeneralSourceReliabilityRule",
    "GeneralTemporalValidityRule",
    "build_general_rules",
]