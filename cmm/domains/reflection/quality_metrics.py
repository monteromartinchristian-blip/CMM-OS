"""Phase 10.48 – ``domain:reflection`` quality policy catalog.

A local, pure declaration of what the Reflection domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_reflection_quality_metrics"]


def build_reflection_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:reflection`` quality policy."""
    domain_id = DomainId(slug="reflection")
    return (
        DomainQualityMetric(
            id="quality-metric:reflection:epistemic-separation",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="epistemic-separation",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:epistemic-separation",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:reflection:ambiguity-preservation",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="ambiguity-preservation",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:ambiguity-preservation",
            minimum_score=Decimal("0.75"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:reflection:contextual-continuity",
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
            id="quality-metric:reflection:depth",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="depth",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:depth",
            minimum_score=Decimal("0.65"),
            blocking=False,
        ),
        DomainQualityMetric(
            id="quality-metric:reflection:user-agency",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="user-agency",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:user-agency",
            minimum_score=Decimal("0.80"),
            blocking=True,
        ),
    )
