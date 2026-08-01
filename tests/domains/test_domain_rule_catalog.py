from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive import ReasoningRuleContext
from cmm.domains import (
    INITIAL_DOMAIN_REASONING_RULE_IDS,
    build_initial_reasoning_rule_catalog,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_initial_catalog_contains_all_declared_ids_and_no_false_stubs() -> None:
    registry = build_initial_reasoning_rule_catalog()
    definitions = registry.inspect_definitions()
    assert {item.id for item in definitions} == set(INITIAL_DOMAIN_REASONING_RULE_IDS)
    assert "global.distinguish_fact_inference_hypothesis" in INITIAL_DOMAIN_REASONING_RULE_IDS
    assert "security.no_unauthorized_inference" in INITIAL_DOMAIN_REASONING_RULE_IDS
    assert all(callable(rule.evaluate) for rule in registry.list_all())


def test_structural_catalog_rules_are_conservative() -> None:
    registry = build_initial_reasoning_rule_catalog()
    provenance = registry.resolve("global.preserve_provenance")
    assert provenance is not None
    result = provenance.evaluate(ReasoningRuleContext(reasoning_id="r", timestamp=NOW))
    assert result.status.value == "not_applicable"
    red_flags = registry.resolve("health.red_flags")
    assert red_flags is not None
    escalation = red_flags.evaluate(
        ReasoningRuleContext(
            reasoning_id="r", active_domains=("domain:health",), primary_domain="domain:health",
            timestamp=NOW, metadata={"health": {"red_flags_present": True}},
        )
    )
    assert escalation.escalation is not None
