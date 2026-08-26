"""Phase 10.30 — Project Domain Memory Integration.

Builds proposal-only memory views, proposals, and bindings using the shared
Phase 10.18 contracts. Project memory is never written directly or autonomously:
reasoning operations produce a ``DomainMemoryProposalSnapshot`` plus a
``DomainMemoryProposalBinding`` that link the proposal, view, digest, trace,
permissions, and approval references for the canonical approval path.

Every proposal is registered with ``requires_confirmation=True``.
Prohibits silent persistence of unconfirmed proposals as decisions,
unconfirmed commitments, or raw codebase / source code dumps in memory.
"""

from __future__ import annotations

from typing import Any

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
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID

CANDIDATE_PROJECT_LONGITUDINAL_KINDS: tuple[str, ...] = (
    "project_brief",
    "project_plan",
    "milestone_record",
    "dependency_record",
    "resource_record",
    "decision_record",
    "risk_record",
    "project_timeline",
    "architecture_document",
    "roadmap",
)


def validate_project_memory_proposal_content(
    content: dict[str, Any],
) -> dict[str, Any]:
    """Validate proposal content against Project safety and epistemic boundaries."""
    kind = str(content.get("kind", "")).lower()
    status = str(content.get("status", "")).lower()
    orig = str(content.get("original_status", "")).lower()

    # Strict boolean check for is_confirmed - reject non-bool types fail-closed
    is_conf_raw = content.get("is_confirmed", False)
    if "is_confirmed" in content and type(content["is_confirmed"]) is not bool:
        return {
            "is_valid": False,
            "reason": "invalid_confirmation_evidence_type",
        }
    is_conf = (type(is_conf_raw) is bool) and is_conf_raw

    # Reject unconfirmed promotion to decision or commitment
    if (
        status in ("decision", "applied", "completed")
        and not is_conf
        and (
            orig in ("proposal", "draft", "hypothesis", "idea", "inference")
            or kind in ("decision", "proposal", "hypothesis", "inference")
        )
    ):
        return {
            "is_valid": False,
            "reason": "prohibited_unconfirmed_decision_promotion",
        }

    # Reject raw code dumps in memory proposal
    if (
        "raw_source_code" in content
        or "source_code_dump" in content
        or "repository_contents" in content
        or "full_patch" in content
    ):
        return {
            "is_valid": False,
            "reason": "prohibited_raw_code_dump",
        }

    return {
        "is_valid": True,
        "reason": "valid_project_proposal",
    }


def build_project_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple[Any, ...] = (),
    candidates: tuple[Any, ...] = (),
    permission_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryViewRequest:
    """Build a ``DomainMemoryViewRequest`` for ``domain:project``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=PROJECT_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_project_memory_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalSnapshot:
    """Build a project memory proposal (proposal-only, requires confirmation)."""
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=True,
    )


def build_project_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory: Any,
) -> DomainMemoryView:
    """Resolve a proposal-only memory view for ``domain:project``."""
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_project_memory_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for project memory output."""
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


def validate_project_memory_binding(
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
    "CANDIDATE_PROJECT_LONGITUDINAL_KINDS",
    "build_project_memory_binding",
    "build_project_memory_proposal",
    "build_project_memory_view",
    "build_project_memory_view_request",
    "validate_project_memory_binding",
    "validate_project_memory_proposal_content",
]
