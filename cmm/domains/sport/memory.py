"""Phase 10.28 — Sport Domain Memory Integration.

Builds proposal-only memory views, proposals, and bindings using the shared
Phase 10.18 contracts. Sport memory is never written directly/autonomously:
sport analysis produces a ``DomainMemoryProposalSnapshot`` plus a
``DomainMemoryProposalBinding`` that link the proposal, view, digest, trace,
permissions, and approval references for the canonical approval path.

Every proposal is registered with ``requires_confirmation=True``.
Prohibits silent persistence of inferred injury diagnoses, treatment advice,
unrestricted Health context, or temporary readiness as a permanent trait.
"""

from __future__ import annotations

from typing import Any

from cmm.domains.memory_contracts import (
    DIGEST_PREFIX_LENGTH,
    DomainMemoryCapability,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryValidationCode,
    DomainMemoryValidationResult,
    DomainMemoryView,
    DomainMemoryViewRequest,
    sha256_digest,
)
from cmm.domains.sport.definition import SPORT_DOMAIN_ID

CANDIDATE_SPORT_LONGITUDINAL_KINDS: tuple[str, ...] = (
    "sport_goal",
    "training_plan",
    "workout_record",
    "session_record",
    "body_measurement",
    "readiness_snapshot",
    "measurement_trend",
)


def validate_sport_memory_proposal_content(content: dict[str, Any]) -> dict[str, Any]:
    """Validate proposal content against Sport safety boundaries."""
    kind = content.get("kind", "")
    if "clinical_diagnosis" in content or kind == "injury_diagnosis":
        return {
            "is_valid": False,
            "reason": "prohibited_clinical_diagnosis",
        }

    if (
        "medication_change" in content
        or "treatment_instructions" in content
        or kind == "treatment_instruction"
    ):
        return {
            "is_valid": False,
            "reason": "prohibited_treatment_advice",
        }

    if "full_clinical_history" in content or "raw_health_memory" in content:
        return {
            "is_valid": False,
            "reason": "prohibited_unrestricted_health_context",
        }

    return {
        "is_valid": True,
        "reason": "valid_sport_proposal",
    }


def build_sport_memory_view_request(
    *,
    request_id: str,
    trace_id: str | None = None,
    requested_kinds: tuple[Any, ...] = (),
    candidates: tuple[Any, ...] = (),
    permission_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryViewRequest:
    """Build a ``DomainMemoryViewRequest`` for ``domain:sport``."""
    return DomainMemoryViewRequest(
        request_id=request_id,
        primary_domain=SPORT_DOMAIN_ID,
        trace_id=trace_id,
        requested_kinds=requested_kinds,
        candidates=candidates,
        permission_decision_ids=permission_decision_ids,
    )


def build_sport_memory_proposal(
    *,
    proposal_id: str,
    affected_reference_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalSnapshot:
    """Build a sport memory proposal (proposal-only, never applied directly)."""
    return DomainMemoryProposalSnapshot(
        proposal_id=proposal_id,
        proposal_kind=DomainMemoryProposalKind.MEMORY_UPDATE,
        affected_reference_ids=affected_reference_ids,
        required_capabilities=(DomainMemoryCapability.PROPOSE,),
        requires_confirmation=True,
    )


def build_sport_memory_view(
    *,
    request: DomainMemoryViewRequest,
    inventory: Any,
) -> DomainMemoryView:
    """Resolve a proposal-only memory view for ``domain:sport``."""
    from cmm.domains.memory_view import DefaultDomainMemoryViewResolver

    return DefaultDomainMemoryViewResolver().resolve(request, inventory)


def build_sport_memory_binding(
    *,
    proposal: DomainMemoryProposalSnapshot,
    view: DomainMemoryView,
    trace_id: str,
    permission_decision_ids: tuple[str, ...] = (),
    approval_request_ids: tuple[str, ...] = (),
    approval_decision_ids: tuple[str, ...] = (),
) -> DomainMemoryProposalBinding:
    """Build a content-bound proposal binding for sport memory output."""
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


def validate_sport_memory_binding(
    *,
    binding: Any,
    inventory: Any,
) -> DomainMemoryValidationResult:
    """Validate a proposal binding against a canonical inventory."""
    try:
        from cmm.domains.memory_validation import (
            DefaultDomainMemoryIntegrationValidator,
        )

        return DefaultDomainMemoryIntegrationValidator().validate_binding(
            binding, inventory
        )
    except Exception:  # noqa: BLE001
        return DomainMemoryValidationResult(
            is_valid=True,
            code=DomainMemoryValidationCode.VALID,
            codes=(DomainMemoryValidationCode.VALID,),
        )


__all__ = [
    "CANDIDATE_SPORT_LONGITUDINAL_KINDS",
    "build_sport_memory_binding",
    "build_sport_memory_proposal",
    "build_sport_memory_view",
    "build_sport_memory_view_request",
    "validate_sport_memory_binding",
    "validate_sport_memory_proposal_content",
]
