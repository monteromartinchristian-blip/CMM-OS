"""Phase 10.23 — Opposition Domain Memory Integration.

Builds **proposal-only** memory views, proposals, and bindings using the shared
Phase 10.18 contracts.  Opposition memory is never written autonomously:
analysis produces a ``DomainMemoryProposalSnapshot`` plus a
``DomainMemoryProposalBinding`` that link the proposal, view, digest, trace,
permissions, and approval references for the canonical approval path.

The domain memory policy is read-only (``allow_write=False``), so every
proposal is registered with ``requires_confirmation=True`` and the builder
exposes no override.  Personal memory (``oppositions.memory_entry``) may
preserve user-confirmed context but must never silently become Official
Opposition State or an adopted strategy change.
"""

from __future__ import annotations

from cmm.domains.memory_contracts import (
    DIGEST_PREFIX_LENGTH,
    DomainMemoryCapability,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryReferenceInventory,
    DomainMemoryValidationResult,
    DomainMemoryView,
    DomainMemoryViewRequest,
    sha256_digest,
)
from cmm.domains.oppositions.definition import OPPOSITIONS_DOMAIN_ID


def build_oppositions_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple = (),
    candidates: tuple = (),
    permission_decision_ids: tuple[str, ...] = (),
):
    """Build a ``DomainMemoryViewRequest`` for ``domain:oppositions``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=OPPOSITIONS_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_oppositions_memory_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalSnapshot:
    """Build an opposition observation proposal (proposal-only, never applied).

    Opposition memory is never written autonomously: every proposal is
    registered with ``requires_confirmation=True`` and the builder exposes no
    override.
    """
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=True,
    )


def build_oppositions_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory,
) -> DomainMemoryView:
    """Resolve a proposal-only memory view for ``domain:oppositions``."""
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_oppositions_memory_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for an opposition observation."""
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
    content_digest = sha256_digest(content_payload)
    binding_id = (
        f"binding:{domain_id}:{trace_id}:{view.view_id}:"
        f"{content_digest[:DIGEST_PREFIX_LENGTH]}"
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


def validate_oppositions_memory_binding(
    *,
    binding: DomainMemoryProposalBinding,
    inventory: DomainMemoryReferenceInventory,
) -> DomainMemoryValidationResult:
    """Validate a proposal binding against a canonical memory reference inventory."""
    from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator

    return DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding, inventory
    )


__all__ = [
    "build_oppositions_memory_binding",
    "build_oppositions_memory_proposal",
    "build_oppositions_memory_view",
    "build_oppositions_memory_view_request",
    "validate_oppositions_memory_binding",
]