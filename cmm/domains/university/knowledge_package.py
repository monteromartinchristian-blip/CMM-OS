"""Phase 10.49 – ``domain:university`` knowledge package schema.

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

__all__ = ["build_university_knowledge_package_schema"]


def build_university_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:university`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:university",
        domain_id=DomainId(slug="university"),
        version="1",
        required_sections=("objective",),
        # University discipline. Canonical University semantics preserve source
        # authority by attribute (`academic_source_authority`) and treat
        # deadlines, regulations and current academic state as temporally valid
        # (`academic_deadline`). Academic facts must therefore retain provenance
        # and non-unknown temporal scope; interpretations stay uncertain and
        # contradictions stay visible. Observations carry no extra floor, so the
        # shape is deliberately distinct from Health.
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
        minimum_sensitivity=SensitivityLevel.INTERNAL,
    )
