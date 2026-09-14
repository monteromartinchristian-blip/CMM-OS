"""Phase 10.48 – ``domain:health`` quality policy catalog.

A local, pure declaration of what the Health domain considers quality. No I/O,
no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_health_quality_metrics"]


def build_health_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:health`` quality policy deterministically."""
    domain_id = DomainId(slug="health")
    return (
        DomainQualityMetric(
            id="quality-metric:health:factual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="factual-fidelity",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:factual-fidelity",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:health:prudence",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="prudence",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:prudence",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:health:temporal-correctness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="temporal-correctness",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:temporal-correctness",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:health:privacy-compliance",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="privacy-compliance",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:privacy-compliance",
            minimum_score=Decimal("0.95"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:health:contextual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="contextual-fidelity",
            weight=Decimal("0.10"),
            evaluator_id="evaluator:contextual-fidelity",
            minimum_score=Decimal("0.80"),
            blocking=False,
        ),
    )
