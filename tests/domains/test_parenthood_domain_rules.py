"""Tests for Phase 10.27 Parenthood Domain Rules."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import (
    ReasoningRuleResultStatus,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_RULE_IDS,
    CANONICAL_PARENTHOOD_RULE_NAMES,
)
from cmm.domains.parenthood.rules import (
    CostUncertaintyRule,
    DevelopmentalContextRule,
    MinorPrivacyRule,
    ParenthoodDecisionExplicitRule,
    SiblingIdentityIsolationRule,
    build_parenthood_rules,
)


def _ctx(metadata: dict) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="reasoning-001",
        primary_domain="domain:parenthood",
        active_domains=("domain:parenthood",),
        timestamp=datetime.now(timezone.utc),
        metadata=metadata,
    )


def test_parenthood_rules_count_and_order() -> None:
    """Verify all 17 rules build deterministically in canonical order."""
    rules = build_parenthood_rules()
    assert len(rules) == 17
    rule_ids = tuple(r.definition.id for r in rules)
    assert rule_ids == CANONICAL_PARENTHOOD_RULE_IDS

    rule_names = tuple(r.definition.name for r in rules)
    assert rule_names == CANONICAL_PARENTHOOD_RULE_NAMES


def test_parenthood_decision_explicit_rule_rejects_inferred_adoption() -> None:
    """Verify ParenthoodDecisionExplicitRule distinguishes proposed from adopted decisions."""
    rule = ParenthoodDecisionExplicitRule()

    # Inferred decision without explicit user adoption must NOT be marked adopted
    ctx = _ctx(
        metadata={
            "decisions": [
                {
                    "id": "dec-1",
                    "topic": "surrogacy_pathway",
                    "status": "proposed",
                    "explicitly_adopted": False,
                },
                {
                    "id": "dec-2",
                    "topic": "selected_clinic",
                    "status": "adopted",
                    "explicitly_adopted": True,
                },
            ]
        }
    )
    result = rule.evaluate(ctx)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    findings = {f.code: f for f in result.findings}
    assert "PROPOSED_DECISION_PRESERVED" in findings
    assert "ADOPTED_DECISION_VERIFIED" in findings


def test_cost_uncertainty_rule_preserves_ranges() -> None:
    """Verify CostUncertaintyRule enforces ranges and flags fixed certainty claims."""
    rule = CostUncertaintyRule()

    # Fixed certainty claim on variable journey costs
    ctx = _ctx(
        metadata={
            "financial_scenarios": [
                {
                    "item": "total_cost",
                    "exact_fixed_cost": 85000,
                    "is_guaranteed": True,
                },
            ]
        }
    )
    result = rule.evaluate(ctx)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any("COST_CERTAINTY_FLAGGED" in f.code for f in result.findings)


def test_developmental_context_rule_non_diagnostic() -> None:
    """Verify DevelopmentalContextRule prevents normal variations from becoming diagnoses."""
    rule = DevelopmentalContextRule()

    ctx = _ctx(
        metadata={
            "child_observations": [
                {
                    "behavior": "shyness_around_strangers",
                    "stage": "toddler",
                    "proposed_diagnosis": "social_anxiety_disorder",
                },
            ]
        }
    )
    result = rule.evaluate(ctx)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any("PATHOLOGY_LABEL_REJECTED" in f.code for f in result.findings)


def test_sibling_identity_isolation_rule() -> None:
    """Verify SiblingIdentityIsolationRule detects cross-sibling context contamination."""
    rule = SiblingIdentityIsolationRule()

    ctx = _ctx(
        metadata={
            "active_child_id": "child:001",
            "context_records": [
                {
                    "child_id": "child:002",
                    "record_type": "allergy",
                    "data": "peanuts",
                    "is_shared": False,
                },
            ],
        }
    )
    result = rule.evaluate(ctx)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any("SIBLING_CONTAMINATION_BLOCKED" in f.code for f in result.findings)


def test_minor_privacy_rule() -> None:
    """Verify MinorPrivacyRule flags external transmission of minor details."""
    rule = MinorPrivacyRule()

    ctx = _ctx(
        metadata={
            "child_id": "child:001",
            "action_proposed": "external_api_export",
            "external_destination": "https://external-school-directory.com",
        }
    )
    result = rule.evaluate(ctx)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any("MINOR_PRIVACY_RESTRICTION" in f.code for f in result.findings)
