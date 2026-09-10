"""Phase 10.49 – ``domain:oppositions`` knowledge package schema.

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

__all__ = ["build_oppositions_knowledge_package_schema"]


def build_oppositions_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:oppositions`` knowledge package schema."""
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:oppositions",
        domain_id=DomainId(slug="oppositions"),
        version="1",
        required_sections=("objective",),
        # Oppositions discipline. Canonical Oppositions semantics give priority
        # to official call sources (`official_call_priority`) and treat the whole
        # competition state — calls, syllabi, calendars, milestones — as
        # time-bounded (`temporal_validity`, `temporal_state`). Both recorded
        # facts and observed current state must therefore retain provenance or
        # non-unknown temporal scope respectively. Distinct from University,
        # which leaves observations unfenced.
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
        minimum_sensitivity=SensitivityLevel.INTERNAL,
    )
