"""Phase 10.48 – ``domain:project`` quality policy catalog.

A local, pure declaration of what the Project domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_project_quality_metrics"]


def build_project_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:project`` quality policy."""
    domain_id = DomainId(slug="project")
    return (
        DomainQualityMetric(
            id="quality-metric:project:correctness",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="correctness",
            weight=Decimal("0.25"),
            evaluator_id="evaluator:correctness",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:project:architectural-consistency",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="architectural-consistency",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:architectural-consistency",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:project:validation-quality",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="validation-quality",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:validation-quality",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:project:tool-calling-quality",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="tool-calling-quality",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:tool-calling-quality",
            minimum_score=Decimal("0.85"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:project:structured-output",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="structured-output",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:structured-output",
            minimum_score=Decimal("0.80"),
            blocking=False,
        ),
    )
