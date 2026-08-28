"""Phase 10.33 — Domain Event Adapters.

Pure adapters translating authoritative domain results and lifecycle transitions
into validated DomainEvent contracts. Pure semantic engines remain side-effect free.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictCase,
    DomainConflictResolution,
    DomainConflictStatus,
)
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult

_DEFAULT_FACTORY = DomainEventFactory()

_AUTHORIZATION_HEADER_RE = re.compile(
    r"authorization\s*:\s*bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE
)
_BEARER_RE = re.compile(r"\bbearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE)
_API_KEY_RE = re.compile(r"\b(?:sk|pk|api[_-]?key)[-_][a-zA-Z0-9_\-]+\b", re.IGNORECASE)
_KEY_PATTERN_RE = re.compile(r"\bkey-[a-zA-Z0-9_\-]+\b", re.IGNORECASE)
_COOKIE_SESSION_RE = re.compile(
    r"\b(?:cookie|session[_-]?token|auth[_-]?token)\s*=\s*[^\s;]+", re.IGNORECASE
)


def _sanitize_public_error_message(error: str) -> str:
    """Sanitize raw exception/error strings to prevent secret leakage across the event boundary."""
    if not isinstance(error, str):
        return str(error)
    sanitized = _AUTHORIZATION_HEADER_RE.sub("[REDACTED_AUTH_HEADER]", error)
    sanitized = _BEARER_RE.sub("[REDACTED_BEARER]", sanitized)
    sanitized = _API_KEY_RE.sub("[REDACTED_KEY]", sanitized)
    sanitized = _KEY_PATTERN_RE.sub("[REDACTED_KEY]", sanitized)
    sanitized = _COOKIE_SESSION_RE.sub("[REDACTED_TOKEN]", sanitized)
    return sanitized


def _ensure_domain_id(dom: DomainId | str) -> DomainId:
    if isinstance(dom, DomainId):
        return dom
    if isinstance(dom, str):
        return (
            DomainId.from_str(dom) if dom.startswith("domain:") else DomainId(slug=dom)
        )
    raise TypeError(f"Expected DomainId or str, got {type(dom).__name__}")


# ── 1. Resolution Lifecycle Adapters ──────────────────────────────────────────


def adapt_resolution_started(
    context_id: str,
    actor: str = "system",
    domain_id: DomainId | str | None = None,
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.resolution.started event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id) if domain_id else DomainId(slug="general")
    ref = DomainEventReference(
        kind="resolution_context", reference_id=context_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.resolution.started",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"context_id": context_id},
    )


def adapt_resolution_result(
    result: DomainResolutionResult,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.resolution.completed or domain.resolution.ambiguous event from an authoritative result."""
    f = factory or _DEFAULT_FACTORY
    is_ambiguous = (
        result.status == DomainResolutionStatus.AMBIGUOUS
        or result.requires_clarification
    )
    event_type = (
        "domain.resolution.ambiguous" if is_ambiguous else "domain.resolution.completed"
    )

    dom = result.primary_domain or (
        result.ambiguous_domains[0]
        if result.ambiguous_domains
        else DomainId(slug="general")
    )
    related = tuple(d for d in result.ambiguous_domains if d != dom)
    ref = DomainEventReference(kind="resolution", reference_id=result.id, domain_id=dom)

    payload: dict[str, Any] = {
        "result_id": result.id,
        "context_id": result.context_id,
        "status": result.status.value,
    }
    if result.confidence is not None:
        payload["confidence"] = result.confidence
    if result.requires_clarification:
        payload["requires_clarification"] = result.requires_clarification
    if result.recommended_question:
        payload["recommended_question"] = result.recommended_question

    return f.create_event(
        event_type=event_type,
        domain_id=dom,
        related_domain_ids=related,
        actor=actor,
        provenance=(ref,),
        payload=payload,
    )


# ── 2. Composition Lifecycle Adapters ─────────────────────────────────────────


def adapt_composition_created(
    composition: DomainComposition,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.composition.created event from an authoritative composition."""
    f = factory or _DEFAULT_FACTORY
    dom = composition.primary_domain
    related = composition.supporting_domains
    ref = DomainEventReference(
        kind="composition", reference_id=composition.id, domain_id=dom
    )

    return f.create_event(
        event_type="domain.composition.created",
        domain_id=dom,
        related_domain_ids=related,
        actor=actor,
        provenance=(ref,),
        payload={
            "composition_id": composition.id,
            "resolution_id": composition.resolution_id,
            "status": composition.status.value,
        },
    )


def adapt_composition_updated(
    previous: DomainComposition,
    current: DomainComposition,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent | None:
    """Create a domain.composition.updated event if composition actually changed.

    Recomputing an identical composition is not an update and returns None.
    """
    if previous == current or previous.id == current.id:
        return None

    f = factory or _DEFAULT_FACTORY
    dom = current.primary_domain
    related = current.supporting_domains
    ref_curr = DomainEventReference(
        kind="composition", reference_id=current.id, domain_id=dom
    )
    ref_prev = DomainEventReference(
        kind="composition", reference_id=previous.id, domain_id=previous.primary_domain
    )

    return f.create_event(
        event_type="domain.composition.updated",
        domain_id=dom,
        related_domain_ids=related,
        actor=actor,
        provenance=(ref_curr, ref_prev),
        payload={
            "previous_composition_id": previous.id,
            "composition_id": current.id,
            "status": current.status.value,
        },
    )


# ── 3. Domain Execution Lifecycle Adapters ────────────────────────────────────


def adapt_execution_started(
    execution_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    session_id: str | None = None,
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.execution.started event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="execution", reference_id=execution_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.execution.started",
        domain_id=dom,
        actor=actor,
        session_id=session_id,
        provenance=(ref,),
        payload={"execution_id": execution_id},
    )


def adapt_execution_completed(
    execution_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    session_id: str | None = None,
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.execution.completed event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="execution", reference_id=execution_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.execution.completed",
        domain_id=dom,
        actor=actor,
        session_id=session_id,
        provenance=(ref,),
        payload={"execution_id": execution_id, "status": "completed"},
    )


def adapt_execution_failed(
    execution_id: str,
    domain_id: DomainId | str,
    error: str,
    actor: str = "system",
    session_id: str | None = None,
    error_code: str | None = None,
    error_type: str | None = None,
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.execution.failed event with sanitized error information."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="execution", reference_id=execution_id, domain_id=dom
    )
    safe_error = _sanitize_public_error_message(error)
    payload: dict[str, Any] = {
        "execution_id": execution_id,
        "error": safe_error,
        "status": "failed",
    }
    if error_code is not None:
        payload["error_code"] = error_code
    if error_type is not None:
        payload["error_type"] = error_type
    return f.create_event(
        event_type="domain.execution.failed",
        domain_id=dom,
        actor=actor,
        session_id=session_id,
        provenance=(ref,),
        payload=payload,
    )


# ── 4. Conflict Lifecycle Adapters ────────────────────────────────────────────


def adapt_conflict_detected(
    case: DomainConflictCase,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.conflict.detected event from an authoritative conflict case."""
    f = factory or _DEFAULT_FACTORY
    dom = case.domains[0] if case.domains else DomainId(slug="general")
    related = tuple(d for d in case.domains if d != dom)
    ref = DomainEventReference(
        kind="conflict_case", reference_id=case.id, domain_id=dom
    )

    return f.create_event(
        event_type="domain.conflict.detected",
        domain_id=dom,
        related_domain_ids=related,
        actor=actor,
        provenance=(ref,),
        payload={
            "conflict_id": case.id,
            "kind": case.kind.value,
            "severity": case.severity.value,
            "status": case.status.value,
            "blocking": case.blocking,
        },
    )


def adapt_conflict_resolution(
    resolution: DomainConflictResolution,
    primary_domain: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent | None:
    """Create a domain.conflict.resolved event ONLY if conflict is genuinely resolved.

    Returns None for maintain_conflict, postpone_action, ask_user, human_review, or blocked states.
    """
    if resolution.status != DomainConflictStatus.RESOLVED or not resolution.can_proceed:
        return None

    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(primary_domain)
    ref = DomainEventReference(
        kind="conflict_resolution", reference_id=resolution.conflict_id, domain_id=dom
    )

    return f.create_event(
        event_type="domain.conflict.resolved",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={
            "conflict_id": resolution.conflict_id,
            "status": resolution.status.value,
            "strategy": resolution.strategy.value,
            "winning_reference_ids": list(resolution.winning_reference_ids),
            "can_proceed": resolution.can_proceed,
        },
    )


# ── 5. Permission Lifecycle Adapters ──────────────────────────────────────────


def adapt_permission_requested(
    capability: str,
    domain_id: DomainId | str,
    actor: str = "system",
    effective_permissions: Sequence[str] = (),
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.permission.requested event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    return f.create_event(
        event_type="domain.permission.requested",
        domain_id=dom,
        actor=actor,
        permissions=tuple(effective_permissions),
        payload={"capability": capability},
    )


def adapt_permission_denied(
    capability: str,
    domain_id: DomainId | str,
    reason: str,
    actor: str = "system",
    effective_permissions: Sequence[str] = (),
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.permission.denied event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    return f.create_event(
        event_type="domain.permission.denied",
        domain_id=dom,
        actor=actor,
        permissions=tuple(effective_permissions),
        payload={"capability": capability, "reason": reason},
    )


# ── 6. Approval Lifecycle Adapters ────────────────────────────────────────────


def adapt_approval_requested(
    approval_id: str,
    domain_id: DomainId | str,
    action: str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.approval.requested event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(kind="approval", reference_id=approval_id, domain_id=dom)
    return f.create_event(
        event_type="domain.approval.requested",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"approval_id": approval_id, "action": action},
    )


def adapt_approval_received(
    approval_id: str,
    domain_id: DomainId | str,
    approved: bool,
    decision_by: str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.approval.received event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(kind="approval", reference_id=approval_id, domain_id=dom)
    return f.create_event(
        event_type="domain.approval.received",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={
            "approval_id": approval_id,
            "approved": approved,
            "decision_by": decision_by,
        },
    )


# ── 7. Memory Lifecycle Adapters ──────────────────────────────────────────────


def adapt_memory_proposed(
    proposal_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.memory.proposed event (does not imply write)."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="memory_proposal", reference_id=proposal_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.memory.proposed",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"proposal_id": proposal_id, "status": "proposed"},
    )


def adapt_memory_updated(
    update_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.memory.updated event (emitted only after authoritative write)."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="memory_update", reference_id=update_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.memory.updated",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"update_id": update_id, "status": "updated"},
    )


# ── 8. Workflow Lifecycle Adapters ────────────────────────────────────────────


def adapt_workflow_started(
    workflow_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.workflow.started event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="workflow_run", reference_id=workflow_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.workflow.started",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"workflow_id": workflow_id, "status": "started"},
    )


def adapt_workflow_paused(
    workflow_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.workflow.paused event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="workflow_run", reference_id=workflow_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.workflow.paused",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"workflow_id": workflow_id, "status": "paused"},
    )


def adapt_workflow_resumed(
    workflow_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.workflow.resumed event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="workflow_run", reference_id=workflow_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.workflow.resumed",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"workflow_id": workflow_id, "status": "resumed"},
    )


def adapt_workflow_completed(
    workflow_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.workflow.completed event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="workflow_run", reference_id=workflow_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.workflow.completed",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"workflow_id": workflow_id, "status": "completed"},
    )


# ── 9. Operation Lifecycle Adapters ───────────────────────────────────────────


def adapt_operation_started(
    operation_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.operation.started event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="operation_run", reference_id=operation_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.operation.started",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"operation_id": operation_id, "status": "started"},
    )


def adapt_operation_completed(
    operation_id: str,
    domain_id: DomainId | str,
    actor: str = "system",
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.operation.completed event."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="operation_run", reference_id=operation_id, domain_id=dom
    )
    return f.create_event(
        event_type="domain.operation.completed",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload={"operation_id": operation_id, "status": "completed"},
    )


def adapt_operation_failed(
    operation_id: str,
    domain_id: DomainId | str,
    error: str,
    actor: str = "system",
    error_code: str | None = None,
    error_type: str | None = None,
    factory: DomainEventFactory | None = None,
) -> DomainEvent:
    """Create a domain.operation.failed event with sanitized error information."""
    f = factory or _DEFAULT_FACTORY
    dom = _ensure_domain_id(domain_id)
    ref = DomainEventReference(
        kind="operation_run", reference_id=operation_id, domain_id=dom
    )
    safe_error = _sanitize_public_error_message(error)
    payload: dict[str, Any] = {
        "operation_id": operation_id,
        "error": safe_error,
        "status": "failed",
    }
    if error_code is not None:
        payload["error_code"] = error_code
    if error_type is not None:
        payload["error_type"] = error_type
    return f.create_event(
        event_type="domain.operation.failed",
        domain_id=dom,
        actor=actor,
        provenance=(ref,),
        payload=payload,
    )
