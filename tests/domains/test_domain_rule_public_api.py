from __future__ import annotations

from cmm import domains


def test_phase_10_12_domain_api_is_public() -> None:
    expected = {
        "DefaultDomainRuleExecutor", "DefaultDomainRuleSelector",
        "DomainReasoningRuleDefinition", "DomainRuleExecutionPlan",
        "DomainRuleExecutionResult", "DomainRuleExecutionStatus",
        "DomainRuleResult", "DomainRuleSelectionPolicy", "DomainRuleSelectionStatus",
        "DomainRuleSelector", "DomainRuleSource", "InMemoryReasoningRuleRegistry",
        "INITIAL_DOMAIN_REASONING_RULE_IDS", "SelectedReasoningRule",
        "build_initial_reasoning_rule_catalog",
    }
    assert expected <= set(domains.__all__)
    assert all(hasattr(domains, name) for name in expected)
