"""Phase 10.49 – ``domain:neurodivergence`` knowledge package schema.

A local, pure declaration narrowing the canonical Phase 8
:class:`cmm.cognitive.knowledge_packages.KnowledgePackage`.  No I/O, no
model/provider calls, no registry mutation, no knowledge storage.  No second
Knowledge Package builder is introduced and no second global knowledge kind is
defined.

The schema keeps the approved reasoning context reachable — the active
objective, the developmental timeline, evidence by source and period, confirmed
information, in-evaluation information, working hypotheses, contradictory or
insufficient evidence, functional observations, authorized supporting-domain
projections and privacy/permission evidence — while never collapsing epistemic
levels and never making the package a second medical record.

Domain-specific organization is expressed through reachable *section* names
(``developmental_timeline``, ``in_evaluation_information``,
``working_hypotheses``, ``contradictory_or_insufficient_evidence``, …) and
through the canonical Phase 8 fields the builder can actually populate.  No
field is invented that the canonical construction path cannot produce, and no
new knowledge kind is introduced for ``IN EVALUATION`` or ``RULED OUT``.
"""

from __future__ import annotations

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
)

__all__ = ["build_neurodivergence_knowledge_package_schema"]


def build_neurodivergence_knowledge_package_schema() -> DomainKnowledgePackageSchema:
    """Declare the approved ``domain:neurodivergence`` knowledge package schema.

    Only canonical ``KnowledgePackage`` fields are constrained, and no field is
    a hard structural requirement beyond the active objective.  Source- and
    observer-separated, period-separated evidence is surfaced by the resource
    layer (``developmental_history`` carries ``source_identity_required`` and
    ``temporal_provenance_required``; ``longitudinal_evidence`` carries
    ``current_vs_historical_required``), so the package schema preserves the
    discipline without inventing storage.
    """
    return DomainKnowledgePackageSchema(
        id="knowledge-package-schema:neurodivergence",
        domain_id=DomainId(slug="neurodivergence"),
        version="1",
        required_sections=("objective",),
        # Only canonical package sections are declared; each approved
        # Neurodivergence section is made reachable through one of them.
        optional_sections=(
            "timeline",
            "observations",
            "facts",
            "current_state",
            "hypotheses",
            "inferences",
            "contradictions",
            "unknowns",
            "missing_information",
            "other_knowledge",
            "resources",
            "privacy",
        ),
        #: Approved Neurodivergence section -> the canonical package section
        #: that makes it reachable.  This is a documented mapping, not a new
        #: set of field names.
        metadata={
            "phase": "10.53",
            "domain_sections": {
                "active_exploratory_objective": "objective",
                "developmental_timeline": "timeline",
                "evidence_by_source_and_period": "observations",
                "confirmed_information": "facts",
                "in_evaluation_information": "current_state",
                "working_hypotheses": "hypotheses",
                "model_interpretation": "inferences",
                "contradictory_or_insufficient_evidence": "contradictions",
                "unsupported_or_thin_evidence": "unknowns",
                "evidence_that_would_clarify": "missing_information",
                "functional_observations": "other_knowledge",
                "supporting_domain_projections": "resources",
                "privacy_and_permission_evidence": "privacy",
            },
            "second_medical_record": False,
        },
        field_policies=(
            # Confirmed information stays factual and provenance-bound.
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
                require_provenance=True,
            ),
            # Direct observation, retrospective self-report and third-party
            # report all remain observations, separated by their source.  Each
            # observation must retain canonical provenance evidence: a
            # Neurodivergence claim is only as strong as the source behind it.
            DomainKnowledgePackageFieldPolicy(
                field_name="observations",
                allowed_knowledge_kinds=(KnowledgeKind.OBSERVATION,),
                require_provenance=True,
            ),
            # Model interpretation stays an inference, never a fact.
            DomainKnowledgePackageFieldPolicy(
                field_name="inferences",
                preserve_uncertainty=True,
            ),
            # Working hypotheses may never be narrowed to a fact kind and never
            # lose their uncertainty: a hypothesis is not a confirmed status.
            DomainKnowledgePackageFieldPolicy(
                field_name="hypotheses",
                allowed_knowledge_kinds=(
                    KnowledgeKind.HYPOTHESIS,
                    KnowledgeKind.INFERENCE,
                ),
                preserve_uncertainty=True,
            ),
            # Functional observations and other context stay explicitly
            # uncertain rather than hardening into labels.
            DomainKnowledgePackageFieldPolicy(
                field_name="other_knowledge",
                preserve_uncertainty=True,
            ),
            # Competing evidence stays visible.
            DomainKnowledgePackageFieldPolicy(
                field_name="contradictions",
                preserve_contradictions=True,
            ),
        ),
        minimum_sensitivity=SensitivityLevel.SENSITIVE,
    )
