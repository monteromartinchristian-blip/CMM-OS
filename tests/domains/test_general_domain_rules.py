"""Tests for General Domain rules."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive import ReasoningRuleContext
from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.domains.general import (
    GENERAL_RULE_IDS,
    build_general_rules,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="r1",
        timestamp=NOW,
        active_domains=("domain:general",),
        primary_domain="domain:general",
        effective_permissions=("resource.read", "memory.read"),
        metadata=metadata,
    )


def test_all_rules_built():
    rules = build_general_rules()
    assert len(rules) == 6


def test_rule_ids_match():
    rules = build_general_rules()
    ids = tuple(r.definition.id for r in rules)
    assert ids == GENERAL_RULE_IDS


def test_rules_are_deterministic():
    rules = build_general_rules()
    for rule in rules:
        result1 = rule.evaluate(_context())
        result2 = rule.evaluate(_context())
        assert result1.to_dict() == result2.to_dict()


def test_rules_are_registrable():
    from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry

    registry = InMemoryReasoningRuleRegistry()
    for rule in build_general_rules():
        registry.register(rule)
    assert len(registry.list_all()) == 6


def test_temporal_validity_unknown():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.temporal_validity")
    result = rule.evaluate(_context(temporal={"kind": "unknown"}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(g.code == "TEMPORAL_UNKNOWN" for g in result.gaps)


def test_temporal_validity_expired():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.temporal_validity")
    result = rule.evaluate(_context(temporal={"kind": "expired"}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(f.code == "TEMPORAL_EXPIRED" for f in result.findings)


def test_temporal_validity_valid():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.temporal_validity")
    result = rule.evaluate(_context(temporal={"kind": "current"}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.trace_entries[0].code == "TEMPORAL_VALID"


def test_source_reliability_external_no_provenance():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.source_reliability")
    result = rule.evaluate(
        _context(sources=[{"id": "src1", "type": "external_source"}])
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(g.code == "EXTERNAL_SOURCE_NO_PROVENANCE" for g in result.gaps)


def test_source_reliability_with_provenance():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.source_reliability")
    result = rule.evaluate(
        _context(sources=[{"id": "src1", "type": "external_source", "provenance": "ref:1"}])
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert not result.gaps


def test_ambiguity_detected():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.ambiguity")
    result = rule.evaluate(_context(ambiguous_terms=["term1", "term2"]))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert len(result.gaps) == 2


def test_ambiguity_not_applicable():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.ambiguity")
    result = rule.evaluate(_context())
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def test_permission_missing():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.permission")
    result = rule.evaluate(_context(requested_permissions=["resource.read", "export"]))
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert any(f.code == "PERMISSION_MISSING" for f in result.findings)
    assert result.escalation is not None


def test_permission_ok():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.permission")
    result = rule.evaluate(_context(requested_permissions=["resource.read"]))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.trace_entries[0].code == "PERMISSIONS_OK"


def test_goal_clarification_missing_outcome():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.goal_clarification")
    result = rule.evaluate(_context(goal={"expected_outcome": None}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(g.code == "GOAL_NO_OUTCOME" for g in result.gaps)


def test_goal_clarification_complete():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.goal_clarification")
    result = rule.evaluate(
        _context(goal={"expected_outcome": "x", "constraints": ["c1"]})
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert not result.gaps


def test_duplication_detected():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.duplication")
    result = rule.evaluate(
        _context(items=[{"id": "a", "canonical_id": "x"}, {"id": "b", "canonical_id": "x"}])
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(f.code == "DUPLICATE_DETECTED" for f in result.findings)


def test_duplication_not_applicable():
    rules = build_general_rules()
    rule = next(r for r in rules if r.definition.id == "general.duplication")
    result = rule.evaluate(_context(items=[{"id": "a"}]))
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def test_rules_no_mutation():
    rules = build_general_rules()
    for rule in rules:
        context = _context()
        before = context.to_dict()
        rule.evaluate(context)
        assert context.to_dict() == before


def test_rules_trace_reference_only():
    rules = build_general_rules()
    for rule in rules:
        result = rule.evaluate(_context())
        for entry in result.trace_entries:
            assert entry.rule_id == rule.definition.id
            assert entry.domain_id == "domain:general"