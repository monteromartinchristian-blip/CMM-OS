"""Phase 10.53 — Neurodivergence benchmark declaration tests.

Declarative, provider-independent Phase 10.47 benchmark assets.  They never
execute a model, never resolve an evaluator, never select a provider and never
grant clinical, privacy or persistence authority.  No benchmark runtime is
introduced.
"""

from __future__ import annotations

import json

from cmm.domains.benchmark_contracts import (
    DomainBenchmarkCase,
    DomainBenchmarkSuite,
)
from cmm.domains.neurodivergence.benchmarks import (
    NEURODIVERGENCE_BENCHMARK_AREAS,
    build_neurodivergence_benchmark_suites,
)

#: The frozen coverage areas required by the approved plan (Task 6, Step 3).
EXPECTED_AREAS = frozenset(
    {
        "exploratory_hypothesis_usefulness",
        "diagnostic_non_promotion",
        "screening_self_report_non_promotion",
        "developmental_chronology",
        "source_observer_separation",
        "balanced_differential_reasoning",
        "health_authority",
        "cross_domain_deny",
        "unconsumed_approval",
        "consumed_approval",
        "sensitive_memory",
        "professional_assessment_summary",
    }
)


def _suites():
    return build_neurodivergence_benchmark_suites()


def test_benchmark_suite_identity_is_canonical():
    suites = _suites()

    assert len(suites) == 1
    suite = suites[0]
    assert isinstance(suite, DomainBenchmarkSuite)
    assert suite.id == "benchmark-suite:neurodivergence:core"
    assert str(suite.domain_id) == "domain:neurodivergence"
    assert suite.version == "1"
    assert suite.metadata["source"] == "first-party"
    assert suite.metadata["phase"] == "10.53"


def test_every_required_coverage_area_has_a_case():
    suite = _suites()[0]
    areas = {case.metadata["roadmap_area"] for case in suite.cases}

    assert EXPECTED_AREAS <= areas
    assert tuple(NEURODIVERGENCE_BENCHMARK_AREAS) == tuple(sorted(EXPECTED_AREAS))


def test_every_case_is_a_deterministic_declarative_declaration():
    for suite in _suites():
        for case in suite.cases:
            assert isinstance(case, DomainBenchmarkCase)
            assert str(case.domain_id) == "domain:neurodivergence"
            assert case.objective
            assert case.expected_elements
            assert case.evaluation_criteria
            assert case.evaluator_ids
            assert case.required_format == "structured"
            assert case.sensitivity == "sensitive"
            assert case.privacy_requirement == "SENSITIVE"
            if case.human_review_required:
                assert case.human_review_guidance
            assert case.metadata["fixture_kind"] == "synthetic"


def test_declaration_is_deterministic_across_calls():
    first = tuple(json.dumps(suite.to_dict(), sort_keys=True) for suite in _suites())
    second = tuple(json.dumps(suite.to_dict(), sort_keys=True) for suite in _suites())

    assert first == second


def test_declarations_are_provider_and_model_agnostic():
    serialized = json.dumps(
        [suite.to_dict() for suite in _suites()], sort_keys=True
    ).casefold()

    for forbidden in (
        "openai",
        "anthropic",
        "gpt-",
        "claude",
        "gemini",
        "llama",
        "model_provider",
        "provider_id",
        "api_key",
    ):
        assert forbidden not in serialized, forbidden


def test_no_benchmark_runtime_or_evaluator_resolution_exists():
    import cmm.domains.neurodivergence.benchmarks as module

    with open(module.__file__, encoding="utf-8") as handle:
        text = handle.read()

    for forbidden in (
        "class BenchmarkRunner",
        "class BenchmarkRuntime",
        "def run(",
        "def execute(",
        "def evaluate(",
        "resolve_evaluator",
        "import subprocess",
        "requests.",
    ):
        assert forbidden not in text, forbidden


def test_cases_reference_declared_neurodivergence_resources():
    from cmm.domains.neurodivergence.catalog import (
        NEURODIVERGENCE_RESOURCE_IDS,
    )

    for suite in _suites():
        for case in suite.cases:
            assert case.input_resource_refs
            for reference in case.input_resource_refs:
                assert reference in NEURODIVERGENCE_RESOURCE_IDS, reference


def test_prohibited_behaviors_cover_the_fail_closed_boundary():
    """Every fail-closed boundary is declared by the case that covers it."""
    by_area = {
        case.metadata["roadmap_area"]: case
        for suite in _suites()
        for case in suite.cases
    }

    expected = {
        "diagnostic_non_promotion": (
            "present model inference as a confirmed diagnosis"
        ),
        "screening_self_report_non_promotion": (
            "present a screening result as a diagnosis"
        ),
        "health_authority": "override Health clinical authority",
        "cross_domain_deny": ("admit a transfer without current permission authority"),
        "unconsumed_approval": "treat an unconsumed approval as authorization",
        "sensitive_memory": "persist a working hypothesis silently",
        "balanced_differential_reasoning": "erase competing evidence",
    }
    for area, behavior in expected.items():
        assert behavior in by_area[area].prohibited_behaviors, area

    # And every case names at least one prohibited behavior.
    for case in by_area.values():
        assert case.prohibited_behaviors


# ═══════════════════════════════════════════════════════════════════════════════
# Model policy declaration (Phase 10.46)
# ═══════════════════════════════════════════════════════════════════════════════


def test_model_policy_declares_objective_reasoning_requirements():
    from cmm.domains.neurodivergence.model_policy import (
        build_neurodivergence_model_policy,
    )

    policy = build_neurodivergence_model_policy()

    assert str(policy.domain_id) == "domain:neurodivergence"
    assert policy.require_reasoning is True
    assert policy.require_structured_output is True
    assert policy.require_context_validation is True
    assert policy.require_response_validation is True
    assert policy.minimum_context_window and policy.minimum_context_window > 0

    requirements = policy.metadata["reasoning_requirements"]
    for requirement in (
        "structured_reasoning",
        "uncertainty_preservation",
        "source_provenance_fidelity",
        "longitudinal_comparison",
        "differential_comparison",
    ):
        assert requirement in requirements, requirement


def test_model_policy_names_no_provider_model_or_routing():
    from cmm.domains.neurodivergence.model_policy import (
        build_neurodivergence_model_policy,
    )

    serialized = json.dumps(
        build_neurodivergence_model_policy().to_dict(), sort_keys=True
    ).casefold()

    for forbidden in (
        "openai",
        "anthropic",
        "gpt-",
        "claude",
        "gemini",
        "llama",
        "mistral",
        "model_id",
        "provider_id",
        "provider_name",
        "api_key",
        "route_to",
        "ranking",
    ):
        assert forbidden not in serialized, forbidden
    # Model choice remains user-controlled; routing stays in the canonical layer.
    assert (
        build_neurodivergence_model_policy().metadata["user_model_choice_preserved"]
        is True
    )


def test_model_policy_declares_no_fallback_or_execution_surface():
    from cmm.domains.neurodivergence.model_policy import (
        build_neurodivergence_model_policy,
    )

    policy = build_neurodivergence_model_policy()

    assert policy.fallback_policy is None
    import cmm.domains.neurodivergence.model_policy as module

    with open(module.__file__, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in (
        "class DomainModelRouter",
        "def route(",
        "def invoke(",
        "def call_model(",
        "import requests",
        "import subprocess",
    ):
        assert forbidden not in text, forbidden
