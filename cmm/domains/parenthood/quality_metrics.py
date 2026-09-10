"""Phase 10.48 – ``domain:parenthood`` quality policy catalog.

A local, pure declaration of what the Parenthood domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_parenthood_quality_metrics"]


def build_parenthood_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:parenthood`` quality policy."""
    domain_id = DomainId(slug="parenthood")
    return (
        DomainQualityMetric(
            id="quality-metric:parenthood:factual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="factual-fidelity",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:factual-fidelity",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:parenthood:sensitivity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="sensitivity",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:sensitivity",
            minimum_score=Decimal("0.80"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:parenthood:prudence",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="prudence",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:prudence",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:parenthood:temporal-correctness",
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
            id="quality-metric:parenthood:privacy-compliance",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="privacy-compliance",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:privacy-compliance",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
    )
