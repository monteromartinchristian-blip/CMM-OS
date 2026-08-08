"""Tests for Phase 10.21 Relationships Domain reasoning rules."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.relationships import build_relationships_rules
from cmm.domains.relationships.rules import (
    classify_relationship_perspective,
    classify_relationship_statement,
)

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:relationships",),
        primary_domain="domain:relationships",
        metadata=metadata,
    )


def _by_id(rules):
    return {rule.definition.id: rule for rule in rules}


def test_eight_rules_and_ids():
    rules = build_relationships_rules()
    assert len(rules) == 8
    ids = [rule.definition.id for rule in rules]
    assert ids == sorted(ids)


def test_separate_facts_interpretations_classifies_observed():
    """A directly observed behavior with grounded evidence classifies as
    observed_fact; a bare observed boolean does not."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.separate_facts_interpretations"]
    result = rule.evaluate(
        _context(
            relationship_statements=[
                {"id": "s1", "observed": True, "evidence_references": ("res-1",)},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "EPISTEMIC_CATEGORY" and "observed_fact" in finding.message
        for finding in result.findings
    )
    # Fail-closed: observed without a grounded evidence reference is not a fact.
    ungrounded = rule.evaluate(
        _context(
            relationship_statements=[
                {"id": "s1", "observed": True},
            ]
        )
    )
    assert not any(
        finding.code == "EPISTEMIC_CATEGORY" and "observed_fact" in finding.message
        for finding in ungrounded.findings
    )


def test_separate_facts_interpretations_never_promotes_interpretation():
    """A user interpretation is never promoted to an observed fact, even with
    provenance present."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.separate_facts_interpretations"]
    result = rule.evaluate(
        _context(
            relationship_statements=[
                {"id": "s1", "user_interpretation": True, "provenance": "user"},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "EPISTEMIC_CATEGORY"
        and "user_interpretation" in finding.message
        and "observed_fact" not in finding.message
        for finding in result.findings
    )


def test_separate_facts_interpretations_keeps_possible_function_as_hypothesis():
    """A possible function is a hypothesis, never an intention or fact."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.separate_facts_interpretations"]
    result = rule.evaluate(
        _context(
            relationship_statements=[
                {"id": "s1", "possible_function": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "EPISTEMIC_CATEGORY" and "possible_function" in finding.message
        for finding in result.findings
    )


def test_do_not_infer_intent_blocks_without_direct_evidence():
    """Intent cannot be established without direct evidence; the rule blocks."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.do_not_infer_intent"]
    result = rule.evaluate(
        _context(
            intent_claim={"intent": "left me", "direct_evidence": False},
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.escalation is not None
    assert result.escalation.code == "INTENT_BLOCKED"
    assert any(finding.code == "INTENT_NOT_ESTABLISHED" for finding in result.findings)


def test_do_not_infer_intent_blocks_without_source():
    """Intent with no direct evidence and no sourced statement blocks."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.do_not_infer_intent"]
    result = rule.evaluate(_context(intent_claim={"intent": "ignored me"}))
    assert result.status is ReasoningRuleResultStatus.BLOCKED


def test_do_not_infer_intent_allows_direct_evidence():
    """Intent directly evidenced / attributed by an authorized source requires a
    grounded evidence reference; a bare boolean is fail-closed."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.do_not_infer_intent"]
    # Grounded: a real evidence reference backs the direct evidence.
    result = rule.evaluate(
        _context(
            intent_claim={
                "intent": "left me",
                "direct_evidence": True,
                "evidence_reference": "res-1",
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    # Ungrounded: direct_evidence=True with no usable reference is blocked.
    blocked = rule.evaluate(
        _context(
            intent_claim={"intent": "left me", "direct_evidence": True},
        )
    )
    assert blocked.status is ReasoningRuleResultStatus.BLOCKED


def test_do_not_infer_intent_sourced_not_fact():
    """A source stating an intention is represented with provenance, not fact;
    a sourced statement requires a real source reference."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.do_not_infer_intent"]
    result = rule.evaluate(
        _context(
            intent_claim={
                "intent": "left me",
                "sourced_statement": True,
                "source_reference": "doc-1",
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(finding.code == "INTENT_SOURCED_NOT_FACT" for finding in result.findings)
    # A sourced statement with no usable source reference is blocked, and no
    # fake "unknown" reference is fabricated.
    blocked = rule.evaluate(
        _context(
            intent_claim={"intent": "left me", "sourced_statement": True},
        )
    )
    assert blocked.status is ReasoningRuleResultStatus.BLOCKED
    assert all(
        "unknown" not in reference
        for finding in blocked.findings
        for reference in finding.references
    )


def test_relationship_timeline_never_causal_ordering():
    """A timeline is ordered but temporal proximity is never recorded as cause."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.relationship_timeline"]
    result = rule.evaluate(
        _context(
            timeline=[
                {"id": "t1", "kind": "event"},
                {"id": "t2", "kind": "conversation"},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(gap.code == "TEMPORAL_PROXIMITY_NOT_CAUSE" for gap in result.gaps)


def test_pattern_without_certainty_records_hypothesis():
    """A pattern is recorded as a hypothesis with evidence and counterexamples."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.pattern_without_certainty"]
    result = rule.evaluate(
        _context(
            pattern={
                "pattern_kind": "approach_distance_cycle",
                "support_count": 3,
                "counterexample_count": 0,
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(finding.code == "PATTERN_HYPOTHESIS" for finding in result.findings)


def test_emotion_need_distinction_separates_categories():
    """Emotion, need, desire, expectation, interpretation, and behavior stay
    distinct; no bucket is inferred from another."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.emotion_need_distinction"]
    result = rule.evaluate(
        _context(
            statements=[
                {"id": "s1", "emotion": True, "need": True},
                {"id": "s2", "expectation": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    codes = {finding.code for finding in result.findings}
    assert "DISTINCT_CATEGORY" in codes


def test_boundary_consistency_never_acts():
    """Boundary consistency is evaluated; no boundary action is taken."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.boundary_consistency"]
    result = rule.evaluate(
        _context(
            boundary={"id": "b1", "expressed": True, "applied": True, "violated": True},
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "BOUNDARY_STATE" and "contradictory" in finding.message
        for finding in result.findings
    )


def test_ambivalence_preservation_keeps_contradictory_feelings():
    """Simultaneous contradictory feelings are preserved, not collapsed."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.ambivalence_preservation"]
    result = rule.evaluate(
        _context(
            ambivalence={
                "wants_closeness": True,
                "wants_distance": True,
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "AMBIVALENCE_PRESERVED"
        and "wants_closeness" in finding.message
        and "wants_distance" in finding.message
        for finding in result.findings
    )


def test_self_other_perspective_unknown_is_gap():
    """An unresolvable other-perspective claim surfaces as an unknown gap, never
    as a fact about the other person."""
    rules = _by_id(build_relationships_rules())
    rule = rules["relationships.self_other_perspective"]
    result = rule.evaluate(
        _context(
            perspective_claims=[
                {"id": "c1", "other_possible": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "PERSPECTIVE_CATEGORY"
        and "possible_other_perspective" in finding.message
        for finding in result.findings
    )


def test_deterministic_helpers():
    from cmm.domains.relationships.rules import (
        compare_relationship_options,
        detect_relationship_pattern,
        evaluate_boundary_consistency,
        preserve_relationship_ambivalence,
        separate_emotion_need_expectation,
    )

    # classify_relationship_statement: provenance never promotes.
    assert (
        classify_relationship_statement(provenance="user", is_user_interpretation=True)
        == "user_interpretation"
    )
    assert (
        classify_relationship_statement(provenance="user", is_system_hypothesis=True)
        == "system_hypothesis"
    )
    assert (
        classify_relationship_statement(provenance="user", is_possible_function=True)
        == "possible_function"
    )
    assert (
        classify_relationship_statement(provenance="user", is_possible_origin=True)
        == "possible_origin"
    )
    # Grounded observed requires an evidence reference; a bare boolean is
    # fail-closed and never becomes observed_fact.
    assert classify_relationship_statement(is_observed=True) == "unknown"
    assert (
        classify_relationship_statement(
            is_observed=True, evidence_reference_ids=("res-1",)
        )
        == "observed_fact"
    )
    # Provenance presence is not evidence: a grounded reference is required.
    assert (
        classify_relationship_statement(provenance="res-1", is_observed=True)
        == "unknown"
    )
    assert (
        classify_relationship_statement(is_direct_statement=True) == "direct_statement"
    )
    assert classify_relationship_statement() == "unknown"

    # provenance does not promote a possible_function to an intention/fact.
    assert (
        classify_relationship_statement(provenance="user", is_possible_function=True)
        != "observed_fact"
    )

    # classify_relationship_perspective.
    assert (
        classify_relationship_perspective(is_self_experience=True) == "self_experience"
    )
    # other_observable_behavior requires a grounded evidence reference.
    assert classify_relationship_perspective(is_other_observable=True) == "unknown"
    assert (
        classify_relationship_perspective(
            is_other_observable=True, evidence_reference_ids=("res-1",)
        )
        == "other_observable_behavior"
    )
    assert (
        classify_relationship_perspective(is_other_possible=True)
        == "possible_other_perspective"
    )
    assert classify_relationship_perspective() == "unknown"

    # detect_relationship_pattern is always a hypothesis.
    pattern = detect_relationship_pattern(
        pattern_kind="conflict_repair_cycle", support_count=5
    )
    assert pattern["hypothesis"] is True
    assert pattern["psychological_cause"] is None
    assert pattern["uncertainty"] == "low"

    # evaluate_boundary_consistency.
    assert (
        evaluate_boundary_consistency(expressed=True, applied=True, violated=True)
        == "contradictory"
    )
    assert evaluate_boundary_consistency(violated=True) == "violated"
    assert evaluate_boundary_consistency() == "unresolved"

    # separate_emotion_need_expectation.
    separated = separate_emotion_need_expectation(
        statements=[
            {"id": "a", "emotion": True},
            {"id": "b", "need": True},
            {"id": "c", "expectation": True},
        ]
    )
    assert separated["emotions"] == ["a"]
    assert separated["needs"] == ["b"]
    assert separated["expectations"] == ["c"]

    # preserve_relationship_ambivalence.
    amb = preserve_relationship_ambivalence(wants_closeness=True, wants_distance=True)
    assert amb["ambivalent"] is True
    assert amb["preserved"] is True
    assert amb["forced_objective"] is None

    # compare_relationship_options never adopts a decision.
    comparison = compare_relationship_options(
        options=[
            {"id": "opt-a", "criteria": ("clarity", "honesty")},
            {"id": "opt-b", "criteria": ("clarity",)},
        ],
        criteria=("clarity", "honesty"),
    )
    assert comparison["adopted_decision"] is False
    assert comparison["requires_user_confirmation"] is True
    assert comparison["best_match"]["option_id"] == "opt-a"


def test_compare_options_without_criteria_never_selects():
    from cmm.domains.relationships.rules import compare_relationship_options

    comparison = compare_relationship_options(
        options=[{"id": "opt-a", "criteria": ("clarity",)}],
        criteria=(),
    )
    assert comparison["adopted_decision"] is False
    assert comparison["best_match"] is None


def test_not_applicable_when_no_metadata():
    rules = _by_id(build_relationships_rules())
    for rule in rules.values():
        result = rule.evaluate(_context())
        assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE
