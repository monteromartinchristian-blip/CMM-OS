"""Phase 10.52 — Mental Health benchmark suite tests.

Benchmarks are declarative portable data: deterministic serialization and
digest through the existing Phase 10.47 contract, representative coverage, and
no benchmark runtime.
"""

from __future__ import annotations

from cmm.domains.benchmark_contracts import DomainBenchmarkCase, DomainBenchmarkSuite
from cmm.domains.mental_health.benchmarks import build_mental_health_benchmark_suites

_REQUIRED_TOPICS = {
    "ordinary-emotional-conversation",
    "therapy-preparation",
    "therapy-provenance",
    "health-authority",
    "loop-and-safety",
    "persistence-and-privacy",
}


def _suite() -> DomainBenchmarkSuite:
    suites = build_mental_health_benchmark_suites()
    assert len(suites) == 1
    return suites[0]


def test_suite_identity_and_domain():
    suite = _suite()
    assert isinstance(suite, DomainBenchmarkSuite)
    assert suite.id == "benchmark-suite:mental-health:core"
    assert str(suite.domain_id) == "domain:mental-health"
    assert suite.schema_version == "1"
    assert suite.version == "1"


def test_cases_are_declarative_and_canonical():
    suite = _suite()
    assert suite.cases
    for case in suite.cases:
        assert isinstance(case, DomainBenchmarkCase)
        assert str(case.domain_id) == "domain:mental-health"
        assert case.objective
        assert case.expected_elements
        assert case.prohibited_behaviors
        assert case.evaluation_criteria
        assert case.input_resource_refs
        assert case.privacy_requirement == "SENSITIVE"


def test_representative_topics_are_covered():
    suite = _suite()
    covered = {case.metadata.get("roadmap_area") for case in suite.cases}
    assert _REQUIRED_TOPICS <= covered


def test_case_identities_are_unique_and_order_is_stable():
    first = _suite()
    ids = [case.id for case in first.cases]
    assert len(ids) == len(set(ids))
    # Canonical order is the declarative order and is stable across builds.
    second = build_mental_health_benchmark_suites()[0]
    assert [case.id for case in second.cases] == ids


def test_serialization_and_digest_are_deterministic():
    first = build_mental_health_benchmark_suites()
    second = build_mental_health_benchmark_suites()
    assert first == second
    assert first[0].content_digest == second[0].content_digest
    assert first[0].to_dict() == second[0].to_dict()
    round_tripped = DomainBenchmarkSuite.from_dict(first[0].to_dict())
    assert round_tripped == first[0]
    assert round_tripped.content_digest == first[0].content_digest


def test_no_benchmark_runtime_or_executor_is_attached():
    suite = _suite()
    for case in suite.cases:
        assert not hasattr(case, "evaluate")
        assert "runtime" not in case.metadata
        assert "executor" not in case.metadata
    # Executable evaluators stay opaque references, never resolved here.
    for case in suite.cases:
        for evaluator_id in case.evaluator_ids:
            assert evaluator_id.startswith("evaluator:")
