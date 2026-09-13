"""Phase 10.53 — Neurodivergence Domain Trace.

Neurodivergence Domain composes caller-supplied typed references into the
canonical Phase 10.17 trace contracts.  No resource, profile, rule, operation,
workflow, permission, approval or memory reference is fabricated here: they
appear in the trace only when the caller supplies them.

The trace is reference-only.  It never stores private prompt text, hidden chain
of thought, raw sensitive source bodies (developmental records, assessment
reports, psychometric output) and never copies subordinate trace bodies.  No
Neurodivergence trace store exists.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.identifiers import DomainId
from cmm.domains.neurodivergence.catalog import NEURODIVERGENCE_DOMAIN_ID
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

NEURODIVERGENCE_TRACE_REFERENCE_KINDS: tuple[DomainTraceReferenceKind, ...] = (
    DomainTraceReferenceKind.DOMAIN_RESULT,
)


def build_neurodivergence_trace_reference(
    *,
    ref_id: str,
    kind: DomainTraceReferenceKind,
    domain_id: str | None = NEURODIVERGENCE_DOMAIN_ID,
) -> DomainTraceReference:
    """Build a ``DomainTraceReference`` for Neurodivergence Domain.

    Domain-scoped kinds (profile, rules, resources, operations, workflows,
    permission/privacy decisions, approvals, memory proposals) carry the
    Neurodivergence ``domain_id``.  Canonical *global* kinds — a Knowledge
    Package, a Cognitive trace, a cross-domain result — must omit ``domain_id``;
    pass ``domain_id=None`` for those and the canonical contract enforces the
    global/domain distinction rather than letting a global reference be
    relabelled as Neurodivergence-owned.
    """
    return DomainTraceReference(
        ref_id=ref_id,
        kind=kind,
        domain_id=domain_id,
    )


def build_neurodivergence_trace_contribution(
    *,
    domain_result_id: str,
    references: tuple[DomainTraceReference, ...] = (),
    domain_id: str = NEURODIVERGENCE_DOMAIN_ID,
) -> DomainTraceContribution:
    """Build a PRIMARY ``DomainTraceContribution`` for Neurodivergence Domain."""
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


def build_supporting_trace_contribution(
    *,
    domain_result_id: str,
    domain_id: str,
    references: tuple[DomainTraceReference, ...] = (),
) -> DomainTraceContribution:
    """Build a SUPPORTING contribution for a participating supporting domain.

    The supporting domain owns its contribution references; the caller must
    provide real supporting domain result ids produced by the prior execution.
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
        role=DomainTraceRole.SUPPORTING,
        references=tuple(all_references),
    )


def assemble_neurodivergence_trace(
    *,
    request_id: str,
    resolution_context_id: str,
    resolution_result_id: str,
    composition_id: str,
    domain_result_id: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    references: tuple[DomainTraceReference, ...] = (),
    supporting_domains: tuple[DomainId | str, ...] = (),
    contributions: tuple[DomainTraceContribution, ...] = (),
    cross_domain_results: tuple = (),
    goal_id: str | None = None,
) -> DomainTrace:
    """Assemble a final reference-only ``DomainTrace`` for Neurodivergence Domain."""
    now = started_at or datetime.now(timezone.utc)
    end = completed_at or now
    primary = build_neurodivergence_trace_contribution(
        domain_result_id=domain_result_id,
        references=references,
        domain_id=NEURODIVERGENCE_DOMAIN_ID,
    )
    all_contributions = (primary, *contributions)
    refs = DomainTraceReferences(
        resolution_context_id=resolution_context_id,
        resolution_result_id=resolution_result_id,
        composition_id=composition_id,
        cross_domain_results=tuple(cross_domain_results),
    )
    request = DomainTraceAssemblyRequest(
        request_id=request_id,
        primary_domain=NEURODIVERGENCE_DOMAIN_ID,
        supporting_domains=tuple(supporting_domains),
        contributions=all_contributions,
        references=refs,
        started_at=now,
        completed_at=end,
        goal_id=goal_id,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=NEURODIVERGENCE_DOMAIN_ID,
            ),
            *(
                DomainResultTraceReference(
                    result_id=ref.ref_id,
                    domain_id=str(item.domain_id),
                )
                for item in (contributions or ())
                if item.role is DomainTraceRole.SUPPORTING
                for ref in item.references
                if ref.kind is DomainTraceReferenceKind.DOMAIN_RESULT
            ),
        ),
        status=DomainTraceStatus.COMPLETED,
    )
    return DomainTraceAssembler().assemble(request)


def validate_neurodivergence_trace(
    *,
    trace: DomainTrace,
    inventory: DomainTraceReferenceInventory,
) -> DomainTraceValidationResult:
    """Validate an assembled trace against a canonical Phase 10.17 inventory."""
    from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator

    return DefaultDomainTraceReferenceValidator().validate(trace, inventory)


__all__ = [
    "NEURODIVERGENCE_DOMAIN_ID",
    "NEURODIVERGENCE_TRACE_REFERENCE_KINDS",
    "assemble_neurodivergence_trace",
    "build_neurodivergence_trace_contribution",
    "build_neurodivergence_trace_reference",
    "build_supporting_trace_contribution",
    "validate_neurodivergence_trace",
]
