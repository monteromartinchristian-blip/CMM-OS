"""Phase 10.17 assembly behaviour."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceReference,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
)


def test_assembler_derives_a_canonical_trace_id_without_an_objective() -> None:
    request = DomainTraceAssemblyRequest(
        request_id="request:1",
        primary_domain="domain:life-plan",
        contributions=(
            DomainTraceContribution(
                domain_id="domain:life-plan",
                role=DomainTraceRole.PRIMARY,
                references=(
                    DomainTraceReference(
                        ref_id="result:1",
                        kind=DomainTraceReferenceKind.DOMAIN_RESULT,
                        domain_id="domain:life-plan",
                    ),
                ),
            ),
        ),
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:1",
            resolution_result_id="resolution-result:1",
            composition_id="composition:1",
        ),
        domain_results=(DomainResultTraceReference("result:1", "domain:life-plan"),),
        started_at=datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 2, 12, 0, 1, tzinfo=timezone.utc),
    )

    trace = DomainTraceAssembler().assemble(request)

    assert trace.id == f"domain-trace:{trace.digest[:24]}"
    assert trace.duration_ms == 1000
    assert "objective" not in trace.to_dict()
