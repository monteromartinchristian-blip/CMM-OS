"""Phase 10.48 – ``domain:life-plan`` quality policy catalog.

A local, pure declaration of what the Life Plan domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_life_plan_quality_metrics"]


def build_life_plan_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:life-plan`` quality policy."""
    domain_id = DomainId(slug="life-plan")
    return (
        DomainQualityMetric(
            id="quality-metric:life-plan:contextual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="contextual-fidelity",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:contextual-fidelity",
            minimum_score=Decimal("0.80"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:life-plan:feasibility",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="feasibility",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:feasibility",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:life-plan:tradeoff-quality",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="tradeoff-quality",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:tradeoff-quality",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:life-plan:temporal-correctness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="temporal-correctness",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:temporal-correctness",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:life-plan:plan-quality",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="plan-quality",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:plan-quality",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
    )
