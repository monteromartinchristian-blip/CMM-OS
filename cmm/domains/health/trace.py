"""Phase 10.20 — Health Domain Trace.

Health Domain composes caller-supplied typed references into the canonical
Phase 10.17 trace contracts.  No resource, profile, rule, operation, workflow,
permission, or approval reference is fabricated here: they appear in the trace
only when the caller supplies them.  No provenance or clinical evidence is
invented.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.health.definition import HEALTH_DOMAIN_ID
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceStatus,
    DomainTraceValidationResult,
)


def build_health_trace_reference(
    *,
    ref_id: str,
    kind: DomainTraceReferenceKind,
    domain_id: str = HEALTH_DOMAIN_ID,
) -> DomainTraceReference:
    """Build a domain-scoped ``DomainTraceReference`` owned by Health Domain.

    Only domain-scoped kinds are accepted; the underlying contract rejects
    global kinds that carry a ``domain_id``.  The kind is never inferred.
    """
    return DomainTraceReference(
        ref_id=ref_id,
        kind=kind,
        domain_id=domain_id,
    )


def build_health_trace_contribution(
    *,
    domain_result_id: str,
    references: tuple[DomainTraceReference, ...] = (),
    domain_id: str = HEALTH_DOMAIN_ID,
) -> DomainTraceContribution:
    """Build a PRIMARY ``DomainTraceContribution`` for Health Domain.

    Adds exactly one ``DOMAIN_RESULT`` reference for ``domain_result_id`` and
    preserves any caller-supplied domain-scoped references verbatim.  Nothing
    else is fabricated.
    """
    all_references = [
        DomainTraceReference(
            ref_id=domain_result_id,
            kind=DomainTraceReferenceKind.DOMAIN_RESULT,
            domain_id=domain_id,
        ),
        *references,
    ]
    return DomainTraceContribution(
        domain_id=domain_id,
        role=DomainTraceRole.PRIMARY,
        references=tuple(all_references),
    )


def assemble_health_trace(
    *,
    request_id: str,
    resolution_context_id: str,
    resolution_result_id: str,
    composition_id: str,
    domain_result_id: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    references: tuple[DomainTraceReference, ...] = (),
    goal_id: str | None = None,
) -> DomainTrace:
    """Assemble a final reference-only ``DomainTrace`` for Health Domain.

    Uses the canonical ``DomainTraceAssembler``.  The caller supplies the real
    global IDs (resolution context/result and composition) plus the domain
    result ID; this helper never fabricates supporting domains or contributions.
    """
    now = started_at or datetime.now(timezone.utc)
    end = completed_at or now
    contribution = build_health_trace_contribution(
        domain_result_id=domain_result_id,
        references=references,
        domain_id=HEALTH_DOMAIN_ID,
    )
    refs = DomainTraceReferences(
        resolution_context_id=resolution_context_id,
        resolution_result_id=resolution_result_id,
        composition_id=composition_id,
    )
    request = DomainTraceAssemblyRequest(
        request_id=request_id,
        primary_domain=HEALTH_DOMAIN_ID,
        supporting_domains=(),
        contributions=(contribution,),
        references=refs,
        started_at=now,
        completed_at=end,
        goal_id=goal_id,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=HEALTH_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
    )
    return DomainTraceAssembler().assemble(request)


def validate_health_trace(
    *,
    trace: DomainTrace,
    inventory: DomainTraceReferenceInventory,
) -> DomainTraceValidationResult:
    """Validate an assembled trace against a canonical Phase 10.17 inventory.

    Delegates exclusively to the real ``DefaultDomainTraceReferenceValidator``.
    """
    from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator

    return DefaultDomainTraceReferenceValidator().validate(trace, inventory)


__all__ = [
    "assemble_health_trace",
    "build_health_trace_contribution",
    "build_health_trace_reference",
    "validate_health_trace",
]
