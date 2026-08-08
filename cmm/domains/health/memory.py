"""Phase 10.20 — Health Domain Memory Integration.

Builds **proposal-only** memory views, proposals, and bindings using the real
Phase 10.18 contracts.  Health memory is never written autonomously:
``register_symptom_update`` and other sensitive operations produce a
``DomainMemoryProposalSnapshot`` plus a ``DomainMemoryProposalBinding`` that
link the proposal, view, digest, trace, permissions, and approval references
for the canonical approval path.
"""

from __future__ import annotations

from cmm.domains.health.definition import HEALTH_DOMAIN_ID
from cmm.domains.memory_contracts import (
    _DIGEST_PREFIX_LENGTH,
    DomainMemoryCapability,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryReferenceInventory,
    DomainMemoryValidationResult,
    DomainMemoryView,
    DomainMemoryViewRequest,
    _sha256_digest,
)


def build_health_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple = (),
    candidates: tuple = (),
    permission_decision_ids: tuple[str, ...] = (),
):
    """Build a ``DomainMemoryViewRequest`` for ``domain:health``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=HEALTH_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_health_symptom_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalSnapshot:
    """Build a symptom registration proposal (proposal-only, never applied).

    Sensitive Health memory is never written autonomously: every symptom
    proposal is registered with ``requires_confirmation=True`` and the builder
    exposes no override, so the confirmation invariant (see the profile's
    ``unconfirmed_sensitive_memory_persistence`` prohibition) cannot be
    silently disabled by a caller.
    """
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=True,
    )


def build_health_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory,
) -> DomainMemoryView:
    """Resolve a proposal-only memory view for ``domain:health``.

    Uses the canonical ``DefaultDomainMemoryViewResolver`` so the view is
    content-bound and deterministic.
    """
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_health_symptom_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for a symptom registration.

    The binding links the proposal, view, digest, trace, permissions, and
    approval references using the real Phase 10.18 contract.
    """
    domain_id = view.primary_domain
    content_payload = {
        "domain_id": str(domain_id),
        "trace_id": trace_id,
        "view_id": view.view_id,
        "view_digest": view.content_digest,
        "memory_proposal_ids": [proposal.proposal_id],
        "agent_knowledge_proposal_ids": [],
        "affected_reference_ids": list(proposal.affected_reference_ids),
        "permission_decision_ids": list(permission_decision_ids),
        "approval_request_ids": list(approval_request_ids),
        "approval_decision_ids": list(approval_decision_ids),
    }
    content_digest = _sha256_digest(content_payload)
    binding_id = (
        f"binding:{domain_id}:{trace_id}:{view.view_id}:"
        f"{content_digest[:_DIGEST_PREFIX_LENGTH]}"
    )
    return DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id=domain_id,
        trace_id=trace_id,
        view_id=view.view_id,
        view_digest=view.content_digest,
        memory_proposal_ids=(proposal.proposal_id,),
        agent_knowledge_proposal_ids=(),
        affected_reference_ids=proposal.affected_reference_ids,
        permission_decision_ids=permission_decision_ids,
        approval_request_ids=approval_request_ids,
        approval_decision_ids=approval_decision_ids,
    )


def validate_health_memory_binding(
    *,
    binding: DomainMemoryProposalBinding,
    inventory: DomainMemoryReferenceInventory,
) -> DomainMemoryValidationResult:
    """Validate a proposal binding against a canonical memory reference inventory.

    Delegates exclusively to the Phase 10.18
    ``DefaultDomainMemoryIntegrationValidator`` so no validation rule is
    duplicated here.
    """
    from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator

    return DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding, inventory
    )


__all__ = [
    "build_health_memory_view",
    "build_health_memory_view_request",
    "build_health_symptom_binding",
    "build_health_symptom_proposal",
    "validate_health_memory_binding",
]
