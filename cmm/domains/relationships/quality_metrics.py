"""Phase 10.48 – ``domain:relationships`` quality policy catalog.

A local, pure declaration of what the Relationships domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_relationships_quality_metrics"]


def build_relationships_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:relationships`` quality policy."""
    domain_id = DomainId(slug="relationships")
    return (
        DomainQualityMetric(
            id="quality-metric:relationships:ambiguity-handling",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="ambiguity-handling",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:ambiguity-handling",
            minimum_score=Decimal("0.80"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:relationships:contextual-continuity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="contextual-continuity",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:contextual-continuity",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:relationships:non-attribution-of-intent",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="non-attribution-of-intent",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:non-attribution-of-intent",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:relationships:uncertainty-preservation",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="uncertainty-preservation",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:uncertainty-preservation",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:relationships:usefulness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="usefulness",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:usefulness",
            minimum_score=Decimal("0.70"),
            blocking=False,
        ),
    )
