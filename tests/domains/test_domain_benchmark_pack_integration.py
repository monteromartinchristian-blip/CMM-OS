"""Phase 10.47 – Domain Pack preservation and fail-closed benchmark integration."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from cmm.domains.benchmark_contracts import DomainBenchmarkCase, DomainBenchmarkSuite
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainPackKind
from cmm.domains.errors import DomainError
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.manifest import (
    DomainComponentReference,
    DomainManifest,
    DomainPermissionReference,
)
from cmm.domains.pack import DomainPack, ParsedDomainPack


def _component(component_id: str) -> DomainComponentReference:
    return DomainComponentReference(id=component_id, path=f"{component_id}.py")


def build_manifest_for_definition(definition: DomainDefinition) -> DomainManifest:
    """Build a coherent canonical manifest for a real DomainDefinition."""
    return DomainManifest(
        id=definition.manifest_id,
        domain_id=definition.id,
        schema_version="1",
        package_version=definition.version,
        pack_kind=DomainPackKind.INTERNAL,
        resources=tuple(_component(c) for c in definition.resources),
        rules=tuple(_component(c) for c in definition.rules),
        operations=tuple(_component(c) for c in definition.operations),
        workflows=tuple(_component(c) for c in definition.workflows),
        validators=tuple(_component(c) for c in definition.validators),
        permissions=(
            DomainPermissionReference(required_permissions=definition.permissions)
            if definition.permissions
            else None
        ),
        dependencies=definition.dependencies,
        conflicts=definition.conflicts,
    )


def _case(
    case_id: str, domain_slug: str, objective: str = "Representative objective"
) -> DomainBenchmarkCase:
    return DomainBenchmarkCase(
        id=case_id,
        domain_id=DomainId(slug=domain_slug),
        objective=objective,
    )


def _suite(
    suite_id: str,
    domain_slug: str,
    cases: tuple[DomainBenchmarkCase, ...] | None = None,
) -> DomainBenchmarkSuite:
    return DomainBenchmarkSuite(
        id=suite_id,
        domain_id=DomainId(slug=domain_slug),
        schema_version="1",
        version="1",
        cases=cases or (_case(f"benchmark-case:{domain_slug}:core-001", domain_slug),),
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


def _parsed(definition: DomainDefinition) -> ParsedDomainPack:
    return ParsedDomainPack(
        definition=definition, manifest=build_manifest_for_definition(definition)
    )


# ── Round-trip preservation ───────────────────────────────────────────────────


def test_parsed_pack_round_trip_preserves_benchmark_suites() -> None:
    definition = _definition(
        benchmark_suites=(_suite("benchmark-suite:university:core", "university"),)
    )
    parsed = _parsed(definition)

    restored = ParsedDomainPack.from_dict(parsed.to_dict())

    assert restored.definition.benchmark_suites == definition.benchmark_suites
    assert restored.to_dict() == parsed.to_dict()


def test_domain_pack_round_trip_preserves_benchmark_suites() -> None:
    definition = _definition(
        benchmark_suites=(_suite("benchmark-suite:university:core", "university"),)
    )
    pack = DomainPack(
        definition=definition,
        manifest=build_manifest_for_definition(definition),
        root_path="/opt/university",
    )

    restored = DomainPack.from_dict(pack.to_dict())

    assert restored.definition.benchmark_suites == definition.benchmark_suites
    assert restored.to_dict() == pack.to_dict()


# ── Fail-closed serialized pack validation ────────────────────────────────────


def _definition_payload() -> dict[str, Any]:
    definition = _definition(
        benchmark_suites=(_suite("benchmark-suite:university:core", "university"),)
    )
    return definition.to_dict()


def test_pack_rejects_suite_domain_mismatch() -> None:
    payload = _definition_payload()
    payload["benchmark_suites"] = [
        _suite("benchmark-suite:other:core", "other").to_dict()
    ]

    with pytest.raises(DomainError):
        ParsedDomainPack.from_dict(
            {
                "definition": payload,
                "manifest": build_manifest_for_definition(_definition()).to_dict(),
            }
        )


def test_pack_rejects_case_domain_mismatch() -> None:
    payload = _definition_payload()
    suite_payload = copy.deepcopy(payload["benchmark_suites"][0])
    suite_payload["cases"] = [_case("benchmark-case:other:core-001", "other").to_dict()]
    payload["benchmark_suites"] = [suite_payload]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_pack_rejects_duplicate_suite_ids() -> None:
    payload = _definition_payload()
    payload["benchmark_suites"] = [
        payload["benchmark_suites"][0],
        payload["benchmark_suites"][0],
    ]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_pack_rejects_duplicate_case_ids() -> None:
    payload = _definition_payload()
    suite_payload = copy.deepcopy(payload["benchmark_suites"][0])
    suite_payload["cases"] = [suite_payload["cases"][0], suite_payload["cases"][0]]
    payload["benchmark_suites"] = [suite_payload]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_pack_rejects_unknown_benchmark_field() -> None:
    payload = _definition_payload()
    payload["benchmark_suites"][0]["candidate_models"] = ["x"]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_pack_rejects_reserved_model_provider_metadata() -> None:
    payload = _definition_payload()
    payload["benchmark_suites"][0]["metadata"] = {"preferred_providers": ["x"]}

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_pack_rejects_invalid_maximum_cost() -> None:
    payload = _definition_payload()
    payload["benchmark_suites"][0]["cases"][0]["maximum_cost_eur"] = "-1"

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_pack_rejects_invalid_benchmark_payload_instead_of_dropping_it() -> None:
    payload = _definition_payload()
    payload["benchmark_suites"][0]["cases"] = []

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_parsed_pack_rejects_definition_mapping_with_invalid_benchmark_suite() -> None:
    payload = _definition_payload()
    payload["benchmark_suites"][0]["cases"][0]["id"] = "benchmark-case:university:"

    with pytest.raises(DomainError):
        ParsedDomainPack(
            definition=payload,
            manifest=build_manifest_for_definition(_definition()),
        )


def test_manifest_domain_mismatch_still_fails_with_benchmark_suites() -> None:
    definition = _definition(
        benchmark_suites=(_suite("benchmark-suite:university:core", "university"),)
    )

    with pytest.raises(DomainError):
        manifest = DomainManifest(
            id=DomainManifestId(slug="university", version="1.0.0"),
            domain_id=DomainId(slug="college"),
            schema_version="1",
            package_version="1.0.0",
            pack_kind=DomainPackKind.INTERNAL,
        )
        ParsedDomainPack(definition=definition, manifest=manifest)
