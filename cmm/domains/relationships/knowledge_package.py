"""Phase 10.49 – ``domain:relationships`` knowledge package schema.

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

__all__ = ["build_relationships_knowledge_package_schema"]


def build_relationships_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:relationships`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:relationships",
        domain_id=DomainId(slug="relationships"),
        version="1",
        required_sections=("objective",),
        # Relationships discipline. Canonical Relationships semantics separate
        # observed behaviour from user interpretation (`separate_facts_
        # interpretations`) and forbid inferring intent (`do_not_infer_intent`).
        # Observed interaction evidence must therefore retain its provenance,
        # while the Domain deliberately does not force factual certainty:
        # ambivalence and hypotheses are legitimate (`ambivalence_preservation`,
        # `pattern_without_certainty`).
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
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
