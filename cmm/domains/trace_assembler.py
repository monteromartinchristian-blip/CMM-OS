"""Pure, deterministic assembly of reference-only Domain Traces."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    _canonical_json,
    _canonical_participants,
    _thaw,
    _validate_domain_result_coverage,
    _validate_global_id_uniqueness,
)


@dataclass(frozen=True, slots=True)
class DomainTraceIdentity:
    """Canonical pre-assembly identity and cryptographic digest for a DomainTrace."""

    trace_id: str
    digest: str


def calculate_domain_trace_identity(
    request: DomainTraceAssemblyRequest | Mapping[str, Any],
) -> DomainTraceIdentity:
    """Calculate deterministic trace_id and digest from canonical assembly request inputs."""
    if not isinstance(request, DomainTraceAssemblyRequest):
        if not isinstance(request, Mapping):
            raise TypeError("request must be DomainTraceAssemblyRequest or a mapping")
        request = DomainTraceAssemblyRequest.from_dict(request)

    contributions = DomainTraceAssembler._canonical_contributions(request)
    _validate_domain_result_coverage(contributions, request.domain_results)
    _validate_global_id_uniqueness(contributions, request.references)
    duration_ms = int(
        (request.completed_at - request.started_at).total_seconds() * 1000
    )

    payload = {
        "request_id": request.request_id,
        "goal_id": request.goal_id,
        "primary_domain": str(request.primary_domain),
        "supporting_domains": [str(item) for item in request.supporting_domains],
        "contributions": [item.to_dict() for item in contributions],
        "references": request.references.to_dict(),
        "domain_results": [
            {
                "result_id": item.result_id,
                "domain_id": str(item.domain_id),
                "trace_id": None,
            }
            for item in request.domain_results
        ],
        "status": request.status.value,
        "started_at": request.started_at.isoformat(),
        "completed_at": request.completed_at.isoformat(),
        "duration_ms": duration_ms,
        "metadata": _thaw(request.metadata),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    trace_id = f"domain-trace:{digest[:24]}"
    return DomainTraceIdentity(trace_id=trace_id, digest=digest)


class DomainTraceAssembler:
    """Constructs a final trace without querying any runtime or store."""

    @staticmethod
    def identity_for(
        request: DomainTraceAssemblyRequest | Mapping[str, Any],
    ) -> DomainTraceIdentity:
        """Derive canonical pre-assembly identity for the given assembly request."""
        return calculate_domain_trace_identity(request)

    def assemble(
        self, request: DomainTraceAssemblyRequest | Mapping[str, Any]
    ) -> DomainTrace:
        if not isinstance(request, DomainTraceAssemblyRequest):
            if not isinstance(request, Mapping):
                raise TypeError(
                    "request must be DomainTraceAssemblyRequest or a mapping"
                )
            request = DomainTraceAssemblyRequest.from_dict(request)
        identity = calculate_domain_trace_identity(request)
        contributions = self._canonical_contributions(request)
        duration_ms = int(
            (request.completed_at - request.started_at).total_seconds() * 1000
        )
        return DomainTrace(
            id=identity.trace_id,
            digest=identity.digest,
            request_id=request.request_id,
            goal_id=request.goal_id,
            primary_domain=request.primary_domain,
            supporting_domains=tuple(item.domain_id for item in contributions[1:]),
            contributions=contributions,
            references=request.references,
            domain_results=tuple(
                DomainResultTraceReference(
                    item.result_id, item.domain_id, identity.trace_id
                )
                for item in request.domain_results
            ),
            status=request.status,
            started_at=request.started_at,
            completed_at=request.completed_at,
            duration_ms=duration_ms,
            metadata=request.metadata,
        )

    @staticmethod
    def _canonical_contributions(
        request: DomainTraceAssemblyRequest,
    ) -> tuple[DomainTraceContribution, ...]:
        _, contributions = _canonical_participants(
            request.primary_domain,
            request.supporting_domains,
            request.contributions,
        )
        return contributions


__all__ = [
    "DomainTraceAssembler",
    "DomainTraceIdentity",
    "calculate_domain_trace_identity",
]
