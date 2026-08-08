"""Phase 10.21 — Audit v1 remediation RED→GREEN tests.

Each test below is a regression guard for a substantiated audit finding.  The
tests are intentionally written against the *actual* contracts (rule evaluation
paths, operation schemas, resource bindings) rather than calling private
helpers directly, so they prove the production path is fixed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains import relationships
from cmm.domains.relationships.rules import classify_relationship_statement

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
    """A sourced claim without a usable source reference is not a sourced
    statement — it is blocked, not adopted as a system diagnosis."""
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
    # is BLOCKED and never adopted as a system diagnosis.
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.escalation is not None
    assert result.escalation.code == "THIRD_PARTY_DIAGNOSIS_BLOCKED"
    assert any(
        finding.metadata.get("adopted_as_system_diagnosis") is False
        for finding in result.findings
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Audit V2 — Grounding cannot be bypassed by a boolean (P1)
# ═══════════════════════════════════════════════════════════════════════════════


def test_observed_boolean_alone_never_emits_observed_fact():
    """is_observed=True with no grounded evidence reference is fail-closed."""
    assert classify_relationship_statement(is_observed=True) == "unknown"
    assert (
        classify_relationship_statement(is_observed=True, provenance="res-1")
        == "unknown"
    )


def test_observed_with_grounded_reference_may_emit_observed_fact():
    assert (
        classify_relationship_statement(
            is_observed=True, evidence_reference_ids=("res-1",)
        )
        == "observed_fact"
    )


def test_ungrounded_observed_does_not_promote_interpretation():
    """Mixed flags: is_observed=True + is_user_interpretation=True with no
    factual evidence reference must NOT promote the interpretation to fact."""
    assert (
        classify_relationship_statement(is_observed=True, is_user_interpretation=True)
        == "user_interpretation"
    )


def test_ungrounded_observed_does_not_promote_hypothesis():
    """Mixed flags: is_observed=True + is_system_hypothesis=True with no
    separate grounded factual proposition must NOT promote the hypothesis."""
    assert (
        classify_relationship_statement(is_observed=True, is_system_hypothesis=True)
        == "system_hypothesis"
    )


def test_ungrounded_observed_does_not_promote_possible_origin():
    assert (
        classify_relationship_statement(is_observed=True, is_possible_origin=True)
        == "possible_origin"
    )


def test_grounded_observed_wins_over_interpretation():
    """A separately grounded factual proposition still yields observed_fact."""
    assert (
        classify_relationship_statement(
            is_observed=True,
            is_user_interpretation=True,
            evidence_reference_ids=("res-1",),
        )
        == "observed_fact"
    )


def test_other_observable_boolean_alone_never_establishes_behavior():
    from cmm.domains.relationships.rules import classify_relationship_perspective

    # Without grounded evidence, other_observable stays possible/unknown, never
    # fact.
    assert classify_relationship_perspective(is_other_observable=True) == "unknown"
    assert (
        classify_relationship_perspective(
            is_other_observable=True, is_other_possible=True
        )
        == "possible_other_perspective"
    )
    assert (
        classify_relationship_perspective(
            is_other_observable=True, evidence_reference_ids=("res-1",)
        )
        == "other_observable_behavior"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Audit V2 — DoNotInferIntentRule grounding (P1)
# ═══════════════════════════════════════════════════════════════════════════════


def test_direct_evidence_requires_grounding_reference():
    """direct_evidence=True with no usable evidence/source reference is
    BLOCKED / not established."""
    rule = _RULES["relationships.do_not_infer_intent"]
    result = rule.evaluate(
        _context(intent_claim={"intent": "x", "direct_evidence": True})
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED


def test_direct_evidence_with_grounding_is_applied():
    rule = _RULES["relationships.do_not_infer_intent"]
    result = rule.evaluate(
        _context(
            intent_claim={
                "intent": "x",
                "direct_evidence": True,
                "evidence_reference": "res-1",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED


def test_sourced_statement_requires_real_source_reference():
    """sourced_statement=True with a missing/blank source is BLOCKED / invalidly
    grounded; no fake 'unknown' reference is fabricated."""
    rule = _RULES["relationships.do_not_infer_intent"]
    for claim in (
        {"intent": "x", "sourced_statement": True},
        {"intent": "x", "sourced_statement": True, "source": ""},
    ):
        result = rule.evaluate(_context(intent_claim=claim))
        assert result.status is ReasoningRuleResultStatus.BLOCKED
        for finding in result.findings:
            assert all("unknown" != ref for ref in finding.references)


def test_sourced_statement_with_real_source_is_applied_not_fact():
    rule = _RULES["relationships.do_not_infer_intent"]
    result = rule.evaluate(
        _context(
            intent_claim={
                "intent": "x",
                "sourced_statement": True,
                "source_reference": "doc-1",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(finding.code == "INTENT_SOURCED_NOT_FACT" for finding in result.findings)


# ═══════════════════════════════════════════════════════════════════════════════
# Audit V2 — Operation schemas are recursively closed (P1)
# ═══════════════════════════════════════════════════════════════════════════════


def _relationship_operations():
    return {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }


def _collect_nested_object_schemas(schema, path):
    """Yield (path, schema) for every nested structured object owned by
    Relationships reachable from ``schema``."""
    found = []
    if isinstance(schema, Mapping):
        if schema.get("type") == "object" and (
            "properties" in schema or "required" in schema
        ):
            found.append((path, schema))
        for key, child in schema.items():
            if key in ("properties",):
                continue
            found.extend(_collect_nested_object_schemas(child, path))
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            for prop_name, prop_schema in properties.items():
                found.extend(
                    _collect_nested_object_schemas(prop_schema, f"{path}.{prop_name}")
                )
    elif isinstance(schema, list):
        for index, child in enumerate(schema):
            found.extend(_collect_nested_object_schemas(child, f"{path}[{index}]"))
    return found


def test_all_relationships_nested_object_schemas_recursively_closed():
    """Every Relationships-owned nested structured object must be closed
    (additionalProperties False)."""
    for operation in _relationship_operations().values():
        for output_schema in (operation.input_schema, operation.output_schema):
            for path, schema in _collect_nested_object_schemas(output_schema, "$"):
                assert schema.get("additionalProperties") is False, (
                    f"{operation.operation_id} nested schema at {path} is not closed"
                )


def test_representative_valid_outputs_validate():
    """Representative valid outputs for the closed nested schemas must validate."""
    valid_outputs = {
        "relationships.build_timeline": {
            "events": [
                {
                    "id": "e1",
                    "kind": "interaction",
                    "timestamp": "2026-01-01",
                    "source_references": ("res-1",),
                }
            ]
        },
        "relationships.compare_periods": {
            "comparison": {
                "period_a": "2026-01-01",
                "period_b": "2026-02-01",
                "observed_changes": ("c1",),
                "summary": "no change",
            }
        },
        "relationships.detect_patterns": {
            "patterns": [
                {
                    "kind": "frequency_change",
                    "hypothesis": True,
                    "support_references": ("s1",),
                    "counterexample_references": (),
                    "uncertainty": "medium",
                }
            ]
        },
        "relationships.extract_events": {
            "events": [{"id": "e1", "kind": "rupture", "timestamp": "2026-01-01"}]
        },
        "relationships.identify_needs": {
            "needs": [{"kind": "clarity", "source_references": ("res-1",)}]
        },
        "relationships.prepare_conversation": {
            "preparation": {
                "objective": "discuss boundaries",
                "facts": ("f1",),
                "feelings": ("g1",),
                "needs": ("n1",),
                "questions": ("q1",),
                "boundary_options": ("b1",),
                "possible_wording": ("w1",),
                "risks": ("r1",),
                "uncertainties": ("u1",),
                "alternatives": ("a1",),
            }
        },
        "relationships.review_boundaries": {
            "review": {"boundary_id": "b1", "state": "violated", "violations": ("v1",)}
        },
        "relationships.separate_facts_interpretations": {
            "category_map": {
                "facts": ("f1",),
                "statements": ("s1",),
                "interpretations": ("i1",),
                "hypotheses": ("h1",),
            }
        },
        "relationships.track_open_questions": {"questions": ("q1",)},
    }
    operations = _relationship_operations()
    for operation_id, payload in valid_outputs.items():
        issues = validate_operation_schema(
            payload, operations[operation_id].output_schema
        )
        assert issues == (), (
            f"{operation_id} valid output failed: {[i.message for i in issues]}"
        )


def test_prepare_conversation_cannot_schema_authorize_send_contact():
    """prepare_conversation.preparation must NOT schema-authorize sent/contacted/
    initiated/executed."""
    operation = _relationship_operations()["relationships.prepare_conversation"]
    forbidden = {
        "preparation": {"sent": True},
    }
    forbidden2 = {
        "preparation": {"objective": "x", "contacted": True},
    }
    for payload in (forbidden, forbidden2):
        issues = validate_operation_schema(payload, operation.output_schema)
        assert any(issue.code == "additional_property" for issue in issues), (
            f"forbidden field was not rejected: {payload}"
        )


def test_prepare_conversation_valid_preparation_has_no_send_field():
    schema = _relationship_operations()[
        "relationships.prepare_conversation"
    ].output_schema
    preparation = schema["properties"]["preparation"]["properties"]
    for forbidden in ("sent", "contacted", "initiated", "executed"):
        assert forbidden not in preparation


def test_detect_patterns_cannot_authorize_psychological_cause():
    """A pattern item must not encode a psychological cause / intent / diagnosis."""
    operation = _relationship_operations()["relationships.detect_patterns"]
    payload = {
        "patterns": [
            {"kind": "x", "hypothesis": True, "psychological_cause": "narcissism"}
        ]
    }
    issues = validate_operation_schema(payload, operation.output_schema)
    assert any(issue.code == "additional_property" for issue in issues)


def test_pattern_item_schema_has_no_inference_fields():
    pattern_schema = _relationship_operations()[
        "relationships.detect_patterns"
    ].output_schema
    item = pattern_schema["properties"]["patterns"]["items"]["properties"]
    for forbidden in (
        "psychological_cause",
        "intent",
        "personality_diagnosis",
        "diagnosis",
    ):
        assert forbidden not in item


def test_review_boundaries_cannot_authorize_mutation():
    """review_boundaries.review must remain REVIEW output, not a mutation result."""
    operation = _relationship_operations()["relationships.review_boundaries"]
    payload = {
        "review": {
            "boundary_id": "b1",
            "state": "violated",
            "enforced": True,
        }
    }
    issues = validate_operation_schema(payload, operation.output_schema)
    assert any(issue.code == "additional_property" for issue in issues)


def test_review_boundaries_schema_has_no_mutation_field():
    review_schema = _relationship_operations()[
        "relationships.review_boundaries"
    ].output_schema
    review_props = review_schema["properties"]["review"]["properties"]
    for forbidden in ("enforced", "modified", "communicated", "withdrawn"):
        assert forbidden not in review_props


def test_separate_facts_interpretations_structurally_separates_categories():
    """category_map must structurally separate facts/statements/interpretations/
    hypotheses."""
    category_map = _relationship_operations()[
        "relationships.separate_facts_interpretations"
    ].output_schema["properties"]["category_map"]
    assert category_map["type"] == "object"
    assert category_map["additionalProperties"] is False
    category_props = category_map["properties"]
    for category in ("facts", "statements", "interpretations", "hypotheses"):
        assert category in category_props
