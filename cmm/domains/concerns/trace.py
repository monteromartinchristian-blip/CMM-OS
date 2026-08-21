"""Phase 10.25 — Concerns Domain Trace.

Concerns Domain composes caller-supplied typed references into the canonical
Phase 10.17 trace contracts.  No resource, profile, rule, operation, workflow,
permission, or approval reference is fabricated here: they appear in the trace
only when the caller supplies them.  Traces reference — never duplicate —
rule/source/operation/permission references, and no private chain-of-thought
is persisted.

The trace can explain: why Concerns was selected, which supporting domains
participated, what support need was inferred (explicit or not), which
resources/evidence were used, which interpretations/hypotheses were preserved,
what uncertainty remained, whether reassurance/material concern/risk
escalation occurred, why questions/action/memory proposals exist, and which
permission decisions constrained the result — all as structured references.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.concerns.definition import CONCERNS_DOMAIN_ID
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


def build_concerns_trace_reference(
    *,
    ref_id: str,
    kind: DomainTraceReferenceKind,
    domain_id: str = CONCERNS_DOMAIN_ID,
) -> DomainTraceReference:
    """Build a domain-scoped ``DomainTraceReference`` owned by Concerns Domain."""
    return DomainTraceReference(
        ref_id=ref_id,
        kind=kind,
        domain_id=domain_id,
    )


def build_concerns_trace_contribution(
    *,
    domain_result_id: str,
    references: tuple[DomainTraceReference, ...] = (),
    domain_id: str = CONCERNS_DOMAIN_ID,
) -> DomainTraceContribution:
    """Build a PRIMARY ``DomainTraceContribution`` for Concerns Domain."""
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


def assemble_concerns_trace(
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
    """Assemble a final reference-only ``DomainTrace`` for Concerns Domain."""
    now = started_at or datetime.now(timezone.utc)
    end = completed_at or now
    contribution = build_concerns_trace_contribution(
        domain_result_id=domain_result_id,
        references=references,
        domain_id=CONCERNS_DOMAIN_ID,
    )
    refs = DomainTraceReferences(
        resolution_context_id=resolution_context_id,
        resolution_result_id=resolution_result_id,
        composition_id=composition_id,
    )
    request = DomainTraceAssemblyRequest(
        request_id=request_id,
        primary_domain=CONCERNS_DOMAIN_ID,
        supporting_domains=(),
        contributions=(contribution,),
        references=refs,
        started_at=now,
        completed_at=end,
        goal_id=goal_id,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=CONCERNS_DOMAIN_ID,
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
    )
    return DomainTraceAssembler().assemble(request)


def validate_concerns_trace(
    *,
    trace: DomainTrace,
    inventory: DomainTraceReferenceInventory,
) -> DomainTraceValidationResult:
    """Validate an assembled trace against a canonical Phase 10.17 inventory."""
    from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator

    return DefaultDomainTraceReferenceValidator().validate(trace, inventory)


__all__ = [
    "assemble_concerns_trace",
    "build_concerns_trace_contribution",
    "build_concerns_trace_reference",
    "validate_concerns_trace",
]
