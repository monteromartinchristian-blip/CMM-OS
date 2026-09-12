"""Phase 10.52 — Mental Health quality metric tests.

Quality declarations use the existing Phase 10.48 contract and make every
required unacceptable outcome blocking.  No quality evaluator runtime exists.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.mental_health.quality_metrics import (
    build_mental_health_quality_metrics,
)
from cmm.domains.quality_contracts import DomainQualityMetric

_REQUIRED_BLOCKING_DIMENSIONS = {
    "health-authority-boundary-fidelity",
    "epistemic-separation",
    "provenance-fidelity",
    "privacy-adherence",
    "safety-proportionality",
    "sensitive-memory-proposal-discipline",
    "non-pathologizing-behavior",
    "cross-domain-minimization",
}


def _metrics():
    return build_mental_health_quality_metrics()


def test_metrics_are_canonical_and_domain_owned():
    metrics = _metrics()
    assert metrics
    for metric in metrics:
        assert isinstance(metric, DomainQualityMetric)
        assert str(metric.domain_id) == "domain:mental-health"
        assert metric.schema_version == "1"
        assert metric.version == "1"
        assert metric.evaluator_id.startswith("evaluator:")
        assert Decimal(0) < metric.minimum_score <= Decimal(1)


def test_metric_identities_are_unique_and_order_is_stable():
    ids = [metric.id for metric in _metrics()]
    assert len(ids) == len(set(ids))
    assert [metric.id for metric in build_mental_health_quality_metrics()] == ids


def test_required_unacceptable_outcomes_are_blocking():
    blocking = {metric.name for metric in _metrics() if metric.blocking}
    assert _REQUIRED_BLOCKING_DIMENSIONS <= blocking


def test_blocking_metrics_forbid_full_authority_failures():
    by_name = {metric.name: metric for metric in _metrics()}
    # Invented diagnosis / treatment-medication change / Health violation.
    assert by_name["health-authority-boundary-fidelity"].minimum_score == Decimal(
        "1.00"
    )
    # Unauthorized sensitive transfer or persistence.
    assert by_name["privacy-adherence"].minimum_score == Decimal("1.00")
    assert by_name["sensitive-memory-proposal-discipline"].minimum_score == Decimal(
        "1.00"
    )
    # Interpretation promoted to fact / therapy provenance loss.
    assert by_name["epistemic-separation"].blocking is True
    assert by_name["provenance-fidelity"].blocking is True
    # Emergency escalation without material basis.
    assert by_name["safety-proportionality"].blocking is True


def test_declaration_is_deterministic():
    assert (
        build_mental_health_quality_metrics() == build_mental_health_quality_metrics()
    )


def test_no_quality_evaluator_runtime_is_attached():
    for metric in _metrics():
        assert not hasattr(metric, "evaluate")
        assert not hasattr(metric, "run")
