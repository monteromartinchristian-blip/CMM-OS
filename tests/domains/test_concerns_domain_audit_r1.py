"""Phase 10.25 — Audit-remediation regression tests for reassurance semantics.

Remediates B-001 (target-aware evidence stance) and B-002 (operation output
schema parity).  These tests encode the frozen design §22 requirement that
reassurance direction is relative to the *target claim being assessed*, never
to the lexical key a record happens to use, and that every canonical operation
helper's real output satisfies its declared operation output schema.
"""

from __future__ import annotations

import json

import pytest

from cmm.agent_runtime.operation_schema import validate_operation_schema
from cmm.domains.concerns.catalog import CANONICAL_CONCERNS_OPERATION_IDS
from cmm.domains.concerns.operations import (
    build_concerns_operation_definitions,
    calibrate_uncertainty_result,
    evaluate_reassurance_result,
    evaluate_risk_result,
    explore_hypotheses_result,
    explore_options_result,
    identify_open_questions_result,
    infer_support_need_result,
    map_lived_experience_result,
    prepare_next_step_result,
    prepare_professional_discussion_result,
    review_recurring_concern_result,
    separate_reality_interpretation_result,
    understand_concern_result,
)
from cmm.domains.concerns.rules import (
    CONCERN_SUPPORTED,
    INSUFFICIENT_BASIS,
    REASSURANCE_PARTIAL,
    REASSURANCE_SUPPORTED,
    UNCERTAIN,
    evaluate_reassurance,
)

# ── B-001: target-relative evidence stance ──────────────────────────────────


def test_benign_explanation_support_is_not_concern_evidence():
    """The audit reproduction: two grounded records supporting a BENIGN
    explanation must not be counted as concern evidence merely because they
    carry a ``supports`` key.  Nothing here supports the feared reading, so
    CONCERN_SUPPORTED is invalid."""
    record = evaluate_reassurance(
        target_claim="friend is rejecting me",
        evidence=(
            {
                "identity": "e1",
                "claim": "they have been busy with work",
                "stance": "opposes_target",
                "grounding": "source:1",
            },
            {
                "identity": "e2",
                "claim": "they replied warmly yesterday",
                "stance": "opposes_target",
                "grounding": "source:2",
            },
        ),
    )
    assert record["assessment"] in (
        REASSURANCE_SUPPORTED,
        REASSURANCE_PARTIAL,
        UNCERTAIN,
    )
    assert record["assessment"] != CONCERN_SUPPORTED


def test_reassurance_stance_is_relative_to_target_claim():
    """Direction is decided by each record's explicit stance relative to the
    target claim, not by which bucket it arrived in and not by the verb/key
    ``supports``."""
    # A record explicitly supporting the feared target blocks full reassurance.
    pro_target = evaluate_reassurance(
        target_claim="manager is cutting me",
        evidence=(
            {
                "identity": "x",
                "claim": "c",
                "stance": "supports_target",
                "grounding": "s1",
            },
        ),
        counterevidence=(
            {
                "identity": "y",
                "claim": "d",
                "stance": "opposes_target",
                "grounding": "s2",
            },
            {
                "identity": "z",
                "claim": "e",
                "stance": "opposes_target",
                "grounding": "s3",
            },
        ),
    )
    assert pro_target["assessment"] != REASSURANCE_SUPPORTED

    # Legacy key-based records without an explicit stance fail closed: they
    # can neither strengthen reassurance nor concern.
    legacy = evaluate_reassurance(
        target_claim="fear",
        evidence=(
            {"identity": "l1", "supports": "benign explanation", "grounding": "g1"},
            {"identity": "l2", "supports": "benign explanation", "grounding": "g2"},
        ),
    )
    assert legacy["assessment"] == INSUFFICIENT_BASIS


def test_same_provenance_with_different_record_ids_does_not_inflate():
    """The audit threshold-crossing case: one provenance repeated under two
    caller-controlled IDs must not upgrade PARTIAL to SUPPORTED."""
    single = evaluate_reassurance(
        target_claim="feared meaning",
        evidence=(
            {
                "identity": "r1",
                "claim": "they were warm at lunch",
                "stance": "opposes_target",
                "grounding": "source:1",
            },
        ),
    )
    duplicated = evaluate_reassurance(
        target_claim="feared meaning",
        evidence=(
            {
                "identity": "r1",
                "claim": "they were warm at lunch",
                "stance": "opposes_target",
                "grounding": "source:1",
            },
            {
                "identity": "r1-different-id",
                "claim": "they were warm at lunch",
                "stance": "opposes_target",
                "grounding": "source:1",
            },
        ),
    )
    assert single["assessment"] == REASSURANCE_PARTIAL
    assert duplicated["assessment"] == REASSURANCE_PARTIAL
    assert duplicated["duplicate_count"] >= 1


def test_source_quality_can_limit_reassurance():
    """Low-quality sources cannot produce full reassurance even when their
    stance opposes the target; only grounded-quality sources may."""
    weak = evaluate_reassurance(
        target_claim="feared meaning",
        evidence=(
            {
                "identity": "w1",
                "claim": "probably nothing",
                "stance": "opposes_target",
                "grounding": "rumor:1",
                "source_quality": "unverified_hearsay",
            },
            {
                "identity": "w2",
                "claim": "seems fine",
                "stance": "opposes_target",
                "grounding": "guess:2",
                "source_quality": "speculation",
            },
        ),
    )
    assert weak["assessment"] != REASSURANCE_SUPPORTED

    strong = evaluate_reassurance(
        target_claim="feared meaning",
        evidence=(
            {
                "identity": "s1",
                "claim": "documented reply",
                "stance": "opposes_target",
                "grounding": "msg:1",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
            {
                "identity": "s2",
                "claim": "documented meeting",
                "stance": "opposes_target",
                "grounding": "msg:2",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
        ),
    )
    assert strong["assessment"] == REASSURANCE_SUPPORTED


def test_temporally_stale_evidence_cannot_upgrade_reassurance():
    """Stale evidence about a past state cannot fully support reassurance
    about the current situation."""
    stale = evaluate_reassurance(
        target_claim="current rejection",
        evidence=(
            {
                "identity": "t1",
                "claim": "things were good last year",
                "stance": "opposes_target",
                "grounding": "journal:old",
                "temporal_relevance": "stale",
            },
            {
                "identity": "t2",
                "claim": "no conflict observed previously",
                "stance": "opposes_target",
                "grounding": "note:old",
                "temporal_relevance": "stale",
            },
        ),
    )
    assert stale["assessment"] != REASSURANCE_SUPPORTED

    current = evaluate_reassurance(
        target_claim="current rejection",
        evidence=(
            {
                "identity": "t3",
                "claim": "warm reply today",
                "stance": "opposes_target",
                "grounding": "msg:today",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
            {
                "identity": "t4",
                "claim": "meeting scheduled this week",
                "stance": "opposes_target",
                "grounding": "cal:this-week",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
        ),
    )
    assert current["assessment"] == REASSURANCE_SUPPORTED


def test_base_plausibility_is_preserved_not_invented():
    """Base plausibility is represented as structured context when supplied
    and is never invented numerically."""
    implausible = evaluate_reassurance(
        target_claim="the sun will not rise tomorrow",
        base_plausibility="implausible",
        evidence=(
            {
                "identity": "b1",
                "claim": "sun rose today",
                "stance": "opposes_target",
                "grounding": "obs:1",
            },
        ),
    )
    assert implausible["base_plausibility"] == "implausible"
    assert implausible["numeric_probability_assigned"] is False
    assert implausible["probability"] is None
    json.dumps(implausible, allow_nan=False)

    unspecified = evaluate_reassurance(
        target_claim="x",
        evidence=(),
    )
    assert unspecified["base_plausibility"] is None


def test_unknown_stance_fails_closed_neither_direction():
    """Unknown/malformed stance values cannot strengthen either side."""
    record = evaluate_reassurance(
        target_claim="fear",
        evidence=(
            {"identity": "u1", "claim": "c", "stance": "vibes", "grounding": "g1"},
            {"identity": "u2", "claim": "d", "stance": None, "grounding": "g2"},
            {"identity": "u3", "claim": "e", "grounding": "g3"},
        ),
    )
    assert record["malformed_count"] >= 3
    assert record["assessment"] == INSUFFICIENT_BASIS


def test_material_negative_signal_dimension_is_represented():
    """A material negative signal remains visible in the structured output."""
    record = evaluate_reassurance(
        target_claim="all is fine",
        material_concerns=("documented missed deadlines",),
        evidence=(
            {
                "identity": "m1",
                "claim": "apology received",
                "stance": "opposes_target",
                "grounding": "msg:1",
            },
            {
                "identity": "m2",
                "claim": "meeting scheduled",
                "stance": "opposes_target",
                "grounding": "cal:1",
            },
        ),
    )
    assert record["material_concern"] is True
    assert tuple(record["acknowledged_concerns"]) != ()
    assert record["concern_erased"] is False
    assert record["assessment"] != REASSURANCE_SUPPORTED


def test_remaining_uncertainty_dimension_is_represented():
    record = evaluate_reassurance(
        target_claim="fear",
        uncertainty=({"identity": "u1", "unknown": "their intent"},),
        evidence=(
            {
                "identity": "e1",
                "claim": "warm reply",
                "stance": "opposes_target",
                "grounding": "g1",
            },
            {
                "identity": "e2",
                "claim": "meeting set",
                "stance": "opposes_target",
                "grounding": "g2",
            },
        ),
    )
    assert record["remaining_uncertainty"] == ("u1",)
    assert record["reassurance_coexists_with_uncertainty"] is True


def test_helper_output_carries_structured_evidence_dimensions():
    """The operation helper preserves the new structured dimensions."""
    record = evaluate_reassurance_result(
        target_claim="friend is rejecting me",
        evidence=(
            {
                "identity": "e1",
                "claim": "busy week documented",
                "stance": "opposes_target",
                "grounding": "msg:1",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
            {
                "identity": "e2",
                "claim": "warm reply yesterday",
                "stance": "opposes_target",
                "grounding": "msg:2",
                "source_quality": "grounded",
                "temporal_relevance": "current",
            },
        ),
    )
    assert record["target_claim"] == "friend is rejecting me"
    assert record["false_reassurance_detected"] is False
    json.dumps(record, allow_nan=False)


# ── B-002: operation helper output satisfies declared schema ────────────────


def _representative_helper_inputs() -> dict:
    return {
        "concerns.understand_concern": lambda: understand_concern_result(
            material={
                "situation": "manager silent five days",
                "what_matters": "position risk",
            }
        ),
        "concerns.infer_support_need": lambda: infer_support_need_result(
            explicit_request="Tell me what you think."
        ),
        "concerns.map_lived_experience": lambda: map_lived_experience_result(
            material={"emotion_statements": ("I'm anxious",)}
        ),
        "concerns.separate_reality_interpretation": lambda: (
            separate_reality_interpretation_result(
                statements=(
                    {
                        "statement": "email sent Monday",
                        "level": "fact",
                        "evidence_references": ("m1",),
                    },
                )
            )
        ),
        "concerns.explore_hypotheses": lambda: explore_hypotheses_result(
            hypotheses=(
                {
                    "identity": "h1",
                    "statement": "workload explains it",
                    "supporting_ids": ("s1",),
                },
            )
        ),
        "concerns.calibrate_uncertainty": lambda: calibrate_uncertainty_result(
            records=(
                {"identity": "c1", "claim": "email sent", "basis_references": ("m1",)},
            )
        ),
        "concerns.evaluate_reassurance": lambda: evaluate_reassurance_result(
            target_claim="friend is rejecting me",
            evidence=(
                {
                    "identity": "e1",
                    "claim": "busy week",
                    "stance": "opposes_target",
                    "grounding": "msg:1",
                },
                {
                    "identity": "e2",
                    "claim": "warm reply",
                    "stance": "opposes_target",
                    "grounding": "msg:2",
                },
            ),
        ),
        "concerns.evaluate_risk": lambda: evaluate_risk_result(
            severity=None, evidence=()
        ),
        "concerns.identify_open_questions": lambda: identify_open_questions_result(
            questions=(
                {"question": "did others get replies?", "changes": ("interpretation",)},
            )
        ),
        "concerns.explore_options": lambda: explore_options_result(
            options=({"option_id": "o1", "expected_benefit": "clarity"},)
        ),
        "concerns.prepare_next_step": lambda: prepare_next_step_result(
            options=("write down observations",),
            user_request="one reasonable next step",
            grounded_options=True,
        ),
        "concerns.review_recurring_concern": lambda: review_recurring_concern_result(
            current={"topic": "t", "question": "q", "evidence_references": ["m1"]},
            previous=({"topic": "t", "question": "q", "evidence_references": ["m1"]},),
        ),
        "concerns.prepare_professional_discussion": lambda: (
            prepare_professional_discussion_result(
                concern_summary="salary review silence",
            )
        ),
    }


@pytest.mark.parametrize("operation_id", CANONICAL_CONCERNS_OPERATION_IDS)
def test_operation_helper_output_satisfies_declared_output_schema(operation_id):
    """Reusable schema-parity gate: every canonical operation helper's REAL
    output validates against its declared DomainOperationDefinition output
    schema (B-002)."""
    definitions = {op.operation_id: op for op in build_concerns_operation_definitions()}
    definition = definitions[operation_id]
    helpers = _representative_helper_inputs()
    output = helpers[operation_id]()
    issues = validate_operation_schema(output, definition.output_schema)
    assert issues == (), (
        f"{operation_id} helper output violates its declared output schema: "
        + "; ".join(f"{issue.path}: {issue.code}" for issue in issues)
    )


def test_evaluate_reassurance_helper_output_satisfies_declared_operation_schema():
    """The specific audited defect: the flat canonical reassurance helper
    output must satisfy concerns.evaluate_reassurance's declared schema."""
    definitions = {op.operation_id: op for op in build_concerns_operation_definitions()}
    op = definitions["concerns.evaluate_reassurance"]
    output = evaluate_reassurance_result(
        target_claim="worst reading",
        evidence=(
            {
                "identity": "e1",
                "claim": "benign sign",
                "stance": "opposes_target",
                "grounding": "s1",
            },
        ),
        uncertainty=({"identity": "u1", "unknown": "intent"},),
    )
    issues = validate_operation_schema(output, op.output_schema)
    assert issues == (), "; ".join(f"{i.path}:{i.code}" for i in issues)
