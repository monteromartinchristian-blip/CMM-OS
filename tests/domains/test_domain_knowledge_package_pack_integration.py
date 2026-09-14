"""Phase 10.49 – knowledge package schemas in ``DomainDefinition`` and the Pack path."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.domains.benchmark_contracts import DomainBenchmarkCase, DomainBenchmarkSuite
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainPackKind
from cmm.domains.errors import DomainContractValidationError, DomainError
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
)
from cmm.domains.manifest import DomainManifest
from cmm.domains.model_policy_contracts import DomainModelPolicy
from cmm.domains.pack import DomainPack, ParsedDomainPack
from cmm.domains.quality_contracts import DomainQualityMetric


def _schema(
    domain_slug: str = "university", **overrides: Any
) -> DomainKnowledgePackageSchema:
    data: dict[str, Any] = {
        "id": f"knowledge-package-schema:{domain_slug}",
        "domain_id": DomainId(domain_slug),
        "version": "1",
        "required_sections": ("objective", "facts"),
        "prohibited_sections": ("hypotheses",),
        "field_policies": (
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                required_non_empty=True,
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
            ),
        ),
        "minimum_sensitivity": SensitivityLevel.INTERNAL,
    }
    data.update(overrides)
    return DomainKnowledgePackageSchema(**data)


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


def _manifest_for(definition: DomainDefinition) -> DomainManifest:
    return DomainManifest(
        id=definition.manifest_id,
        domain_id=definition.id,
        schema_version="1",
        package_version=definition.version,
        pack_kind=DomainPackKind.INTERNAL,
    )


# ── DomainDefinition integration ──────────────────────────────────────────────


def test_domain_definition_defaults_knowledge_package_schema_to_none() -> None:
    assert _definition().knowledge_package_schema is None


def test_domain_definition_serializes_knowledge_package_schema() -> None:
    schema = _schema()
    definition = _definition(knowledge_package_schema=schema)

    payload = definition.to_dict()

    assert payload["knowledge_package_schema"] == schema.to_dict()
    assert DomainDefinition.from_dict(payload) == definition


def test_domain_definition_absent_schema_stays_none_on_round_trip() -> None:
    payload = _definition().to_dict()
    assert payload["knowledge_package_schema"] is None
    del payload["knowledge_package_schema"]

    restored = DomainDefinition.from_dict(payload)

    assert restored.knowledge_package_schema is None


def test_domain_definition_rejects_schema_ownership_mismatch() -> None:
    with pytest.raises(DomainContractValidationError):
        _definition(
            id="domain:health",
            knowledge_package_schema=_schema("university"),
        )


def test_domain_definition_coerces_schema_mappings() -> None:
    payload = _definition().to_dict()
    payload["knowledge_package_schema"] = _schema().to_dict()

    definition = DomainDefinition.from_dict(payload)

    assert definition.knowledge_package_schema == _schema()


def test_domain_definition_from_dict_rejects_malformed_schema() -> None:
    payload = _definition().to_dict()
    malformed = _schema().to_dict()
    malformed["minimum_sensitivity"] = "nonsense"
    payload["knowledge_package_schema"] = malformed

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_domain_definition_from_dict_rejects_schema_domain_mismatch() -> None:
    payload = _definition().to_dict()
    payload["knowledge_package_schema"] = _schema("relationships").to_dict()

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


@pytest.mark.parametrize("item", (42, "knowledge-package-schema:university", [1]))
def test_domain_definition_rejects_non_schema_values(item: object) -> None:
    with pytest.raises(DomainContractValidationError):
        _definition(knowledge_package_schema=item)


# ── Coexistence with 10.46 / 10.47 / 10.48 ────────────────────────────────────


def test_definition_round_trips_policy_benchmarks_quality_and_schema_together() -> None:
    definition = _definition(
        model_policy=DomainModelPolicy(
            domain_id="domain:university",
            require_tool_calling=True,
            minimum_context_window=16_384,
        ),
        benchmark_suites=(_suite("benchmark-suite:university:core", "university"),),
        quality_metrics=(_quality_metric(),),
        knowledge_package_schema=_schema(),
    )

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert restored.model_policy == definition.model_policy
    assert restored.benchmark_suites == definition.benchmark_suites
    assert restored.quality_metrics == definition.quality_metrics
    assert restored.knowledge_package_schema == definition.knowledge_package_schema
    assert restored.to_dict() == payload


# ── Declarative Domain Pack path ──────────────────────────────────────────────


def _declarative_payload() -> dict[str, Any]:
    return {
        "id": "university",
        "version": "1.0.0",
        "name": "university",
        "display_name": "University",
        "description": "university domain",
        "author": "tester",
        "license": "MIT",
        "knowledge_package_schema": _schema().to_dict(),
    }


def test_declarative_pack_preserves_knowledge_package_schema() -> None:
    parsed = ParsedDomainPack.from_declarative_dict(_declarative_payload())

    assert parsed.definition.knowledge_package_schema == _schema()


def test_declarative_pack_without_schema_stays_backward_compatible() -> None:
    payload = _declarative_payload()
    del payload["knowledge_package_schema"]

    parsed = ParsedDomainPack.from_declarative_dict(payload)

    assert parsed.definition.knowledge_package_schema is None


@pytest.mark.parametrize("container", ("not-a-mapping", 42, ["not-a-mapping"]))
def test_declarative_pack_rejects_invalid_schema_container(container: object) -> None:
    payload = _declarative_payload()
    payload["knowledge_package_schema"] = container

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_rejects_schema_domain_mismatch() -> None:
    payload = _declarative_payload()
    payload["knowledge_package_schema"] = _schema("relationships").to_dict()

    with pytest.raises(DomainError):
        ParsedDomainPack.from_declarative_dict(payload)


def test_declarative_pack_preserves_benchmarks_quality_and_schema_together() -> None:
    payload = _declarative_payload()
    payload["benchmark_suites"] = [
        _suite("benchmark-suite:university:core", "university").to_dict()
    ]
    payload["quality_metrics"] = [_quality_metric().to_dict()]

    parsed = ParsedDomainPack.from_declarative_dict(payload)

    assert len(parsed.definition.benchmark_suites) == 1
    assert parsed.definition.quality_metrics == (_quality_metric(),)
    assert parsed.definition.knowledge_package_schema == _schema()


# ── Canonical pack round-trip preservation ────────────────────────────────────


def test_parsed_pack_round_trip_preserves_knowledge_package_schema() -> None:
    definition = _definition(knowledge_package_schema=_schema())
    parsed = ParsedDomainPack(definition=definition, manifest=_manifest_for(definition))

    restored = ParsedDomainPack.from_dict(parsed.to_dict())

    assert restored.definition.knowledge_package_schema == _schema()
    assert restored.to_dict() == parsed.to_dict()


def test_domain_pack_round_trip_preserves_knowledge_package_schema() -> None:
    definition = _definition(
        quality_metrics=(_quality_metric(),),
        knowledge_package_schema=_schema(),
    )
    pack = DomainPack(
        definition=definition,
        manifest=_manifest_for(definition),
        root_path="/opt/university",
    )

    restored = DomainPack.from_dict(pack.to_dict())

    assert restored.definition.knowledge_package_schema == _schema()
    assert restored.to_dict() == pack.to_dict()
