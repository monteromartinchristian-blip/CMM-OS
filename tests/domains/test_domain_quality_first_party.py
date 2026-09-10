"""Phase 10.48 – first-party domain quality policy catalogs."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.general.quality_metrics import build_general_quality_metrics
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.health.quality_metrics import build_health_quality_metrics
from cmm.domains.relationships.definition import (
    build_relationships_domain_definition,
)
from cmm.domains.relationships.quality_metrics import (
    build_relationships_quality_metrics,
)
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
}

DEFINITION_BUILDERS = {
    "general": build_general_domain_definition,
    "health": build_health_domain_definition,
    "relationships": build_relationships_domain_definition,
    "university": build_university_domain_definition,
}

FACTORY_BUILDERS = {
    "general": build_general_quality_metrics,
    "health": build_health_quality_metrics,
    "relationships": build_relationships_quality_metrics,
    "university": build_university_quality_metrics,
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
