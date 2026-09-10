"""Phase 10.49 – ``domain:parenthood`` knowledge package schema.

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

__all__ = ["build_parenthood_knowledge_package_schema"]


def build_parenthood_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:parenthood`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:parenthood",
        domain_id=DomainId(slug="parenthood"),
        version="1",
        required_sections=("objective",),
        # Parenthood discipline. Canonical Parenthood semantics make legal and
        # administrative validity explicitly temporal (`legal_temporal_
        # validity`) and separate medical from legal reasoning, while keeping
        # parental uncertainty visible (`parental_uncertainty`,
        # `uncertainties_and_boundaries`). Recorded facts must retain provenance
        # and non-unknown temporal scope; observations must retain provenance.
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
                require_provenance=True,
                require_temporal_scope=True,
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="observations",
                allowed_knowledge_kinds=(KnowledgeKind.OBSERVATION,),
                require_provenance=True,
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
