"""Phase 10.51 — test-only Domain Intelligence core conformance inventory.

This module is **test evidence**, not a production registry. It maps the
historical Phase 10.51 Implementation Order (exactly 28 blocks) onto the
singular canonical production owners created and independently closed by
Phases 10.1–10.50.

Critical rules:

- Production code must never import this module.
- This module must not become a second registry, loader or resolver.
- Owners listed here describe where authority already lives; they do not own
  runtime behaviour.

The design specification forbids green-by-documentation, so every owner module
listed here is imported by the inventory test to prove real reachability.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum
from importlib import import_module

from cmm.domains.contracts import DomainDefinition


class CoreConformanceClassification(str, Enum):
    """How a historical Implementation Order block is satisfied today."""

    CANONICAL_OWNER_VERIFIED = "canonical_owner_verified"
    CANONICAL_ADAPTER_VERIFIED = "canonical_adapter_verified"
    INTENTIONALLY_DEFERRED_TO_10_52_10_53 = (
        "intentionally_deferred_to_10_52_10_53"
    )
    INTENTIONALLY_PHASE11 = "intentionally_phase11"
    NOT_APPLICABLE_SUPERSEDED_BY_CANONICAL_OWNER = (
        "not_applicable_superseded_by_canonical_owner"
    )
    GAP_RED = "gap_red"


@dataclass(frozen=True, slots=True)
class CoreConformanceRequirement:
    """One historical block mapped to its existing canonical owner(s)."""

    block: int
    name: str
    owner_modules: tuple[str, ...]
    classification: CoreConformanceClassification
    evidence: tuple[str, ...]


CORE_CONFORMANCE_REQUIREMENTS: tuple[CoreConformanceRequirement, ...] = (
    CoreConformanceRequirement(
        block=1,
        name="Domain Contracts",
        owner_modules=(
            "cmm.domains.contracts",
            "cmm.domains.enums",
            "cmm.domains.errors",
            "cmm.domains.identifiers",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_contracts.py",
            "tests/domains/test_domain_identifiers.py",
            "tests/domains/test_domain_serialization.py",
            "late additive DomainDefinition fields coexist on one contract",
        ),
    ),
    CoreConformanceRequirement(
        block=2,
        name="Domain Manifest",
        owner_modules=(
            "cmm.domains.manifest",
            "cmm.domains.manifest_reader",
            "cmm.domains.pack",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_manifest.py",
            "tests/domains/test_domain_manifest_reader.py",
            "tests/domains/test_domain_pack.py",
            "single declarative ParsedDomainPack path",
        ),
    ),
    CoreConformanceRequirement(
        block=3,
        name="Domain Registry",
        owner_modules=(
            "cmm.domains.registry",
            "cmm.domains.registry_contracts",
            "cmm.domains.registry_store",
            "cmm.domains.registry_validation",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_registry.py",
            "tests/domains/test_domain_registry_contracts.py",
            "tests/domains/test_domain_registry_store.py",
        ),
    ),
    CoreConformanceRequirement(
        block=4,
        name="Discovery and Loader",
        owner_modules=(
            "cmm.domains.discovery",
            "cmm.domains.discovery_contracts",
            "cmm.domains.loader",
            "cmm.domains.loader_contracts",
            "cmm.domains.lifecycle_bridge",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_discovery.py",
            "tests/domains/test_domain_discovery_contracts.py",
            "tests/domains/test_domain_loader.py",
            "tests/domains/test_domain_loader_contracts.py",
        ),
    ),
    CoreConformanceRequirement(
        block=5,
        name="Domain Validation",
        owner_modules=(
            "cmm.domains.validation",
            "cmm.domains.validation_contracts",
            "cmm.domains.validation_validators",
            "cmm.domains.validation_fragmentation",
            "cmm.domains.validation_security",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_validation_pipeline.py",
            "tests/domains/test_domain_validation_fragmentation.py",
            "tests/domains/test_domain_validation_security.py",
            "Phase 7 remains authoritative for validation execution",
        ),
    ),
    CoreConformanceRequirement(
        block=6,
        name="Domain Resolution",
        owner_modules=(
            "cmm.domains.resolver",
            "cmm.domains.resolver_contracts",
            "cmm.domains.resolver_scoring",
            "cmm.domains.resolution_contracts",
            "cmm.domains.resolution_builder",
            "cmm.domains.selection",
            "cmm.domains.selection_contracts",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_resolver_integration.py",
            "tests/domains/test_domain_resolution_policy.py",
            "tests/domains/test_domain_selection_policy_dp031_acceptance.py",
        ),
    ),
    CoreConformanceRequirement(
        block=7,
        name="Domain Composition",
        owner_modules=(
            "cmm.domains.composer",
            "cmm.domains.composition_contracts",
            "cmm.domains.composition_items",
            "cmm.domains.composition_permissions",
            "cmm.domains.composition_conflicts",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_composer.py",
            "tests/domains/test_domain_composition_permissions.py",
            "tests/domains/test_domain_composition_conflicts.py",
            "most-restrictive composition, never an authority union",
        ),
    ),
    CoreConformanceRequirement(
        block=8,
        name="Cross-Domain Coordination",
        owner_modules=(
            "cmm.domains.cross_domain_engine",
            "cmm.domains.cross_domain_contracts",
            "cmm.domains.cross_domain_context",
            "cmm.domains.cross_domain_limits",
            "cmm.domains.cross_domain_ports",
            "cmm.domains.cross_domain_aggregation",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_cross_domain_engine.py",
            "tests/domains/test_cross_domain_limits.py",
            "tests/domains/test_cross_domain_boundaries.py",
        ),
    ),
    CoreConformanceRequirement(
        block=9,
        name="Domain Resources",
        owner_modules=(
            "cmm.domains.resource_contracts",
            "cmm.domains.resource_registry",
            "cmm.domains.resource_resolver",
            "cmm.domains.resource_authority",
            "cmm.domains.resource_derivation",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_resource_registry.py",
            "tests/domains/test_domain_resource_resolver.py",
            "tests/domains/test_domain_resource_boundaries.py",
        ),
    ),
    CoreConformanceRequirement(
        block=10,
        name="Domain Profiles",
        owner_modules=(
            "cmm.domains.profile_contracts",
            "cmm.domains.profile_registry",
            "cmm.domains.profile_resolver",
            "cmm.domains.profile_composition",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_profile_registry.py",
            "tests/domains/test_domain_profile_composition.py",
            "tests/domains/test_domain_profile_boundaries.py",
        ),
    ),
    CoreConformanceRequirement(
        block=11,
        name="Domain Rules",
        owner_modules=(
            "cmm.domains.rule_contracts",
            "cmm.domains.rule_catalog",
            "cmm.domains.rule_selection",
            "cmm.domains.rule_execution",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_rule_catalog.py",
            "tests/domains/test_domain_rule_selection.py",
            "tests/domains/test_domain_rule_execution.py",
            "Phase 8 remains the Cognitive knowledge/reasoning authority",
        ),
    ),
    CoreConformanceRequirement(
        block=12,
        name="Domain Operations",
        owner_modules=(
            "cmm.domains.operation_contracts",
            "cmm.domains.operation_catalog",
            "cmm.domains.operation_registry",
            "cmm.domains.operation_availability",
            "cmm.domains.operation_schema",
            "cmm.domains.operation_execution",
            "cmm.domains.operation_approval",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_operation_availability.py",
            "tests/domains/test_domain_operation_execution.py",
            "tests/domains/test_domain_operation_approval.py",
            "declared-but-unimplemented operations stay fail-closed",
        ),
    ),
    CoreConformanceRequirement(
        block=13,
        name="Domain Workflows",
        owner_modules=(
            "cmm.domains.workflow_contracts",
            "cmm.domains.workflow_catalog",
            "cmm.domains.workflow_registry",
            "cmm.domains.workflow_resolution",
            "cmm.domains.workflow_execution",
            "cmm.domains.workflow_errors",
        ),
        classification=CoreConformanceClassification.CANONICAL_ADAPTER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_workflows.py",
            "tests/domains/test_domain_workflow_pending.py",
            "tests/domains/test_domain_workflow_result_preservation.py",
            "shared workflow engine remains authoritative (cmm.workflows)",
        ),
    ),
    CoreConformanceRequirement(
        block=14,
        name="Domain Permissions",
        owner_modules=(
            "cmm.domains.permission_contracts",
            "cmm.domains.permission_catalog",
            "cmm.domains.permission_registry",
            "cmm.domains.permission_resolution",
            "cmm.domains.permission_evaluator",
            "cmm.domains.permission_gate",
            "cmm.domains.permission_adapters",
            "cmm.domains.approval_bridge",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_permission_resolution.py",
            "tests/domains/test_domain_permission_evaluator.py",
            "tests/domains/test_domain_permission_gate.py",
            "Phase 10.15 remains the permission authority; permissions only narrow",
        ),
    ),
    CoreConformanceRequirement(
        block=15,
        name="Domain Presentation",
        owner_modules=(
            "cmm.domains.presentation_contracts",
            "cmm.domains.presentation_planner",
            "cmm.domains.presentation_requirements",
            "cmm.domains.presentation_validation",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_presentation_planner.py",
            "tests/domains/test_domain_presentation_validator.py",
            "tests/domains/test_domain_presentation_multidomain.py",
            "Phase 10.16 remains authoritative and is not Phase 11 UI",
        ),
    ),
    CoreConformanceRequirement(
        block=16,
        name="Domain Trace",
        owner_modules=(
            "cmm.domains.trace_contracts",
            "cmm.domains.trace_assembler",
            "cmm.domains.trace_validation",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_trace_assembler.py",
            "tests/domains/test_domain_trace_validation.py",
            "tests/domains/test_domain_trace_privacy.py",
            "reference-only evidence; no alternative trace store",
        ),
    ),
    CoreConformanceRequirement(
        block=17,
        name="Memory Integration",
        owner_modules=(
            "cmm.domains.memory_contracts",
            "cmm.domains.memory_view",
            "cmm.domains.memory_validation",
            "cmm.domains.memory_knowledge_integration",
            "cmm.domains.memory_knowledge_integration_contracts",
            "cmm.domains.knowledge_authority",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_memory_view.py",
            "tests/domains/test_domain_memory_proposals.py",
            "tests/domains/test_domain_memory_knowledge_dp044_acceptance.py",
            "Phases 10.18 and 10.44 remain authoritative; proposal/reference only",
        ),
    ),
    CoreConformanceRequirement(
        block=18,
        name="General Domain",
        owner_modules=(
            "cmm.domains.general.definition",
            "cmm.domains.general.bootstrap",
            "cmm.domains.general.integration",
            "cmm.domains.general.catalog",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_general_domain_definition.py",
            "tests/domains/test_general_domain_bootstrap.py",
            "General keeps its approved no-Domain-wide-privacy-default case",
        ),
    ),
    CoreConformanceRequirement(
        block=19,
        name="Health Domain",
        owner_modules=(
            "cmm.domains.health.definition",
            "cmm.domains.health.bootstrap",
            "cmm.domains.health.integration",
            "cmm.domains.health.catalog",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_health_domain_definition.py",
            "tests/domains/test_health_domain_bootstrap.py",
            "tests/domains/test_health_domain_safety.py",
        ),
    ),
    CoreConformanceRequirement(
        block=20,
        name="University Domain",
        owner_modules=(
            "cmm.domains.university.definition",
            "cmm.domains.university.bootstrap",
            "cmm.domains.university.integration",
            "cmm.domains.university.catalog",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_university_domain_definition.py",
            "tests/domains/test_university_domain_bootstrap.py",
            "tests/domains/test_university_domain_safety.py",
        ),
    ),
    CoreConformanceRequirement(
        block=21,
        name="Project Domain",
        owner_modules=(
            "cmm.domains.project.definition",
            "cmm.domains.project.bootstrap",
            "cmm.domains.project.integration",
            "cmm.domains.project.catalog",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_project_domain_e2e.py",
            "tests/domains/test_project_domain_dp030_acceptance.py",
            "tests/domains/test_project_domain_closure_adversarial.py",
        ),
    ),
    CoreConformanceRequirement(
        block=22,
        name="Life Plan Domain",
        owner_modules=(
            "cmm.domains.life_plan.definition",
            "cmm.domains.life_plan.bootstrap",
            "cmm.domains.life_plan.integration",
            "cmm.domains.life_plan.catalog",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_life_plan_domain_definition.py",
            "tests/domains/test_life_plan_domain_bootstrap.py",
            "tests/domains/test_life_plan_domain_dp029_acceptance.py",
        ),
    ),
    CoreConformanceRequirement(
        block=23,
        name="Relationships Domain",
        owner_modules=(
            "cmm.domains.relationships.definition",
            "cmm.domains.relationships.bootstrap",
            "cmm.domains.relationships.integration",
            "cmm.domains.relationships.catalog",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_relationships_domain_definition.py",
            "tests/domains/test_relationships_domain_bootstrap.py",
            "tests/domains/test_relationships_domain_safety.py",
        ),
    ),
    CoreConformanceRequirement(
        block=24,
        name="Secondary Domains",
        owner_modules=(
            "cmm.domains.oppositions.definition",
            "cmm.domains.reflection.definition",
            "cmm.domains.concerns.definition",
            "cmm.domains.languages.definition",
            "cmm.domains.parenthood.definition",
            "cmm.domains.sport.definition",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_oppositions_domain_definition.py",
            "tests/domains/test_reflection_domain_definition.py",
            "tests/domains/test_concerns_domain_definition.py",
            "tests/domains/test_languages_domain_definition.py",
            "tests/domains/test_parenthood_domain_definition.py",
            "tests/domains/test_sport_domain_definition.py",
            "domain:parenthood supersedes historical Paternidad/Nil wording",
        ),
    ),
    CoreConformanceRequirement(
        block=25,
        name="Domain SDK",
        owner_modules=(
            "cmm.domains.sdk",
            "cmm.domains.sdk.builders",
            "cmm.domains.sdk.scaffold",
            "cmm.domains.sdk.harness",
            "cmm.domains.sdk.fixtures",
            "cmm.domains.sdk.packager",
            "cmm.domains.sdk.validation",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_sdk_builders.py",
            "tests/domains/test_domain_sdk_scaffold.py",
            "tests/domains/test_domain_sdk_harness.py",
            "tests/domains/test_domain_sdk_packager.py",
            "tests/domains/test_domain_sdk_dp035_acceptance.py",
        ),
    ),
    CoreConformanceRequirement(
        block=26,
        name="API and CLI",
        owner_modules=(
            "cmm.domains.api",
            "cmm.domains.sdk.cli",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_api_dp036_acceptance.py",
            "tests/domains/test_domain_api_adversarial.py",
            "tests/domains/test_domain_sdk_cli.py",
            "public surfaces present canonical state; no independent authority",
        ),
    ),
    CoreConformanceRequirement(
        block=27,
        name="Security and Observability",
        owner_modules=(
            "cmm.domains.trust_contracts",
            "cmm.domains.trust_evaluator",
            "cmm.domains.credential_policy",
            "cmm.domains.validation_security",
            "cmm.domains.validation_fragmentation",
            "cmm.domains.observability_contracts",
            "cmm.domains.observability_service",
            "cmm.domains.observability_health",
            "cmm.domains.observability_metrics",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_security_dp038_acceptance.py",
            "tests/domains/test_domain_trust_evaluator.py",
            "tests/domains/test_domain_observability_dp037_acceptance.py",
            "tests/domains/test_domain_architecture_guard_dp039_acceptance.py",
            "no evidence never becomes zero or a guessed value",
        ),
    ),
    CoreConformanceRequirement(
        block=28,
        name="Final Integration",
        owner_modules=(
            "cmm.domains.cognitive_integration",
            "cmm.domains.cognitive_integration_contracts",
            "cmm.domains.agent_runtime_integration",
            "cmm.domains.agent_runtime_integration_contracts",
            "cmm.domains.planner_workflow_integration",
            "cmm.domains.planner_workflow_integration_contracts",
            "cmm.domains.validation_integration",
            "cmm.domains.memory_knowledge_integration",
            "cmm.domains.interface_integration",
            "cmm.domains.interface_integration_contracts",
            "cmm.domains.model_policy_contracts",
            "cmm.domains.benchmark_contracts",
            "cmm.domains.quality_contracts",
            "cmm.domains.knowledge_package_contracts",
            "cmm.domains.knowledge_package_composition",
            "cmm.domains.knowledge_package_validation",
            "cmm.domains.privacy_policy_contracts",
        ),
        classification=CoreConformanceClassification.CANONICAL_OWNER_VERIFIED,
        evidence=(
            "tests/domains/test_domain_cognitive_dp040_acceptance.py",
            "tests/domains/test_domain_agent_runtime_dp041_acceptance.py",
            "tests/domains/test_domain_planner_workflow_dp042_acceptance.py",
            "tests/domains/test_domain_validation_integration_dp043_acceptance.py",
            "tests/domains/test_domain_memory_knowledge_dp044_acceptance.py",
            "tests/domains/test_domain_interface_dp045_acceptance.py",
            "tests/domains/test_domain_model_policy_dp046_acceptance.py",
            "tests/domains/test_domain_benchmark_dp047_acceptance.py",
            "tests/domains/test_domain_quality_dp048_acceptance.py",
            "tests/domains/test_domain_knowledge_package_dp049_acceptance.py",
            "tests/domains/test_domain_privacy_policy_dp050_acceptance.py",
            "Phase 11 platform/UI integration stays deferred at this boundary",
        ),
    ),
)


#: Exactly the twelve canonical pre-10.52 first-party Domain Pack identities.
FIRST_PARTY_DOMAIN_IDS: frozenset[str] = frozenset(
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

#: Domain Packs explicitly deferred to Phase 10.52 and Phase 10.53.
DEFERRED_DOMAIN_IDS: frozenset[str] = frozenset(
    {
        "domain:mental-health",
        "domain:neurodivergence",
    }
)

#: Historical block numbers that the pre-10.52 core must satisfy now.
REQUIRED_BLOCKS: tuple[int, ...] = tuple(range(1, 29))

#: Additive ``DomainDefinition`` surfaces introduced by closed Phases 10.46–10.50.
LATE_ADDITIVE_DEFINITION_FIELDS: tuple[str, ...] = (
    "model_policy",
    "benchmark_suites",
    "quality_metrics",
    "knowledge_package_schema",
    "privacy_policy",
)

#: Production module names that Phase 10.51 must never introduce.
FORBIDDEN_PARALLEL_OWNER_NAMES: tuple[str, ...] = (
    "DomainCoreEngine",
    "DomainCoreRuntime",
    "DomainCoreRegistry",
    "DomainCoreResolver",
    "DomainCoreLoader",
    "DomainCoreStore",
    "DomainConformanceRegistry",
    "DomainConformanceRuntime",
    "DomainConformanceEngine",
    "DomainIntegrationEngineV2",
    "DomainFinalIntegrator",
    "DomainFinalRuntime",
    "DomainClosureEngine",
    "DomainClosureRegistry",
    "DomainOrchestrationEngine",
)

#: Production packages whose absence proves 10.52/10.53 remain NOT_STARTED.
DEFERRED_DOMAIN_PACKAGE_PATHS: tuple[str, ...] = (
    "cmm/domains/mental_health",
    "cmm/domains/neurodivergence",
)

#: Definition builders for the twelve official first-party Domain Packs.
_FIRST_PARTY_DEFINITION_BUILDERS: tuple[tuple[str, str, str], ...] = (
    (
        "domain:general",
        "cmm.domains.general.definition",
        "build_general_domain_definition",
    ),
    (
        "domain:health",
        "cmm.domains.health.definition",
        "build_health_domain_definition",
    ),
    (
        "domain:relationships",
        "cmm.domains.relationships.definition",
        "build_relationships_domain_definition",
    ),
    (
        "domain:university",
        "cmm.domains.university.definition",
        "build_university_domain_definition",
    ),
    (
        "domain:oppositions",
        "cmm.domains.oppositions.definition",
        "build_oppositions_domain_definition",
    ),
    (
        "domain:reflection",
        "cmm.domains.reflection.definition",
        "build_reflection_domain_definition",
    ),
    (
        "domain:concerns",
        "cmm.domains.concerns.definition",
        "build_concerns_domain_definition",
    ),
    (
        "domain:languages",
        "cmm.domains.languages.definition",
        "build_languages_domain_definition",
    ),
    (
        "domain:parenthood",
        "cmm.domains.parenthood.definition",
        "build_parenthood_domain_definition",
    ),
    (
        "domain:sport",
        "cmm.domains.sport.definition",
        "build_sport_domain_definition",
    ),
    (
        "domain:life-plan",
        "cmm.domains.life_plan.definition",
        "build_life_plan_domain_definition",
    ),
    (
        "domain:project",
        "cmm.domains.project.definition",
        "build_project_domain_definition",
    ),
)


def required_blocks() -> tuple[int, ...]:
    """The historical Implementation Order block numbers (1..28)."""
    return REQUIRED_BLOCKS


def historical_block_count() -> int:
    """HISTORICAL_BLOCKS aggregate."""
    return len(CORE_CONFORMANCE_REQUIREMENTS)


def unmapped_required_blocks() -> tuple[int, ...]:
    """UNMAPPED_REQUIRED_BLOCKS: required blocks lacking an owner or evidence."""
    by_block = {item.block: item for item in CORE_CONFORMANCE_REQUIREMENTS}
    return tuple(
        block
        for block in REQUIRED_BLOCKS
        if not by_block.get(block)
        or not by_block[block].owner_modules
        or not by_block[block].evidence
    )


def gap_red_requirements() -> tuple[CoreConformanceRequirement, ...]:
    """Requirements proven genuinely missing; PARALLEL_OWNER_REQUIRED derives from this."""
    return tuple(
        item
        for item in CORE_CONFORMANCE_REQUIREMENTS
        if item.classification is CoreConformanceClassification.GAP_RED
    )


def parallel_owner_required_count() -> int:
    """PARALLEL_OWNER_REQUIRED: blocks needing a new owner must be zero."""
    return len(gap_red_requirements())


def deferred_classification_count() -> int:
    """DEFERRED_DOMAIN_PACKS: approved later-phase boundaries in the inventory."""
    return len(DEFERRED_DOMAIN_IDS)


def first_party_definition_builders() -> dict[str, Callable[[], DomainDefinition]]:
    """The official builders for the twelve first-party DomainDefinitions."""
    builders: dict[str, Callable[[], DomainDefinition]] = {}
    for domain_id, module_name, symbol in _FIRST_PARTY_DEFINITION_BUILDERS:
        module = import_module(module_name)
        builders[domain_id] = getattr(module, symbol)
    return builders


def load_first_party_definitions() -> tuple[DomainDefinition, ...]:
    """Load the real official first-party DomainDefinitions, deterministically."""
    builders = first_party_definition_builders()
    return tuple(builders[domain_id]() for domain_id in sorted(builders))


def iter_owner_modules() -> Iterator[str]:
    """Every canonical owner module referenced by the 28-block inventory."""
    for requirement in CORE_CONFORMANCE_REQUIREMENTS:
        yield from requirement.owner_modules


__all__ = [
    "CORE_CONFORMANCE_REQUIREMENTS",
    "DEFERRED_DOMAIN_IDS",
    "DEFERRED_DOMAIN_PACKAGE_PATHS",
    "FIRST_PARTY_DOMAIN_IDS",
    "FORBIDDEN_PARALLEL_OWNER_NAMES",
    "LATE_ADDITIVE_DEFINITION_FIELDS",
    "REQUIRED_BLOCKS",
    "CoreConformanceClassification",
    "CoreConformanceRequirement",
    "deferred_classification_count",
    "first_party_definition_builders",
    "gap_red_requirements",
    "historical_block_count",
    "iter_owner_modules",
    "load_first_party_definitions",
    "parallel_owner_required_count",
    "required_blocks",
    "unmapped_required_blocks",
]
