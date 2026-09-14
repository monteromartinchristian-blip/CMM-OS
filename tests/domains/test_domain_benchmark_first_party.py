"""Phase 10.47 — first-party Domain benchmark conformance."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import fields

import pytest

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
    export_domain_benchmark_suite,
    import_domain_benchmark_suite,
)
from cmm.domains.concerns.definition import build_concerns_domain_definition
from cmm.domains.contracts import DomainDefinition
from cmm.domains.general.definition import build_general_domain_definition
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.languages.definition import build_languages_domain_definition
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
from cmm.domains.mental_health.definition import (
    build_mental_health_domain_definition,
)
from cmm.domains.neurodivergence.definition import (
    build_neurodivergence_domain_definition,
)
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
    build_mental_health_domain_definition,
    build_neurodivergence_domain_definition,
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
    "mental-health": "benchmark-suite:mental-health:core",
    "neurodivergence": "benchmark-suite:neurodivergence:core",
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


# ── Conformance hardening ─────────────────────────────────────────────────────

_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "model",
        "model_id",
        "model_ids",
        "model_family",
        "models",
        "candidate_models",
        "preferred_models",
        "prohibited_models",
        "provider",
        "provider_id",
        "provider_ids",
        "providers",
        "candidate_providers",
        "preferred_providers",
        "prohibited_providers",
        "routing_weight",
        "routing_weights",
    }
)

_FORBIDDEN_CONTRACT_FIELDS = frozenset(
    {
        "candidate_models",
        "candidate_providers",
        "preferred_models",
        "preferred_providers",
        "weight",
        "minimum_score",
        "blocking",
        "aggregate_score",
    }
)

_FORBIDDEN_CONTENT_MARKERS = (
    "/Users/",
    "BEGIN PRIVATE KEY",
    "api_key",
    "Authorization: Bearer",
)


def _normalize_key(key: str) -> str:
    import re

    key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    key = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", key)
    return re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").lower()


def _iter_mapping_keys(value: object) -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_mapping_keys(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _iter_mapping_keys(nested)


def test_first_party_domain_count_is_fourteen_after_phase_10_53() -> None:
    assert len(FIRST_PARTY_BUILDERS) == 14
    slugs = {builder().id.slug for builder in FIRST_PARTY_BUILDERS}
    assert len(slugs) == 14
    assert "mental-health" in slugs
    assert "neurodivergence" in slugs
    assert set(slugs) == set(EXPECTED_SUITE_IDS)


def test_first_party_contracts_expose_no_authority_or_quality_fields() -> None:
    case_fields = {f.name for f in fields(DomainBenchmarkCase)}
    suite_fields = {f.name for f in fields(DomainBenchmarkSuite)}

    assert not (case_fields & _FORBIDDEN_CONTRACT_FIELDS)
    assert not (suite_fields & _FORBIDDEN_CONTRACT_FIELDS)

    for builder in FIRST_PARTY_BUILDERS:
        for suite in builder().benchmark_suites:
            payload = suite.to_dict()
            for metadata in (
                payload["metadata"],
                *(case["metadata"] for case in payload["cases"]),
            ):
                for key in _iter_mapping_keys(metadata):
                    assert _normalize_key(key) not in _FORBIDDEN_AUTHORITY_KEYS


def test_first_party_assets_contain_no_secrets_or_local_paths() -> None:
    for builder in FIRST_PARTY_BUILDERS:
        for suite in builder().benchmark_suites:
            text = export_domain_benchmark_suite(suite).decode("utf-8")
            for marker in _FORBIDDEN_CONTENT_MARKERS:
                assert marker not in text
            for case in suite.cases:
                assert case.objective.strip()


def test_first_party_export_is_deterministic_and_round_trips() -> None:
    for builder in FIRST_PARTY_BUILDERS:
        for suite in builder().benchmark_suites:
            first = export_domain_benchmark_suite(suite)
            assert first == export_domain_benchmark_suite(suite)
            restored = import_domain_benchmark_suite(first)
            assert restored == suite
            assert restored.content_digest == suite.content_digest


def test_first_party_builders_are_pure_and_deterministic() -> None:
    for builder in FIRST_PARTY_BUILDERS:
        assert builder().benchmark_suites == builder().benchmark_suites
