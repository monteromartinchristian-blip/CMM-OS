"""Phase 10.48 – ``domain:university`` quality policy catalog.

A local, pure declaration of what the University domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_university_quality_metrics"]


def build_university_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:university`` quality policy."""
    domain_id = DomainId(slug="university")
    return (
        DomainQualityMetric(
            id="quality-metric:university:temporal-correctness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="temporal-correctness",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:temporal-correctness",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:university:constraint-compliance",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="constraint-compliance",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:constraint-compliance",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:university:feasibility",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="feasibility",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:feasibility",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:university:plan-quality",
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
            id="quality-metric:university:factual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="factual-fidelity",
            weight=Decimal("0.10"),
            evaluator_id="evaluator:factual-fidelity",
            minimum_score=Decimal("0.80"),
            blocking=False,
        ),
    )
