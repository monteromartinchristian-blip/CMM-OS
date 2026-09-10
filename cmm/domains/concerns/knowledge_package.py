"""Phase 10.49 – ``domain:concerns`` knowledge package schema.

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

__all__ = ["build_concerns_knowledge_package_schema"]


def build_concerns_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:concerns`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:concerns",
        domain_id=DomainId(slug="concerns"),
        version="1",
        required_sections=("objective",),
        # Concerns discipline. Canonical Concerns semantics require the support
        # process to keep what is not known visible (`contextual_question`,
        # `uncertainty_preservation`) and never to force closure. A Concerns
        # package must therefore record its missing information explicitly,
        # while uncertainty and contradictions stay visible and no factual
        # section is required.
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="observations",
                allowed_knowledge_kinds=(KnowledgeKind.OBSERVATION,),
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
                field_name="missing_information",
                required_non_empty=True,
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="contradictions",
                preserve_contradictions=True,
            ),
        ),
        minimum_sensitivity=SensitivityLevel.SENSITIVE,
    )
