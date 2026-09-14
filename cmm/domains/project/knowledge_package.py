"""Phase 10.49 – ``domain:project`` knowledge package schema.

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

__all__ = ["build_project_knowledge_package_schema"]


def build_project_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:project`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:project",
        domain_id=DomainId(slug="project"),
        version="1",
        required_sections=("objective",),
        # Project discipline. Canonical Project semantics require progress to
        # be evidenced (`progress_evidence`) and separate decisions, risks and
        # open dependencies from raw source material. Recorded facts and
        # observed project state must therefore retain provenance, and
        # non-categorised knowledge is limited to decisions and open questions.
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
            DomainKnowledgePackageFieldPolicy(
                field_name="other_knowledge",
                allowed_knowledge_kinds=(
                    KnowledgeKind.DECISION,
                    KnowledgeKind.QUESTION,
                ),
            ),
            DomainKnowledgePackageFieldPolicy(
                field_name="contradictions",
                preserve_contradictions=True,
            ),
        ),
        minimum_sensitivity=SensitivityLevel.INTERNAL,
    )
