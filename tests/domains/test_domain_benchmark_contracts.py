"""Phase 10.47 – ``DomainBenchmarkCase`` / ``DomainBenchmarkSuite`` contract tests."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
    export_domain_benchmark_suite,
    import_domain_benchmark_suite,
)
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.errors import DomainError
from cmm.domains.identifiers import DomainId
from cmm.domains.model_policy_contracts import DomainModelPolicy

_CASE_ID = "benchmark-case:health:clinical-timeline-001"
_SUITE_ID = "benchmark-suite:health:core"


def _health_case(**overrides: object) -> DomainBenchmarkCase:
    values: dict[str, object] = {
        "id": _CASE_ID,
        "domain_id": DomainId(slug="health"),
        "objective": "Build a reliable clinical timeline",
        "input_resource_refs": ("health.resource.medical_report",),
        "expected_elements": ("chronology is explicit",),
        "required_constraints": ("preserve source uncertainty",),
        "prohibited_behaviors": ("invent diagnosis",),
        "evaluation_criteria": ("temporal correctness",),
        "required_format": "structured",
        "sensitivity": "highly_sensitive",
        "privacy_requirement": "SENSITIVE",
        "maximum_cost_eur": Decimal("0.25"),
        "evaluator_ids": ("evaluator:required-elements",),
        "human_review_required": True,
        "human_review_guidance": ("Review uncertainty handling",),
        "metadata": {"fixture_kind": "synthetic"},
    }
    values.update(overrides)
    return DomainBenchmarkCase(**values)  # type: ignore[arg-type]


def _health_suite(**overrides: object) -> DomainBenchmarkSuite:
    values: dict[str, object] = {
        "id": _SUITE_ID,
        "domain_id": DomainId(slug="health"),
        "schema_version": "1",
        "version": "1",
        "cases": (_health_case(),),
        "metadata": {"scope": "core"},
    }
    values.update(overrides)
    return DomainBenchmarkSuite(**values)  # type: ignore[arg-type]


# ── Construction and immutability ─────────────────────────────────────────────


def test_benchmark_case_and_suite_are_constructible_and_immutable() -> None:
    case = _health_case()
    suite = _health_suite()

    assert suite.cases == (case,)
    assert case.maximum_cost_eur == Decimal("0.25")
    assert case.domain_id == DomainId(slug="health")
    assert suite.content_digest == _health_suite().content_digest


def test_contracts_are_frozen() -> None:
    case = _health_case()
    suite = _health_suite()

    with pytest.raises(FrozenInstanceError):
        case.objective = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        suite.version = "2"  # type: ignore[misc]


def test_case_accepts_string_domain_id_and_coerces_collections() -> None:
    case = DomainBenchmarkCase(
        id=_CASE_ID,
        domain_id="domain:health",
        objective="Objective",
        expected_elements=["a", "b"],
        metadata={"k": "v"},
    )

    assert case.domain_id == DomainId(slug="health")
    assert case.expected_elements == ("a", "b")


def test_metadata_is_deeply_immutable() -> None:
    case = _health_case(metadata={"nested": {"inner": ["x"]}})

    with pytest.raises(TypeError):
        case.metadata["nested"]["inner"] = ()  # type: ignore[index]


# ── Identity ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_id",
    (
        "",
        "benchmark-suite-health-core",
        "benchmark-suite:Health:core",
        "benchmark-suite:health:",
        "benchmark-suite::core",
        "benchmark-case:health:clinical-timeline-001",
    ),
)
def test_suite_rejects_malformed_ids(bad_id: str) -> None:
    with pytest.raises(DomainError):
        _health_suite(id=bad_id)


@pytest.mark.parametrize(
    "bad_id",
    (
        "",
        "benchmark-case-health-core",
        "benchmark-case:Health:case",
        "benchmark-case:health:",
        "benchmark-suite:health:core",
    ),
)
def test_case_rejects_malformed_ids(bad_id: str) -> None:
    with pytest.raises(DomainError):
        _health_case(id=bad_id)


def test_case_rejects_domain_id_mismatch() -> None:
    with pytest.raises(DomainError):
        _health_case(domain_id=DomainId(slug="project"))


def test_suite_rejects_domain_id_mismatch() -> None:
    with pytest.raises(DomainError):
        _health_suite(domain_id=DomainId(slug="project"))


def test_suite_rejects_case_domain_mismatch() -> None:
    other_case = DomainBenchmarkCase(
        id="benchmark-case:project:architecture-001",
        domain_id=DomainId(slug="project"),
        objective="Objective",
    )
    with pytest.raises(DomainError):
        _health_suite(cases=(other_case,))


# ── Structural validation ─────────────────────────────────────────────────────


def test_case_rejects_empty_objective() -> None:
    with pytest.raises(DomainError):
        _health_case(objective="   ")


def test_suite_rejects_empty_cases() -> None:
    with pytest.raises(DomainError):
        _health_suite(cases=())


def test_suite_rejects_duplicate_case_ids() -> None:
    with pytest.raises(DomainError):
        _health_suite(cases=(_health_case(), _health_case()))


def test_suite_rejects_empty_version_and_schema_version() -> None:
    with pytest.raises(DomainError):
        _health_suite(version="")
    with pytest.raises(DomainError):
        _health_suite(schema_version="")


@pytest.mark.parametrize(
    "field_name",
    (
        "input_resource_refs",
        "expected_elements",
        "required_constraints",
        "prohibited_behaviors",
        "evaluation_criteria",
        "evaluator_ids",
        "human_review_guidance",
    ),
)
def test_case_rejects_empty_or_duplicate_string_collections(field_name: str) -> None:
    with pytest.raises(DomainError):
        _health_case(**{field_name: ("",)})
    with pytest.raises(DomainError):
        _health_case(**{field_name: ("dup", "dup")})


@pytest.mark.parametrize("value", (1, 0, "true", "false", None))
def test_case_rejects_non_bool_human_review_required(value: object) -> None:
    with pytest.raises(DomainError):
        _health_case(human_review_required=value)


@pytest.mark.parametrize(
    "value",
    (
        True,
        False,
        0,
        1,
        0.25,
        "0.25",
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ),
)
def test_case_rejects_invalid_maximum_cost(value: object) -> None:
    with pytest.raises(DomainError):
        _health_case(maximum_cost_eur=value)


@pytest.mark.parametrize(
    "value",
    (None, Decimal(0), Decimal("0.25"), Decimal(1000)),
)
def test_case_accepts_valid_maximum_cost(value: Decimal | None) -> None:
    assert _health_case(maximum_cost_eur=value).maximum_cost_eur == value


def test_case_rejects_empty_optional_strings() -> None:
    with pytest.raises(DomainError):
        _health_case(knowledge_package_id="")
    with pytest.raises(DomainError):
        _health_case(required_format="")
    with pytest.raises(DomainError):
        _health_case(sensitivity="")
    with pytest.raises(DomainError):
        _health_case(privacy_requirement="")


def test_case_rejects_non_mapping_metadata_and_schema() -> None:
    with pytest.raises(DomainError):
        _health_case(metadata=("not", "a", "mapping"))
    with pytest.raises(DomainError):
        _health_case(required_schema=("not", "a", "mapping"))


def test_case_rejects_non_json_metadata_values() -> None:
    with pytest.raises(DomainError):
        _health_case(metadata={"cost": Decimal("1.5")})
    with pytest.raises(DomainError):
        _health_case(metadata={"nested": {"bad": object()}})


def test_case_accepts_json_metadata_and_schema() -> None:
    case = _health_case(
        metadata={"a": 1, "b": [1, 2, {"c": None}], "d": True},
        required_schema={"type": "object", "properties": {"x": {"type": "string"}}},
    )

    assert case.required_schema is not None
    assert json.loads(json.dumps(case.to_dict())) == case.to_dict()


# ── Model/provider authority prohibition ──────────────────────────────────────


@pytest.mark.parametrize(
    "metadata",
    (
        {"candidate_models": ["x"]},
        {"model_id": "x"},
        {"model": "x"},
        {"models": ["x"]},
        {"preferred_models": ["x"]},
        {"prohibited_models": ["x"]},
        {"modelId": "x"},
        {"ModelID": "x"},
        {"candidateModels": ["x"]},
        {"provider": "x"},
        {"provider_id": "x"},
        {"providerId": "x"},
        {"providers": ["x"]},
        {"candidate_providers": ["x"]},
        {"preferred_providers": ["x"]},
        {"prohibited_providers": ["x"]},
        {"routing_weight": 1},
        {"routing_weights": {"a": 1}},
        {"routingWeight": 1},
        {"model-family": "x"},
        {"nested": {"candidate_models": ["x"]}},
    ),
)
def test_benchmark_metadata_rejects_model_provider_authority(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(DomainError):
        _health_case(metadata=metadata)


def test_suite_metadata_rejects_model_provider_authority() -> None:
    with pytest.raises(DomainError):
        _health_suite(metadata={"candidate_models": ["x"]})


def test_metadata_allows_innocent_prose_values() -> None:
    case = _health_case(
        metadata={"note": "the model of care matters", "model_reviewed": "no"}
    )

    assert case.metadata["note"] == "the model of care matters"


# ── Serialization ─────────────────────────────────────────────────────────────


def test_case_round_trip_is_exact() -> None:
    case = _health_case()

    assert DomainBenchmarkCase.from_dict(case.to_dict()) == case


def test_suite_round_trip_is_exact() -> None:
    suite = _health_suite()

    assert DomainBenchmarkSuite.from_dict(suite.to_dict()) == suite


def test_case_round_trip_without_optional_fields() -> None:
    case = DomainBenchmarkCase(
        id="benchmark-case:project:architecture-consistency-001",
        domain_id=DomainId(slug="project"),
        objective="Keep architecture consistent",
    )

    assert DomainBenchmarkCase.from_dict(case.to_dict()) == case


def test_maximum_cost_serializes_as_canonical_decimal_string() -> None:
    payload = _health_case().to_dict()

    assert payload["maximum_cost_eur"] == "0.25"
    assert _health_case(maximum_cost_eur=None).to_dict()["maximum_cost_eur"] is None


@pytest.mark.parametrize(
    "field_name",
    ("id", "domain_id", "objective"),
)
def test_case_from_dict_rejects_missing_required_fields(field_name: str) -> None:
    payload = _health_case().to_dict()
    payload.pop(field_name)

    with pytest.raises(DomainError):
        DomainBenchmarkCase.from_dict(payload)


@pytest.mark.parametrize(
    "field_name",
    ("id", "domain_id", "schema_version", "version", "cases"),
)
def test_suite_from_dict_rejects_missing_required_fields(field_name: str) -> None:
    payload = _health_suite().to_dict()
    payload.pop(field_name)

    with pytest.raises(DomainError):
        DomainBenchmarkSuite.from_dict(payload)


def test_case_from_dict_rejects_unknown_fields() -> None:
    payload = _health_case().to_dict()
    payload["candidate_models"] = ["x"]

    with pytest.raises(DomainError):
        DomainBenchmarkCase.from_dict(payload)


def test_suite_from_dict_rejects_unknown_fields() -> None:
    payload = _health_suite().to_dict()
    payload["quality_weights"] = {"a": 1}

    with pytest.raises(DomainError):
        DomainBenchmarkSuite.from_dict(payload)


# ── Deterministic export and digest ───────────────────────────────────────────


def test_export_is_byte_deterministic_and_round_trips() -> None:
    suite = _health_suite()
    first = export_domain_benchmark_suite(suite)
    second = export_domain_benchmark_suite(suite)

    assert first == second
    assert import_domain_benchmark_suite(first) == suite
    assert import_domain_benchmark_suite(first).content_digest == suite.content_digest


def test_export_is_canonical_utf8_json_without_incidental_content() -> None:
    suite = _health_suite(metadata={"scope": "core", "note": "áé"})
    payload = export_domain_benchmark_suite(suite)

    assert isinstance(payload, bytes)
    text = payload.decode("utf-8")
    assert "áé" in text
    assert "/Users/" not in text
    assert "content_digest" not in text
    assert json.loads(text) == suite.to_dict()


def test_content_digest_is_sha256_hex_and_stable() -> None:
    suite = _health_suite()

    assert len(suite.content_digest) == 64
    assert int(suite.content_digest, 16) >= 0
    assert suite.content_digest == _health_suite().content_digest
    assert (
        suite.content_digest
        == DomainBenchmarkSuite.from_dict(suite.to_dict()).content_digest
    )


def test_semantic_change_changes_digest() -> None:
    suite = _health_suite()
    payload = suite.to_dict()
    payload["cases"][0]["expected_elements"] = ["different expected element"]
    changed = DomainBenchmarkSuite.from_dict(payload)

    assert changed.content_digest != suite.content_digest


def test_version_change_changes_digest() -> None:
    assert _health_suite(version="2").content_digest != _health_suite().content_digest


def test_import_rejects_non_bytes_payload() -> None:
    with pytest.raises(DomainError):
        import_domain_benchmark_suite("not bytes")  # type: ignore[arg-type]


def test_import_rejects_invalid_json_payload() -> None:
    with pytest.raises(DomainError):
        import_domain_benchmark_suite(b"{not json")


# ── DomainDefinition integration ──────────────────────────────────────────────


def _make_definition(**overrides: object) -> DomainDefinition:
    data: dict[str, object] = {
        "id": "domain:test",
        "name": "test",
        "display_name": "Test",
        "version": "1.0.0",
        "kind": DomainKind.PERSONAL,
        "description": "test domain",
        "manifest_id": "manifest:test:1.0.0",
    }
    data.update(overrides)
    return DomainDefinition(**data)  # type: ignore[arg-type]


def _test_suite(suite_id: str = "benchmark-suite:test:core") -> DomainBenchmarkSuite:
    return DomainBenchmarkSuite(
        id=suite_id,
        domain_id=DomainId(slug="test"),
        schema_version="1",
        version="1",
        cases=(
            DomainBenchmarkCase(
                id="benchmark-case:test:core-001",
                domain_id=DomainId(slug="test"),
                objective="Representative objective",
            ),
        ),
    )


def test_domain_definition_benchmark_suites_default_empty() -> None:
    assert _make_definition().benchmark_suites == ()


def test_benchmark_suites_is_the_last_declared_field() -> None:
    names = [f.name for f in fields(DomainDefinition)]

    assert names[-1] == "benchmark_suites"


def test_old_domain_definition_payload_without_benchmarks_still_loads() -> None:
    payload = _make_definition().to_dict()
    payload.pop("benchmark_suites", None)

    restored = DomainDefinition.from_dict(payload)

    assert restored.benchmark_suites == ()


def test_domain_definition_round_trips_benchmark_suites() -> None:
    definition = _make_definition(benchmark_suites=(_test_suite(),))

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert restored.benchmark_suites == definition.benchmark_suites
    assert restored.to_dict() == payload


def test_domain_definition_coerces_benchmark_suite_mappings() -> None:
    payload = _make_definition().to_dict()
    payload["benchmark_suites"] = [_test_suite().to_dict()]

    definition = DomainDefinition.from_dict(payload)

    assert definition.benchmark_suites == (_test_suite(),)


def test_domain_definition_rejects_suite_for_another_domain() -> None:
    other = DomainBenchmarkSuite(
        id="benchmark-suite:other:core",
        domain_id=DomainId(slug="other"),
        schema_version="1",
        version="1",
        cases=(
            DomainBenchmarkCase(
                id="benchmark-case:other:core-001",
                domain_id=DomainId(slug="other"),
                objective="Objective",
            ),
        ),
    )
    with pytest.raises(DomainError):
        _make_definition(benchmark_suites=(other,))


def test_domain_definition_rejects_duplicate_suite_ids() -> None:
    with pytest.raises(DomainError):
        _make_definition(benchmark_suites=(_test_suite(), _test_suite()))


def test_domain_definition_rejects_invalid_suite_mapping() -> None:
    payload = _make_definition().to_dict()
    payload["benchmark_suites"] = [{"id": "benchmark-suite:test:core"}]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_model_policy_and_benchmark_suites_coexist() -> None:
    definition = _make_definition(
        model_policy=DomainModelPolicy(
            domain_id="domain:test",
            require_structured_output=True,
        ),
        benchmark_suites=(_test_suite(),),
    )

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert restored.model_policy == definition.model_policy
    assert restored.benchmark_suites == definition.benchmark_suites
    assert restored.to_dict() == payload
