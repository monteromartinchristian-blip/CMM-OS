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
from cmm.domains.identifiers import DomainId
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


def build_supporting_trace_contribution(
    *,
    domain_result_id: str,
    domain_id: str,
    references: tuple[DomainTraceReference, ...] = (),
) -> DomainTraceContribution:
    """Build a SUPPORTING ``DomainTraceContribution`` for a participating
    supporting domain (I-008 remediation).

    The supporting domain owns its contribution references (shared
    DOMAIN_RESULT ownership rule); the caller must provide real supporting
    domain result ids produced by the prior execution.
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
    supporting_domains: tuple[DomainId | str, ...] = (),
    contributions: tuple[DomainTraceContribution, ...] = (),
    cross_domain_results: tuple = (),
    goal_id: str | None = None,
) -> DomainTrace:
    """Assemble a final reference-only ``DomainTrace`` for Concerns Domain.

    ``supporting_domains`` names the real supporting domains that
    participated; matching SUPPORTING contributions (including their
    domain-result references and cross-domain result pairings) are carried
    through the shared ``DomainTraceAssemblyRequest`` contract (I-008).
    Cross-domain results are global ``CROSS_DOMAIN_RESULT`` references and
    must never be stuffed into Contributions-owned references.
    """
    now = started_at or datetime.now(timezone.utc)
    end = completed_at or now
    if contributions:
        primary = build_concerns_trace_contribution(
            domain_result_id=domain_result_id,
            references=references,
            domain_id=CONCERNS_DOMAIN_ID,
        )
        all_contributions = (primary, *contributions)
    else:
        all_contributions = (
            build_concerns_trace_contribution(
                domain_result_id=domain_result_id,
                references=references,
                domain_id=CONCERNS_DOMAIN_ID,
            ),
        )
    refs = DomainTraceReferences(
        resolution_context_id=resolution_context_id,
        resolution_result_id=resolution_result_id,
        composition_id=composition_id,
        cross_domain_results=tuple(cross_domain_results),
    )
    request = DomainTraceAssemblyRequest(
        request_id=request_id,
        primary_domain=CONCERNS_DOMAIN_ID,
        supporting_domains=tuple(supporting_domains),
        contributions=all_contributions,
        references=refs,
        started_at=now,
        completed_at=end,
        goal_id=goal_id,
        domain_results=(
            DomainResultTraceReference(
                result_id=domain_result_id,
                domain_id=CONCERNS_DOMAIN_ID,
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
    "build_supporting_trace_contribution",
    "validate_concerns_trace",
]
