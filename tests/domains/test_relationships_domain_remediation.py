"""Phase 10.21 — Audit v1 remediation RED→GREEN tests.

Each test below is a regression guard for a substantiated audit finding.  The
tests are intentionally written against the *actual* contracts (rule evaluation
paths, operation schemas, resource bindings) rather than calling private
helpers directly, so they prove the production path is fixed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains import relationships

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


_RULES = _by_id(relationships.build_relationships_rules())


# ═══════════════════════════════════════════════════════════════════════════════
# Item 3 — compare_periods schema: nested period must validate real instances
# ═══════════════════════════════════════════════════════════════════════════════


def _compare_periods_schema():
    ops = {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }
    return ops["relationships.compare_periods"].input_schema


def test_compare_periods_valid_period_payload_validates():
    """A real representative period payload must validate (P1)."""
    schema = _compare_periods_schema()
    payload = {
        "period_a": {"start": "2026-01-01", "end": "2026-02-01"},
        "period_b": {"start": "2026-03-01", "end": "2026-04-01"},
    }
    issues = validate_operation_schema(payload, schema)
    assert issues == (), f"expected valid payload, got issues: {issues}"


def test_compare_periods_missing_start_fails():
    """A period missing ``start`` must fail validation (no required property is
    simultaneously forbidden)."""
    schema = _compare_periods_schema()
    payload = {
        "period_a": {"end": "2026-02-01"},
        "period_b": {"start": "2026-03-01", "end": "2026-04-01"},
    }
    issues = validate_operation_schema(payload, schema)
    assert any(issue.code == "required" for issue in issues)
    assert any("period_a.start" in issue.path for issue in issues)


def test_compare_periods_missing_end_fails():
    schema = _compare_periods_schema()
    payload = {
        "period_a": {"start": "2026-01-01", "end": "2026-02-01"},
        "period_b": {"start": "2026-03-01"},
    }
    issues = validate_operation_schema(payload, schema)
    assert any(issue.code == "required" for issue in issues)
    assert any("period_b.end" in issue.path for issue in issues)


def test_compare_periods_rejects_unknown_period_field():
    """CLOSED nested period schema: an unknown field is rejected."""
    schema = _compare_periods_schema()
    payload = {
        "period_a": {"start": "2026-01-01", "end": "2026-02-01", "bogus": "x"},
        "period_b": {"start": "2026-03-01", "end": "2026-04-01"},
    }
    issues = validate_operation_schema(payload, schema)
    assert any(issue.code == "additional_property" for issue in issues)


# ═══════════════════════════════════════════════════════════════════════════════
# Item 4 — Ambivalence: both approved pairs must be ambivalent
# ═══════════════════════════════════════════════════════════════════════════════


def test_ambivalence_pair_wants_closeness_and_distance():
    rule = _RULES["relationships.ambivalence_preservation"]
    result = rule.evaluate(
        _context(
            ambivalence={"wants_closeness": True, "wants_distance": True},
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(finding.code == "AMBIVALENCE_PRESERVED" for finding in result.findings)
    # The rule must surface the ambivalent state, not collapse it.
    assert any("wants_closeness" in finding.message for finding in result.findings)
    assert any("wants_distance" in finding.message for finding in result.findings)


def test_ambivalence_pair_misses_person_and_relief_without_contact():
    """The explicit second approved pair must also be ambivalence (P1)."""
    rule = _RULES["relationships.ambivalence_preservation"]
    result = rule.evaluate(
        _context(
            ambivalence={"misses_person": True, "relief_without_contact": True},
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(finding.code == "AMBIVALENCE_PRESERVED" for finding in result.findings)
    assert any("misses_person" in finding.message for finding in result.findings)
    assert any(
        "relief_without_contact" in finding.message for finding in result.findings
    )


def test_ambivalence_both_pairs_coexist_and_all_feelings_preserved():
    rule = _RULES["relationships.ambivalence_preservation"]
    result = rule.evaluate(
        _context(
            ambivalence={
                "wants_closeness": True,
                "wants_distance": True,
                "misses_person": True,
                "relief_without_contact": True,
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    message = " ".join(f.message for f in result.findings)
    for feeling in (
        "wants_closeness",
        "wants_distance",
        "misses_person",
        "relief_without_contact",
    ):
        assert feeling in message


def test_ambivalence_never_creates_forced_objective():
    from cmm.domains.relationships.rules import preserve_relationship_ambivalence

    for kwargs in (
        {"wants_closeness": True, "wants_distance": True},
        {"misses_person": True, "relief_without_contact": True},
        {
            "wants_closeness": True,
            "wants_distance": True,
            "misses_person": True,
            "relief_without_contact": True,
        },
    ):
        record = preserve_relationship_ambivalence(**kwargs)
        assert record["ambivalent"] is True
        assert record["forced_objective"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Item 5 — Decision-support tie preservation
# ═══════════════════════════════════════════════════════════════════════════════


def test_decision_support_unambiguous_best_match_when_unique():
    """A unique best match is surfaced; no arbitrary tie-breaking when tied."""
    rule = _RULES["relationships.ambivalence_preservation"]
    result = rule.evaluate(
        _context(
            decision_support={
                "options": [
                    {"id": "opt-a", "criteria": ("clarity", "honesty")},
                    {"id": "opt-b", "criteria": ("clarity",)},
                ],
                "criteria": ("clarity", "honesty"),
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "DECISION_SUPPORT_COMPARISON" for finding in result.findings
    )
    comparison = _comparison_from_result(result)
    assert comparison["adopted_decision"] is False
    assert comparison["requires_user_confirmation"] is True
    assert comparison["best_match"]["option_id"] == "opt-a"


def test_decision_support_tie_preserves_ambiguity():
    """A tie must NOT invent a unique winner; ambiguity is preserved (P2)."""
    rule = _RULES["relationships.ambivalence_preservation"]
    result = rule.evaluate(
        _context(
            decision_support={
                "options": [
                    {"id": "opt-a", "criteria": ("clarity", "honesty")},
                    {"id": "opt-b", "criteria": ("clarity", "honesty")},
                ],
                "criteria": ("clarity", "honesty"),
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    comparison = _comparison_from_result(result)
    assert comparison["adopted_decision"] is False
    assert comparison["requires_user_confirmation"] is True
    # No arbitrary winner: best_match stays None and tied matches are retained.
    assert comparison["best_match"] is None
    assert set(comparison["tied_best_matches"]) == {"opt-a", "opt-b"}


def _comparison_from_result(result):
    """Extract the retained comparison payload from the rule result."""
    for finding in result.findings:
        if finding.code == "DECISION_SUPPORT_COMPARISON":
            return finding.metadata.get("comparison")
    raise AssertionError("no DECISION_SUPPORT_COMPARISON finding emitted")


# ═══════════════════════════════════════════════════════════════════════════════
# Item 6 — Pattern counterexamples
# ═══════════════════════════════════════════════════════════════════════════════


def test_pattern_counterexamples_preserved_in_rule_result():
    """Counterexamples survive the rule output and temper uncertainty (P2)."""
    rule = _RULES["relationships.pattern_without_certainty"]
    result = rule.evaluate(
        _context(
            pattern={
                "pattern_kind": "approach_distance_cycle",
                "support_count": 4,
                "counterexample_count": 2,
                "references": ("s1", "s2", "s3", "s4"),
                "counterexample_references": ("c1", "c2"),
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(finding.code == "PATTERN_HYPOTHESIS" for finding in result.findings)
    finding = next(f for f in result.findings if f.code == "PATTERN_HYPOTHESIS")
    # Supporting references preserved.
    assert "s1" in finding.references and "s4" in finding.references
    # Counterexample references preserved in a supported contract field.
    counterexample_references = finding.metadata.get("counterexample_references", ())
    assert set(counterexample_references) == {"c1", "c2"}


def test_pattern_counterexamples_affect_uncertainty():
    """High support with substantial counterevidence is NOT misleadingly 'low'."""
    from cmm.domains.relationships.rules import detect_relationship_pattern

    with_counterexamples = detect_relationship_pattern(
        pattern_kind="x",
        support_count=4,
        counterexample_count=2,
    )
    assert with_counterexamples["psychological_cause"] is None
    assert with_counterexamples["hypothesis"] is True
    assert with_counterexamples["uncertainty"] != "low"

    # Without counterexamples, the same support may be lower uncertainty.
    without_counterexamples = detect_relationship_pattern(
        pattern_kind="x",
        support_count=4,
        counterexample_count=0,
    )
    assert without_counterexamples["uncertainty"] == "low"


# ═══════════════════════════════════════════════════════════════════════════════
# Item 7 — Entity binding coverage
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_canonical_entities_reachable_through_resource_bindings():
    """commitment and support_event must be reachable via resource entity_types."""
    from cmm.domains.relationships.catalog import (
        CANONICAL_RELATIONSHIPS_ENTITY_TYPES,
    )

    resources = relationships.build_relationships_resource_definitions()
    bound = set()
    for resource in resources:
        bound.update(resource.entity_types)
    assert bound == set(CANONICAL_RELATIONSHIPS_ENTITY_TYPES)
    assert "commitment" in bound
    assert "support_event" in bound


# ═══════════════════════════════════════════════════════════════════════════════
# Item 1 — Decision support connected through a canonical reasoning path
# ═══════════════════════════════════════════════════════════════════════════════


def test_decision_support_reachable_through_reasoning_rule():
    """The decision-support comparison is reached through an existing canonical
    rule evaluation (AmbivalencePreservationRule), NOT by calling
    compare_relationship_options() directly."""
    rule = _RULES["relationships.ambivalence_preservation"]
    result = rule.evaluate(
        _context(
            decision_support={
                "options": [
                    {"id": "opt-a", "criteria": ("clarity",)},
                ],
                "criteria": ("clarity",),
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = next(
        f for f in result.findings if f.code == "DECISION_SUPPORT_COMPARISON"
    )
    comparison = finding.metadata["comparison"]
    assert comparison["adopted_decision"] is False
    assert comparison["requires_user_confirmation"] is True
    assert comparison["best_match"]["option_id"] == "opt-a"


def test_decision_support_workflow_uses_ambivalence_preservation_rule():
    """The decision_support workflow's REASON node applies the rule that owns
    decision-support comparison."""
    wf = next(
        w
        for w in relationships.build_relationships_workflow_definitions()
        if w.workflow_id == "relationships.decision_support"
    )
    reason_nodes = [n for n in wf.nodes if n.node_type.value == "reason"]
    assert reason_nodes
    # The REASON node transitively reaches the rule set that includes
    # ambivalence_preservation (the rule that owns decision-support comparison).
    assert (
        "relationships.ambivalence_preservation"
        in relationships.build_relationships_domain_definition().rules
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Item 2 — Third-party diagnosis must block behaviorally
# ═══════════════════════════════════════════════════════════════════════════════


def test_third_party_diagnosis_unsupported_claim_blocks():
    """A system-generated unsupported diagnosis claim is BLOCKED (P1)."""
    rule = _RULES["relationships.self_other_perspective"]
    result = rule.evaluate(
        _context(
            third_party_diagnosis_claim={
                "label": "narcissistic personality disorder",
                "source_statement": False,
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.escalation is not None
    assert result.escalation.code == "THIRD_PARTY_DIAGNOSIS_BLOCKED"
    assert any(
        finding.code == "THIRD_PARTY_DIAGNOSIS_UNSUPPORTED"
        for finding in result.findings
    )


def test_third_party_diagnosis_other_unsupported_labels_block():
    """Other unsupported diagnosis labels block too — policy, not a keyword
    detector (the rule blocks on the structured claim semantics, not on the
    label text)."""
    rule = _RULES["relationships.self_other_perspective"]
    for label in (
        "narcissism",
        "personality disorder",
        "attachment diagnosis",
        "depression",
    ):
        result = rule.evaluate(
            _context(
                third_party_diagnosis_claim={
                    "label": label,
                    "source_statement": False,
                },
            )
        )
        assert result.status is ReasoningRuleResultStatus.BLOCKED, label


def test_third_party_diagnosis_sourced_remains_sourced_statement():
    """An authorized source stating a diagnosis is represented with provenance,
    never adopted as a system diagnosis."""
    rule = _RULES["relationships.self_other_perspective"]
    result = rule.evaluate(
        _context(
            third_party_diagnosis_claim={
                "label": "depression",
                "source_statement": True,
                "source_reference": "doc-123",
            },
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "THIRD_PARTY_DIAGNOSIS_SOURCED" for finding in result.findings
    )
    sourced = next(
        f for f in result.findings if f.code == "THIRD_PARTY_DIAGNOSIS_SOURCED"
    )
    # Provenance retained, but the claim is a sourced statement, not a system
    # fact.
    assert sourced.references == ("doc-123",)
    assert sourced.metadata.get("adopted_as_system_diagnosis") is False


def test_third_party_diagnosis_adversarial_missing_source_reference_blocks():
    """A sourced claim without a usable source reference is not a system
    diagnosis either — it must not be adopted without provenance."""
    rule = _RULES["relationships.self_other_perspective"]
    result = rule.evaluate(
        _context(
            third_party_diagnosis_claim={
                "label": "anxiety",
                "source_statement": True,
                "source_reference": "",
            },
        )
    )
    # An empty/unusable reference cannot back a sourced statement: the claim
    # must not be adopted as a system diagnosis.
    assert any(
        finding.metadata.get("adopted_as_system_diagnosis") is False
        for finding in result.findings
    )
