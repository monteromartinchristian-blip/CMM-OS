"""Phase 10.49 – ``domain:mental-health`` knowledge package schema.

A local, pure declaration narrowing the canonical Phase 8
:class:`cmm.cognitive.knowledge_packages.KnowledgePackage`.  No I/O, no
model/provider calls, no registry mutation, no knowledge storage.  No second
Knowledge Package builder is introduced.
"""

from __future__ import annotations

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
)

__all__ = ["build_mental_health_knowledge_package_schema"]


def build_mental_health_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:mental-health`` knowledge package schema.

    Mental Health discipline.  The schema keeps the approved context
    reachable — facts/observations with provenance, interpretations and
    hypotheses explicitly uncertain, contradictions visible, and the active
    emotional objective required — while never collapsing epistemic levels.
    Source-separated therapy evidence and speaker identity are surfaced by the
    resource layer (``therapy_transcript`` / ``therapy_session_note`` carry
    ``speaker_identity_required`` and ``source_identity_required``), so no
    field is hard-required that the canonical construction path cannot
    populate.
    """
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:mental_health",
        domain_id=DomainId(slug="mental-health"),
        version="1",
        required_sections=("objective",),
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
                field_name="contradictions",
                preserve_contradictions=True,
            ),
        ),
        minimum_sensitivity=SensitivityLevel.SENSITIVE,
    )
