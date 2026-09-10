"""Phase 10.48 – ``domain:general`` quality policy catalog.

A local, pure declaration of what the General domain considers quality. No I/O,
no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_general_quality_metrics"]


def build_general_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:general`` quality policy deterministically."""
    domain_id = DomainId(slug="general")
    return (
        DomainQualityMetric(
            id="quality-metric:general:factual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="factual-fidelity",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:factual-fidelity",
            minimum_score=Decimal("0.70"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:general:contextual-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="contextual-fidelity",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:contextual-fidelity",
            minimum_score=Decimal("0.65"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:general:usefulness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="usefulness",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:usefulness",
            minimum_score=Decimal("0.65"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:general:clarity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="clarity",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:clarity",
            minimum_score=Decimal("0.65"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:general:instruction-compliance",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="instruction-compliance",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:instruction-compliance",
            minimum_score=Decimal("0.70"),
            blocking=True,
        ),
    )
