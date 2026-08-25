"""Phase 10.29 — Life Plan Domain Memory Integration.

Builds proposal-only memory views, proposals, and bindings using the shared
Phase 10.18 contracts. Life Plan memory is never written directly or autonomously:
reasoning operations produce a ``DomainMemoryProposalSnapshot`` plus a
``DomainMemoryProposalBinding`` that link the proposal, view, digest, trace,
permissions, and approval references for the canonical approval path.

Every proposal is registered with ``requires_confirmation=True``.
Prohibits silent persistence of unconfirmed preferences or scenarios as decisions,
unconfirmed commitments, or raw cross-domain clinical/dossier context.
"""

from __future__ import annotations

from typing import Any

from cmm.domains.life_plan.catalog import LIFE_PLAN_DOMAIN_ID
from cmm.domains.memory_contracts import (
    DIGEST_PREFIX_LENGTH,
    DomainMemoryCapability,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryValidationResult,
    DomainMemoryView,
    DomainMemoryViewRequest,
    sha256_digest,
)

CANDIDATE_LIFE_PLAN_LONGITUDINAL_KINDS: tuple[str, ...] = (
    "life_goal",
    "milestone",
    "scenario",
    "dependency",
    "constraint",
    "risk",
    "decision",
    "financial_plan",
    "timeline",
)


def validate_life_plan_memory_proposal_content(content: dict[str, Any]) -> dict[str, Any]:
    """Validate proposal content against Life Plan safety and epistemic boundaries."""
    kind = content.get("kind", "")
    status = str(content.get("status", "")).lower()
    orig = str(content.get("original_status", "")).lower()
    is_conf = content.get("is_confirmed", False)

    # Reject unconfirmed promotion to decision or commitment
    if status in ("decision", "commitment") and not is_conf:
        if orig in ("idea", "preference", "hypothesis", "scenario") or kind == "decision":
            return {
                "is_valid": False,
                "reason": "prohibited_unconfirmed_decision_promotion",
            }

    if (
        "clinical_diagnosis" in content
        or "full_clinical_history" in content
        or "medication_list" in content
        or "raw_health_memory" in content
    ):
        return {
            "is_valid": False,
            "reason": "prohibited_clinical_context",
        }

    return {
        "is_valid": True,
        "reason": "valid_life_plan_proposal",
    }


def build_life_plan_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple[Any, ...] = (),
    candidates: tuple[Any, ...] = (),
    permission_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryViewRequest:
    """Build a ``DomainMemoryViewRequest`` for ``domain:life-plan``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=LIFE_PLAN_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_life_plan_memory_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalSnapshot:
    """Build a life plan memory proposal (proposal-only, requires confirmation)."""
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=True,
    )


def build_life_plan_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory: Any,
) -> DomainMemoryView:
    """Resolve a proposal-only memory view for ``domain:life-plan``."""
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_life_plan_memory_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for life plan memory output."""
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


def validate_life_plan_memory_binding(
    *,
    binding: Any,
    inventory: Any,
) -> DomainMemoryValidationResult:
    """Validate a proposal binding against a canonical memory reference inventory."""
    from cmm.domains.memory_validation import (
        DefaultDomainMemoryIntegrationValidator,
    )

    return DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding, inventory
    )


__all__ = [
    "CANDIDATE_LIFE_PLAN_LONGITUDINAL_KINDS",
    "build_life_plan_memory_binding",
    "build_life_plan_memory_proposal",
    "build_life_plan_memory_view",
    "build_life_plan_memory_view_request",
    "validate_life_plan_memory_binding",
    "validate_life_plan_memory_proposal_content",
]
