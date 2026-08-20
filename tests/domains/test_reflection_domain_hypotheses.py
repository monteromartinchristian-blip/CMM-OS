"""Phase 10.24 — Reflection multiple-hypotheses semantics tests.

``evaluate_hypotheses`` and ``MultipleHypothesesRule`` must preserve every
plausible explanation, keep counterevidence and uncertainty visible, avoid
arbitrary winners, and never convert a hypothesis into a fact (spec §8, §14).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.reflection.rules import (
    MultipleHypothesesRule,
    evaluate_hypotheses,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _hypothesis(identity, statement, *, support=(), against=(), uncertainty=0.5,
                scope=None, temporal=None):
    return {
        "identity": identity,
        "statement": statement,
        "supporting_ids": tuple(support),
        "counterevidence_ids": tuple(against),
        "uncertainty": uncertainty,
        "scope": scope,
        "temporal": temporal,
    }


def test_two_compatible_hypotheses_both_retained():
    result = evaluate_hypotheses(
        hypotheses=(
            _hypothesis("h1", "maybe interest-driven", support=("s1",)),
            _hypothesis("h2", "maybe habit-driven", support=("s2",)),
        )
    )
    assert len(result["hypotheses"]) == 2
    assert {h["identity"] for h in result["hypotheses"]} == {"h1", "h2"}
    assert result["winner_selected"] is False
    assert result["forced_conclusion"] is False


def test_equal_support_disagreement_no_winner():
    result = evaluate_hypotheses(
        hypotheses=(
            _hypothesis("h1", "explanation one", support=("s1",), against=("s2",)),
            _hypothesis("h2", "explanation two", support=("s2",), against=("s1",)),
        )
    )
    assert result["unresolved"] is True
    assert result["winner_selected"] is False
    assert set(result["supported_ids"]) == {"s1", "s2"}
    assert set(result["conflicting_ids"]) == {"s1", "s2"}


def test_one_stronger_hypothesis_is_not_fact():
    result = evaluate_hypotheses(
        hypotheses=(
            _hypothesis("h1", "strong explanation", support=("s1", "s2", "s3")),
            _hypothesis("h2", "weak explanation", support=("s4",)),
        )
    )
    assert result["winner_selected"] is False
    assert result["forced_conclusion"] is False
    ranks = {h["identity"]: h["relative_strength"] for h in result["hypotheses"]}
    assert ranks["h1"] == "stronger"
    assert ranks["h2"] is None
    for h in result["hypotheses"]:
        assert h["status"] == "hypothesis"
        assert h.get("fact") is not True


def test_hypothesis_carries_support_counterevidence_uncertainty():
    result = evaluate_hypotheses(
        hypotheses=(
            _hypothesis(
                "h1",
                "possible avoidance pattern",
                support=("s1", "s2"),
                against=("s3",),
                uncertainty=0.6,
                scope="work-context",
                temporal="2026-01..2026-06",
            ),
        )
    )
    h = result["hypotheses"][0]
    assert set(h["supporting_ids"]) == {"s1", "s2"}
    assert set(h["counterevidence_ids"]) == {"s3"}
    assert h["uncertainty"] == 0.6
    assert h["scope"] == "work-context"
    assert h["temporal"] == "2026-01..2026-06"


def test_missing_evidence_unresolved():
    result = evaluate_hypotheses(
        hypotheses=(_hypothesis("h1", "explanation", support=()),)
    )
    assert result["unresolved"] is True
    assert result["insufficient_basis_to_rank"] is True


def test_conflicting_evidence_unresolved_but_hypotheses_retained():
    result = evaluate_hypotheses(
        hypotheses=(
            _hypothesis("h1", "a", support=("s1",)),
            _hypothesis("h2", "b", support=("s1",)),
        )
    )
    # the same source supports two mutually exclusive hypotheses -> conflict
    assert result["unresolved"] is True
    assert len(result["hypotheses"]) == 2


def test_input_permutation_identical_semantics():
    hypotheses = (
        _hypothesis("h1", "a", support=("s1", "s2")),
        _hypothesis("h2", "b", support=("s2",)),
        _hypothesis("h3", "c", support=("s3",)),
    )
    import itertools

    results = [
        evaluate_hypotheses(hypotheses=tuple(order))
        for order in itertools.permutations(hypotheses)
    ]
    canonical = [
        (
            tuple(h["identity"] for h in r["hypotheses"]),
            r["unresolved"],
            r["winner_selected"],
            r["forced_conclusion"],
        )
        for r in results
    ]
    assert len(set(canonical)) == 1


def test_exact_duplicates_no_evidence_inflation():
    result = evaluate_hypotheses(
        hypotheses=(
            _hypothesis("h1", "a", support=("s1",)),
            _hypothesis("h1", "a", support=("s1",)),
        )
    )
    # duplicate identity/statement collapses to a single hypothesis
    assert len(result["hypotheses"]) == 1
    assert len(result["hypotheses"][0]["supporting_ids"]) == 1


def test_json_safe_public_result():
    result = evaluate_hypotheses(
        hypotheses=(
            _hypothesis("h1", "a", support=("s1",)),
            _hypothesis("h2", "b", support=("s2",)),
        )
    )
    json.dumps(result, allow_nan=False)


def test_multiple_hypotheses_rule_applied():
    context = ReasoningRuleContext(
        reasoning_id="rr-1",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "hypotheses": (
                _hypothesis("h1", "a", support=("s1",)),
                _hypothesis("h2", "b", support=("s2",)),
            )
        },
    )
    rule = MultipleHypothesesRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert len(result.findings) == 1
    finding = result.findings[0]
    meta = finding.metadata
    assert meta["hypothesis_count"] == 2
    assert meta["winner_selected"] is False
    assert meta["forced_conclusion"] is False
    json.dumps(finding.to_dict(), allow_nan=False)


def test_multiple_hypotheses_rule_not_applicable():
    context = ReasoningRuleContext(
        reasoning_id="rr-2",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={},
    )
    rule = MultipleHypothesesRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def test_multiple_hypotheses_rule_finding_json_with_nan_probe():
    """Supported public serializer gate for the rule finding."""
    context = ReasoningRuleContext(
        reasoning_id="rr-3",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={"hypotheses": (_hypothesis("h1", "a", support=("s1",)),)},
    )
    rule = MultipleHypothesesRule(definition=_definition())
    result = rule.evaluate(context)
    json.dumps(result.findings[0].to_dict(), allow_nan=False)


def _definition():
    from cmm.cognitive.enums import (
        ReasoningRiskLevel,
        ReasoningRuleCategory,
        ReasoningRuleScope,
        ReasoningRuleStatus,
    )
    from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

    return DomainReasoningRuleDefinition(
        id="reflection.multiple_hypotheses",
        name="MultipleHypothesesRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:reflection",
        category=ReasoningRuleCategory.INFERENCE.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=700,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description="Multiple hypotheses rule.",
        metadata={"phase": "10.24"},
    )