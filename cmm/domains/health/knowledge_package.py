"""Phase 10.49 – ``domain:health`` knowledge package schema.

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

__all__ = ["build_health_knowledge_package_schema"]


def build_health_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:health`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:health",
        domain_id=DomainId(slug="health"),
        version="1",
        required_sections=("objective",),
        # Health evidence discipline. Canonical Health semantics distinguish
        # documented information from provenance and require current, sourced
        # clinical information (`clinical_source_priority`, `medical_temporal_
        # validity`). Health packages therefore require documented facts and
        # demand retained provenance and non-unknown temporal scope on both
        # facts and reported observations, while hypotheses stay explicitly
        # uncertain and contradictions stay visible.
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                required_non_empty=True,
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
                require_provenance=True,
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
