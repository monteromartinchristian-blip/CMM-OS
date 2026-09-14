"""Phase 10.24 — Reflection Domain Trace.

Reflection Domain composes caller-supplied typed references into the canonical
Phase 10.17 trace contracts.  No resource, profile, rule, operation, workflow,
permission, or approval reference is fabricated here: they appear in the trace
only when the caller supplies them.  Traces reference, never duplicate,
rule/source/operation/permission references.  No private chain-of-thought is
persisted.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.reflection.definition import REFLECTION_DOMAIN_ID
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


def build_reflection_trace_reference(
    *,
    ref_id: str,
    kind: DomainTraceReferenceKind,
    domain_id: str = REFLECTION_DOMAIN_ID,
) -> DomainTraceReference:
    """Build a domain-scoped ``DomainTraceReference`` owned by Reflection Domain."""
    return DomainTraceReference(
        ref_id=ref_id,
        kind=kind,
        domain_id=domain_id,
    )


def build_reflection_trace_contribution(
    *,
    domain_result_id: str,
    references: tuple[DomainTraceReference, ...] = (),
    domain_id: str = REFLECTION_DOMAIN_ID,
) -> DomainTraceContribution:
    """Build a PRIMARY ``DomainTraceContribution`` for Reflection Domain."""
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


def assemble_reflection_trace(
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
    """Assemble a final reference-only ``DomainTrace`` for Reflection Domain."""
    now = started_at or datetime.now(timezone.utc)
    end = completed_at or now
    contribution = build_reflection_trace_contribution(
        domain_result_id=domain_result_id,
        references=references,
        domain_id=REFLECTION_DOMAIN_ID,
    )
    refs = DomainTraceReferences(
        resolution_context_id=resolution_context_id,
        resolution_result_id=resolution_result_id,
        composition_id=composition_id,
    )
    request = DomainTraceAssemblyRequest(
        request_id=request_id,
        primary_domain=REFLECTION_DOMAIN_ID,
        supporting_domains=(),
        contributions=(contribution,),
        references=refs,
        started_at=now,
        completed_at=end,
        goal_id=goal_id,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=REFLECTION_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
    )
    return DomainTraceAssembler().assemble(request)


def validate_reflection_trace(
    *,
    trace: DomainTrace,
    inventory: DomainTraceReferenceInventory,
) -> DomainTraceValidationResult:
    """Validate an assembled trace against a canonical Phase 10.17 inventory."""
    from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator

    return DefaultDomainTraceReferenceValidator().validate(trace, inventory)


__all__ = [
    "assemble_reflection_trace",
    "build_reflection_trace_contribution",
    "build_reflection_trace_reference",
    "validate_reflection_trace",
]
