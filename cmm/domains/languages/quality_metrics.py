"""Phase 10.48 – ``domain:languages`` quality policy catalog.

A local, pure declaration of what the Languages domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_languages_quality_metrics"]


def build_languages_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:languages`` quality policy."""
    domain_id = DomainId(slug="languages")
    return (
        DomainQualityMetric(
            id="quality-metric:languages:linguistic-correctness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="linguistic-correctness",
            weight=Decimal("0.30"),
            evaluator_id="evaluator:linguistic-correctness",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:languages:level-alignment",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="level-alignment",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:level-alignment",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:languages:instruction-compliance",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="instruction-compliance",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:instruction-compliance",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:languages:usefulness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="usefulness",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:usefulness",
            minimum_score=Decimal("0.70"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:languages:clarity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="clarity",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:clarity",
            minimum_score=Decimal("0.70"),
            blocking=False,
        ),
    )
