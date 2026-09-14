"""Phase 10.28 — Sport Domain Trace Integration.

Composes caller-supplied typed references into canonical Phase 10.17 trace contracts.
Traces reference — never duplicate — rule/source/operation/permission references,
and preserve functional scope and cross-domain Health provenance where applicable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cmm.domains.identifiers import DomainId
from cmm.domains.sport.definition import SPORT_DOMAIN_ID
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


def build_sport_trace_reference(
    *,
    ref_id: str,
    kind: DomainTraceReferenceKind,
    domain_id: str = SPORT_DOMAIN_ID,
) -> DomainTraceReference:
    """Build a domain-scoped ``DomainTraceReference`` owned by Sport Domain."""
    return DomainTraceReference(
        ref_id=ref_id,
        kind=kind,
        domain_id=domain_id,
    )


def build_sport_trace_contribution(
    *,
    domain_result_id: str,
    references: tuple[DomainTraceReference, ...] = (),
    domain_id: str = SPORT_DOMAIN_ID,
) -> DomainTraceContribution:
    """Build a PRIMARY ``DomainTraceContribution`` for Sport Domain."""
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
    """Build a SUPPORTING ``DomainTraceContribution`` for a participating supporting domain."""
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


def assemble_sport_trace(
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
    cross_domain_results: tuple[Any, ...] = (),
    presentation_result_ids: tuple[str, ...] = (),
    goal_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DomainTrace:
    """Assemble a final reference-only ``DomainTrace`` for Sport Domain."""
    now = started_at or datetime.now(timezone.utc)
    end = completed_at or now
    if contributions:
        primary = build_sport_trace_contribution(
            domain_result_id=domain_result_id,
            references=references,
            domain_id=SPORT_DOMAIN_ID,
        )
        all_contributions = (primary, *contributions)
    else:
        all_contributions = (
            build_sport_trace_contribution(
                domain_result_id=domain_result_id,
                references=references,
                domain_id=SPORT_DOMAIN_ID,
            ),
        )

    meta = dict(metadata or {})

    refs = DomainTraceReferences(
        resolution_context_id=resolution_context_id,
        resolution_result_id=resolution_result_id,
        composition_id=composition_id,
        cross_domain_results=tuple(cross_domain_results),
        presentation_result_ids=presentation_result_ids,
    )
    request = DomainTraceAssemblyRequest(
        request_id=request_id,
        primary_domain=SPORT_DOMAIN_ID,
        supporting_domains=tuple(supporting_domains),
        contributions=all_contributions,
        references=refs,
        started_at=now,
        completed_at=end,
        goal_id=goal_id,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=SPORT_DOMAIN_ID,
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
        metadata=meta,
    )
    return DomainTraceAssembler().assemble(request)


def validate_sport_trace(
    *,
    trace: DomainTrace,
    inventory: DomainTraceReferenceInventory,
) -> DomainTraceValidationResult:
    """Validate an assembled trace against a canonical Phase 10.17 inventory."""
    from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator

    return DefaultDomainTraceReferenceValidator().validate(trace, inventory)


__all__ = [
    "assemble_sport_trace",
    "build_sport_trace_contribution",
    "build_sport_trace_reference",
    "build_supporting_trace_contribution",
    "validate_sport_trace",
]
