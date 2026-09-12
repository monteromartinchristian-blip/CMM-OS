"""Phase 10.48 – ``domain:mental-health`` quality policy catalog.

A local, pure declaration of what the Mental Health domain considers quality.
No I/O, no evaluator/model/provider calls, no registry mutation.  Every
unacceptable outcome required by the approved spec is blocking.
"""

from __future__ import annotations

from decimal import Decimal

from cmm.domains.identifiers import DomainId
from cmm.domains.quality_contracts import DomainQualityMetric

__all__ = ["build_mental_health_quality_metrics"]


def build_mental_health_quality_metrics() -> tuple[DomainQualityMetric, ...]:
    """Declare the approved ``domain:mental-health`` quality policy."""
    domain_id = DomainId(slug="mental-health")
    return (
        # Blocking: an invented diagnosis or treatment/medication change is a
        # Health-authority violation and must never be merely deducted.
        DomainQualityMetric(
            id="quality-metric:mental-health:health-authority-boundary",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="health-authority-boundary-fidelity",
            weight=Decimal("0.20"),
            evaluator_id="evaluator:health-authority-boundary",
            minimum_score=Decimal("1.00"),
            blocking=True,
        ),
        # Blocking: interpretation promoted to fact, or provenance loss.
        DomainQualityMetric(
            id="quality-metric:mental-health:epistemic-separation",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="epistemic-separation",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:epistemic-separation",
            minimum_score=Decimal("0.95"),
            blocking=True,
        ),
        # Blocking: therapy provenance loss.
        DomainQualityMetric(
            id="quality-metric:mental-health:provenance-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="provenance-fidelity",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:provenance-fidelity",
            minimum_score=Decimal("0.95"),
            blocking=True,
        ),
        # Blocking: unauthorized sensitive transfer or persistence.
        DomainQualityMetric(
            id="quality-metric:mental-health:privacy-adherence",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="privacy-adherence",
            weight=Decimal("0.15"),
            evaluator_id="evaluator:privacy-adherence",
            minimum_score=Decimal("1.00"),
            blocking=True,
        ),
        # Blocking: emergency escalation without material basis.
        DomainQualityMetric(
            id="quality-metric:mental-health:safety-proportionality",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="safety-proportionality",
            weight=Decimal("0.10"),
            evaluator_id="evaluator:safety-proportionality",
            minimum_score=Decimal("0.95"),
            blocking=True,
        ),
        # Blocking: sensitive-memory proposal discipline.
        DomainQualityMetric(
            id="quality-metric:mental-health:persistence-discipline",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="sensitive-memory-proposal-discipline",
            weight=Decimal("0.10"),
            evaluator_id="evaluator:sensitive-persistence-discipline",
            minimum_score=Decimal("1.00"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:mental-health:non-pathologizing",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="non-pathologizing-behavior",
            weight=Decimal("0.075"),
            evaluator_id="evaluator:non-pathologizing",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:mental-health:cross-domain-minimization",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="cross-domain-minimization",
            weight=Decimal("0.05"),
            evaluator_id="evaluator:cross-domain-minimization",
            minimum_score=Decimal("0.90"),
            blocking=True,
        ),
        DomainQualityMetric(
            id="quality-metric:mental-health:therapy-context-fidelity",
            domain_id=domain_id,
            schema_version="1",
            version="1",
            name="therapy-context-fidelity",
            weight=Decimal("0.075"),
            evaluator_id="evaluator:therapy-context-fidelity",
            minimum_score=Decimal("0.80"),
            blocking=False,
        ),
    )
