from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.cognitive import (
    ContradictionStatus,
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRecommendation,
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleContext,
    ReasoningRuleContractError,
    ReasoningRuleDefinition,
    ReasoningRuleError,
    ReasoningRuleResult,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningRuleTraceEntry,
    ReasoningSeverity,
)

NOW = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)


def definition(**overrides: object) -> ReasoningRuleDefinition:
    values: dict[str, object] = {
        "id": "global.preserve_provenance",
        "name": "PreserveProvenance",
        "version": "1.0.0",
        "scope": ReasoningRuleScope.GLOBAL,
        "category": ReasoningRuleCategory.EPISTEMIC,
        "status": ReasoningRuleStatus.ENABLED,
        "priority": 1000,
        "required_permissions": (),
        "risk_level": ReasoningRiskLevel.LOW,
        "deterministic": True,
        "description": "Preserve evidence provenance.",
        "metadata": {"nested": {"items": ["a"]}},
    }
    values.update(overrides)
    return ReasoningRuleDefinition(**values)  # type: ignore[arg-type]


def test_definition_is_strict_deeply_immutable_and_hashable() -> None:
    source = {"nested": {"items": ["a"]}}
    item = definition(metadata=source)
    source["nested"]["items"].append("b")  # type: ignore[index,union-attr]
    assert item.metadata["nested"]["items"] == ("a",)  # type: ignore[index]
    assert isinstance(item.metadata, MappingProxyType)
    hash(item)
    with pytest.raises(FrozenInstanceError):
        item.priority = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("id", "Not Canonical"),
        ("name", " "),
        ("version", "1.10"),
        ("priority", True),
        ("priority", 10001),
        ("required_permissions", "permission.read"),
        ("required_permissions", ("permission.read", "permission.read")),
        ("deterministic", 1),
        ("metadata", {"bad": object()}),
    ],
)
def test_definition_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ReasoningRuleContractError) as caught:
        definition(**{field: value})
    assert caught.value.field is not None


def test_definition_enforces_scope_domain_invariants() -> None:
    with pytest.raises(ReasoningRuleContractError, match="domain_id"):
        definition(domain_id="domain:health")
    domain = definition(
        id="health.red_flags",
        scope="domain",
        domain_id="domain:health",
    )
    assert domain.domain_id == "domain:health"
    with pytest.raises(ReasoningRuleContractError, match="domain_id"):
        definition(id="health.red_flags", scope="domain")


def test_audit_elements_are_typed_and_preserve_sources() -> None:
    finding = ReasoningFinding(
        code="PROVENANCE_MISSING",
        message="Knowledge item has no evidence.",
        severity=ReasoningSeverity.WARNING,
        rule_id="global.preserve_provenance",
        references=("knowledge:1",),
    )
    recommendation = ReasoningRecommendation(
        code="ADD_EVIDENCE",
        message="Add an evidence reference.",
        severity="info",
        rule_id=finding.rule_id,
    )
    gap = ReasoningGap(
        code="EVIDENCE_GAP",
        message="Evidence is required.",
        severity="warning",
        rule_id=finding.rule_id,
    )
    escalation = ReasoningEscalation(
        code="HUMAN_REVIEW_RECOMMENDED",
        message="Review sensitive evidence.",
        severity="error",
        rule_id=finding.rule_id,
    )
    trace = ReasoningRuleTraceEntry(
        code="RULE_APPLIED",
        message="Rule completed.",
        rule_id=finding.rule_id,
        occurred_at=NOW,
        references=("knowledge:1",),
    )
    assert finding.severity is ReasoningSeverity.WARNING
    assert recommendation.rule_id == gap.rule_id == escalation.rule_id
    assert trace.occurred_at == NOW


def test_reasoning_severity_has_only_reasoning_values() -> None:
    assert tuple(item.value for item in ReasoningSeverity) == (
        "info",
        "warning",
        "error",
        "critical",
    )
    assert tuple(item.value for item in ContradictionStatus) == (
        "unresolved",
        "resolved",
        "deferred",
        "acknowledged",
    )


def test_context_rejects_implicit_runtime_and_naive_time() -> None:
    context = ReasoningRuleContext(
        reasoning_id="reasoning-1",
        active_domains=("domain:health", "domain:project"),
        primary_domain="domain:health",
        supporting_domains=("domain:project",),
        effective_permissions=("knowledge.health.read",),
        effective_risk="high",
        timestamp=NOW,
        metadata={"safe": [1, 2]},
    )
    assert context.active_domains == ("domain:health", "domain:project")
    assert context.metadata["safe"] == (1, 2)
    with pytest.raises(ReasoningRuleContractError, match="timezone-aware"):
        ReasoningRuleContext(reasoning_id="r", timestamp=NOW.replace(tzinfo=None))
    with pytest.raises(ReasoningRuleContractError, match="primary_domain"):
        ReasoningRuleContext(
            reasoning_id="r",
            active_domains=("domain:project",),
            primary_domain="domain:health",
            timestamp=NOW,
        )


def test_result_duration_and_confidence_are_bounded() -> None:
    result = ReasoningRuleResult(
        rule_id="global.preserve_provenance",
        rule_name="PreserveProvenance",
        rule_version="1.0.0",
        status=ReasoningRuleResultStatus.APPLIED,
        confidence_delta=0.25,
        started_at=NOW,
        completed_at=NOW,
    )
    assert result.duration_seconds == 0.0
    with pytest.raises(ReasoningRuleContractError, match="confidence_delta"):
        ReasoningRuleResult(
            rule_id=result.rule_id,
            rule_name=result.rule_name,
            rule_version=result.rule_version,
            status="applied",
            confidence_delta=float("nan"),
            started_at=NOW,
            completed_at=NOW,
        )
    with pytest.raises(ReasoningRuleContractError, match="completed_at"):
        ReasoningRuleResult(
            rule_id=result.rule_id,
            rule_name=result.rule_name,
            rule_version=result.rule_version,
            status="applied",
            started_at=NOW,
            completed_at=datetime(2026, 8, 1, 11, tzinfo=timezone.utc),
        )


def test_reasoning_error_details_are_deeply_immutable() -> None:
    source = {"nested": {"items": ["a"]}}
    error = ReasoningRuleError("safe", details=source)
    source["nested"]["items"].append("b")  # type: ignore[index,union-attr]
    assert error.details["nested"]["items"] == ("a",)  # type: ignore[index]
    with pytest.raises(TypeError):
        error.details["nested"]["new"] = True  # type: ignore[index]
