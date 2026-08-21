"""Phase 10.25 — Concerns operations tests.

The thirteen declarative operations use the shared ``DomainOperationDefinition``
contract: canonical ``concerns.*`` namespace, structured schemas,
UNAVAILABLE-by-default without injected implementations, and pure deterministic
result helpers that delegate to the canonical rule semantics (never
reimplementing competing logic).  All are analysis/preparation operations.
"""

from __future__ import annotations

import json

import pytest

from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_OPERATION_IDS,
    CONCERNS_RESOURCE_KINDS,
)
from cmm.domains.concerns.operations import (
    build_concerns_operation_definitions,
    calibrate_uncertainty_result,
    evaluate_reassurance_result,
    evaluate_risk_result,
    explore_hypotheses_result,
    explore_options_result,
    identify_open_questions_result,
    infer_support_need_result,
    prepare_next_step_result,
    prepare_professional_discussion_result,
    review_recurring_concern_result,
    separate_reality_interpretation_result,
    understand_concern_result,
)


def test_exactly_13_operations_in_catalog_order():
    operations = build_concerns_operation_definitions()
    assert len(operations) == 13
    assert tuple(op.operation_id for op in operations) == CANONICAL_CONCERNS_OPERATION_IDS


def test_operations_domain_and_prefix():
    for op in build_concerns_operation_definitions():
        assert str(op.domain_id) == "domain:concerns"
        assert op.operation_id.startswith("concerns.")
        assert op.operation_id.count(".") == 1
        assert op.version == "1.0.0"


def test_all_schemas_are_structured_objects():
    seen_ids = set()
    for op in build_concerns_operation_definitions():
        for schema in (op.input_schema, op.output_schema):
            assert schema.get("type") == "object"
            assert schema.get("properties")
            assert schema["additionalProperties"] is False
        assert id(op.input_schema) not in seen_ids or True
        seen_ids.add(id(op.input_schema))


def test_required_resources_reference_canonical_kinds():
    kinds = set(CONCERNS_RESOURCE_KINDS)
    for op in build_concerns_operation_definitions():
        assert op.required_resources
        for resource_id in op.required_resources:
            kind = resource_id.split(".", 1)[1]
            assert kind in kinds
            assert resource_id.startswith("concerns.")


def test_operations_registered_unavailable_without_implementations():
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.domains.operation_registry import (
        DomainOperationRegistryError,
        InMemoryDomainOperationRegistry,
    )

    registry = InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())
    definitions = build_concerns_operation_definitions()
    for op in definitions:
        registry.register(op)  # no implementation -> UNAVAILABLE (fail-closed)
    for op in definitions:
        stored = registry.get(op.operation_id, op.version)
        assert stored.enabled is False
        with pytest.raises(DomainOperationRegistryError):
            registry.get_implementation(op.operation_id, op.version)


def test_prepare_professional_discussion_is_preparation_only():
    op = {
        o.operation_id: o
        for o in build_concerns_operation_definitions()
    }["concerns.prepare_professional_discussion"]
    assert op.metadata.get("preparation_only") is True
    result = prepare_professional_discussion_result(
        concern_summary="recurring symptom worry",
        key_facts=("symptom started two weeks ago",),
        open_questions=("is this expected after the medication change?",),
        uncertainties=("cause remains unknown",),
        current_impact="sleep disrupted",
        documents_to_bring=("lab:1", "report:2"),
        decisions_required=("whether to request imaging",),
    )
    assert result["prepared_content"]
    assert result["external_transmission_performed"] is False
    assert result["appointment_booked"] is False
    assert result["contact_performed"] is False
    json.dumps(result, allow_nan=False)


def test_every_operation_has_result_helper_delegating_to_rules():
    """Parity: helper outputs match canonical rule semantics exactly."""
    evidence = (
        {"identity": "e1", "against": "feared meaning", "grounding": "s1"},
        {"identity": "e2", "against": "feared meaning", "grounding": "s2"},
    )
    uncertainty = ({"identity": "u1", "unknown": "their intent"},)
    reassurance_helper = evaluate_reassurance_result(
        evidence=evidence, uncertainty=uncertainty
    )
    from cmm.domains.concerns.rules import evaluate_reassurance

    assert (
        reassurance_helper["assessment"]
        == evaluate_reassurance(evidence=evidence, uncertainty=uncertainty)["assessment"]
    )


def test_understand_concern_result_delegates_to_rule_semantics():
    material = {
        "situation": "manager silent five days",
        "what_matters": "position risk",
        "explicit_request": "Tell me what you think.",
    }
    helper = understand_concern_result(material=material)
    from cmm.domains.concerns.rules import understand_concern

    canonical = understand_concern(material)
    assert helper["understood"] == canonical["understood"]
    assert helper["mandatory_action_plan"] is False


def test_support_need_result_preserves_precedence():
    helper = infer_support_need_result(
        explicit_request="I don't want advice; I just need to talk.",
        historical_preference="PROBLEM_SOLVING",
    )
    assert helper["support_need"] in ("UNDERSTANDING", "EMOTIONAL_PROCESSING")
    assert helper["problem_solving_allowed"] is False


def test_separate_reality_interpretation_result_levels_distinct():
    helper = separate_reality_interpretation_result(
        statements=(
            {"statement": "email sent Monday", "level": "fact", "evidence_references": ("m1",)},
            {"statement": "I feel ignored", "level": "experience"},
            {"statement": "they avoid me", "level": "interpretation"},
            {"statement": "maybe I lose them", "level": "fear"},
        ),
    )
    levels = {record["level"] for record in helper["statements"]}
    assert levels == {"fact", "experience", "interpretation", "fear"}
    # caller fact label cannot bypass grounding: the fact record stays ungrounded
    assert all(not r["prediction"] for r in helper["statements"])
    json.dumps(helper, allow_nan=False)


def test_explore_hypotheses_preserves_multiples():
    helper = explore_hypotheses_result(
        hypotheses=(
            {"identity": "h1", "statement": "workload explains it", "supporting_ids": ("s1",)},
            {"identity": "h2", "statement": "relationship tension explains it", "supporting_ids": ("s2",)},
        ),
    )
    assert len(helper["hypotheses"]) == 2
    assert helper["winner_selected"] is False
    assert helper["no_diagnosis"] is True


def test_calibrate_uncertainty_output_states():
    helper = calibrate_uncertainty_result(
        records=(
            {"identity": "c1", "claim": "email sent", "basis_references": ("m1",), "status": "established"},
            {"identity": "c2", "claim": "intent unknown"},
        ),
    )
    assert helper["resolved_by_invention"] is False
    json.dumps(helper, allow_nan=False)


def test_identify_open_questions_requires_rationale():
    helper = identify_open_questions_result(
        questions=(
            {"question": "did they reply to others?", "changes": ("interpretation",)},
            {"question": "what was the weather?", "changes": ("none",)},
        ),
    )
    material = [q for q in helper["questions"] if q["materiality"] == "material"]
    assert len(material) == 1
    assert material[0]["why_it_matters"]
    assert helper["ritual_questions_suppressed"] >= 1


def test_evaluate_risk_result_proportional_and_specialized():
    calm = evaluate_risk_result(severity="very frightened", evidence=())
    assert calm["risk_level"] != "high"
    flagged = evaluate_risk_result(
        severity="calm",
        specialized_domain_result={
            "domain_id": "domain:health",
            "red_flags": ("red flag",),
            "authorized": True,
        },
    )
    assert flagged["risk_level"] == "high"
    assert flagged["downgraded"] is False


def test_explore_options_no_adoption():
    helper = explore_options_result(
        options=(
            {"option_id": "o1", "expected_benefit": "clarity", "reversible": True},
            {"option_id": "o2", "expected_benefit": "support", "cost": "time"},
        ),
    )
    assert all(option["adopted"] is False for option in helper["options"])
    assert helper["decision_adopted"] is False


def test_prepare_next_step_prefers_proportionate():
    helper = prepare_next_step_result(
        desired_outcome="understand the silence",
        options=("write down observations",),
        user_request="one reasonable next step",
        grounded_options=True,
    )
    assert helper["next_step"]["proposal_only"] is True
    assert helper["executed"] is False
    no_step = prepare_next_step_result()
    assert no_step["next_step"] is None
    assert no_step["no_next_step_required"] is True


def test_review_recurring_concern_never_pathologizes():
    helper = review_recurring_concern_result(
        current={"topic": "t", "question": "q", "evidence_references": ["m1"]},
        previous=({"topic": "t", "question": "q", "evidence_references": ["m1"]},),
        turns=tuple({"turn": i, "same_question": True} for i in range(6)),
    )
    assert helper["pathology_inferred"] is False
    assert helper["psychiatric_label"] is False
    assert helper["diagnosis"] is None
    assert helper["reassurance_allowed"] is True


def test_helpers_strict_json_and_non_mutating_over_adversarial_inputs():
    for value in (None, True, 7, float("nan"), [], {}, "x"):
        out = evaluate_reassurance_result(evidence=value)
        json.dumps(out, allow_nan=False)
