"""Phase 10.51 — Domain Intelligence core conformance inventory.

Test-owned evidence that the historical 28-block Implementation Order is fully
mapped to singular canonical production owners. This module never imports the
conformance support into production code; the support file is test-only.

Executable source of the owner matrix:
``tests/domains/domain_core_conformance_support.py``.
"""

from __future__ import annotations

import importlib

from tests.domains.domain_core_conformance_support import (
    CORE_CONFORMANCE_REQUIREMENTS,
    DEFERRED_DOMAIN_IDS,
    FIRST_PARTY_DOMAIN_IDS,
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
