"""Phase 10.49 – ``domain:languages`` knowledge package schema.

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

__all__ = ["build_languages_knowledge_package_schema"]


def build_languages_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:languages`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:languages",
        domain_id=DomainId(slug="languages"),
        version="1",
        required_sections=("objective",),
        # Languages discipline. Canonical Languages semantics require every
        # proficiency claim to be evidenced (`language_level_evidence`,
        # `progression_evidence`) and distinguish certified proficiency from
        # estimated proficiency and observed performance. Recorded facts and
        # observed performance must therefore retain provenance. Languages has
        # no contradiction rule in its canonical rule set, so it does not
        # inherit contradiction preservation automatically.
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
                require_provenance=True,
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
        ),
        minimum_sensitivity=SensitivityLevel.INTERNAL,
    )
