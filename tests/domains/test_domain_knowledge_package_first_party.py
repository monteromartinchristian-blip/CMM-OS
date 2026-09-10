"""Phase 10.49 – first-party domain knowledge package schemas."""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.concerns.knowledge_package import (
    build_concerns_knowledge_package_schema,
)
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.general.knowledge_package import (
    build_general_knowledge_package_schema,
)
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.health.knowledge_package import (
    build_health_knowledge_package_schema,
)
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.languages.knowledge_package import (
    build_languages_knowledge_package_schema,
)
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.life_plan.knowledge_package import (
    build_life_plan_knowledge_package_schema,
)
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.oppositions.knowledge_package import (
    build_oppositions_knowledge_package_schema,
)
from cmm.domains.parenthood.definition import build_parenthood_domain_definition
from cmm.domains.parenthood.knowledge_package import (
    build_parenthood_knowledge_package_schema,
)
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.project.knowledge_package import (
    build_project_knowledge_package_schema,
)
from cmm.domains.reflection.definition import build_reflection_domain_definition
from cmm.domains.reflection.knowledge_package import (
    build_reflection_knowledge_package_schema,
)
from cmm.domains.relationships.definition import (
    build_relationships_domain_definition,
)
from cmm.domains.relationships.knowledge_package import (
    build_relationships_knowledge_package_schema,
)
from cmm.domains.sport.definition import build_sport_domain_definition
from cmm.domains.sport.knowledge_package import (
    build_sport_knowledge_package_schema,
)
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageSchema,
)
from cmm.domains.university.definition import build_university_domain_definition
from cmm.domains.university.knowledge_package import (
    build_university_knowledge_package_schema,
)

# Approved first-party inventory: slug -> exact canonical Domain ID.
EXPECTED: dict[str, str] = {
    "general": "domain:general",
    "health": "domain:health",
    "relationships": "domain:relationships",
    "university": "domain:university",
    "oppositions": "domain:oppositions",
    "reflection": "domain:reflection",
    "concerns": "domain:concerns",
    "languages": "domain:languages",
    "parenthood": "domain:parenthood",
    "sport": "domain:sport",
    "life_plan": "domain:life-plan",
    "project": "domain:project",
}

# Approved minimum sensitivity floors. General, Sport and Life Plan are derived
# from each Domain's own profile ``memory_policy.sensitivity_limit``.
EXPECTED_SENSITIVITY: dict[str, SensitivityLevel] = {
    "general": SensitivityLevel.INTERNAL,
    "health": SensitivityLevel.SENSITIVE,
    "relationships": SensitivityLevel.SENSITIVE,
    "university": SensitivityLevel.INTERNAL,
    "oppositions": SensitivityLevel.INTERNAL,
    "reflection": SensitivityLevel.SENSITIVE,
    "concerns": SensitivityLevel.SENSITIVE,
    "languages": SensitivityLevel.INTERNAL,
    "parenthood": SensitivityLevel.SENSITIVE,
    "sport": SensitivityLevel.SENSITIVE,
    "life_plan": SensitivityLevel.SENSITIVE,
    "project": SensitivityLevel.INTERNAL,
}

IMPLEMENTED_SCHEMA_DOMAINS = set(EXPECTED)

SCHEMA_BUILDERS = {
    "general": build_general_knowledge_package_schema,
    "health": build_health_knowledge_package_schema,
    "relationships": build_relationships_knowledge_package_schema,
    "university": build_university_knowledge_package_schema,
    "oppositions": build_oppositions_knowledge_package_schema,
    "reflection": build_reflection_knowledge_package_schema,
    "concerns": build_concerns_knowledge_package_schema,
    "languages": build_languages_knowledge_package_schema,
    "parenthood": build_parenthood_knowledge_package_schema,
    "sport": build_sport_knowledge_package_schema,
    "life_plan": build_life_plan_knowledge_package_schema,
    "project": build_project_knowledge_package_schema,
}

DEFINITION_BUILDERS = {
    "general": build_general_domain_definition,
    "health": build_health_domain_definition,
    "relationships": build_relationships_domain_definition,
    "university": build_university_domain_definition,
    "oppositions": build_oppositions_domain_definition,
    "reflection": build_reflection_domain_definition,
    "concerns": build_concerns_domain_definition,
    "languages": build_languages_domain_definition,
    "parenthood": build_parenthood_domain_definition,
    "sport": build_sport_domain_definition,
    "life_plan": build_life_plan_domain_definition,
    "project": build_project_domain_definition,
}


def _all_first_party_schemas() -> dict[str, DomainKnowledgePackageSchema]:
    """Build every approved first-party schema, keyed by slug."""
    return {slug: builder() for slug, builder in SCHEMA_BUILDERS.items()}


def _normalized_policy_body(
    schema: DomainKnowledgePackageSchema,
) -> tuple[object, ...]:
    """Normalize a schema to its semantic policy body.

    Identity, sensitivity and metadata are deliberately excluded: they are
    per-Domain labels, not evidence of Domain-specific package policy.
    """
    return (
        schema.required_sections,
        schema.optional_sections,
        schema.prohibited_sections,
        tuple(policy.to_dict() for policy in schema.field_policies),
        schema.validator_refs,
    )


_FORBIDDEN_SERIALIZATION_TOKENS = (
    "model",
    "provider",
    "api_key",
    "apikey",
    "endpoint",
    "callback",
    "openai",
    "anthropic",
    "claude",
    "http://",
    "https://",
)


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_schema_binds_exactly_its_domain(slug: str) -> None:
    schema = SCHEMA_BUILDERS[slug]()

    assert str(schema.domain_id) == EXPECTED[slug]
    assert schema.id == f"knowledge-package-schema:{slug}"
    assert schema.version == "1"
    assert schema.base_schema == "KnowledgePackage"


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_schema_declares_approved_sensitivity_floor(slug: str) -> None:
    assert SCHEMA_BUILDERS[slug]().minimum_sensitivity is EXPECTED_SENSITIVITY[slug]


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_schema_factory_is_deterministic(slug: str) -> None:
    assert SCHEMA_BUILDERS[slug]() == SCHEMA_BUILDERS[slug]()


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_schema_round_trips(slug: str) -> None:
    schema = SCHEMA_BUILDERS[slug]()
    from cmm.domains.knowledge_package_contracts import (
        DomainKnowledgePackageSchema,
    )

    assert DomainKnowledgePackageSchema.from_dict(schema.to_dict()) == schema


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_schema_requires_objective_and_declares_epistemic_discipline(slug: str) -> None:
    schema = SCHEMA_BUILDERS[slug]()

    assert "objective" in schema.required_sections
    assert schema.prohibited_sections == ()

    policies = {policy.field_name: policy for policy in schema.field_policies}
    assert policies["facts"].allowed_knowledge_kinds == (KnowledgeKind.FACT,)
    assert policies["observations"].allowed_knowledge_kinds == (
        KnowledgeKind.OBSERVATION,
    )
    assert policies["inferences"].preserve_uncertainty is True
    assert policies["hypotheses"].preserve_uncertainty is True
    assert policies["contradictions"].preserve_contradictions is True


def test_first_party_knowledge_package_policies_are_meaningfully_domain_specific() -> None:
    """The twelve schemas must not collapse into one normalized policy body."""
    schemas = _all_first_party_schemas()

    shapes = {repr(_normalized_policy_body(schema)) for schema in schemas.values()}

    assert len(shapes) >= 4


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_definition_attaches_exactly_one_schema(slug: str) -> None:
    definition = DEFINITION_BUILDERS[slug]()

    assert definition.knowledge_package_schema == SCHEMA_BUILDERS[slug]()
    assert str(definition.id) == EXPECTED[slug]


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_no_provider_or_executable_content_in_serialization(slug: str) -> None:
    payload = SCHEMA_BUILDERS[slug]().to_dict()
    text = json.dumps(payload, sort_keys=True).lower()

    for token in _FORBIDDEN_SERIALIZATION_TOKENS:
        assert token not in text, f"{slug} serialization leaked {token!r}"
    assert payload["validator_refs"] == []
    assert payload["metadata"] == {}


def test_implemented_schema_inventory_is_exactly_twelve() -> None:
    assert set(EXPECTED) == IMPLEMENTED_SCHEMA_DOMAINS
    assert set(SCHEMA_BUILDERS) == IMPLEMENTED_SCHEMA_DOMAINS
    assert set(DEFINITION_BUILDERS) == IMPLEMENTED_SCHEMA_DOMAINS
    assert len(IMPLEMENTED_SCHEMA_DOMAINS) == 12


def test_production_inventory_matches_exactly_twelve() -> None:
    files = sorted(pathlib.Path("cmm/domains").glob("*/knowledge_package.py"))

    assert {path.parent.name for path in files} == IMPLEMENTED_SCHEMA_DOMAINS


@pytest.mark.parametrize("slug", ("mental_health", "neurodivergence"))
def test_future_domain_schemas_are_absent(slug: str) -> None:
    package_dir = pathlib.Path("cmm/domains") / slug
    assert not package_dir.exists()
    assert not (package_dir / "knowledge_package.py").exists()
    try:
        spec = importlib.util.find_spec(f"cmm.domains.{slug}.knowledge_package")
    except ModuleNotFoundError:
        spec = None
    assert spec is None
