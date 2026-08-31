"""Phase 10.24 — Reflection ambivalence preservation tests.

``evaluate_ambivalence`` and ``PreserveAmbivalenceRule`` treat ambivalence as
valid information: simultaneous conflicting emotions/needs/beliefs are
preserved with their context/time distinctness, never forced into one true
state (spec §9, §41).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.reflection.rules import (
    PreserveAmbivalenceRule,
    evaluate_ambivalence,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _position(
    identity,
    statement,
    *,
    kind,
    polarity=0,
    context=None,
    temporal=None,
    opposes=(),
    source=None,
):
    return {
        "identity": identity,
        "statement": statement,
        "kind": kind,
        "polarity": polarity,
        "context": context,
        "temporal": temporal,
        "opposes": tuple(opposes),
        "source": source,
    }


def test_want_closeness_and_distance_preserved():
    result = evaluate_ambivalence(
        records=(
            _position(
                "p1",
                "I want closeness",
                kind="need",
                polarity=1,
                context="relationship",
                temporal="2026-08-01",
            ),
            _position(
                "p2",
                "I want distance",
                kind="need",
                polarity=-1,
                context="relationship",
                temporal="2026-08-01",
            ),
        )
    )
    assert result["ambivalence_present"] is True
    assert result["forced_resolution"] is False
    assert len(result["positions"]) == 2


def test_relief_and_sadness_preserved():
    result = evaluate_ambivalence(
        records=(
            _position(
                "p1",
                "relieved",
                kind="emotion",
                polarity=1,
                context="same",
                temporal="2026-08-01",
            ),
            _position(
                "p2",
                "sad",
                kind="emotion",
                polarity=-1,
                context="same",
                temporal="2026-08-01",
            ),
        )
    )
    assert result["ambivalence_present"] is True
    assert result["forced_resolution"] is False


def test_belief_and_doubt_preserved():
    result = evaluate_ambivalence(
        records=(
            _position(
                "p1",
                "I believe they mean well",
                kind="belief",
                polarity=1,
                context="same",
                temporal="2026-08-01",
            ),
            _position(
                "p2",
                "part of me doubts it",
                kind="belief",
                polarity=-1,
                context="same",
                temporal="2026-08-01",
            ),
        )
    )
    assert result["ambivalence_present"] is True
    assert result["forced_resolution"] is False


def test_same_context_time_contradiction_is_ambivalence_not_winner():
    result = evaluate_ambivalence(
        records=(
            _position(
                "p1",
                "want to move",
                kind="need",
                polarity=1,
                context="job",
                temporal="2026-08-01",
            ),
            _position(
                "p2",
                "want to stay",
                kind="need",
                polarity=-1,
                context="job",
                temporal="2026-08-01",
            ),
        )
    )
    assert result["ambivalence_present"] is True
    assert result["forced_resolution"] is False
    assert result["conflict_state"] == "ambivalent"
    assert result["winner_selected"] is False


def test_different_contexts_preserve_context_distinction():
    result = evaluate_ambivalence(
        records=(
            _position(
                "p1", "want closeness", kind="need", polarity=1, context="partnership"
            ),
            _position(
                "p2",
                "want distance",
                kind="need",
                polarity=-1,
                context="work-relationship",
            ),
        )
    )
    assert result["ambivalence_present"] is False
    assert result["forced_resolution"] is False
    assert len(result["positions"]) == 2
    assert set(result["context_distinctions"]) == {"p1", "p2"}


def test_different_grounded_times_preserve_temporal_distinction():
    result = evaluate_ambivalence(
        records=(
            _position(
                "p1", "felt close", kind="emotion", polarity=1, temporal="2026-01-01"
            ),
            _position(
                "p2", "felt distant", kind="emotion", polarity=-1, temporal="2026-06-01"
            ),
        )
    )
    assert result["ambivalence_present"] is False
    assert result["forced_resolution"] is False
    assert set(result["temporal_distinctions"]) == {"p1", "p2"}


def test_duplicate_identical_position_no_double_weight():
    result = evaluate_ambivalence(
        records=(
            _position(
                "p1",
                "relieved",
                kind="emotion",
                polarity=1,
                context="same",
                temporal="2026-08-01",
            ),
            _position(
                "p1",
                "relieved",
                kind="emotion",
                polarity=1,
                context="same",
                temporal="2026-08-01",
            ),
        )
    )
    assert len(result["positions"]) == 1
    assert "p1" in result["duplicates_ignored"]


def test_ambivalence_preserving_rule_applied():
    context = ReasoningRuleContext(
        reasoning_id="rr-amb-1",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "records": (
                _position(
                    "p1",
                    "relieved",
                    kind="emotion",
                    polarity=1,
                    context="same",
                    temporal="2026-08-01",
                ),
                _position(
                    "p2",
                    "sad",
                    kind="emotion",
                    polarity=-1,
                    context="same",
                    temporal="2026-08-01",
                ),
            )
        },
    )
    rule = PreserveAmbivalenceRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["ambivalence_present"] is True
    assert finding.metadata["forced_resolution"] is False
    json.dumps(finding.to_dict(), allow_nan=False)


def test_ambivalence_rule_not_applicable():
    context = ReasoningRuleContext(
        reasoning_id="rr-amb-2",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={},
    )
    rule = PreserveAmbivalenceRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def _definition():
    from cmm.cognitive.enums import (
        ReasoningRiskLevel,
        ReasoningRuleCategory,
        ReasoningRuleScope,
        ReasoningRuleStatus,
    )
    from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

    return DomainReasoningRuleDefinition(
        id="reflection.preserve_ambivalence",
        name="PreserveAmbivalenceRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:reflection",
        category=ReasoningRuleCategory.CONSISTENCY.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=720,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description="Preserve ambivalence rule.",
        metadata={"phase": "10.24"},
    )
