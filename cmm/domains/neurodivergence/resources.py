"""Phase 10.53 — Neurodivergence Domain Resources.

Builds the ten Neurodivergence resource definitions deterministically using the
shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts.  No resource store is created here: resources are definitions only.

Source-authority principle: ``academic_function_context``,
``social_function_context`` and ``differential_overlap_context`` are authorized
cross-domain projection boundaries.  University, Relationships and Mental
Health remain the owners of the facts projected through them; the projection
metadata declares ``purpose_minimized`` / ``read_only_projection`` so an
imported fact is never re-emitted as Neurodivergence-owned truth.

Developmental, assessment and psychometric material stays
provenance-sensitive: source identity, observer identity and temporal
provenance must survive any use, and no resource metadata carries a raw source
body.  Certainty remains attached to every family because a
Neurodivergence claim is only ever as strong as the evidence behind it.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.neurodivergence.catalog import (
    CANONICAL_NEURODIVERGENCE_RESOURCE_IDS,
    NEURODIVERGENCE_RESOURCE_KINDS,
)
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

__all__ = [
    "NEURODIVERGENCE_RESOURCE_KINDS",
    "build_neurodivergence_resource_definitions",
]


def _resource(
    resource_id: str,
    *,
    adapter: str,
    entity_types: tuple[str, ...],
    reliability: float,
    effective_date_required: bool = False,
    expiration_required: bool = False,
    metadata: dict | None = None,
) -> DomainResourceDefinition:
    return DomainResourceDefinition(
        id=resource_id,
        kind=resource_id.split(".", 1)[1],
        domain_id="domain:neurodivergence",
        adapter=adapter,
        entity_types=entity_types,
        # Every Neurodivergence resource defaults to SENSITIVE (spec §9).
        default_sensitivity=SensitivityLevel.SENSITIVE,
        default_reliability=reliability,
        temporal_policy=DomainResourceTemporalPolicy(
            effective_date_required=effective_date_required,
            expiration_required=expiration_required,
            historical_allowed=True,
        ),
        metadata=metadata or {},
    )


def build_neurodivergence_resource_definitions() -> tuple[
    DomainResourceDefinition, ...
]:
    """Build the ten Neurodivergence resource definitions deterministically.

    Definitions are returned in canonical order (catalog order).  Every
    Neurodivergence resource is **SENSITIVE**, uses the canonical provenance /
    temporality / reliability / sensitivity contracts, and never embeds a raw
    private source body.  No Neurodivergence-owned persistent store exists.
    """
    by_id = {
        "neurodivergence.developmental_history": _resource(
            "neurodivergence.developmental_history",
            adapter="cognitive.document",
            entity_types=("developmental_milestone", "developmental_observation"),
            reliability=0.5,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "source_identity_required": True,
                "observer_identity_supported": True,
                "temporal_provenance_required": True,
                "retrospective_report_possible": True,
                "certainty_sensitive": True,
            },
        ),
        "neurodivergence.assessment_records": _resource(
            "neurodivergence.assessment_records",
            adapter="cognitive.record",
            entity_types=("assessment_record", "assessment_question"),
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "source_identity_required": True,
                "assessment_context_required": True,
                "clinical_status_authority_required": True,
                "certainty_sensitive": True,
            },
        ),
        "neurodivergence.psychometric_results": _resource(
            "neurodivergence.psychometric_results",
            adapter="cognitive.test_result",
            entity_types=("psychometric_result", "screening_result"),
            reliability=0.6,
            effective_date_required=True,
            expiration_required=True,
            metadata={
                "provenance": True,
                "source_identity_required": True,
                "instrument_identity_required": True,
                # A score is evidence, never a diagnosis (spec §11.6).
                "screening_is_not_diagnosis": True,
                "certainty_sensitive": True,
            },
        ),
        "neurodivergence.executive_function_context": _resource(
            "neurodivergence.executive_function_context",
            adapter="cognitive.note",
            entity_types=("executive_function_context", "functional_observation"),
            reliability=0.5,
            metadata={
                "provenance": True,
                "user_reported": True,
                "functional_only": True,
                "impairment_claim_requires_impact_evidence": True,
                "certainty_sensitive": True,
            },
        ),
        "neurodivergence.sensory_context": _resource(
            "neurodivergence.sensory_context",
            adapter="cognitive.note",
            entity_types=("sensory_context", "functional_observation"),
            reliability=0.5,
            metadata={
                "provenance": True,
                "user_reported": True,
                "functional_only": True,
                "impairment_claim_requires_impact_evidence": True,
                "certainty_sensitive": True,
            },
        ),
        # Authorized University-owned projection: institutional facts stay
        # University-authoritative and are never rewritten here.
        "neurodivergence.academic_function_context": _resource(
            "neurodivergence.academic_function_context",
            adapter="cognitive.external_projection",
            entity_types=("academic_function_context",),
            reliability=0.7,
            metadata={
                "cross_domain_projection": True,
                "source_domain": "domain:university",
                "purpose_minimized": True,
                "read_only_projection": True,
                "source_authority_preserved": True,
            },
        ),
        # Authorized Relationships-owned projection.
        "neurodivergence.social_function_context": _resource(
            "neurodivergence.social_function_context",
            adapter="cognitive.external_projection",
            entity_types=("social_context",),
            reliability=0.6,
            metadata={
                "cross_domain_projection": True,
                "source_domain": "domain:relationships",
                "purpose_minimized": True,
                "read_only_projection": True,
                "source_authority_preserved": True,
            },
        ),
        "neurodivergence.functional_impact": _resource(
            "neurodivergence.functional_impact",
            adapter="cognitive.note",
            entity_types=("functional_observation",),
            reliability=0.5,
            metadata={
                "provenance": True,
                "functional_only": True,
                # A trait is not by itself clinically significant impairment.
                "trait_function_separation": True,
                "certainty_sensitive": True,
            },
        ),
        "neurodivergence.longitudinal_evidence": _resource(
            "neurodivergence.longitudinal_evidence",
            adapter="cognitive.timeline",
            entity_types=("observation", "developmental_observation"),
            reliability=0.6,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporal_provenance_required": True,
                "current_vs_historical_required": True,
                # No Neurodivergence-owned timeline store exists; this is a
                # reference view over canonical temporal/evidence contracts.
                "independent_timeline_store": False,
                "certainty_sensitive": True,
            },
        ),
        # Authorized Mental Health-owned projection used for differential and
        # overlap reasoning; the emotional context stays Mental-Health-owned.
        "neurodivergence.differential_overlap_context": _resource(
            "neurodivergence.differential_overlap_context",
            adapter="cognitive.external_projection",
            entity_types=("differential_hypothesis", "overlap_hypothesis"),
            reliability=0.6,
            metadata={
                "cross_domain_projection": True,
                "source_domain": "domain:mental-health",
                "purpose_minimized": True,
                "read_only_projection": True,
                "source_authority_preserved": True,
                "overlap_is_not_co_diagnosis": True,
            },
        ),
    }
    return tuple(
        by_id[resource_id] for resource_id in CANONICAL_NEURODIVERGENCE_RESOURCE_IDS
    )
