"""Phase 10.47 — first-party Domain benchmark conformance."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.contracts import DomainDefinition
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.parenthood.definition import build_parenthood_domain_definition
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.reflection.definition import build_reflection_domain_definition
from cmm.domains.relationships.definition import build_relationships_domain_definition
from cmm.domains.sport.definition import build_sport_domain_definition
from cmm.domains.university.definition import build_university_domain_definition

Builder = Callable[[], DomainDefinition]

FIRST_PARTY_BUILDERS: tuple[Builder, ...] = (
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

EXPECTED_SUITE_IDS: dict[str, str] = {
    "general": "benchmark-suite:general:core",
    "health": "benchmark-suite:health:core",
    "relationships": "benchmark-suite:relationships:core",
    "university": "benchmark-suite:university:core",
    "oppositions": "benchmark-suite:oppositions:core",
    "reflection": "benchmark-suite:reflection:core",
    "concerns": "benchmark-suite:concerns:core",
    "languages": "benchmark-suite:languages:core",
    "parenthood": "benchmark-suite:parenthood:core",
    "sport": "benchmark-suite:sport:core",
    "life-plan": "benchmark-suite:life-plan:core",
    "project": "benchmark-suite:project:core",
}

_CONCERNS_ROADMAP_AREAS = frozenset(
    {
        "understanding before intervention",
        "support-need calibration",
        "emotional validation without fact inflation",
        "reality / interpretation / fear / scenario separation",
        "evidence-calibrated reassurance",
        "uncertainty preservation",
        "proportional risk",
        "no catastrophic escalation",
        "no false reassurance",
        "recurrence without automatic pathologization",
        "materially useful questions",
        "grounded directness",
        "proportional action",
        "cross-domain factual and risk handoff",
    }
)


def _builder_for_slug(slug: str) -> Builder:
    for builder in FIRST_PARTY_BUILDERS:
        if builder().id.slug == slug:
            return builder
    raise AssertionError(f"no first-party builder for slug {slug!r}")


@pytest.mark.parametrize("builder", FIRST_PARTY_BUILDERS, ids=lambda b: b.__name__)
def test_first_party_definition_exposes_benchmark_suites(
    builder: Builder,
) -> None:
    definition = builder()

    assert definition.benchmark_suites
    suite_ids = [suite.id for suite in definition.benchmark_suites]
    assert len(set(suite_ids)) == len(suite_ids)
    for suite in definition.benchmark_suites:
        assert suite.domain_id == definition.id
        assert suite.cases
        case_ids = [case.id for case in suite.cases]
        assert len(set(case_ids)) == len(case_ids)
        for case in suite.cases:
            assert case.domain_id == definition.id
            assert case.objective.strip()


@pytest.mark.parametrize("slug", sorted(EXPECTED_SUITE_IDS))
def test_first_party_suite_ids_are_stable(slug: str) -> None:
    definition = _builder_for_slug(slug)()

    assert definition.benchmark_suites[0].id == EXPECTED_SUITE_IDS[slug]


def test_health_sensitive_case_preserves_privacy_and_cost() -> None:
    definition = build_health_domain_definition()
    cases = [case for suite in definition.benchmark_suites for case in suite.cases]

    sensitive = [case for case in cases if case.privacy_requirement == "SENSITIVE"]

    assert sensitive
    for case in sensitive:
        assert case.sensitivity
        assert case.human_review_required is True
    assert any(case.maximum_cost_eur is not None for case in cases)
    for case in cases:
        for prohibited in ("invent diagnosis", "change medication"):
            assert prohibited in case.prohibited_behaviors


def test_concerns_suite_covers_roadmap_areas() -> None:
    definition = build_concerns_domain_definition()

    criteria = {
        criterion
        for suite in definition.benchmark_suites
        for case in suite.cases
        for criterion in case.evaluation_criteria
    }

    assert _CONCERNS_ROADMAP_AREAS <= criteria


def test_project_suite_covers_roadmap_areas() -> None:
    definition = build_project_domain_definition()

    criteria = {
        criterion
        for suite in definition.benchmark_suites
        for case in suite.cases
        for criterion in case.evaluation_criteria
    }

    assert {
        "code generation",
        "architectural consistency",
        "tool calling",
        "structured output",
        "validation",
        "error correction",
    } <= criteria
