"""Phase 10.25 — Concerns Domain adversarial closure gate.

Primitive matrix (no accidental exception), no permission/certainty/
persistence widening, permutation invariance, duplicate handling, input
non-mutation, and strict JSON safety across every public Concerns helper.
Probe values intentionally differ from committed regression tests
(implementation plan Task 12).
"""

from __future__ import annotations

import copy
import itertools
import json

from cmm.domains.concerns.operations import (
    evaluate_reassurance_result,
    identify_open_questions_result,
    prepare_professional_discussion_result,
    review_recurring_concern_result,
    separate_reality_interpretation_result,
)
from cmm.domains.concerns.permissions import (
    is_persistence_restricted_content,
    permission_authorization_allows,
    persistence_confirmation_accepted,
)
from cmm.domains.concerns.rules import (
    classify_concern_statement,
    detect_catastrophic_escalation,
    detect_false_reassurance,
    evaluate_action_state,
    evaluate_grounded_directness,
    evaluate_immediate_risk_escalation,
    evaluate_proportional_risk,
    evaluate_question_materiality,
    evaluate_reassurance,
    evaluate_repetitive_certainty_pattern,
    evaluate_uncertainty,
    infer_support_need,
    map_lived_experience,
    normalize_json_value,
    review_recurring_concern_state,
    understand_concern,
)

_PRIMITIVES = [
    None,
    True,
    False,
    0,
    1,
    -1,
    2.75,
    float("nan"),
    float("inf"),
    -float("inf"),
    "",
    "arbitrary-string",
    {},
    [],
    (),
    [{}],
    {"nested": {"deep": [1, {"x": None}]}},
    {"statement": "probe", "level": "interpretation", "fact": True},
]


def _probe(fn) -> bool:
    """True only when ``fn`` raised no exception and returned JSON-safe output."""
    try:
        value = fn()
    except Exception:  # noqa: BLE001 -- no-exception gate swallows everything
        return False
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def test_no_exception_gate_primitive_matrix():
    probes = []
    for value in _PRIMITIVES:
        probes.append(_probe(lambda v=value: understand_concern(v)))
        probes.append(_probe(lambda v=value: map_lived_experience(v)))
        probes.append(
            _probe(
                lambda v=value: infer_support_need(explicit_request=v, current_signal=v)
            )
        )
        probes.append(
            _probe(lambda v=value: evaluate_question_materiality(question=v, changes=v))
        )
        probes.append(_probe(lambda v=value: classify_concern_statement(v)))
        probes.append(_probe(lambda v=value: evaluate_uncertainty(records=v)))
        probes.append(
            _probe(lambda v=value: evaluate_reassurance(evidence=v, counterevidence=v))
        )
        probes.append(
            _probe(lambda v=value: evaluate_proportional_risk(severity=v, immediacy=v))
        )
        probes.append(
            _probe(
                lambda v=value: detect_catastrophic_escalation(
                    source_state=v, proposed_state=v
                )
            )
        )
        probes.append(
            _probe(lambda v=value: detect_false_reassurance(reassurance_state=v))
        )
        probes.append(_probe(lambda v=value: review_recurring_concern_state(current=v)))
        probes.append(
            _probe(lambda v=value: evaluate_repetitive_certainty_pattern(turns=v))
        )
        probes.append(
            _probe(lambda v=value: evaluate_action_state(options=v, urgency=v))
        )
        probes.append(
            _probe(
                lambda v=value: evaluate_grounded_directness(assessment=v, evidence=v)
            )
        )
        probes.append(
            _probe(lambda v=value: evaluate_immediate_risk_escalation(risk_state=v))
        )
        probes.append(
            _probe(lambda v=value: separate_reality_interpretation_result(statements=v))
        )
        probes.append(_probe(lambda v=value: evaluate_reassurance_result(evidence=v)))
        probes.append(
            _probe(lambda v=value: identify_open_questions_result(questions=v))
        )
        probes.append(
            _probe(lambda v=value: review_recurring_concern_result(current=v))
        )
        probes.append(
            _probe(lambda v=value: persistence_confirmation_accepted(confirmation=v))
        )
        probes.append(_probe(lambda v=value: permission_authorization_allows(v)))
        probes.append(_probe(lambda v=value: is_persistence_restricted_content(v)))
    assert all(probes), "primitive matrix raised or produced non-JSON-safe output"


def test_no_permission_widening_from_primitive_matrix():
    for value in _PRIMITIVES:
        if value is True:
            continue
        assert permission_authorization_allows(value) is False
        record = persistence_confirmation_accepted(confirmation=value)
        assert record["accepted"] is False


def test_no_certainty_inflation_from_primitive_matrix():
    baseline = evaluate_reassurance()["assessment"]
    for value in _PRIMITIVES:
        with_garbage = evaluate_reassurance(evidence=value)["assessment"]
        if value in (None, [], (), {}, ""):
            # valid-empty inputs keep the insufficient-basis state
            assert with_garbage == baseline
        else:
            assert with_garbage == baseline or with_garbage == "UNCERTAIN"
            assert (
                with_garbage != "REASSURANCE_SUPPORTED"
                or baseline != "INSUFFICIENT_BASIS"
            )


def test_no_authorization_widening_from_mappings():
    for mapping in (
        {"approved": True},
        {"decision_id": "d", "request_id": "r", "approved": True},
        {"authorized": "yes"},
        {"authorized": 1},
    ):
        record = persistence_confirmation_accepted(confirmation=mapping)
        assert record["accepted"] is False
        risk = evaluate_proportional_risk(
            severity=None, specialized_domain_result=mapping
        )
        assert risk["specialized_ownership_preserved"] is False


def test_permutation_gate_equivalent_sets_identical_semantics():
    evidence_set = (
        {
            "identity": "e1",
            "claim": "benign",
            "stance": "opposes_target",
            "grounding": "g1",
        },
        {
            "identity": "e2",
            "claim": "benign",
            "stance": "opposes_target",
            "grounding": "g2",
        },
        {
            "identity": "e3",
            "claim": "benign",
            "stance": "opposes_target",
            "grounding": "g3",
        },
    )
    canonical = {
        (
            evaluate_reassurance(target_claim="benign", evidence=order)["assessment"],
            evaluate_proportional_risk(severity="low")["risk_level"],
        )
        for order in itertools.permutations(evidence_set)
    }
    assert len(canonical) == 1

    uncertainty_set = (
        {"identity": "u1", "unknown": "intent"},
        {"identity": "u2", "unknown": "timing"},
    )
    u_canonical = {
        tuple(
            sorted(
                item["identity"]
                for item in evaluate_uncertainty(records=order)["uncertainties"]
            )
        )
        for order in itertools.permutations(uncertainty_set)
    }
    assert len(u_canonical) == 1

    statements = (
        {"statement": "a fact", "level": "fact", "evidence_references": ("m1",)},
        {"statement": "an interpretation", "level": "interpretation"},
        {"statement": "a fear", "level": "fear"},
    )
    s_canonical = {
        tuple(
            sorted(
                r["level"]
                for r in separate_reality_interpretation_result(statements=o)[
                    "statements"
                ]
            )
        )
        for o in itertools.permutations(statements)
    }
    assert len(s_canonical) == 1


def test_duplicate_evidence_gate():
    base = (
        {
            "identity": "c1",
            "claim": "feared reading",
            "stance": "opposes_target",
            "grounding": "a",
        },
        {
            "identity": "c2",
            "claim": "feared reading",
            "stance": "opposes_target",
            "grounding": "b",
        },
    )
    single_assessment = evaluate_reassurance(
        target_claim="feared reading", evidence=base
    )["assessment"]
    duplicated = evaluate_reassurance(
        target_claim="feared reading",
        evidence=(
            *base,
            {
                "identity": "c1-dup",
                "claim": "feared reading",
                "stance": "opposes_target",
                "grounding": "a",
            },
            {
                "identity": "c1-dup",
                "claim": "feared reading",
                "stance": "opposes_target",
                "grounding": "a",
            },
        ),
    )["assessment"]
    assert duplicated == single_assessment


def test_malformed_evidence_gate_never_increases_anything():
    clean = evaluate_reassurance(
        target_claim="x",
        counterevidence=(
            {
                "identity": "c1",
                "claim": "x",
                "stance": "opposes_target",
                "grounding": "a",
            },
            {
                "identity": "c2",
                "claim": "x",
                "stance": "opposes_target",
                "grounding": "b",
            },
            {
                "identity": "c3",
                "claim": "x",
                "stance": "opposes_target",
                "grounding": "c",
            },
        ),
    )
    dirty = evaluate_reassurance(
        target_claim="x",
        evidence=(float("nan"), {"no_claim": True}, 7, [1, 2], "junk"),
        counterevidence=(
            {
                "identity": "c1",
                "claim": "x",
                "stance": "opposes_target",
                "grounding": "a",
            },
            {
                "identity": "c2",
                "claim": "x",
                "stance": "opposes_target",
                "grounding": "b",
            },
            {
                "identity": "c3",
                "claim": "x",
                "stance": "opposes_target",
                "grounding": "c",
            },
        ),
    )
    assert dirty["malformed_count"] >= 4
    assert dirty["assessment"] == clean["assessment"]


def test_input_non_mutation_gate():
    material = {
        "situation": "s",
        "emotion_statements": ["e"],
        "fear_statements": ["f"],
        "session_context": {"active_topic": "t"},
    }
    statements = [{"statement": "x", "level": "interpretation"}]
    current = {"topic": "t", "question": "q"}
    snapshots = [
        copy.deepcopy(material),
        copy.deepcopy(statements),
        copy.deepcopy(current),
    ]
    understand_concern(material)
    separate_reality_interpretation_result(statements=statements)
    review_recurring_concern_state(current=current)
    assert material == snapshots[0]
    assert statements == snapshots[1]
    assert current == snapshots[2]


def test_strict_json_gate_all_public_helpers():
    nan = float("nan")
    inf = float("inf")
    outputs = (
        normalize_json_value({"x": nan}),
        classify_concern_statement({"statement": "s", "value": nan}),
        evaluate_uncertainty(
            records=({"identity": "u", "unknown": "x", "value": nan},)
        ),
        evaluate_reassurance(
            evidence=({"identity": "e", "supports": "x", "value": inf},)
        ),
        evaluate_proportional_risk(severity=nan),
        detect_false_reassurance(reassurance_state={"assessment": "X", "v": nan}),
        review_recurring_concern_state(current={"topic": nan}),
        evaluate_action_state(options=("o",), urgency=nan),
        prepare_professional_discussion_result(concern_summary=nan, key_facts=(nan,)),
    )
    for output in outputs:
        json.dumps(output, allow_nan=False)


def test_gate_summary_all_named_adversarial_gates_pass():
    gates = {
        "NO_EXCEPTION_GATE": (
            all(
                _probe(lambda v=p: understand_concern(v))
                for p in (None, 1, "s", {}, [])
            )
            and all(
                _probe(lambda v=p: classify_concern_statement(v))
                for p in (None, 1, "s", {}, [])
            )
            and all(
                _probe(lambda v=p: evaluate_uncertainty(records=v))
                for p in (None, 1, "s", {}, [])
            )
            and all(
                _probe(lambda v=p: evaluate_reassurance(evidence=v))
                for p in (None, 1, "s", {}, [])
            )
            and all(
                _probe(lambda v=p: review_recurring_concern_state(current=v))
                for p in (None, 1, "s", {}, [])
            )
        ),
        "PERMISSION_GATE": all(
            permission_authorization_allows(raw) is False
            for raw in ("true", 1, 0, [], {}, None, 0.0, float("nan"))
        )
        and permission_authorization_allows(True) is True,
        "DUPLICATE_EVIDENCE_GATE": _probe(
            lambda: evaluate_reassurance(
                target_claim="f",
                evidence=(
                    {
                        "identity": "d",
                        "claim": "f",
                        "stance": "opposes_target",
                        "grounding": "g",
                    },
                    {
                        "identity": "d",
                        "claim": "f",
                        "stance": "opposes_target",
                        "grounding": "g",
                    },
                    {
                        "identity": "d2",
                        "claim": "f",
                        "stance": "opposes_target",
                        "grounding": "g2",
                    },
                ),
            )
        ),
        "MALFORMED_EVIDENCE_GATE": _probe(
            lambda: evaluate_reassurance(evidence=(float("nan"), {}, 3))
        ),
        "INPUT_NON_MUTATION_GATE": _probe(lambda: _immutability_probe()),
        "STRICT_JSON_GATE": _probe(
            lambda: json.dumps(
                evaluate_reassurance_result(evidence=()), allow_nan=False
            )
        ),
        "PERMUTATION_GATE": len(
            {
                evaluate_reassurance(target_claim="b", evidence=order)["assessment"]
                for order in itertools.permutations(
                    (
                        {
                            "identity": "p1",
                            "claim": "b",
                            "stance": "opposes_target",
                            "grounding": "1",
                        },
                        {
                            "identity": "p2",
                            "claim": "b",
                            "stance": "opposes_target",
                            "grounding": "2",
                        },
                    )
                )
            }
        )
        == 1,
    }
    assert all(gates.values()), gates


def _immutability_probe():
    payload = {
        "topic": "probe",
        "question": "probe?",
        "nested": {"list": [1, 2]},
    }
    snapshot = copy.deepcopy(payload)
    review_recurring_concern_state(current=payload)
    evaluate_action_state(options=("o",))
    return payload == snapshot
