"""Phase 10.45 — Domain Interface Integration.

Thin, stateless, interface-neutral integration boundary over canonical Domain
Intelligence authority. ``project()`` verifies canonical coherence and returns
immutable interface projections; selector intents (added in later blocks)
delegate only to existing canonical authority.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import DomainCompositionStatus, DomainResolutionStatus
from cmm.domains.errors import DomainInterfaceAuthorityError
from cmm.domains.interface_integration_contracts import (
    DomainInterfaceProjection,
    DomainInterfaceProjectionRequest,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeProjection,
)
from cmm.domains.presentation_contracts import DomainPresentationPlan
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.session_contracts import DomainSessionContext

__all__ = [
    "DefaultDomainInterfaceIntegrator",
    "DomainInterfaceIntegrator",
]


@runtime_checkable
class DomainInterfaceIntegrator(Protocol):
    """Stateless interface projection authority."""

    def project(
        self,
        *,
        request: DomainInterfaceProjectionRequest,
        resolution: DomainResolutionResult,
        composition: DomainComposition,
        presentation: DomainPresentationPlan | None = None,
        session: DomainSessionContext | None = None,
        memory_knowledge: DomainMemoryKnowledgeProjection | None = None,
    ) -> DomainInterfaceProjection:
        raise NotImplementedError


def _validate_authority(
    *,
    request: DomainInterfaceProjectionRequest,
    resolution: DomainResolutionResult,
    composition: DomainComposition,
    presentation: DomainPresentationPlan | None,
    session: DomainSessionContext | None,
    memory_knowledge: DomainMemoryKnowledgeProjection | None,
) -> None:
    """Verify exact canonical authority coherence, failing closed on any doubt."""
    if type(resolution) is not DomainResolutionResult:
        raise DomainInterfaceAuthorityError(
            "resolution must be a canonical DomainResolutionResult"
        )
    if resolution.status is not DomainResolutionStatus.RESOLVED:
        raise DomainInterfaceAuthorityError(
            "resolution must be RESOLVED for interface projection"
        )
    if type(composition) is not DomainComposition:
        raise DomainInterfaceAuthorityError(
            "composition must be a canonical DomainComposition"
        )
    if composition.status not in (
        DomainCompositionStatus.COMPOSED,
        DomainCompositionStatus.PARTIAL,
    ):
        raise DomainInterfaceAuthorityError(
            "composition status must be COMPOSED or PARTIAL"
        )
    if request.resolution_reference_id != resolution.id:
        raise DomainInterfaceAuthorityError("resolution reference mismatch")
    if request.composition_reference_id != composition.id:
        raise DomainInterfaceAuthorityError("composition reference mismatch")
    if composition.resolution_id != resolution.id:
        raise DomainInterfaceAuthorityError("composition resolution mismatch")
    if resolution.primary_domain is None or str(composition.primary_domain) != str(
        resolution.primary_domain
    ):
        raise DomainInterfaceAuthorityError(
            "resolution and composition primary domains diverge"
        )
    if frozenset(str(d) for d in composition.supporting_domains) != frozenset(
        str(d) for d in resolution.supporting_domains
    ):
        raise DomainInterfaceAuthorityError(
            "composition supporting domains diverge from resolution"
        )
    if presentation is not None and type(presentation) is not DomainPresentationPlan:
        raise DomainInterfaceAuthorityError(
            "presentation must be a canonical DomainPresentationPlan"
        )
    if presentation is not None and presentation.composition_id != composition.id:
        raise DomainInterfaceAuthorityError("presentation composition binding mismatch")
    if session is not None:
        if type(session) is not DomainSessionContext:
            raise DomainInterfaceAuthorityError(
                "session must be a canonical DomainSessionContext"
            )
        if (
            request.session_reference_id is None
            or session.session_id != request.session_reference_id
        ):
            raise DomainInterfaceAuthorityError("session reference mismatch")
    if (
        memory_knowledge is not None
        and type(memory_knowledge) is not DomainMemoryKnowledgeProjection
    ):
        raise DomainInterfaceAuthorityError(
            "memory_knowledge must be a canonical DomainMemoryKnowledgeProjection"
        )


class DefaultDomainInterfaceIntegrator:
    """Default implementation of ``DomainInterfaceIntegrator``.

    Stateless: ``project()`` performs no store lookups and no writes. View
    assembly blocks are added incrementally over canonical inputs only.
    """

    def __init__(self) -> None:
        pass

    def project(
        self,
        *,
        request: DomainInterfaceProjectionRequest,
        resolution: DomainResolutionResult,
        composition: DomainComposition,
        presentation: DomainPresentationPlan | None = None,
        session: DomainSessionContext | None = None,
        memory_knowledge: DomainMemoryKnowledgeProjection | None = None,
    ) -> DomainInterfaceProjection:
        _validate_authority(
            request=request,
            resolution=resolution,
            composition=composition,
            presentation=presentation,
            session=session,
            memory_knowledge=memory_knowledge,
        )
        return DomainInterfaceProjection(
            projection_id=f"interface-projection:{request.request_id}",
            request_id=request.request_id,
            resolution_reference_id=resolution.id,
            composition_reference_id=composition.id,
            session_reference_id=request.session_reference_id,
            conversational=None,
            selector=None,
            domain_center=None,
            cross_domain=None,
            review_center=None,
            content_digest="",
        )
