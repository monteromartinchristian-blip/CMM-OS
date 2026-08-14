"""Phase 10.23 — Opposition Domain Trace.

Opposition Domain composes caller-supplied typed references into the canonical
Phase 10.17 trace contracts.  No resource, profile, rule, operation, workflow,
permission, or approval reference is fabricated here: they appear in the trace
only when the caller supplies them.  No provenance or official evidence is
invented.  Traces reference, never duplicate, rule/source/operation/strategy
references.  No hidden chain-of-thought persistence occurs.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.oppositions.definition import OPPOSITIONS_DOMAIN_ID
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


def build_oppositions_trace_reference(
    *,
    ref_id: str,
    kind: DomainTraceReferenceKind,
    domain_id: str = OPPOSITIONS_DOMAIN_ID,
) -> DomainTraceReference:
    """Build a domain-scoped ``DomainTraceReference`` owned by Opposition Domain."""
    return DomainTraceReference(
        ref_id=ref_id,
        kind=kind,
        domain_id=domain_id,
    )


def build_oppositions_trace_contribution(
    *,
    domain_result_id: str,
    references: tuple[DomainTraceReference, ...] = (),
    domain_id: str = OPPOSITIONS_DOMAIN_ID,
) -> DomainTraceContribution:
    """Build a PRIMARY ``DomainTraceContribution`` for Opposition Domain."""
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


def assemble_oppositions_trace(
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
    """Assemble a final reference-only ``DomainTrace`` for Opposition Domain."""
    now = started_at or datetime.now(timezone.utc)
    end = completed_at or now
    contribution = build_oppositions_trace_contribution(
        domain_result_id=domain_result_id,
        references=references,
        domain_id=OPPOSITIONS_DOMAIN_ID,
    )
    refs = DomainTraceReferences(
        resolution_context_id=resolution_context_id,
        resolution_result_id=resolution_result_id,
        composition_id=composition_id,
    )
    request = DomainTraceAssemblyRequest(
        request_id=request_id,
        primary_domain=OPPOSITIONS_DOMAIN_ID,
        supporting_domains=(),
        contributions=(contribution,),
        references=refs,
        started_at=now,
        completed_at=end,
        goal_id=goal_id,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=OPPOSITIONS_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
    )
    return DomainTraceAssembler().assemble(request)


def validate_oppositions_trace(
    *,
    trace: DomainTrace,
    inventory: DomainTraceReferenceInventory,
) -> DomainTraceValidationResult:
    """Validate an assembled trace against a canonical Phase 10.17 inventory."""
    from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator

    return DefaultDomainTraceReferenceValidator().validate(trace, inventory)


__all__ = [
    "assemble_oppositions_trace",
    "build_oppositions_trace_contribution",
    "build_oppositions_trace_reference",
    "validate_oppositions_trace",
]