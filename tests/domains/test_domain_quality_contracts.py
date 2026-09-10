"""Phase 10.48 – Domain quality policy/evidence contract tests."""

from __future__ import annotations

from decimal import Context, Decimal, localcontext

import pytest

from cmm.domains.errors import DomainContractValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import (
    DomainQualityHumanReviewResult,
    DomainQualityMetric,
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
