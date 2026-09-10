"""Phase 10.48 – ``domain:oppositions`` quality policy catalog.

A local, pure declaration of what the Oppositions domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_oppositions_quality_metrics"]


def build_oppositions_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:oppositions`` quality policy."""
    domain_id = DomainId(slug="oppositions")
    return (
        DomainQualityMetric(
            id="quality-metric:oppositions:official-source-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="official-source-fidelity",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:official-source-fidelity",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:oppositions:temporal-correctness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="temporal-correctness",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:temporal-correctness",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:oppositions:requirement-precision",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="requirement-precision",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:requirement-precision",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:oppositions:contextual-continuity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="contextual-continuity",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:contextual-continuity",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:oppositions:usefulness",
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
