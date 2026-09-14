"""Phase 10.53 — Neurodivergence Domain Memory Integration.

Builds **proposal-only** memory views, proposals and bindings using the shared
Phase 10.18 contracts.  Neurodivergence memory is never written autonomously:
analysis produces a ``DomainMemoryProposalSnapshot`` plus a
``DomainMemoryProposalBinding`` that link the proposal, view, digest, trace,
permissions and approval references for the canonical approval path.

The profile memory policy is read-only (``allow_write=False``), so every
proposal is registered with ``requires_confirmation=True`` and the builder
exposes no override.

A **working hypothesis** may be proposed for memory.  It is never applied by
this pack, it keeps its hypothesis status, and it is never persisted silently.
Content kinds that would assert a clinical status (a confirmed diagnosis, a
psychiatric label, a medication or treatment change, a rewritten source
authority) can never be proposed at all.

``READ != PROPOSE != APPROVE != APPLY != INVALIDATE != DELETE``.  No
Neurodivergence memory store exists.
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
from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_DOMAIN_ID
from cmm.domains.neurodivergence.rules import is_persistence_restricted_content


class NeurodivergenceMemoryPolicyError(ValueError):
    """Raised when a proposal request would violate the persistence invariant."""


def build_neurodivergence_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple = (),
    candidates: tuple = (),
    permission_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryViewRequest:
    """Build a ``DomainMemoryViewRequest`` for ``domain:neurodivergence``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=NEURODIVERGENCE_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_neurodivergence_memory_proposal(
    *,
    proposal_id: str,
    content_kind: str | None = None,
    affected_reference_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalSnapshot:
    """Build a sensitive-content proposal (proposal-only, never applied).

    Neurodivergence memory is never written autonomously: every proposal is
    registered with ``requires_confirmation=True`` and the builder exposes no
    override.  Content kinds that assert clinical status can never be proposed
    for persistence at all; working hypotheses can be proposed but remain
    proposals pending the canonical approval path.
    """
    if content_kind is not None and is_persistence_restricted_content(content_kind):
        raise NeurodivergenceMemoryPolicyError(
            "restricted content must not be proposed for persistence: "
            + str(content_kind)
        )
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=True,
    )


def build_neurodivergence_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory,
) -> DomainMemoryView:
    """Resolve a proposal-only memory view for ``domain:neurodivergence``."""
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_neurodivergence_memory_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for a sensitive update."""
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


def validate_neurodivergence_memory_binding(
    *,
    binding: DomainMemoryProposalBinding,
    inventory: DomainMemoryReferenceInventory,
) -> DomainMemoryValidationResult:
    """Validate a proposal binding against a canonical memory inventory.

    Delegates exclusively to the Phase 10.18
    ``DefaultDomainMemoryIntegrationValidator`` so no validation rule is
    duplicated here and a malformed or unauthorized affected-reference
    inventory fails closed.  A revoked permission decision therefore
    invalidates a stale binding instead of leaving it authorized.
    """
    from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator

    return DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding, inventory
    )


__all__ = [
    "NeurodivergenceMemoryPolicyError",
    "build_neurodivergence_memory_binding",
    "build_neurodivergence_memory_proposal",
    "build_neurodivergence_memory_view",
    "build_neurodivergence_memory_view_request",
    "validate_neurodivergence_memory_binding",
]
