"""Phase 10.47 — AT-DP-047 Connected Domain Benchmark Asset Acceptance.

Scenarios A–J use the real canonical Domain infrastructure: the twelve
first-party definition builders, ``DomainDefinition``, the official
``ParsedDomainPack`` path, benchmark export/import and the Phase 10.46
``DomainModelPolicy``.
"""

from __future__ import annotations

import copy
import importlib
import json
from dataclasses import fields, replace
from decimal import Decimal
from pathlib import Path

import pytest

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
    export_domain_benchmark_suite,
    import_domain_benchmark_suite,
)
from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainLoadStatus, DomainPackKind
from cmm.domains.errors import DomainError
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.loader import DeclarativeDomainLoader
from cmm.domains.manifest import (
    DomainComponentReference,
    DomainManifest,
    DomainPermissionReference,
)
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.model_policy_contracts import DomainModelPolicy
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.pack import ParsedDomainPack
from cmm.domains.parenthood.definition import build_parenthood_domain_definition
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.reflection.definition import build_reflection_domain_definition
from cmm.domains.registry import DomainRegistry
from cmm.domains.relationships.definition import build_relationships_domain_definition
from cmm.domains.sport.definition import build_sport_domain_definition
from cmm.domains.university.definition import build_university_domain_definition

from ._loader_helpers import make_candidate

FIRST_PARTY_BUILDERS = (
    build_general_domain_definition,
    build_health_domain_definition,
    build_relationships_domain_definition,
    build_university_domain_definition,
    build_oppositions_domain_definition,
    build_reflection_domain_definition,
    build_concerns_domain_definition,
    build_languages_domain_definition,
    build_parenthood_domain_definition,
    build_sport_domain_definition,
    build_life_plan_domain_definition,
    build_project_domain_definition,
)

_FORBIDDEN_RUNTIME_IMPORTS = ("ModelRouter", "OutcomeEvaluationEngine")


def _component(component_id: str) -> DomainComponentReference:
    return DomainComponentReference(id=component_id, path=f"{component_id}.py")


def _manifest_for(definition: DomainDefinition) -> DomainManifest:
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
            DomainPermissionReference(
                policy="permissions.py",
                required_permissions=definition.permissions,
            )
            if definition.permissions
            else None
        ),
        dependencies=definition.dependencies,
        conflicts=definition.conflicts,
    )


def _parsed(definition: DomainDefinition) -> ParsedDomainPack:
    return ParsedDomainPack(definition=definition, manifest=_manifest_for(definition))


def _all_cases(definition: DomainDefinition) -> list[DomainBenchmarkCase]:
    return [case for suite in definition.benchmark_suites for case in suite.cases]


# ── Scenario A — canonical first-party coverage ───────────────────────────────


def test_scenario_a_every_first_party_definition_has_suite_and_case() -> None:
    assert len(FIRST_PARTY_BUILDERS) == 12

    for builder in FIRST_PARTY_BUILDERS:
        definition = builder()
        assert definition.benchmark_suites, f"{definition.id} has no benchmark suite"
        for suite in definition.benchmark_suites:
            assert suite.domain_id == definition.id
            assert len(suite.cases) >= 1
            for case in suite.cases:
                assert case.domain_id == definition.id


# ── Scenario B — Domain Pack connected round-trip ─────────────────────────────


def test_scenario_b_declarative_loader_preserves_real_benchmark_suites(
    tmp_path: Path,
) -> None:
    source = build_health_domain_definition()
    payload = {
        "id": source.id.slug,
        "version": source.version,
        "name": source.name,
        "display_name": source.display_name,
        "description": source.description,
        "author": "tester",
        "license": "MIT",
        "benchmark_suites": [suite.to_dict() for suite in source.benchmark_suites],
    }
    domain_dir = tmp_path / source.id.slug
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    candidate = make_candidate(domain_dir, source.id.slug, source.version)
    loader = DeclarativeDomainLoader(
        manifest_reader=JsonDomainManifestReader(),
        registry=DomainRegistry(),
    )

    result = loader.load(candidate)

    assert result.status == DomainLoadStatus.LOADED
    assert result.pack is not None
    loaded_suites = result.pack.definition.benchmark_suites
    assert loaded_suites == source.benchmark_suites
    assert loaded_suites
    assert all(suite.cases for suite in loaded_suites)


def test_scenario_b_supplemental_python_pack_round_trip_preserves_benchmarks() -> None:
    definition = build_health_domain_definition()
    parsed = _parsed(definition)

    restored = ParsedDomainPack.from_dict(parsed.to_dict())

    assert restored.definition.benchmark_suites == definition.benchmark_suites
    assert restored.definition.benchmark_suites


# ── Scenario C — deterministic export ─────────────────────────────────────────


def test_scenario_c_deterministic_export_and_round_trip() -> None:
    suite = build_health_domain_definition().benchmark_suites[0]

    first = export_domain_benchmark_suite(suite)
    second = export_domain_benchmark_suite(suite)
    restored = import_domain_benchmark_suite(first)

    assert first == second
    assert import_domain_benchmark_suite(second).content_digest == suite.content_digest
    assert restored == suite
    assert restored.content_digest == suite.content_digest


def test_scenario_c_semantically_equal_costs_export_and_digest_identically() -> None:
    suite = build_health_domain_definition().benchmark_suites[0]
    suites = []
    for cost in (Decimal("0.25"), Decimal("0.250"), Decimal("2.5E-1")):
        payload = suite.to_dict()
        payload["cases"][0]["maximum_cost_eur"] = str(cost)
        suites.append(DomainBenchmarkSuite.from_dict(payload))

    assert all(equal_suite == suites[0] for equal_suite in suites)
    assert len({export_domain_benchmark_suite(s) for s in suites}) == 1
    assert len({s.content_digest for s in suites}) == 1


# ── Scenario D — semantic mutation changes identity ───────────────────────────


def test_scenario_d_semantic_mutation_changes_digest() -> None:
    suite = build_health_domain_definition().benchmark_suites[0]
    payload = suite.to_dict()
    payload["cases"][0]["expected_elements"] = ["a materially different element"]

    mutated = DomainBenchmarkSuite.from_dict(payload)

    assert mutated.content_digest != suite.content_digest


# ── Scenario E — fail-closed ownership ────────────────────────────────────────


def _minimal_definition(slug: str, **overrides: object) -> DomainDefinition:
    data: dict[str, object] = {
        "id": f"domain:{slug}",
        "name": slug,
        "display_name": slug.title(),
        "version": "1.0.0",
        "kind": DomainKind.PERSONAL,
        "description": f"{slug} domain",
        "manifest_id": f"manifest:{slug}:1.0.0",
    }
    data.update(overrides)
    return DomainDefinition(**data)  # type: ignore[arg-type]


def _suite_for(slug: str, suite_id: str | None = None) -> DomainBenchmarkSuite:
    return DomainBenchmarkSuite(
        id=suite_id or f"benchmark-suite:{slug}:core",
        domain_id=DomainId(slug=slug),
        schema_version="1",
        version="1",
        cases=(
            DomainBenchmarkCase(
                id=f"benchmark-case:{slug}:core-001",
                domain_id=DomainId(slug=slug),
                objective="Representative objective",
            ),
        ),
    )


def test_scenario_e_suite_definition_domain_mismatch_fails_closed() -> None:
    with pytest.raises(DomainError):
        _minimal_definition("other", benchmark_suites=(_suite_for("university"),))


def test_scenario_e_case_suite_domain_mismatch_fails_closed() -> None:
    payload = _minimal_definition(
        "university", benchmark_suites=(_suite_for("university"),)
    ).to_dict()
    payload["benchmark_suites"][0]["cases"] = [
        DomainBenchmarkCase(
            id="benchmark-case:other:core-001",
            domain_id=DomainId(slug="other"),
            objective="Objective",
        ).to_dict()
    ]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


def test_scenario_e_duplicate_suite_ids_fail_closed() -> None:
    suite = _suite_for("university")
    with pytest.raises(DomainError):
        _minimal_definition("university", benchmark_suites=(suite, suite))


def test_scenario_e_duplicate_case_ids_fail_closed() -> None:
    payload = _minimal_definition(
        "university", benchmark_suites=(_suite_for("university"),)
    ).to_dict()
    case = payload["benchmark_suites"][0]["cases"][0]
    payload["benchmark_suites"][0]["cases"] = [case, copy.deepcopy(case)]

    with pytest.raises(DomainError):
        DomainDefinition.from_dict(payload)


# ── Scenario F — model/provider agnosticism ───────────────────────────────────


def test_scenario_f_contracts_expose_no_model_or_provider_authority() -> None:
    case_fields = {f.name for f in fields(DomainBenchmarkCase)}
    suite_fields = {f.name for f in fields(DomainBenchmarkSuite)}

    for forbidden in (
        "candidate_models",
        "preferred_models",
        "prohibited_models",
        "model_id",
        "candidate_providers",
        "preferred_providers",
        "prohibited_providers",
        "provider_id",
        "routing_weight",
    ):
        assert forbidden not in case_fields
        assert forbidden not in suite_fields

    with pytest.raises(DomainError):
        DomainBenchmarkCase(
            id="benchmark-case:health:authority-001",
            domain_id="domain:health",
            objective="Objective",
            metadata={"candidate_models": ["x"]},
        )


def test_scenario_f_required_schema_allows_model_and_provider_properties() -> None:
    case = DomainBenchmarkCase(
        id="benchmark-case:health:output-schema-001",
        domain_id="domain:health",
        objective="Objective",
        required_schema={
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "model": {"type": "string"},
            },
        },
    )

    assert case.required_schema is not None


@pytest.mark.parametrize(
    "metadata",
    (
        {"preferred_model": "x"},
        {"candidate_model": "x"},
        {"preferred_provider": "x"},
        {"candidate_provider": "x"},
        {"preferredModel": "x"},
        {"candidateProvider": "x"},
        {"preferred-model": "x"},
        {"routingWeight": 1},
        {"policy": {"preferredModel": "x"}},
    ),
)
def test_scenario_f_metadata_authority_aliases_fail_closed(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(DomainError):
        DomainBenchmarkCase(
            id="benchmark-case:health:authority-alias-001",
            domain_id="domain:health",
            objective="Objective",
            metadata=metadata,
        )


def test_scenario_f_ordinary_prose_metadata_is_accepted() -> None:
    case = DomainBenchmarkCase(
        id="benchmark-case:health:prose-001",
        domain_id="domain:health",
        objective="Objective",
        metadata={
            "description": (
                "Checks whether the response names a healthcare provider "
                "and explains the model output."
            )
        },
    )

    assert case.metadata["description"].startswith("Checks whether")


# ── Scenario G — Phase 10.48 boundary ─────────────────────────────────────────


def test_scenario_g_no_weighted_quality_metric_fields() -> None:
    contract_fields = {f.name for f in fields(DomainBenchmarkCase)} | {
        f.name for f in fields(DomainBenchmarkSuite)
    }

    for forbidden in ("weight", "minimum_score", "blocking", "aggregate_score"):
        assert forbidden not in contract_fields


# ── Scenario H — no execution ─────────────────────────────────────────────────


def test_scenario_h_benchmark_modules_do_not_reference_execution_runtime() -> None:
    module_names = ["cmm.domains.benchmark_contracts"] + [
        f"cmm.domains.{builder().id.slug.replace('-', '_')}.benchmarks"
        for builder in FIRST_PARTY_BUILDERS
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        source = getattr(module, "__file__", None)
        assert source is not None
        text = Path(source).read_text(encoding="utf-8")
        for token in _FORBIDDEN_RUNTIME_IMPORTS:
            assert token not in text
        for value in vars(module).values():
            qualified = (
                f"{getattr(value, '__module__', '')}.{getattr(value, '__name__', '')}"
            )
            for token in _FORBIDDEN_RUNTIME_IMPORTS:
                assert token not in qualified


def test_scenario_h_construction_pack_and_export_execute_no_runtime() -> None:
    definition = build_health_domain_definition()
    parsed = _parsed(definition)
    restored = ParsedDomainPack.from_dict(parsed.to_dict())
    suite = restored.definition.benchmark_suites[0]

    payload = export_domain_benchmark_suite(suite)
    reimported = import_domain_benchmark_suite(payload)

    assert reimported == suite


# ── Scenario I — privacy/cost preservation ────────────────────────────────────


def test_scenario_i_privacy_and_cost_survive_pack_and_export() -> None:
    definition = build_health_domain_definition()
    case = next(
        case
        for case in _all_cases(definition)
        if case.privacy_requirement == "SENSITIVE"
    )
    assert case.sensitivity
    assert case.maximum_cost_eur == Decimal("0.25")

    restored = ParsedDomainPack.from_dict(_parsed(definition).to_dict())
    suite = next(
        suite
        for suite in restored.definition.benchmark_suites
        if any(c.id == case.id for c in suite.cases)
    )
    round_tripped = import_domain_benchmark_suite(export_domain_benchmark_suite(suite))
    restored_case = next(c for c in round_tripped.cases if c.id == case.id)

    assert restored_case.sensitivity == case.sensitivity
    assert restored_case.privacy_requirement == case.privacy_requirement
    assert restored_case.maximum_cost_eur == case.maximum_cost_eur

    case_fields = {f.name for f in fields(DomainBenchmarkCase)}
    for authorization_field in (
        "authorized",
        "allow_egress",
        "provider_allowed",
        "remote_allowed",
        "budget_reserved",
    ):
        assert authorization_field not in case_fields


# ── Scenario J — Phase 10.46 coexistence ──────────────────────────────────────


def test_scenario_j_model_policy_and_benchmark_suites_coexist() -> None:
    definition = replace(
        build_health_domain_definition(),
        model_policy=DomainModelPolicy(
            domain_id="domain:health",
            require_reasoning=True,
            require_structured_output=True,
        ),
    )

    payload = definition.to_dict()
    restored = DomainDefinition.from_dict(payload)

    assert restored.model_policy == definition.model_policy
    assert restored.benchmark_suites == definition.benchmark_suites
    assert restored.to_dict() == payload
