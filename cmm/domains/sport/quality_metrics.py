"""Phase 10.48 – ``domain:sport`` quality policy catalog.

A local, pure declaration of what the Sport domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_sport_quality_metrics"]


def build_sport_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:sport`` quality policy."""
    domain_id = DomainId(slug="sport")
    return (
        DomainQualityMetric(
            id="quality-metric:sport:factual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="factual-fidelity",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:factual-fidelity",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:sport:temporal-correctness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="temporal-correctness",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:temporal-correctness",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:sport:plan-quality",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="plan-quality",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:plan-quality",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:sport:usefulness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="usefulness",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:usefulness",
            minimum_score=Decimal("0.70"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:sport:instruction-compliance",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="instruction-compliance",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:instruction-compliance",
            minimum_score=Decimal("0.75"),
            blocking=True,
        ),
    )
