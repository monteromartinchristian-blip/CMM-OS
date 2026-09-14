"""Phase 10.24 — Reflection belief/evidence separation tests.

``classify_belief_evidence`` and ``BeliefEvidenceRule`` preserve the five
canonical dimensions — belief, evidence, counterevidence, experience,
interpretation — and never silently promote a lower level into a higher one:
experience -> external fact, interpretation -> observation, memory -> current
truth, belief -> verified fact (spec §10, §24, §25, §41).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.reflection.rules import (
    BeliefEvidenceRule,
    classify_belief_evidence,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _record(
    identity,
    statement,
    kind,
    *,
    fact=False,
    inferred=False,
    uncertain=False,
    contradicted=False,
    source=None,
    value=None,
):
    return {
        "identity": identity,
        "statement": statement,
        "kind": kind,
        "fact": fact,
        "inferred": inferred,
        "uncertain": uncertain,
        "contradicted": contradicted,
        "source": source,
        "value": value,
    }


def test_experience_alone_cannot_become_external_fact():
    result = classify_belief_evidence(
        records=(_record("r1", "I felt ignored", kind="experience", fact=True),)
    )
    assert all(item["kind"] == "experience" for item in result["experiences"])
    assert result["facts"] == ()
    assert "r1" in result["promotions_blocked"]
    assert result["promotion_applied"] is False


def test_interpretation_cannot_become_observation():
    result = classify_belief_evidence(
        records=(_record("r2", "She was angry at me", kind="interpretation"),)
    )
    assert all(item["kind"] == "interpretation" for item in result["interpretations"])
    assert result["observations"] == ()


def test_memory_entry_is_provenance_not_current_fact():
    result = classify_belief_evidence(
        records=(
            _record(
                "r3", "He never listens (memory summary)", kind="memory", fact=True
            ),
        )
    )
    assert all(item["kind"] == "memory" for item in result["memories"])
    assert result["facts"] == ()
    assert "r3" in result["promotions_blocked"]


def test_duplicate_evidence_does_not_inflate():
    result = classify_belief_evidence(
        records=(
            _record("e1", "They cancelled twice", kind="evidence", source="s1"),
            _record("e2", "They cancelled twice", kind="evidence", source="s1"),
        )
    )
    # distinct identities with identical content from the same source collapse
    assert len(result["evidence"]) == 1
    assert result["duplicates_ignored"] == ("e2",)


def test_conflicting_evidence_remains_conflict():
    result = classify_belief_evidence(
        records=(
            _record(
                "e1", "They called often", kind="evidence", value="high", source="s1"
            ),
            _record(
                "e2", "They called rarely", kind="evidence", value="low", source="s1"
            ),
        )
    )
    assert result["unresolved"] is True
    assert result["conflict_state"] == "conflicting"


def test_malformed_record_fails_closed():
    result = classify_belief_evidence(records=("not-a-mapping", 7, {}))
    assert result["unresolved"] is True
    assert len(result["malformed_records"]) >= 1
    assert all(item["kind"] != "fact" for item in result.get("facts", ()))


def test_belief_statuses_preserved():
    result = classify_belief_evidence(
        records=(
            _record("b1", "I think they are reliable", kind="belief", inferred=True),
            _record("b2", "I am sure I want to leave", kind="belief"),
            _record("b3", "maybe I am not good enough", kind="belief", uncertain=True),
            _record("b4", "I believed they cared", kind="belief", contradicted=True),
        )
    )
    statuses = {b["identity"]: b["status"] for b in result["beliefs"]}
    assert statuses["b1"] == "inferred"
    assert statuses["b2"] == "explicit"
    assert statuses["b3"] == "uncertain"
    assert statuses["b4"] == "contradicted"
    assert result["beliefs_as_facts"] == ()


def test_no_inferred_belief_becomes_user_fact():
    result = classify_belief_evidence(
        records=(_record("b1", "I think they avoid me", kind="belief", inferred=True),)
    )
    assert result["facts"] == ()
    assert result["beliefs_as_facts"] == ()
    assert "b1" in result["promotions_blocked"] or result["promotion_applied"] is False


def test_belief_evidence_rule_applied():
    context = ReasoningRuleContext(
        reasoning_id="rr-be-1",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "records": (
                _record("r1", "I felt ignored", kind="experience", fact=True),
                _record("e1", "They cancelled twice", kind="evidence", source="s1"),
            )
        },
    )
    rule = BeliefEvidenceRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    # the fact label on the experience is a blocked attempt, never applied
    assert finding.metadata["type_promotion"] is True
    assert finding.metadata["promotion_applied"] is False
    assert finding.metadata["facts"] == ()
    assert "r1" in finding.metadata["promotions_blocked"]
    json.dumps(finding.to_dict(), allow_nan=False)


def test_belief_evidence_rule_not_applicable():
    context = ReasoningRuleContext(
        reasoning_id="rr-be-2",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={},
    )
    rule = BeliefEvidenceRule(definition=_definition())
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
        id="reflection.belief_evidence",
        name="BeliefEvidenceRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:reflection",
        category=ReasoningRuleCategory.EPISTEMIC.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=730,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description="Belief/evidence separation rule.",
        metadata={"phase": "10.24"},
    )
