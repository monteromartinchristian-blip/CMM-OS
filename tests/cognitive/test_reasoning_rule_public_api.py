from __future__ import annotations

from cmm import cognitive


def test_phase_10_12_cognitive_api_is_public() -> None:
    expected = {
        "DefaultReasoningRuleEngine",
        "InMemoryReasoningRuleRegistry",
        "ReasoningEscalation",
        "ReasoningFinding",
        "ReasoningGap",
        "ReasoningRecommendation",
        "ReasoningRiskLevel",
        "ReasoningRule",
        "ReasoningRuleCategory",
        "ReasoningRuleContext",
        "ReasoningRuleContractError",
        "ReasoningRuleDefinition",
        "ReasoningRuleEngine",
        "ReasoningRuleError",
        "ReasoningRuleExecutionError",
        "ReasoningRuleRegistry",
        "ReasoningRuleRegistryError",
        "ReasoningRuleResult",
        "ReasoningRuleResultStatus",
        "ReasoningRuleScope",
        "ReasoningRuleSerializationError",
        "ReasoningRuleStatus",
        "ReasoningRuleTraceEntry",
        "ReasoningSeverity",
    }
    assert expected <= set(cognitive.__all__)
    assert all(hasattr(cognitive, name) for name in expected)
