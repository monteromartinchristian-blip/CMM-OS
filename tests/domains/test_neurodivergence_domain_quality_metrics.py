"""Phase 10.53 — Neurodivergence quality metric declaration tests.

Declarative Phase 10.48 quality policy only.  No evaluator resolves, no model
runs and no runtime is introduced: the pack declares what would make an output
unacceptable, and every unacceptable outcome required by the approved spec is
blocking.
"""

from __future__ import annotations

from cmm.domains.neurodivergence.quality_metrics import (
    NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES,
    build_neurodivergence_quality_metrics,
)

#: The frozen metric topics required by the approved plan (Task 6, Step 5).
EXPECTED_TOPICS = (
    "certainty_fidelity",
    "source_authority_fidelity",
    "developmental_temporality",
    "differential_reasoning_quality",
    "exploratory_usefulness",
    "functional_relevance",
    "cross_domain_minimization",
    "privacy_adherence",
    "sensitive_memory_discipline",
    "assessment_summary_fidelity",
)

#: The frozen blocking failures required by the approved plan.
EXPECTED_BLOCKING_FAILURES = frozenset(
    {
        "hypothesis_to_diagnosis",
        "screening_to_diagnosis",
        "self_report_to_diagnosis",
        "model_inference_as_clinical_fact",
        "health_authority_violation",
        "permission_deny_bypass",
        "unconsumed_approval_as_authority",
        "unauthorized_sensitive_persistence",
        "unauthorized_sensitive_transfer",
        "provenance_loss",
        "source_domain_authority_loss",
    }
)


def _metrics():
    return build_neurodivergence_quality_metrics()


def test_every_frozen_metric_topic_is_declared():
    metrics = _metrics()

    assert tuple(metric.name for metric in metrics) == EXPECTED_TOPICS
    assert len(metrics) == 10


def test_metric_identity_is_canonical_and_slug_valid():
    for metric in _metrics():
        assert metric.id.startswith("quality-metric:neurodivergence:")
        assert str(metric.domain_id) == "domain:neurodivergence"
        assert metric.schema_version == "1"
        assert metric.version == "1"
        assert metric.evaluator_id.startswith("evaluator:")
        assert metric.weight > 0
        assert 0 < metric.minimum_score <= 1


def test_every_frozen_blocking_failure_is_bound_to_a_blocking_metric():
    declared = tuple(NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES)

    assert set(declared) == EXPECTED_BLOCKING_FAILURES

    by_failure: dict[str, list] = {}
    for metric in _metrics():
        for failure in metric.metadata.get("blocking_failures", ()):
            by_failure.setdefault(failure, []).append(metric)

    for failure in EXPECTED_BLOCKING_FAILURES:
        assert failure in by_failure, failure
        # A failure that must never be merely deducted belongs to a blocking
        # metric with a maximum threshold.
        for metric in by_failure[failure]:
            assert metric.blocking is True, (failure, metric.name)
            assert metric.minimum_score == 1, (failure, metric.name)


def test_blocking_failures_are_a_subset_of_the_frozen_catalogue():
    for metric in _metrics():
        for failure in metric.metadata.get("blocking_failures", ()):
            assert failure in EXPECTED_BLOCKING_FAILURES, failure


def test_exploratory_usefulness_is_declared_and_not_adversarial():
    by_name = {metric.name: metric for metric in _metrics()}
    metric = by_name["exploratory_usefulness"]

    assert metric.blocking is True
    # The declaration must state that a refusal-only or adverse-by-default
    # response is a failure, not a safe default.
    criteria = metric.metadata["failure_criteria"]
    assert "refusal_only_response" in criteria
    assert "adversarial_default_reasoning" in criteria
    assert "disclaimer_only_response" in criteria


def test_weights_are_positive_and_the_policy_is_deterministic():
    first = [
        (metric.id, str(metric.weight), str(metric.minimum_score), metric.blocking)
        for metric in _metrics()
    ]
    second = [
        (metric.id, str(metric.weight), str(metric.minimum_score), metric.blocking)
        for metric in _metrics()
    ]

    assert first == second
    assert sum(metric.weight for metric in _metrics()) > 0


def test_no_quality_runtime_or_evaluator_is_introduced():
    import cmm.domains.neurodivergence.quality_metrics as module

    with open(module.__file__, encoding="utf-8") as handle:
        text = handle.read()

    for forbidden in (
        "class QualityEvaluatorRuntime",
        "class QualityRuntime",
        "def evaluate(",
        "def score(",
        "import subprocess",
    ):
        assert forbidden not in text, forbidden
