"""Phase 10.25 — Concerns Domain Resources.

Builds the ten Concerns resource definitions deterministically using the
shared ``DomainResourceDefinition`` and ``DomainResourceTemporalPolicy``
contracts.  No resource store is created here: resources are definitions only.

Shared-resource principle: ``user_message``, ``conversation``, ``note``,
``journal_entry``, ``memory_entry``, ``event``, ``goal`` and ``decision``
reuse the shared cognitive adapters and are never duplicated just because
Concerns interprets them differently.  Resource metadata never creates truth:
a resource existing is not the same as a fact being authoritative,
``memory_entry`` is provenance (not current truth), ``domain_result`` is the
authorized cross-domain projection boundary, and ``external_source`` is NOT
external-search authorization.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_RESOURCE_IDS,
    CONCERNS_RESOURCE_KINDS,
)
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)

__all__ = ["CONCERNS_RESOURCE_KINDS", "build_concerns_resource_definitions"]


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
        domain_id="domain:concerns",
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


def build_concerns_resource_definitions() -> tuple[DomainResourceDefinition, ...]:
    """Build the ten Concerns Domain resource definitions deterministically.

    Definitions are returned in canonical order (catalog order).  Every
    Concerns resource reuses the canonical provenance / temporality /
    reliability / sensitivity contracts.
    """
    by_id = {
        "concerns.conversation": _resource(
            "concerns.conversation",
            adapter="cognitive.conversation",
            entity_types=("concern", "situation", "emotion", "support_need"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "concerns.decision": _resource(
            "concerns.decision",
            adapter="cognitive.goal",
            entity_types=("option", "action"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "candidate_not_adopted": True,
            },
        ),
        "concerns.domain_result": _resource(
            "concerns.domain_result",
            adapter="cognitive.event",
            entity_types=("fact", "evidence", "uncertainty", "risk"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "cross_domain_projection": True,
                "minimal_authorized_projection": True,
                "no_private_store_merge": True,
                "specialized_ownership_preserved": True,
            },
        ),
        "concerns.event": _resource(
            "concerns.event",
            adapter="cognitive.event",
            entity_types=("situation", "trigger", "fact"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True, "user_reported": True},
        ),
        "concerns.external_source": _resource(
            "concerns.external_source",
            adapter="cognitive.note",
            entity_types=("fact", "uncertainty"),
            sensitivity=SensitivityLevel.INTERNAL,
            reliability=0.5,
            metadata={
                "provenance": True,
                "unverified": True,
                "external_search_authorized": False,
                "provenance_not_authorization": True,
            },
        ),
        "concerns.goal": _resource(
            "concerns.goal",
            adapter="cognitive.goal",
            entity_types=("desired_outcome", "option"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            effective_date_required=True,
            metadata={"provenance": True, "temporality": True},
        ),
        "concerns.journal_entry": _resource(
            "concerns.journal_entry",
            adapter="cognitive.note",
            entity_types=(
                "concern",
                "emotion",
                "fear",
                "interpretation",
                "uncertainty",
                "desired_outcome",
            ),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.6,
            effective_date_required=True,
            metadata={
                "provenance": True,
                "temporality": True,
                "user_reported": True,
                "interpretation_heavy": True,
            },
        ),
        "concerns.memory_entry": _resource(
            "concerns.memory_entry",
            adapter="cognitive.memory",
            entity_types=("concern", "emotion", "fear", "support_need", "uncertainty"),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.7,
            metadata={
                "memory_integration": True,
                "proposal_only": True,
                "provenance_not_truth": True,
            },
        ),
        "concerns.note": _resource(
            "concerns.note",
            adapter="cognitive.note",
            entity_types=("concern", "situation", "hypothesis", "option"),
            sensitivity=SensitivityLevel.PERSONAL,
            reliability=0.6,
            metadata={"provenance": True, "user_reported": True},
        ),
        "concerns.user_message": _resource(
            "concerns.user_message",
            adapter="cognitive.message",
            entity_types=(
                "concern",
                "trigger",
                "emotion",
                "fear",
                "support_need",
                "interpretation",
            ),
            sensitivity=SensitivityLevel.SENSITIVE,
            reliability=0.5,
            metadata={"provenance": True, "user_reported": True, "unverified": True},
        ),
    }
    return tuple(
        by_id[resource_id]
        for resource_id in CANONICAL_CONCERNS_RESOURCE_IDS
    )
