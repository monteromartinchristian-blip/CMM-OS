"""Phase 10.52 — Mental Health Domain Resources.

Builds the ten Mental Health resource definitions deterministically using the
shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts.  No resource store is created here: resources are definitions only.

Shared-resource principle: ``conversation``, ``decision``, ``goal`` and
``memory_reference`` reuse the shared cognitive adapters and are never
duplicated just because Mental Health interprets them differently.
``health_projection`` and ``relationship_projection`` are authorized
cross-domain projection boundaries, never a duplication of sibling-domain
state.  ``therapy_transcript`` and ``therapy_session_note`` are
provenance-sensitive: speaker identity and source identity must survive any
use.  ``external_source`` is NOT external-search authorization.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.mental_health.catalog import (
    CANONICAL_MENTAL_HEALTH_RESOURCE_IDS,
    MENTAL_HEALTH_RESOURCE_KINDS,
)
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

__all__ = ["MENTAL_HEALTH_RESOURCE_KINDS", "build_mental_health_resource_definitions"]


def _resource(
    resource_id: str,
    *,
    adapter: str,
    entity_types: tuple[str, ...],
    sensitivity: SensitivityLevel,
    reliability: float,
    effective_date_required: bool = False,
    expiration_required: bool = False,
    metadata: dict | None = None,
) -> DomainResourceDefinition:
    return DomainResourceDefinition(
        id=resource_id,
        kind=resource_id.split(".", 1)[1],
        domain_id="domain:mental-health",
        adapter=adapter,
        entity_types=entity_types,
        default_sensitivity=sensitivity,
        default_reliability=reliability,
        temporal_policy=DomainResourceTemporalPolicy(
            effective_date_required=effective_date_required,
            expiration_required=expiration_required,
            historical_allowed=True,
        ),
        metadata=metadata or {},
    )


def build_mental_health_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the ten Mental Health resource definitions deterministically.

    Definitions are returned in canonical order (catalog order).  Every Mental
    Health resource is **SENSITIVE** and reuses the canonical provenance /
    temporality / reliability / sensitivity contracts rather than bypassing
    them.  No Mental Health-owned persistent store exists.
    """
    by_id = {
        "mental_health.conversation": _resource(
            "mental_health.conversation",
            adapter="cognitive.message",
            entity_types=("emotion", "emotional_objective"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
        "mental_health.therapy_session_note": _resource(
            "mental_health.therapy_session_note",
            adapter="cognitive.document",
            entity_types=("therapy_session", "therapy_topic"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "speaker_identity_required": True,
                "user_provided": True,
            },
        ),
        "mental_health.therapy_transcript": _resource(
            "mental_health.therapy_transcript",
            adapter="cognitive.document",
            entity_types=("therapy_session", "therapy_topic"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "speaker_identity_required": True,
                "source_identity_required": True,
                "verbatim_vs_summary_required": True,
            },
        ),
        "mental_health.user_reflection": _resource(
            "mental_health.user_reflection",
            adapter="cognitive.document",
            entity_types=("emotion", "interpretation", "uncertainty"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
        "mental_health.decision": _resource(
            "mental_health.decision",
            adapter="cognitive.decision",
            entity_types=("decision", "preference"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "mental_health.goal": _resource(
            "mental_health.goal",
            adapter="cognitive.goal",
            entity_types=("preference", "emotional_objective"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "mental_health.memory_reference": _resource(
            "mental_health.memory_reference",
            adapter="cognitive.memory",
            entity_types=("emotion", "coping_pattern", "emotional_loop"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            metadata={
                "memory_integration": True,
                "proposal_only": True,
                "provenance": True,
            },
        ),
        "mental_health.health_projection": _resource(
            "mental_health.health_projection",
            adapter="cognitive.external_projection",
            entity_types=("fact", "observation"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            metadata={
                "cross_domain_projection": True,
                "source_domain": "domain:health",
                "purpose_minimized": True,
                "read_only_projection": True,
            },
        ),
        "mental_health.relationship_projection": _resource(
            "mental_health.relationship_projection",
            adapter="cognitive.external_projection",
            entity_types=("emotion", "trigger"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            metadata={
                "cross_domain_projection": True,
                "source_domain": "domain:relationships",
                "purpose_minimized": True,
                "read_only_projection": True,
            },
        ),
        "mental_health.external_source": _resource(
            "mental_health.external_source",
            adapter="cognitive.external",
            entity_types=("interpretation", "uncertainty"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.3,
            effective_date_required=True,
            expiration_required=True,
            metadata={
                "provenance": True,
                "untrusted": True,
                "external_content": True,
            },
        ),
    }
    return tuple(
        by_id[resource_id] for resource_id in CANONICAL_MENTAL_HEALTH_RESOURCE_IDS
    )
