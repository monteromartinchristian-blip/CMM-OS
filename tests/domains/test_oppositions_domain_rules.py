"""Phase 10.23 — Opposition Domain rule evaluate()-path tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains import oppositions

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:oppositions",),
        primary_domain="domain:oppositions",
        metadata=metadata,
    )


def test_exactly_six_rules_built():
    rules = oppositions.build_oppositions_rules()
    assert len(rules) == 6
    ids = {rule.definition.id for rule in rules}
    assert ids == {
        "oppositions.official_call_priority",
        "oppositions.temporal_validity",
        "oppositions.syllabus_coverage",
        "oppositions.study_feasibility",
        "oppositions.mock_exam_interpretation",
        "oppositions.alternative_route",
    }


def test_official_call_priority_rule_evaluate():
    rule = {
        r.definition.id: r for r in oppositions.build_oppositions_rules()
    }["oppositions.official_call_priority"]
    result = rule.evaluate(
        _context(
            opposition_claims=[
                {
                    "id": "call1",
                    "attribute": "application_deadline",
                    "value": "2026-08-31",
                    "source_class": "specific_official_call",
                    "provenance": "grounded",
                    "temporal": "valid",
                    "specificity": "specific",
                    "scope": "body:admin",
                    "critical": True,
                }
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(f.code == "ATTRIBUTE_AUTHORITY" for f in result.findings)
    assert result.findings[0].metadata["authority_resolved"] is True


def test_official_call_priority_not_applicable():
    rule = {
        r.definition.id: r for r in oppositions.build_oppositions_rules()
    }["oppositions.official_call_priority"]
    result = rule.evaluate(_context())
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def test_temporal_validity_rule_evaluate():
    rule = {
        r.definition.id: r for r in oppositions.build_oppositions_rules()
    }["oppositions.temporal_validity"]
    result = rule.evaluate(
        _context(
            temporal_facts=[
                {
                    "attribute": "application_deadline",
                    "value": "2026-08-31",
                    "temporal": "valid",
                    "grounded": True,
                    "source_reference": "r1",
                    "decision_critical": True,
                }
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(f.code == "TEMPORAL_STATE" for f in result.findings)
    assert result.findings[0].metadata["calendar_not_created"] is True


def test_syllabus_coverage_rule_evaluate():
    rule = {
        r.definition.id: r for r in oppositions.build_oppositions_rules()
    }["oppositions.syllabus_coverage"]
    result = rule.evaluate(
        _context(
            topics=[{"id": "t1", "studied": "yes"}, {"id": "t2", "studied": "yes"}],
            syllabus_version="v2",
            syllabus_current=True,
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.findings[0].code == "SYLLABUS_COVERAGE"


def test_study_feasibility_rule_evaluate():
    rule = {
        r.definition.id: r for r in oppositions.build_oppositions_rules()
    }["oppositions.study_feasibility"]
    result = rule.evaluate(
        _context(
            remaining_hours=20,
            available_hours=30,
            target_days=30,
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.findings[0].metadata["proposal_only"] is True
    assert result.findings[0].metadata["adopted_plan"] is False


def test_mock_interpretation_rule_evaluate():
    rule = {
        r.definition.id: r for r in oppositions.build_oppositions_rules()
    }["oppositions.mock_exam_interpretation"]
    result = rule.evaluate(
        _context(mocks=[{"id": "m1", "score": 30, "total": 50, "scoring": "standard"}])
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.findings[0].metadata["one_mock_is_trend"] is False


def test_alternative_route_rule_evaluate():
    rule = {
        r.definition.id: r for r in oppositions.build_oppositions_rules()
    }["oppositions.alternative_route"]
    result = rule.evaluate(
        _context(
            primary={"id": "primary", "eligibility": "eligible"},
            alternatives=[{"id": "alt1", "eligibility": "eligible", "syllabus_overlap": 0.7}],
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.findings[0].metadata["target_unchanged"] is True
    assert result.findings[0].metadata["primary_abandoned"] is False


def test_rule_ids_prefix_match_catalog():
    rules = oppositions.build_oppositions_rules()
    for rule in rules:
        assert rule.definition.domain_id == "domain:oppositions"