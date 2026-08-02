"""Pure, deterministic assembly of reference-only Domain Traces."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    _canonical_participants,
    _validate_domain_result_coverage,
    _validate_global_id_uniqueness,
)


class DomainTraceAssembler:
    """Constructs a final trace without querying any runtime or store."""

    def assemble(self, request: DomainTraceAssemblyRequest | Mapping[str, Any]) -> DomainTrace:
        if not isinstance(request, DomainTraceAssemblyRequest):
            if not isinstance(request, Mapping):
                raise TypeError("request must be DomainTraceAssemblyRequest or a mapping")
            request = DomainTraceAssemblyRequest.from_dict(request)
        contributions = self._canonical_contributions(request)
        _validate_domain_result_coverage(contributions, request.domain_results)
        _validate_global_id_uniqueness(contributions, request.references)
        duration_ms = int((request.completed_at - request.started_at).total_seconds() * 1000)
        probe = DomainTrace(
            id="domain-trace:probe", digest="0" * 64, request_id=request.request_id, goal_id=request.goal_id,
            primary_domain=request.primary_domain, supporting_domains=tuple(item.domain_id for item in contributions[1:]),
            contributions=contributions, references=request.references,
            domain_results=tuple(DomainResultTraceReference(item.result_id, item.domain_id, "domain-trace:probe") for item in request.domain_results),
            status=request.status, started_at=request.started_at, completed_at=request.completed_at,
            duration_ms=duration_ms, metadata=request.metadata,
        )
        digest = probe.calculate_digest()
        trace_id = f"domain-trace:{digest[:24]}"
        return DomainTrace(
            id=trace_id, digest=digest, request_id=request.request_id, goal_id=request.goal_id,
            primary_domain=request.primary_domain, supporting_domains=tuple(item.domain_id for item in contributions[1:]),
            contributions=contributions, references=request.references,
            domain_results=tuple(DomainResultTraceReference(item.result_id, item.domain_id, trace_id) for item in request.domain_results),
            status=request.status, started_at=request.started_at, completed_at=request.completed_at,
            duration_ms=duration_ms, metadata=request.metadata,
        )

    @staticmethod
    def _canonical_contributions(request: DomainTraceAssemblyRequest) -> tuple[DomainTraceContribution, ...]:
        _, contributions = _canonical_participants(
            request.primary_domain,
            request.supporting_domains,
            request.contributions,
        )
        return contributions
