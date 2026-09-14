"""Phase 10.48 – quality metrics in ``DomainDefinition`` and the Domain Pack path."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from cmm.domains.benchmark_contracts import DomainBenchmarkCase, DomainBenchmarkSuite
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainPackKind
from cmm.domains.errors import DomainContractValidationError, DomainError
from cmm.domains.identifiers import DomainId
from cmm.domains.manifest import DomainManifest
from cmm.domains.model_policy_contracts import DomainModelPolicy
from cmm.domains.pack import DomainPack, ParsedDomainPack
from cmm.domains.quality_contracts import DomainQualityMetric


def _quality_metric(
    domain_slug: str = "university", **overrides: Any
) -> DomainQualityMetric:
    name = overrides.pop("name", "factual-fidelity")
    data: dict[str, Any] = {
        "id": f"quality-metric:{domain_slug}:{name}",
        "domain_id": DomainId(slug=domain_slug),
        "schema_version": "1",
        "version": "1",
        "name": name,
        "weight": Decimal(1),
        "evaluator_id": f"evaluator:{name}",
        "minimum_score": Decimal("0.80"),
        "blocking": True,
    }
    data.update(overrides)
    return DomainQualityMetric(**data)


def _definition(**overrides: object) -> DomainDefinition:
    data: dict[str, object] = {
        "id": "domain:university",
        "name": "university",
        "display_name": "University",
        "version": "1.0.0",
        "kind": DomainKind.PERSONAL,
        "description": "university domain",
        "manifest_id": "manifest:university:1.0.0",
    }
    data.update(overrides)
    return DomainDefinition(**data)  # type: ignore[arg-type]


def _case(case_id: str, domain_slug: str) -> DomainBenchmarkCase:
    return DomainBenchmarkCase(
        id=case_id,
        domain_id=DomainId(slug=domain_slug),
        objective="Representative objective",
    )


def _suite(suite_id: str, domain_slug: str) -> DomainBenchmarkSuite:
    return DomainBenchmarkSuite(
        id=suite_id,
        domain_id=DomainId(slug=domain_slug),
        schema_version="1",
        version="1",
        cases=(_case(f"benchmark-case:{domain_slug}:core-001", domain_slug),),
    )


def _manifest_for(definition: DomainDefinition) -> DomainManifest:
    return DomainManifest(
        id=definition.manifest_id,
        domain_id=definition.id,
        schema_version="1",
        package_version=definition.version,
        pack_kind=DomainPackKind.INTERNAL,
    )


# ── DomainDefinition integration ──────────────────────────────────────────────


def test_domain_definition_defaults_quality_metrics_to_empty() -> None:
    assert _definition().quality_metrics == ()


def test_domain_definition_serializes_quality_metrics() -> None:
    metric = _quality_metric()
    definition = _definition(quality_metrics=(metric,))

    payload = definition.to_dict()

    assert payload["quality_metrics"] == [metric.to_dict()]
    assert DomainDefinition.from_dict(payload) == definition


def test_domain_definition_deserializes_missing_quality_metrics_to_empty() -> None:
    payload = _definition().to_dict()
    assert "quality_metrics" in payload
    del payload["quality_metrics"]

    assert DomainDefinition.from_dict(payload).quality_metrics == ()


def test_domain_definition_rejects_quality_metric_wrong_domain() -> None:
    with pytest.raises(DomainContractValidationError):
        _definition(quality_metrics=(_quality_metric("relationships"),))


def test_domain_definition_rejects_duplicate_quality_metric_ids() -> None:
    metric = _quality_metric()
    with pytest.raises(DomainContractValidationError):
        _definition(quality_metrics=(metric, metric))


@pytest.mark.parametrize("item", (None, 42, "quality-metric:university:core", object()))
def test_domain_definition_rejects_non_quality_metric_items(item: object) -> None:
    with pytest.raises(DomainContractValidationError):
        _definition(quality_metrics=(item,))


def test_domain_definition_coerces_quality_metric_mappings() -> None:
    payload = _definition().to_dict()
    payload["quality_metrics"] = [_quality_metric().to_dict()]

    definition = DomainDefinition.from_dict(payload)

    assert definition.quality_metrics == (_quality_metric(),)


def test_domain_definition_from_dict_rejects_non_list_quality_metrics() -> None:
    payload = _definition().to_dict()
    payload["quality_metrics"] = "quality-metric:university:core"

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_domain_definition_from_dict_rejects_malformed_quality_metric_mapping() -> None:
    payload = _definition().to_dict()
    metric_payload = _quality_metric().to_dict()
    metric_payload["weight"] = "not-a-decimal"
    payload["quality_metrics"] = [metric_payload]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


# ── Phase 10.46 / 10.47 coexistence ───────────────────────────────────────────


def test_definition_round_trips_model_policy_benchmarks_and_quality_together() -> None:
    definition = _definition(
        model_policy=DomainModelPolicy(
            domain_id="domain:university",
            require_tool_calling=True,
            minimum_context_window=16_384,
        ),
        benchmark_suites=(_suite("benchmark-suite:university:core", "university"),),
        quality_metrics=(_quality_metric(),),
    )

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert restored.model_policy == definition.model_policy
    assert restored.benchmark_suites == definition.benchmark_suites
    assert restored.quality_metrics == definition.quality_metrics
    assert restored.to_dict() == payload


# ── Declarative Domain Pack path (Task 4) ─────────────────────────────────────


def _declarative_payload() -> dict[str, Any]:
    return {
        "id": "university",
        "version": "1.0.0",
        "name": "university",
        "display_name": "University",
        "description": "university domain",
        "author": "tester",
        "license": "MIT",
        "quality_metrics": [_quality_metric().to_dict()],
    }


def test_declarative_pack_preserves_quality_metrics() -> None:
    parsed = ParsedDomainPack.from_declarative_dict(_declarative_payload())

    assert parsed.definition.quality_metrics == (_quality_metric(),)


def test_declarative_pack_without_quality_metrics_stays_backward_compatible() -> None:
    payload = _declarative_payload()
    del payload["quality_metrics"]

    parsed = ParsedDomainPack.from_declarative_dict(payload)

    assert parsed.definition.quality_metrics == ()


@pytest.mark.parametrize(
    "container",
    (
        "quality-metric:university:factual-fidelity",
        {"id": "quality-metric:university:factual-fidelity"},
        42,
    ),
)
def test_declarative_pack_rejects_invalid_quality_metrics_container(
    container: object,
) -> None:
    payload = _declarative_payload()
    payload["quality_metrics"] = container

    with pytest.raises(DomainError) as excinfo:
        ParsedDomainPack.from_declarative_dict(payload)

    assert excinfo.value.field == "quality_metrics"


def test_declarative_pack_rejects_non_mapping_quality_metric_item() -> None:
    payload = _declarative_payload()
    payload["quality_metrics"] = ["not-a-mapping"]

    with pytest.raises(DomainError) as excinfo:
        ParsedDomainPack.from_declarative_dict(payload)

    assert excinfo.value.field == "quality_metrics[0]"


def test_declarative_pack_rejects_quality_metric_domain_mismatch() -> None:
    payload = _declarative_payload()
    payload["quality_metrics"] = [_quality_metric("relationships").to_dict()]

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_rejects_duplicate_quality_metric_ids() -> None:
    payload = _declarative_payload()
    payload["quality_metrics"] = [
        _quality_metric().to_dict(),
        _quality_metric().to_dict(),
    ]

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_rejects_unknown_quality_metric_field() -> None:
    payload = _declarative_payload()
    payload["quality_metrics"][0]["candidate_models"] = ["x"]

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_rejects_reserved_quality_metadata_authority_key() -> None:
    payload = _declarative_payload()
    payload["quality_metrics"][0]["metadata"] = {"preferred_providers": ["x"]}

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_preserves_benchmarks_and_quality_together() -> None:
    payload = _declarative_payload()
    payload["benchmark_suites"] = [
        _suite("benchmark-suite:university:core", "university").to_dict()
    ]

    parsed = ParsedDomainPack.from_declarative_dict(payload)

    assert len(parsed.definition.benchmark_suites) == 1
    assert parsed.definition.quality_metrics == (_quality_metric(),)


# ── Canonical pack round-trip preservation ────────────────────────────────────


def test_parsed_pack_round_trip_preserves_quality_metrics() -> None:
    definition = _definition(quality_metrics=(_quality_metric(),))
    parsed = ParsedDomainPack(definition=definition, manifest=_manifest_for(definition))

    restored = ParsedDomainPack.from_dict(parsed.to_dict())

    assert restored.definition.quality_metrics == definition.quality_metrics
    assert restored.to_dict() == parsed.to_dict()


def test_domain_pack_round_trip_preserves_quality_metrics() -> None:
    definition = _definition(
        benchmark_suites=(_suite("benchmark-suite:university:core", "university"),),
        quality_metrics=(_quality_metric(),),
    )
    pack = DomainPack(
        definition=definition,
        manifest=_manifest_for(definition),
        root_path="/opt/university",
    )

    restored = DomainPack.from_dict(pack.to_dict())

    assert restored.definition.quality_metrics == definition.quality_metrics
    assert restored.definition.benchmark_suites == definition.benchmark_suites
    assert restored.to_dict() == pack.to_dict()
