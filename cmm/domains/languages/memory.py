"""Phase 10.26 — Languages Domain Memory Integration.

Builds proposal-only memory views, proposals, and bindings using the shared
Phase 10.18 contracts. Languages memory is never written autonomously: learning
analysis produces a ``DomainMemoryProposalSnapshot`` plus a
``DomainMemoryProposalBinding`` that link the proposal, view, digest, trace,
permissions, and approval references for the canonical approval path.

Every proposal is registered with ``requires_confirmation=True`` and the builder
exposes no override. A ``memory_entry`` input is evidence/provenance, not current truth.
No private Languages memory store exists.
"""

from __future__ import annotations

from typing import Any

from cmm.domains.languages.definition import LANGUAGES_DOMAIN_ID
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

CANDIDATE_LONGITUDINAL_KINDS: tuple[str, ...] = (
    "estimated_proficiency",
    "skill_profile",
    "language_goal",
    "learning_plan",
    "error_pattern",
    "vocabulary_review_state",
    "grammar_review_state",
    "certification_target",
    "progress_history",
)


def build_languages_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple[str, ...] = (),
    candidates: tuple[Any, ...] = (),
    permission_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryViewRequest:
    """Build a ``DomainMemoryViewRequest`` for ``domain:languages``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=LANGUAGES_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_languages_memory_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalSnapshot:
    """Build a language learning memory proposal (proposal-only, never applied)."""
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=True,
    )


def build_languages_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory: Any,
) -> DomainMemoryView:
    """Resolve a proposal-only memory view for ``domain:languages``."""
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_languages_memory_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for language learning output."""
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


def validate_languages_memory_binding(
    *,
    binding: DomainMemoryProposalBinding,
    inventory: Any,
) -> DomainMemoryValidationResult:
    """Validate a proposal binding against a canonical memory reference inventory."""
    from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator

    return DefaultDomainMemoryIntegrationValidator().validate_binding(
        binding, inventory
    )


__all__ = [
    "CANDIDATE_LONGITUDINAL_KINDS",
    "build_languages_memory_binding",
    "build_languages_memory_proposal",
    "build_languages_memory_view",
    "build_languages_memory_view_request",
    "validate_languages_memory_binding",
]
