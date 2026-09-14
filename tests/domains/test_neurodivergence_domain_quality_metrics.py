"""Phase 10.53 — Neurodivergence quality metric declaration tests.

Declarative Phase 10.48 quality policy only.  No evaluator resolves, no model
runs and no runtime is introduced: the pack declares what would make an output
unacceptable, and every unacceptable outcome required by the approved spec is
blocking.

The canonical ``DomainQualityMetric`` carries empty metadata, so the blocking
failure catalogue is asserted at the module-policy level and every failure must
be owned by a blocking metric with a maximum threshold.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.neurodivergence.quality_metrics import (
    NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES,
    NEURODIVERGENCE_METRIC_BLOCKING_FAILURES,
    NEURODIVERGENCE_QUALITY_FAILURE_CRITERIA,
    NEURODIVERGENCE_QUALITY_METRIC_NAMES,
    build_neurodivergence_quality_metrics,
)

#: The frozen metric topics required by the approved plan (Task 6, Step 5),
#: expressed in the canonical slug form (spec topic ``x_y`` -> slug ``x-y``).
EXPECTED_TOPICS = (
    "certainty-fidelity",
    "source-authority-fidelity",
    "developmental-temporality",
    "differential-reasoning-quality",
    "exploratory-usefulness",
    "functional-relevance",
    "cross-domain-minimization",
    "privacy-adherence",
    "sensitive-memory-discipline",
    "assessment-summary-fidelity",
)

#: The frozen blocking failures required by the approved plan/spec.
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
    assert NEURODIVERGENCE_QUALITY_METRIC_NAMES == EXPECTED_TOPICS
    assert len(metrics) == 10


def test_metric_identity_is_canonical():
    for metric in _metrics():
        assert metric.id == f"quality-metric:neurodivergence:{metric.name}"
        assert str(metric.domain_id) == "domain:neurodivergence"
        assert metric.schema_version == "1"
        assert metric.version == "1"
        assert metric.evaluator_id == f"evaluator:{metric.name}"
        assert metric.weight > 0
        assert 0 < metric.minimum_score <= 1
        # A canonical first-party metric carries no local metadata: the policy
        # is the declaration itself, never a hidden side table.
        assert metric.metadata == {}


def test_weights_sum_to_exactly_one():
    total = sum((metric.weight for metric in _metrics()), Decimal(0))

    assert total == Decimal(1)


def test_every_frozen_blocking_failure_is_owned_by_a_blocking_metric():
    assert set(NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES) == (
        EXPECTED_BLOCKING_FAILURES
    )

    by_name = {metric.name: metric for metric in _metrics()}
    owned: set[str] = set()
    for metric_name, failures in NEURODIVERGENCE_METRIC_BLOCKING_FAILURES.items():
        assert metric_name in by_name, metric_name
        metric = by_name[metric_name]
        # A failure that must never be merely deducted belongs to a blocking
        # metric with a maximum threshold.
        assert metric.blocking is True, metric_name
        assert metric.minimum_score == 1, metric_name
        owned.update(failures)

    assert owned == EXPECTED_BLOCKING_FAILURES


def test_no_blocking_failure_is_left_unassigned():
    for failure in NEURODIVERGENCE_BLOCKING_QUALITY_FAILURES:
        owners = [
            metric_name
            for metric_name, failures in (
                NEURODIVERGENCE_METRIC_BLOCKING_FAILURES.items()
            )
            if failure in failures
        ]
        assert owners, failure


def test_owned_failures_are_a_subset_of_the_frozen_catalogue():
    for failures in NEURODIVERGENCE_METRIC_BLOCKING_FAILURES.values():
        for failure in failures:
            assert failure in EXPECTED_BLOCKING_FAILURES, failure
    for criteria in NEURODIVERGENCE_QUALITY_FAILURE_CRITERIA.values():
        assert criteria


def test_exploratory_usefulness_is_declared_and_not_adversarial():
    by_name = {metric.name: metric for metric in _metrics()}
    metric = by_name["exploratory-usefulness"]

    assert metric.blocking is True
    # The declaration must state that a refusal-only or adverse-by-default
    # response is a failure, not a safe default.
    criteria = NEURODIVERGENCE_QUALITY_FAILURE_CRITERIA["exploratory-usefulness"]
    assert "refusal_only_response" in criteria
    assert "disclaimer_only_response" in criteria
    assert "no_hypothesis_offered_for_an_exploratory_request" in criteria


def test_developmental_temporality_names_its_failure_modes():
    criteria = NEURODIVERGENCE_QUALITY_FAILURE_CRITERIA["developmental-temporality"]

    assert "historical_observation_generalized_to_current_impairment" in criteria
    assert "current_difficulty_generalized_to_lifelong_pattern" in criteria
    assert "retrospective_report_presented_as_contemporaneous" in criteria


def test_factory_is_deterministic():
    assert _metrics() == _metrics()


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
