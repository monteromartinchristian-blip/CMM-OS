"""Phase 10.48 – first-party domain quality policy catalogs."""

from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.concerns.quality_metrics import build_concerns_quality_metrics
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.general.quality_metrics import build_general_quality_metrics
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.health.quality_metrics import build_health_quality_metrics
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.languages.quality_metrics import build_languages_quality_metrics
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.life_plan.quality_metrics import build_life_plan_quality_metrics
from cmm.domains.mental_health.definition import (
    build_mental_health_domain_definition,
)
from cmm.domains.mental_health.quality_metrics import (
    build_mental_health_quality_metrics,
)
from cmm.domains.neurodivergence.definition import (
    build_neurodivergence_domain_definition,
)
from cmm.domains.neurodivergence.quality_metrics import (
    build_neurodivergence_quality_metrics,
)
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.oppositions.quality_metrics import build_oppositions_quality_metrics
from cmm.domains.parenthood.definition import build_parenthood_domain_definition
from cmm.domains.parenthood.quality_metrics import build_parenthood_quality_metrics
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.project.quality_metrics import build_project_quality_metrics
from cmm.domains.reflection.definition import build_reflection_domain_definition
from cmm.domains.reflection.quality_metrics import build_reflection_quality_metrics
from cmm.domains.relationships.definition import (
    build_relationships_domain_definition,
)
from cmm.domains.relationships.quality_metrics import (
    build_relationships_quality_metrics,
)
from cmm.domains.sport.definition import build_sport_domain_definition
from cmm.domains.sport.quality_metrics import build_sport_quality_metrics
from cmm.domains.university.definition import build_university_domain_definition
from cmm.domains.university.quality_metrics import build_university_quality_metrics

# Approved first-party policy: (metric-slug, weight, minimum, blocking).
EXPECTED: dict[str, tuple[tuple[str, str, str, bool], ...]] = {
    "general": (
        ("factual-fidelity", "0.25", "0.70", False),
        ("contextual-fidelity", "0.20", "0.65", False),
        ("usefulness", "0.20", "0.65", False),
        ("clarity", "0.15", "0.65", False),
        ("instruction-compliance", "0.20", "0.70", True),
    ),
    "health": (
        ("factual-fidelity", "0.25", "0.90", True),
        ("prudence", "0.25", "0.90", True),
        ("temporal-correctness", "0.20", "0.85", True),
        ("privacy-compliance", "0.20", "0.95", True),
        ("contextual-fidelity", "0.10", "0.80", False),
    ),
    "relationships": (
        ("ambiguity-handling", "0.25", "0.80", False),
        ("contextual-continuity", "0.20", "0.75", False),
        ("non-attribution-of-intent", "0.25", "0.90", True),
        ("uncertainty-preservation", "0.15", "0.80", True),
        ("usefulness", "0.15", "0.70", False),
    ),
    "university": (
        ("temporal-correctness", "0.25", "0.85", True),
        ("constraint-compliance", "0.25", "0.85", True),
        ("feasibility", "0.20", "0.75", False),
        ("plan-quality", "0.20", "0.75", False),
        ("factual-fidelity", "0.10", "0.80", False),
    ),
    "oppositions": (
        ("official-source-fidelity", "0.25", "0.90", True),
        ("temporal-correctness", "0.25", "0.90", True),
        ("requirement-precision", "0.20", "0.85", True),
        ("contextual-continuity", "0.15", "0.75", False),
        ("usefulness", "0.15", "0.70", False),
    ),
    "reflection": (
        ("epistemic-separation", "0.25", "0.80", True),
        ("ambiguity-preservation", "0.20", "0.75", False),
        ("contextual-continuity", "0.20", "0.75", False),
        ("depth", "0.20", "0.65", False),
        ("user-agency", "0.15", "0.80", True),
    ),
    "concerns": (
        ("contextual-understanding", "0.15", "0.75", False),
        ("support-need-calibration", "0.15", "0.80", True),
        ("epistemic-separation", "0.15", "0.85", True),
        ("reassurance-calibration", "0.15", "0.85", True),
        ("proportional-risk", "0.15", "0.90", True),
        ("useful-questioning", "0.10", "0.70", False),
        ("non-pathologizing-recurrence", "0.075", "0.85", True),
        ("user-agency", "0.075", "0.80", True),
    ),
    "languages": (
        ("linguistic-correctness", "0.30", "0.80", True),
        ("level-alignment", "0.20", "0.75", False),
        ("instruction-compliance", "0.20", "0.80", True),
        ("usefulness", "0.15", "0.70", False),
        ("clarity", "0.15", "0.70", False),
    ),
    "parenthood": (
        ("factual-fidelity", "0.25", "0.85", True),
        ("sensitivity", "0.20", "0.80", False),
        ("prudence", "0.20", "0.85", True),
        ("temporal-correctness", "0.15", "0.75", False),
        ("privacy-compliance", "0.20", "0.90", True),
    ),
    "sport": (
        ("factual-fidelity", "0.25", "0.80", True),
        ("temporal-correctness", "0.20", "0.75", False),
        ("plan-quality", "0.20", "0.75", False),
        ("usefulness", "0.20", "0.70", False),
        ("instruction-compliance", "0.15", "0.75", True),
    ),
    "life-plan": (
        ("contextual-fidelity", "0.20", "0.80", False),
        ("feasibility", "0.25", "0.80", True),
        ("tradeoff-quality", "0.20", "0.75", False),
        ("temporal-correctness", "0.15", "0.75", False),
        ("plan-quality", "0.20", "0.75", False),
    ),
    "project": (
        ("correctness", "0.25", "0.90", True),
        ("architectural-consistency", "0.20", "0.85", True),
        ("validation-quality", "0.20", "0.90", True),
        ("tool-calling-quality", "0.20", "0.85", True),
        ("structured-output", "0.15", "0.80", False),
    ),
    "mental-health": (
        ("health-authority-boundary-fidelity", "0.20", "1.00", True),
        ("epistemic-separation", "0.15", "0.95", True),
        ("provenance-fidelity", "0.15", "0.95", True),
        ("privacy-adherence", "0.15", "1.00", True),
        ("safety-proportionality", "0.10", "0.95", True),
        ("sensitive-memory-proposal-discipline", "0.10", "1.00", True),
        ("non-pathologizing-behavior", "0.05", "0.90", True),
        ("cross-domain-minimization", "0.05", "0.90", True),
        ("therapy-context-fidelity", "0.05", "0.80", False),
    ),
    # Phase 10.53 domain:neurodivergence.
    "neurodivergence": (
        ("certainty-fidelity", "0.15", "1.00", True),
        ("source-authority-fidelity", "0.15", "1.00", True),
        ("developmental-temporality", "0.10", "0.95", True),
        ("differential-reasoning-quality", "0.10", "0.85", False),
        ("exploratory-usefulness", "0.10", "0.90", True),
        ("functional-relevance", "0.05", "0.80", False),
        ("cross-domain-minimization", "0.10", "1.00", True),
        ("privacy-adherence", "0.15", "1.00", True),
        ("sensitive-memory-discipline", "0.05", "1.00", True),
        ("assessment-summary-fidelity", "0.05", "0.80", False),
    ),
}

IMPLEMENTED_QUALITY_DOMAINS = {
    "general",
    "health",
    "relationships",
    "university",
    "oppositions",
    "reflection",
    "concerns",
    "languages",
    "parenthood",
    "sport",
    "life-plan",
    "project",
    "mental-health",
    "neurodivergence",
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
    "life-plan": build_life_plan_domain_definition,
    "project": build_project_domain_definition,
    "mental-health": build_mental_health_domain_definition,
    "neurodivergence": build_neurodivergence_domain_definition,
}

FACTORY_BUILDERS = {
    "general": build_general_quality_metrics,
    "health": build_health_quality_metrics,
    "relationships": build_relationships_quality_metrics,
    "university": build_university_quality_metrics,
    "oppositions": build_oppositions_quality_metrics,
    "reflection": build_reflection_quality_metrics,
    "concerns": build_concerns_quality_metrics,
    "languages": build_languages_quality_metrics,
    "parenthood": build_parenthood_quality_metrics,
    "sport": build_sport_quality_metrics,
    "life-plan": build_life_plan_quality_metrics,
    "project": build_project_quality_metrics,
    "mental-health": build_mental_health_quality_metrics,
    "neurodivergence": build_neurodivergence_quality_metrics,
}


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_catalog_matches_approved_policy(slug: str) -> None:
    metrics = FACTORY_BUILDERS[slug]()

    assert [metric.name for metric in metrics] == [row[0] for row in EXPECTED[slug]]
    for metric, (name, weight, minimum, blocking) in zip(
        metrics, EXPECTED[slug], strict=True
    ):
        assert metric.id == f"quality-metric:{slug}:{name}"
        assert metric.domain_id.slug == slug
        assert metric.name == name
        assert metric.weight == Decimal(weight)
        assert metric.minimum_score == Decimal(minimum)
        assert metric.blocking is blocking
        assert metric.evaluator_id == f"evaluator:{name}"
        assert metric.schema_version == "1"
        assert metric.version == "1"
        assert metric.metadata == {}


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_catalog_weights_sum_to_one(slug: str) -> None:
    total = sum((metric.weight for metric in FACTORY_BUILDERS[slug]()), Decimal(0))

    assert total == Decimal(1)


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_catalog_has_at_least_one_blocking_metric(slug: str) -> None:
    assert any(metric.blocking for metric in FACTORY_BUILDERS[slug]())


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_factory_is_deterministic(slug: str) -> None:
    assert FACTORY_BUILDERS[slug]() == FACTORY_BUILDERS[slug]()


@pytest.mark.parametrize("slug", sorted(EXPECTED))
def test_domain_definition_attaches_catalog(slug: str) -> None:
    definition = DEFINITION_BUILDERS[slug]()

    assert definition.quality_metrics == FACTORY_BUILDERS[slug]()
    assert definition.benchmark_suites


def test_implemented_catalog_inventory_is_fourteen_after_phase_10_53() -> None:
    assert set(EXPECTED) == IMPLEMENTED_QUALITY_DOMAINS
    assert set(FACTORY_BUILDERS) == IMPLEMENTED_QUALITY_DOMAINS
    assert set(DEFINITION_BUILDERS) == IMPLEMENTED_QUALITY_DOMAINS
    assert len(IMPLEMENTED_QUALITY_DOMAINS) == 14


def test_every_implemented_domain_exposes_a_loadable_quality_catalog() -> None:
    """No implemented Domain Pack may be missing its declared catalog."""
    files = sorted(pathlib.Path("cmm/domains").glob("*/quality_metrics.py"))
    found = {path.parent.name.replace("_", "-") for path in files}

    assert found == IMPLEMENTED_QUALITY_DOMAINS
    assert "neurodivergence" in IMPLEMENTED_QUALITY_DOMAINS
    assert pathlib.Path("cmm/domains/neurodivergence/quality_metrics.py").exists()
