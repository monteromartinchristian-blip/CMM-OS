"""Phase 10.49 – ``domain:sport`` knowledge package schema.

A local, pure declaration narrowing the canonical Phase 8
:class:`cmm.cognitive.knowledge_packages.KnowledgePackage`.  No I/O, no
model/provider calls, no registry mutation, no knowledge storage.
"""

from __future__ import annotations

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
)

__all__ = ["build_sport_knowledge_package_schema"]


def build_sport_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:sport`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:sport",
        domain_id=DomainId(slug="sport"),
        version="1",
        required_sections=("objective",),
        # Sport discipline. Canonical Sport semantics track load, readiness and
        # measurement over time (`measurement_trend`, `readiness_snapshot`,
        # `recovery`), so recorded facts and observed current performance both
        # require non-unknown temporal scope, and observed performance must
        # retain its resource provenance. Sport does not claim Health authority
        # (`health_constraint`), so it applies no medical evidence floor and
        # requires no factual section.
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
                require_temporal_scope=True,
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="observations",
                allowed_knowledge_kinds=(KnowledgeKind.OBSERVATION,),
                require_provenance=True,
                require_temporal_scope=True,
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="inferences",
                preserve_uncertainty=True,
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="hypotheses",
                preserve_uncertainty=True,
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="contradictions",
                preserve_contradictions=True,
            ),
        ),
        minimum_sensitivity=SensitivityLevel.SENSITIVE,
    )
