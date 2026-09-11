"""Phase 10.47 – ``DomainBenchmarkCase`` / ``DomainBenchmarkSuite`` contract tests."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields
from decimal import Decimal, localcontext

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


def test_required_schema_allows_provider_property_name() -> None:
    case = _health_case(
        required_schema={
            "type": "object",
            "properties": {"provider": {"type": "string"}},
        }
    )

    assert case.required_schema is not None


def test_required_schema_allows_model_property_name() -> None:
    case = _health_case(
        required_schema={
            "type": "object",
            "properties": {"model": {"type": "string"}},
        }
    )

    assert case.required_schema is not None


# ── Model/provider authority prohibition ──────────────────────────────────────


@pytest.mark.parametrize(
    "metadata",
    (
        {"candidate_models": ["x"]},
        {"candidate_model": "x"},
        {"model_id": "x"},
        {"model": "x"},
        {"models": ["x"]},
        {"preferred_model": "x"},
        {"preferred_models": ["x"]},
        {"prohibited_model": "x"},
        {"prohibited_models": ["x"]},
        {"modelId": "x"},
        {"ModelID": "x"},
        {"candidateModels": ["x"]},
        {"preferredModel": "x"},
        {"candidateModel": "x"},
        {"preferred-model": "x"},
        {"PREFERRED_MODEL": "x"},
        {"provider": "x"},
        {"provider_id": "x"},
        {"providerId": "x"},
        {"providers": ["x"]},
        {"candidate_providers": ["x"]},
        {"candidate_provider": "x"},
        {"preferred_provider": "x"},
        {"preferred_providers": ["x"]},
        {"prohibited_provider": "x"},
        {"prohibited_providers": ["x"]},
        {"candidateProvider": "x"},
        {"routing_weight": 1},
        {"routing_weights": {"a": 1}},
        {"routingWeight": 1},
        {"model-family": "x"},
        {"nested": {"candidate_models": ["x"]}},
        {"nested": {"preferredModel": "x"}},
        {"policy": {"candidateProvider": "x"}},
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


def test_suite_metadata_rejects_nested_authority_aliases() -> None:
    with pytest.raises(DomainError):
        _health_suite(metadata={"policy": {"preferredModel": "x"}})


@pytest.mark.parametrize(
    "metadata",
    (
        {"preferred_model_id": "x"},
        {"candidate_model_id": "x"},
        {"prohibited_model_id": "x"},
        {"preferred_model_ids": ["x"]},
        {"candidate_model_ids": ["x"]},
        {"prohibited_model_ids": ["x"]},
        {"preferred_provider_id": "x"},
        {"candidate_provider_id": "x"},
        {"prohibited_provider_id": "x"},
        {"preferred_provider_ids": ["x"]},
        {"candidate_provider_ids": ["x"]},
        {"prohibited_provider_ids": ["x"]},
        {"model_preference": "x"},
        {"provider_preference": "x"},
        {"model_candidate": "x"},
        {"provider_candidates": ["x"]},
        {"routing_model": "x"},
        {"routing_provider": "x"},
        {"routing_model_id": "x"},
        {"routing_provider_ids": ["x"]},
    ),
)
def test_benchmark_metadata_rejects_compound_authority_aliases(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(DomainError):
        _health_case(metadata=metadata)


@pytest.mark.parametrize(
    "metadata",
    (
        {"preferredModelId": "x"},
        {"PreferredModelId": "x"},
        {"preferred-model-id": "x"},
        {"preferred model id": "x"},
        {"candidateProviderId": "x"},
        {"prohibitedProviderIds": ["x"]},
        {"routingProvider": "x"},
        {"routingProviderId": "x"},
        {"ModelPreference": "x"},
    ),
)
def test_benchmark_metadata_rejects_normalized_compound_authority_aliases(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(DomainError):
        _health_case(metadata=metadata)


def test_benchmark_metadata_rejects_nested_compound_authority_aliases() -> None:
    with pytest.raises(DomainError):
        _health_case(metadata={"evaluation": {"preferredModelId": "provider/model-x"}})


@pytest.mark.parametrize(
    "metadata",
    (
        {"modeling_notes": "x"},
        {"provider_context_description": "x"},
        {"model_output_description": "x"},
        {"provider_response_format": "x"},
        {"routing_explanation": "x"},
    ),
)
def test_benchmark_metadata_accepts_descriptive_model_provider_keys(
    metadata: dict[str, object],
) -> None:
    case = _health_case(metadata=metadata)

    assert set(case.metadata) == set(metadata)


def test_metadata_allows_innocent_prose_values() -> None:
    case = _health_case(
        metadata={"note": "the model of care matters", "model_reviewed": "no"}
    )

    assert case.metadata["note"] == "the model of care matters"


def test_metadata_allows_ordinary_prose_mentioning_model_and_provider() -> None:
    case = _health_case(
        metadata={
            "description": (
                "Checks whether the response names a healthcare provider "
                "and explains the model output."
            ),
            "modeling_notes": "provider_context_description",
        }
    )

    assert case.metadata["modeling_notes"] == "provider_context_description"


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


def _cost_suite(value: Decimal) -> DomainBenchmarkSuite:
    return _health_suite(cases=(_health_case(maximum_cost_eur=value),))


@pytest.mark.parametrize(
    "costs",
    (
        (Decimal("0.25"), Decimal("0.250"), Decimal("2.5E-1")),
        (Decimal(1000), Decimal("1E+3"), Decimal("1000.000")),
        (Decimal(0), Decimal("0.0"), Decimal("-0"), Decimal("-0.000")),
    ),
)
def test_semantically_equal_costs_serialize_export_and_digest_identically(
    costs: tuple[Decimal, ...],
) -> None:
    suites = [_cost_suite(cost) for cost in costs]

    assert all(suite == suites[0] for suite in suites)
    serialized = {suite.to_dict()["cases"][0]["maximum_cost_eur"] for suite in suites}
    assert len(serialized) == 1
    assert len({export_domain_benchmark_suite(suite) for suite in suites}) == 1
    assert len({suite.content_digest for suite in suites}) == 1


def test_distinct_costs_remain_distinct_in_export_and_digest() -> None:
    lower = _cost_suite(Decimal("0.25"))
    higher = _cost_suite(Decimal("0.26"))

    assert lower != higher
    assert (
        lower.to_dict()["cases"][0]["maximum_cost_eur"]
        != higher.to_dict()["cases"][0]["maximum_cost_eur"]
    )
    assert export_domain_benchmark_suite(lower) != export_domain_benchmark_suite(higher)
    assert lower.content_digest != higher.content_digest


@pytest.mark.parametrize(
    ("value", "canonical"),
    (
        (Decimal("0.25"), "0.25"),
        (Decimal("0.250"), "0.25"),
        (Decimal(1000), "1000"),
        (Decimal("1E+3"), "1000"),
        (Decimal("-0.000"), "0"),
    ),
)
def test_canonical_cost_round_trip_is_numerically_exact(
    value: Decimal, canonical: str
) -> None:
    suite = _cost_suite(value)
    serialized = suite.to_dict()["cases"][0]["maximum_cost_eur"]

    assert serialized == canonical
    assert Decimal(serialized) == value


_HIGH_PRECISION_COST = Decimal("123456789012345678901234567890.123456789")
_LONG_FRACTION_COST = Decimal("0.123456789012345678901234567890123456789")


@pytest.mark.parametrize(
    "value",
    (_HIGH_PRECISION_COST, _LONG_FRACTION_COST),
)
def test_high_precision_costs_round_trip_exactly(value: Decimal) -> None:
    serialized = _cost_suite(value).to_dict()["cases"][0]["maximum_cost_eur"]

    assert Decimal(serialized) == value


def test_large_positive_exponent_cost_serializes_exact_fixed_point() -> None:
    value = Decimal("1E+30")
    serialized = _cost_suite(value).to_dict()["cases"][0]["maximum_cost_eur"]

    assert serialized == "1000000000000000000000000000000"
    assert Decimal(serialized) == value


def test_decimal_serialization_is_independent_of_ambient_decimal_context() -> None:
    payloads: list[dict[str, object]] = []
    exports: list[bytes] = []
    digests: list[str] = []

    for precision in (10, 28, 50):
        with localcontext() as ctx:
            ctx.prec = precision
            suite = _cost_suite(_HIGH_PRECISION_COST)
            payloads.append(suite.to_dict())
            exports.append(export_domain_benchmark_suite(suite))
            digests.append(suite.content_digest)

    assert payloads[0] == payloads[1] == payloads[2]
    assert exports[0] == exports[1] == exports[2]
    assert digests[0] == digests[1] == digests[2]


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


def test_benchmark_suites_precedes_only_the_phase_10_48_quality_metrics_field() -> None:
    # Phase 10.48 appends `quality_metrics` after `benchmark_suites`; Phase
    # 10.49 appends `knowledge_package_schema` after it; Phase 10.50 appends
    # `privacy_policy` after that.  No other field may be declared in between.
    names = [f.name for f in fields(DomainDefinition)]

    assert names[-4:] == [
        "benchmark_suites",
        "quality_metrics",
        "knowledge_package_schema",
        "privacy_policy",
    ]


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


# ── Public API ────────────────────────────────────────────────────────────────


def test_benchmark_contracts_are_exported_from_public_api() -> None:
    from cmm import domains
    from cmm.domains import (
        DomainBenchmarkCase as PublicCase,
    )
    from cmm.domains import (
        DomainBenchmarkSuite as PublicSuite,
    )
    from cmm.domains import (
        export_domain_benchmark_suite as public_export,
    )
    from cmm.domains import (
        import_domain_benchmark_suite as public_import,
    )

    assert PublicCase is DomainBenchmarkCase
    assert PublicSuite is DomainBenchmarkSuite
    assert public_export is export_domain_benchmark_suite
    assert public_import is import_domain_benchmark_suite
    for symbol in (
        "DomainBenchmarkCase",
        "DomainBenchmarkSuite",
        "export_domain_benchmark_suite",
        "import_domain_benchmark_suite",
    ):
        assert symbol in domains.__all__
    for forbidden in (
        "DomainBenchmarkRegistry",
        "DomainBenchmarkRunner",
        "BenchmarkExecutionEngine",
    ):
        assert forbidden not in domains.__all__
