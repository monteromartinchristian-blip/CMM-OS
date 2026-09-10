"""Phase 10.48 – Domain quality policy/evidence contract tests."""

from __future__ import annotations

from dataclasses import replace
from decimal import Context, Decimal, localcontext

import pytest

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import (
    DomainQualityAssessment,
    DomainQualityHumanReviewResult,
    DomainQualityMetric,
    DomainQualityMetricResult,
    assess_domain_quality,
    build_domain_quality_metric_result,
    export_domain_quality_assessment,
    import_domain_quality_assessment,
)


def _metric(**overrides):
    data = {
        "id": "quality-metric:health:prudence",
        "domain_id": DomainId(slug="health"),
        "schema_version": "1",
        "version": "1",
        "name": "prudence",
        "weight": Decimal("0.25"),
        "evaluator_id": "evaluator:prudence",
        "minimum_score": Decimal("0.90"),
        "blocking": True,
        "metadata": {"source": {"kind": "domain-policy"}},
    }
    data.update(overrides)
    return DomainQualityMetric(**data)


def test_metric_is_immutable_and_domain_owned():
    metric = _metric()
    assert metric.domain_id.slug == "health"
    assert metric.id == "quality-metric:health:prudence"
    assert metric.weight == Decimal("0.25")
    with pytest.raises(TypeError):
        metric.metadata["x"] = "y"


@pytest.mark.parametrize(
    "field,value",
    [
        ("weight", 1),
        ("weight", 0.25),
        ("weight", True),
        ("weight", "0.25"),
        ("minimum_score", 1),
        ("minimum_score", 0.9),
        ("minimum_score", True),
        ("minimum_score", "0.90"),
    ],
)
def test_metric_rejects_non_decimal_constructor_values(field, value):
    with pytest.raises(DomainContractValidationError):
        _metric(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("weight", Decimal(0)),
        ("weight", Decimal("-0.1")),
        ("weight", Decimal("1.01")),
        ("weight", Decimal("NaN")),
        ("weight", Decimal("Infinity")),
        ("minimum_score", Decimal("-0.01")),
        ("minimum_score", Decimal("1.01")),
        ("minimum_score", Decimal("NaN")),
    ],
)
def test_metric_rejects_invalid_decimal_ranges(field, value):
    with pytest.raises(DomainContractValidationError):
        _metric(**{field: value})


def test_metric_id_must_embed_domain_slug():
    with pytest.raises(DomainContractValidationError):
        _metric(id="quality-metric:relationships:prudence")


def test_metric_id_must_use_canonical_prefix():
    with pytest.raises(DomainContractValidationError):
        _metric(id="benchmark-suite:health:prudence")


def test_metric_rejects_empty_required_strings():
    for field in ("schema_version", "version", "name", "evaluator_id"):
        with pytest.raises(DomainContractValidationError):
            _metric(**{field: "   "})


def test_metric_blocking_is_strict_bool():
    with pytest.raises(DomainContractValidationError):
        _metric(blocking=1)


def test_metric_domain_id_must_be_domain_id_or_canonical_string():
    assert _metric(domain_id="domain:health").domain_id == DomainId(slug="health")
    with pytest.raises(DomainContractValidationError):
        _metric(domain_id="health")


def test_metric_unknown_fields_rejected_on_deserialization():
    payload = _metric().to_dict()
    payload["unexpected"] = 1
    from cmm.domains.errors import DomainSerializationError
    from cmm.domains.quality_contracts import DomainQualityMetric as Metric

    with pytest.raises(DomainSerializationError):
        Metric.from_dict(payload)


def test_human_review_is_typed_and_immutable():
    result = DomainQualityHumanReviewResult(
        id="quality-review:health:prudence:001",
        schema_version="1",
        status="accepted",
        score=Decimal("0.90"),
        confidence=Decimal("0.95"),
        reviewer_ref="reviewer:human",
        notes=("Prudence preserved.",),
        metadata={"source": "manual"},
    )
    assert result.score == Decimal("0.90")
    assert result.notes == ("Prudence preserved.",)
    with pytest.raises(TypeError):
        result.metadata["x"] = "y"


def test_human_review_optional_fields_and_round_trip():
    result = DomainQualityHumanReviewResult(
        id="quality-review:health:prudence:002",
        schema_version="1",
        status="pending",
    )
    assert result.score is None
    assert result.confidence is None
    assert result.reviewer_ref is None
    assert result.notes == ()
    restored = DomainQualityHumanReviewResult.from_dict(result.to_dict())
    assert restored == result


@pytest.mark.parametrize(
    "field,value",
    [
        ("score", 1),
        ("score", 0.9),
        ("score", True),
        ("score", "0.9"),
        ("confidence", 1),
        ("confidence", 0.5),
        ("confidence", True),
        ("confidence", "0.5"),
    ],
)
def test_human_review_rejects_non_decimal_values(field, value):
    with pytest.raises(DomainContractValidationError):
        DomainQualityHumanReviewResult(
            id="quality-review:health:prudence:003",
            schema_version="1",
            status="accepted",
            **{field: value},
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("score", Decimal("-0.01")),
        ("score", Decimal("1.01")),
        ("score", Decimal("NaN")),
        ("confidence", Decimal("-0.01")),
        ("confidence", Decimal("Infinity")),
    ],
)
def test_human_review_rejects_invalid_ranges(field, value):
    with pytest.raises(DomainContractValidationError):
        DomainQualityHumanReviewResult(
            id="quality-review:health:prudence:004",
            schema_version="1",
            status="accepted",
            **{field: value},
        )


def test_metric_decimal_round_trip_is_context_independent():
    metric = _metric(
        weight=Decimal("0.123456789012345678901234567890"),
        minimum_score=Decimal("0.987654321098765432109876543210"),
    )
    payloads = []
    for precision in (10, 28, 50):
        with localcontext(Context(prec=precision)):
            payloads.append(metric.to_dict())
    assert payloads[0] == payloads[1] == payloads[2]
    assert DomainQualityMetric.from_dict(payloads[0]) == metric


def test_metric_decimal_round_trip_preserves_high_precision_exactly():
    weight = Decimal("0.123456789012345678901234567890")
    metric = _metric(weight=weight, minimum_score=Decimal(0))
    payload = metric.to_dict()
    # Canonical text strips insignificant trailing zeros without losing value.
    assert payload["weight"] == "0.12345678901234567890123456789"
    assert DomainQualityMetric.from_dict(payload).weight == weight


@pytest.mark.parametrize(
    "key",
    [
        "model",
        "modelId",
        "candidateModels",
        "preferred-provider",
        "provider_ids",
        "routingWeights",
    ],
)
def test_metric_metadata_rejects_model_provider_routing_authority(key):
    with pytest.raises(DomainContractValidationError):
        _metric(metadata={"nested": {key: "forbidden"}})


def test_metric_metadata_allows_descriptive_prose_values():
    metric = _metric(
        metadata={"description": "compare model behavior without selecting a provider"}
    )
    assert metric.metadata["description"].startswith("compare model")


def test_metric_metadata_allows_contract_owned_concepts():
    metric = _metric(
        metadata={
            "weight": "descriptive",
            "minimum_score": 0.9,
            "blocking": True,
            "evaluator_id": "evaluator:x",
            "score": 1,
            "confidence": 0.5,
        }
    )
    assert metric.metadata["evaluator_id"] == "evaluator:x"


def test_metric_metadata_must_be_json_safe():
    with pytest.raises(DomainContractValidationError):
        _metric(metadata={"bad": object()})


# ── Task 2 – metric results, assessment, export/import ────────────────────────


def _build(metric, score, confidence="0.90", evaluator_version="1", **kwargs):
    return build_domain_quality_metric_result(
        metric,
        score=Decimal(score) if isinstance(score, str) else score,
        evaluator_version=evaluator_version,
        confidence=Decimal(confidence) if isinstance(confidence, str) else confidence,
        **kwargs,
    )


def _usefulness_metric(**overrides):
    data = {
        "id": "quality-metric:health:usefulness",
        "name": "usefulness",
        "evaluator_id": "evaluator:usefulness",
        "weight": Decimal("0.25"),
        "minimum_score": Decimal("0.80"),
        "blocking": False,
    }
    data.update(overrides)
    return _metric(**data)


def test_build_metric_result_snapshots_declared_policy():
    metric = _metric()
    result = build_domain_quality_metric_result(
        metric,
        score=Decimal("0.91"),
        evaluator_version="3",
        confidence=Decimal("0.94"),
        human_review_results=(),
    )
    assert isinstance(result, DomainQualityMetricResult)
    assert result.metric_id == metric.id
    assert result.domain_id == metric.domain_id
    assert result.metric_version == metric.version
    assert result.metric_name == metric.name
    assert result.weight == metric.weight
    assert result.minimum_score == metric.minimum_score
    assert result.blocking is True
    assert result.evaluator_id == metric.evaluator_id
    assert result.evaluator_version == "3"
    assert result.threshold_passed is True
    assert result.blocking_failure is False


def test_build_metric_result_flags_below_threshold_blocking_failure():
    result = _build(_metric(), "0.89")
    assert result.threshold_passed is False
    assert result.blocking_failure is True


@pytest.mark.parametrize("value", [1, 0.9, True, "0.9"])
def test_metric_result_builder_rejects_non_decimal_score(value):
    with pytest.raises(DomainContractValidationError):
        build_domain_quality_metric_result(
            _metric(),
            score=value,
            evaluator_version="1",
            confidence=Decimal("0.9"),
        )


@pytest.mark.parametrize("value", [1, 0.9, True, "0.9"])
def test_metric_result_builder_rejects_non_decimal_confidence(value):
    with pytest.raises(DomainContractValidationError):
        build_domain_quality_metric_result(
            _metric(),
            score=Decimal("0.9"),
            evaluator_version="1",
            confidence=value,
        )


def test_metric_result_rejects_malformed_id_and_empty_versions():
    valid = _build(_metric(), "0.9")
    with pytest.raises(DomainContractValidationError):
        replace(valid, metric_id="benchmark-case:health:prudence")
    with pytest.raises(DomainContractValidationError):
        replace(valid, evaluator_version="  ")


def test_assessment_uses_normalized_weighted_mean():
    a = _metric(
        id="quality-metric:health:factual-fidelity",
        name="factual-fidelity",
        evaluator_id="evaluator:factual-fidelity",
        weight=Decimal("0.75"),
        minimum_score=Decimal("0.80"),
        blocking=False,
    )
    b = _metric(
        id="quality-metric:health:prudence",
        name="prudence",
        evaluator_id="evaluator:prudence",
        weight=Decimal("0.25"),
        minimum_score=Decimal("0.80"),
        blocking=True,
    )
    ra = _build(a, "1.00", confidence="0.90")
    rb = _build(b, "0.79", confidence="1.00")

    assessment = assess_domain_quality((a, b), (ra, rb))

    assert assessment.aggregate_score == Decimal("0.9475")
    assert assessment.confidence == Decimal("0.925")
    assert assessment.blocking_failures == (b.id,)
    assert assessment.passed is False
    assert [r.metric_id for r in assessment.metric_results] == [a.id, b.id]


def test_high_aggregate_cannot_compensate_blocking_failure():
    blocking = _metric(weight=Decimal("0.01"), minimum_score=Decimal("0.90"))
    other = _usefulness_metric(weight=Decimal("0.99"), minimum_score=Decimal(0))
    results = (
        _build(blocking, "0.89", confidence=Decimal(1)),
        _build(other, Decimal(1), confidence=Decimal(1)),
    )
    assessment = assess_domain_quality((blocking, other), results)
    assert assessment.aggregate_score == Decimal("0.9989")
    assert assessment.blocking_failures == (blocking.id,)
    assert assessment.passed is False


def test_assessment_weight_normalization_does_not_require_unit_sum():
    a = _metric(weight=Decimal("0.5"), minimum_score=Decimal("0.5"))
    b = _usefulness_metric(weight=Decimal("0.5"), minimum_score=Decimal("0.5"))
    assessment = assess_domain_quality((a, b), (_build(a, "1.0"), _build(b, "0.5")))
    assert assessment.aggregate_score == Decimal("0.75")
    assert assessment.passed is True


_MUTATIONS = {
    "version": ("metric_version", "9"),
    "name": ("metric_name", "other"),
    "weight": ("weight", Decimal("0.5")),
    "threshold": ("minimum_score", Decimal("0.1")),
    "blocking": ("blocking", False),
    "evaluator": ("evaluator_id", "evaluator:other"),
}


@pytest.mark.parametrize("mutation", sorted(_MUTATIONS))
def test_assessment_rejects_policy_mismatch(mutation):
    metric = _metric()
    result = _build(metric, "0.95")
    field, value = _MUTATIONS[mutation]
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality((metric,), (replace(result, **{field: value}),))


def test_assessment_rejects_result_with_wrong_domain():
    result = _build(_metric(), "0.95")
    with pytest.raises(DomainContractValidationError):
        replace(result, domain_id=DomainId(slug="relationships"))


def test_assessment_rejects_missing_result():
    a, b = _metric(), _usefulness_metric()
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality((a, b), (_build(a, "0.95"),))


def test_assessment_rejects_unexpected_result():
    a = _metric()
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality(
            (a,), (_build(a, "0.95"), _build(_usefulness_metric(), "0.9"))
        )


def test_assessment_rejects_duplicate_metric_ids():
    a = _metric()
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality((a, a), (_build(a, "0.95"),))


def test_assessment_rejects_duplicate_result_ids():
    a = _metric()
    result = _build(a, "0.95")
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality((a,), (result, result))


def test_assessment_rejects_empty_metrics():
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality((), ())


def test_assessment_rejects_mixed_domains():
    a = _metric()
    other = _metric(
        id="quality-metric:relationships:usefulness",
        domain_id=DomainId(slug="relationships"),
        name="usefulness",
        evaluator_id="evaluator:usefulness",
    )
    with pytest.raises(DomainContractValidationError):
        assess_domain_quality((a, other), (_build(a, "0.95"), _build(other, "0.95")))


def test_assessment_rejects_caller_controlled_derived_state():
    a = _metric()
    assessment = assess_domain_quality((a,), (_build(a, "0.95"),))

    with pytest.raises(DomainContractValidationError):
        DomainQualityAssessment(
            domain_id=assessment.domain_id,
            schema_version=assessment.schema_version,
            metric_results=assessment.metric_results,
            aggregate_score=assessment.aggregate_score + Decimal("0.01"),
            confidence=assessment.confidence,
            blocking_failures=assessment.blocking_failures,
            passed=assessment.passed,
        )
    with pytest.raises(DomainContractValidationError):
        DomainQualityAssessment(
            domain_id=assessment.domain_id,
            schema_version=assessment.schema_version,
            metric_results=assessment.metric_results,
            aggregate_score=assessment.aggregate_score,
            confidence=assessment.confidence,
            blocking_failures=assessment.blocking_failures,
            passed=not assessment.passed,
        )
    with pytest.raises(DomainContractValidationError):
        DomainQualityAssessment(
            domain_id=assessment.domain_id,
            schema_version=assessment.schema_version,
            metric_results=assessment.metric_results,
            aggregate_score=assessment.aggregate_score,
            confidence=assessment.confidence,
            blocking_failures=(a.id,),
            passed=assessment.passed,
        )


def test_assessment_is_decimal_context_independent():
    a = _metric(weight=Decimal("0.123456789012345678901234567890"))
    b = _usefulness_metric(weight=Decimal("0.876543210987654321098765432110"))
    results = (
        _build(
            a,
            "0.8123456789012345678901234567891",
            confidence="0.7123456789012345678901234567891",
        ),
        _build(
            b,
            "0.5123456789012345678901234567891",
            confidence="0.6123456789012345678901234567891",
        ),
    )
    assessments = []
    payloads = []
    for precision in (10, 28, 50):
        with localcontext(Context(prec=precision)):
            assessment = assess_domain_quality((a, b), results)
            assessments.append(assessment)
            payloads.append(export_domain_quality_assessment(assessment))
    assert assessments[0] == assessments[1] == assessments[2]
    assert payloads[0] == payloads[1] == payloads[2]


def test_assessment_export_is_deterministic_and_round_trips():
    a = _metric()
    review = DomainQualityHumanReviewResult(
        id="quality-review:health:prudence:001",
        schema_version="1",
        status="accepted",
        score=Decimal("0.97"),
        confidence=Decimal("0.99"),
        reviewer_ref="reviewer:human",
        notes=("Prudence preserved.",),
    )
    assessment = assess_domain_quality(
        (a,), (_build(a, "0.95", human_review_results=(review,)),)
    )
    payload = export_domain_quality_assessment(assessment)
    assert isinstance(payload, bytes)
    assert export_domain_quality_assessment(assessment) == payload
    assert import_domain_quality_assessment(payload) == assessment


def test_import_rejects_non_bytes_payload():
    with pytest.raises(DomainSerializationError):
        import_domain_quality_assessment("not-bytes")  # type: ignore[arg-type]


def test_import_rejects_invalid_utf8():
    with pytest.raises(DomainSerializationError):
        import_domain_quality_assessment(b"\xff\xfe\xfd")


def test_import_rejects_invalid_json():
    with pytest.raises(DomainSerializationError):
        import_domain_quality_assessment(b"{not json")


def test_import_rejects_non_object_payload():
    with pytest.raises(DomainSerializationError):
        import_domain_quality_assessment(b"[1, 2, 3]")


def test_import_rejects_unknown_fields():
    a = _metric()
    import json

    payload = json.loads(
        export_domain_quality_assessment(
            assess_domain_quality((a,), (_build(a, "0.95"),))
        )
    )
    payload["unexpected"] = 1
    with pytest.raises(DomainSerializationError):
        import_domain_quality_assessment(json.dumps(payload).encode("utf-8"))


def test_import_preserves_high_precision_values_exactly():
    weight = Decimal("0.123456789012345678901234567890")
    score = Decimal("0.987654321098765432109876543210")
    a = _metric(weight=weight)
    b = _usefulness_metric(weight=Decimal(1) - weight)
    assessment = assess_domain_quality((a, b), (_build(a, score), _build(b, "0.5")))
    restored = import_domain_quality_assessment(
        export_domain_quality_assessment(assessment)
    )
    assert restored == assessment
    assert restored.aggregate_score == assessment.aggregate_score
