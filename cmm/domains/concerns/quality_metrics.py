"""Phase 10.48 – ``domain:concerns`` quality policy catalog.

A local, pure declaration of what the Concerns domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_concerns_quality_metrics"]


def build_concerns_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:concerns`` quality policy."""
    domain_id = DomainId(slug="concerns")
    return (
        DomainQualityMetric(
            id="quality-metric:concerns:contextual-understanding",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="contextual-understanding",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:contextual-understanding",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:concerns:support-need-calibration",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="support-need-calibration",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:support-need-calibration",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:concerns:epistemic-separation",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="epistemic-separation",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:epistemic-separation",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:concerns:reassurance-calibration",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="reassurance-calibration",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:reassurance-calibration",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:concerns:proportional-risk",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="proportional-risk",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:proportional-risk",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:concerns:useful-questioning",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="useful-questioning",
            weight=Decimal("0.10"),
            evaluator_id="evaluator:useful-questioning",
            minimum_score=Decimal("0.70"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:concerns:non-pathologizing-recurrence",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="non-pathologizing-recurrence",
            weight=Decimal("0.075"),
            evaluator_id="evaluator:non-pathologizing-recurrence",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:concerns:user-agency",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="user-agency",
            weight=Decimal("0.075"),
            evaluator_id="evaluator:user-agency",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
    )
