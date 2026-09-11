"""Phase 10.51 — Domain Intelligence core conformance inventory.

Test-owned evidence that the historical 28-block Implementation Order is fully
mapped to singular canonical production owners. This module never imports the
conformance support into production code; the support file is test-only.

Executable source of the owner matrix:
``tests/domains/domain_core_conformance_support.py``.
"""

from __future__ import annotations

import dataclasses
import importlib

from cmm.domains.contracts import DomainDefinition
from tests.domains.domain_core_conformance_support import (
    CORE_CONFORMANCE_REQUIREMENTS,
    DEFERRED_DOMAIN_IDS,
    FIRST_PARTY_DOMAIN_IDS,
    LATE_ADDITIVE_DEFINITION_FIELDS,
    CoreConformanceClassification,
    first_party_definition_builders,
    load_first_party_definitions,
    required_blocks,
)

# The historical Phase 10.51 Implementation Order block names, in order.
HISTORICAL_BLOCK_NAMES: tuple[str, ...] = (
    "Domain Contracts",
    "Domain Manifest",
    "Domain Registry",
    "Discovery and Loader",
    "Domain Validation",
    "Domain Resolution",
    "Domain Composition",
    "Cross-Domain Coordination",
    "Domain Resources",
    "Domain Profiles",
    "Domain Rules",
    "Domain Operations",
    "Domain Workflows",
    "Domain Permissions",
    "Domain Presentation",
    "Domain Trace",
    "Memory Integration",
    "General Domain",
    "Health Domain",
    "University Domain",
    "Project Domain",
    "Life Plan Domain",
    "Relationships Domain",
    "Secondary Domains",
    "Domain SDK",
    "API and CLI",
    "Security and Observability",
    "Final Integration",
)


def test_historical_implementation_order_has_exactly_28_blocks() -> None:
    assert tuple(item.block for item in CORE_CONFORMANCE_REQUIREMENTS) == tuple(
        range(1, 29)
    )


def test_block_names_match_the_historical_implementation_order() -> None:
    assert tuple(item.name for item in CORE_CONFORMANCE_REQUIREMENTS) == (
        HISTORICAL_BLOCK_NAMES
    )


def test_pre_10_52_first_party_domain_inventory_is_exact() -> None:
    assert FIRST_PARTY_DOMAIN_IDS == frozenset(
        {
            "domain:general",
            "domain:health",
            "domain:relationships",
            "domain:university",
            "domain:oppositions",
            "domain:reflection",
            "domain:concerns",
            "domain:languages",
            "domain:parenthood",
            "domain:sport",
            "domain:life-plan",
            "domain:project",
        }
    )
    assert len(FIRST_PARTY_DOMAIN_IDS) == 12


def test_only_later_domain_packs_are_deferred() -> None:
    assert DEFERRED_DOMAIN_IDS == frozenset(
        {
            "domain:mental-health",
            "domain:neurodivergence",
        }
    )
    assert len(DEFERRED_DOMAIN_IDS) == 2


def test_deferred_ids_do_not_overlap_first_party_ids() -> None:
    assert FIRST_PARTY_DOMAIN_IDS.isdisjoint(DEFERRED_DOMAIN_IDS)


def test_every_required_block_has_owner_and_executable_evidence() -> None:
    for requirement in CORE_CONFORMANCE_REQUIREMENTS:
        assert requirement.owner_modules
        assert requirement.evidence
        assert requirement.classification is not CoreConformanceClassification.GAP_RED


def test_owner_modules_import_from_production_tree() -> None:
    for requirement in CORE_CONFORMANCE_REQUIREMENTS:
        for module_name in requirement.owner_modules:
            assert module_name.startswith("cmm.")


def test_every_owner_module_is_importable_from_production() -> None:
    """No-green-by-documentation: each mapped owner must really import."""
    for requirement in CORE_CONFORMANCE_REQUIREMENTS:
        for module_name in requirement.owner_modules:
            module = importlib.import_module(module_name)
            assert module.__name__ == module_name


def test_no_block_requires_a_parallel_owner() -> None:
    """PARALLEL_OWNER_REQUIRED=0: nothing is classified as a genuine gap."""
    gaps = [
        requirement
        for requirement in CORE_CONFORMANCE_REQUIREMENTS
        if requirement.classification is CoreConformanceClassification.GAP_RED
    ]
    assert gaps == []


def test_unmapped_required_blocks_is_zero() -> None:
    for block in required_blocks():
        requirement = CORE_CONFORMANCE_REQUIREMENTS[block - 1]
        assert requirement.owner_modules
        assert requirement.evidence


def test_first_party_definition_builders_cover_all_twelve_ids() -> None:
    builders = first_party_definition_builders()
    assert set(builders) == set(FIRST_PARTY_DOMAIN_IDS)
    assert len(builders) == 12


def test_all_pre_10_52_first_party_definitions_are_unique() -> None:
    definitions = load_first_party_definitions()
    assert len(definitions) == 12
    assert {str(item.id) for item in definitions} == set(FIRST_PARTY_DOMAIN_IDS)
    assert len({str(item.id) for item in definitions}) == 12


def test_canonical_definition_exposes_late_additive_fields() -> None:
    """Phases 10.46–10.50 added fields to one contract, never a second one."""
    fields = {f.name: f for f in dataclasses.fields(DomainDefinition)}
    assert set(LATE_ADDITIVE_DEFINITION_FIELDS).issubset(fields)
    for field_name in LATE_ADDITIVE_DEFINITION_FIELDS:
        field = fields[field_name]
        is_additive = (
            field.default is not dataclasses.MISSING
            or field.default_factory is not dataclasses.MISSING
        )
        assert is_additive, field_name


def test_every_first_party_definition_uses_the_same_canonical_contract() -> None:
    definitions = load_first_party_definitions()
    assert len(definitions) == 12
    for definition in definitions:
        assert isinstance(definition, DomainDefinition)


def test_late_policy_and_evidence_fields_coexist_on_every_definition() -> None:
    from cmm.domains.benchmark_contracts import DomainBenchmarkSuite
    from cmm.domains.knowledge_package_contracts import (
        DomainKnowledgePackageSchema,
    )
    from cmm.domains.quality_contracts import DomainQualityMetric

    for definition in load_first_party_definitions():
        slug = str(definition.id)
        assert definition.benchmark_suites, slug
        assert all(
            isinstance(suite, DomainBenchmarkSuite)
            for suite in definition.benchmark_suites
        ), slug
        assert definition.quality_metrics, slug
        assert all(
            isinstance(metric, DomainQualityMetric)
            for metric in definition.quality_metrics
        ), slug
        assert isinstance(
            definition.knowledge_package_schema, DomainKnowledgePackageSchema
        ), slug
        # model_policy is an optional additive field; absence is conformant.
        assert definition.model_policy is None or hasattr(
            definition.model_policy, "to_dict"
        ), slug


def test_general_keeps_its_approved_no_privacy_default_case() -> None:
    from cmm.domains.privacy_policy_contracts import DomainPrivacyPolicy

    definitions = {str(d.id): d for d in load_first_party_definitions()}
    assert definitions["domain:general"].privacy_policy is None

    declaring = [
        definition
        for definition in definitions.values()
        if definition.privacy_policy is not None
    ]
    assert len(declaring) == 11
    for definition in declaring:
        assert isinstance(definition.privacy_policy, DomainPrivacyPolicy)
        assert definition.privacy_policy.domain_id == definition.id


def test_first_party_definitions_register_through_the_canonical_registry() -> None:
    from cmm.domains.registry import DomainRegistry

    for definition in load_first_party_definitions():
        registry = DomainRegistry()
        registered = registry.register(definition)
        domain_id = str(definition.id)
        assert registry.contains(domain_id), domain_id
        assert str(registered.id) == domain_id
        assert registry.get_required(domain_id).id == definition.id


def test_no_deferred_domain_id_is_present_among_first_party_definitions() -> None:
    loaded_ids = {str(definition.id) for definition in load_first_party_definitions()}
    assert loaded_ids.isdisjoint(DEFERRED_DOMAIN_IDS)
    assert "domain:mental-health" not in loaded_ids
    assert "domain:neurodivergence" not in loaded_ids
