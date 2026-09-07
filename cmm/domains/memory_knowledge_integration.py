"""Phase 10.44 — Domain Memory and Knowledge Graph Integration.

Stateless, reference-only Domain-owned integration boundary over Phase 10.18
memory views, Phase 8 Cognitive Layer knowledge semantics, and Phase 9
Agent Runtime update proposals.
"""

from __future__ import annotations

from cmm.domains.errors import (
    DomainMemoryKnowledgeAuthorizationError,
    DomainMemoryKnowledgeProjectionError,
)
from cmm.domains.memory_contracts import (
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryView,
    DomainMemoryViewRequest,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeContradictionRef,
    DomainMemoryKnowledgeIntegrator,
    DomainMemoryKnowledgeInventory,
    DomainMemoryKnowledgePath,
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
    DomainMemoryKnowledgeRelationRef,
)
from cmm.domains.memory_validation import (
    DefaultDomainMemoryIntegrationValidator,
    DomainMemoryIntegrationValidator,
)


def _is_shared_identity(
    ref: DomainMemoryReference,
    request: DomainMemoryKnowledgeProjectionRequest,
) -> bool:
    """Determine if a canonical reference is shared across domains."""
    if len(ref.applicable_domains) >= 2:
        return True
    participating = {str(request.primary_domain)} | {
        str(d) for d in request.supporting_domains
    }
    ref_domains = {str(ref.domain_id)} | {str(d) for d in ref.applicable_domains}
    return len(ref_domains & participating) >= 2


class DefaultDomainMemoryKnowledgeIntegrator(DomainMemoryKnowledgeIntegrator):
    """Default implementation of DomainMemoryKnowledgeIntegrator.

    Stateless coordination over Phase 10.18 memory views and explicit canonical
    inventories. Performs no hidden store lookups and no direct store writes.
    """

    def __init__(
        self,
        *,
        memory_validator: DomainMemoryIntegrationValidator | None = None,
    ) -> None:
        self._memory_validator = (
            memory_validator
            if memory_validator is not None
            else DefaultDomainMemoryIntegrationValidator()
        )

    def project(
        self,
        request: DomainMemoryKnowledgeProjectionRequest,
        *,
        memory_request: DomainMemoryViewRequest,
        view: DomainMemoryView,
        memory_inventory: DomainMemoryReferenceInventory,
        inventory: DomainMemoryKnowledgeInventory,
    ) -> DomainMemoryKnowledgeProjection:
        """Project authorized canonical knowledge over an authorized Phase 10.18 view."""
        # 1. Structural request / view / memory_request coherence
        if request.memory_view_id != view.view_id:
            raise DomainMemoryKnowledgeProjectionError(
                f"memory_view_id mismatch: request={request.memory_view_id}, view={view.view_id}"
            )
        if request.memory_view_digest != view.digest:
            raise DomainMemoryKnowledgeProjectionError(
                f"memory_view_digest mismatch: request={request.memory_view_digest}, view={view.digest}"
            )
        if str(request.primary_domain) != str(view.primary_domain):
            raise DomainMemoryKnowledgeProjectionError(
                f"primary_domain mismatch: request={request.primary_domain}, view={view.primary_domain}"
            )
        if memory_request.request_id != view.request_id:
            raise DomainMemoryKnowledgeProjectionError(
                f"memory_request request_id mismatch: mem_req={memory_request.request_id}, view={view.request_id}"
            )

        # 2. Authority coherence: requested permission decisions must be covered by memory_request
        if not set(request.permission_decision_ids).issubset(
            set(memory_request.permission_decision_ids)
        ):
            raise DomainMemoryKnowledgeAuthorizationError(
                "Requested permission decisions not present in validated memory request"
            )

        # 3. Phase 10.18 view validation
        val_result = self._memory_validator.validate_view(
            view, memory_request, memory_inventory
        )
        if not val_result.is_valid:
            raise DomainMemoryKnowledgeProjectionError(
                f"DomainMemoryView failed validation: {val_result.code}"
            )

        # 4. Identity selection: only view.selected_references
        selected_refs = view.selected_references
        selected_ref_ids = tuple(sorted({r.reference_id for r in selected_refs}))
        excluded_ref_ids = tuple(
            sorted({d.reference_id for d in view.excluded_decisions})
        )

        # Shared identities
        shared_ref_ids: tuple[str, ...] = ()
        if (
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES
            in request.requested_capabilities
        ):
            shared_ref_ids = tuple(
                sorted(
                    {
                        r.reference_id
                        for r in selected_refs
                        if _is_shared_identity(r, request)
                    }
                )
            )

        relation_refs: tuple[DomainMemoryKnowledgeRelationRef, ...] = ()
        timeline_ref_ids: tuple[str, ...] = ()
        unknown_ordering_ids: tuple[str, ...] = ()
        contradiction_refs: tuple[DomainMemoryKnowledgeContradictionRef, ...] = ()
        dependency_paths: tuple[DomainMemoryKnowledgePath, ...] = ()
        impact_paths: tuple[DomainMemoryKnowledgePath, ...] = ()
        proposal_binding_ids: tuple[str, ...] = ()

        return DomainMemoryKnowledgeProjection.create(
            request_id=request.request_id,
            memory_view_id=view.view_id,
            memory_view_digest=view.digest,
            selected_reference_ids=selected_ref_ids,
            shared_identity_reference_ids=shared_ref_ids,
            relation_refs=relation_refs,
            timeline_reference_ids=timeline_ref_ids,
            unknown_ordering_reference_ids=unknown_ordering_ids,
            contradiction_refs=contradiction_refs,
            dependency_paths=dependency_paths,
            impact_paths=impact_paths,
            proposal_binding_ids=proposal_binding_ids,
            excluded_reference_ids=excluded_ref_ids,
        )
