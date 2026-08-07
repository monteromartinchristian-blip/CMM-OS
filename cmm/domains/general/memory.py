"""Phase 10.19 — General Domain Memory Integration.

Builds reference-only memory proposals, views, and bindings using the real
Phase 10.18 contracts.  ``general.create_task`` and ``general.update_goal``
produce a ``DomainMemoryProposalSnapshot`` plus a
``DomainMemoryProposalBinding`` that links the proposal, view, digest, trace,
permissions, and approval references.
"""

from __future__ import annotations

from cmm.domains.general.definition import GENERAL_DOMAIN_ID
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


def build_general_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple = (),
    candidates: tuple = (),
    permission_decision_ids: tuple[str, ...] = (),
):
    """Build a ``DomainMemoryViewRequest`` for ``domain:general``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=GENERAL_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_general_task_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
    requires_confirmation: bool = True,
) -> DomainMemoryProposalSnapshot:
    """Build a task creation proposal (reference-only, never applied directly)."""
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=requires_confirmation,
    )


def build_general_goal_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
    requires_confirmation: bool = True,
) -> DomainMemoryProposalSnapshot:
    """Build a goal update proposal (reference-only, never applied directly)."""
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=requires_confirmation,
    )


def build_general_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory,
) -> DomainMemoryView:
    """Resolve a reference-only memory view for ``domain:general``.

    Uses the canonical ``DefaultDomainMemoryViewResolver`` so the view is
    content-bound and deterministic.
    """
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_general_task_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for a task creation proposal.

    The binding links the proposal, view, digest, trace, permissions, and
    approval references using the real Phase 10.18 contract.
    """
    return _build_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
        permission_decision_ids=permission_decision_ids,
        approval_request_ids=approval_request_ids,
        approval_decision_ids=approval_decision_ids,
    )


def build_general_goal_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for a goal update proposal."""
    return _build_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
        permission_decision_ids=permission_decision_ids,
        approval_request_ids=approval_request_ids,
        approval_decision_ids=approval_decision_ids,
    )


def _build_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...],
    approval_request_ids: tuple[str, ...],
    approval_decision_ids: tuple[str, ...],
) -> DomainMemoryProposalBinding:
    """Construct a content-bound ``DomainMemoryProposalBinding``.

    The binding_id follows the canonical format
    ``binding:<domain_id>:<trace_id>:<view_id>:<digest_prefix>`` where the
    digest prefix is derived from the binding content.
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


def validate_general_memory_binding(
    *,
    binding: DomainMemoryProposalBinding,
    inventory: DomainMemoryReferenceInventory,
) -> DomainMemoryValidationResult:
    """Validate a proposal binding against a canonical memory reference inventory.

    Delegates exclusively to the Phase 10.18 ``DefaultDomainMemoryIntegrationValidator``
    so no validation rule is duplicated here.
    """
    from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator

    return DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding, inventory
    )


__all__ = [
    "build_general_goal_binding",
    "build_general_goal_proposal",
    "build_general_memory_view",
    "build_general_memory_view_request",
    "build_general_task_binding",
    "build_general_task_proposal",
    "validate_general_memory_binding",
]