"""Phase 10.17 assembly and pre-assembly identity behaviour."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import (
    DomainTraceContractError,
    DomainTraceSerializationError,
)
from cmm.domains.trace_assembler import (
    DomainTraceAssembler,
    DomainTraceIdentity,
    calculate_domain_trace_identity,
)
from cmm.domains.trace_contracts import (
    DomainResultTraceReference,
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceReference,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def _sample_request() -> DomainTraceAssemblyRequest:
    primary = DomainTraceContribution(
        domain_id="domain:life-plan",
        role=DomainTraceRole.PRIMARY,
        references=(
            DomainTraceReference(
                ref_id="result:1",
                kind=DomainTraceReferenceKind.DOMAIN_RESULT,
                domain_id="domain:life-plan",
            ),
            DomainTraceReference(
                ref_id="profile:1",
                kind=DomainTraceReferenceKind.PROFILE,
                domain_id="domain:life-plan",
            ),
        ),
    )
    supporting = DomainTraceContribution(
        domain_id="domain:health",
        role=DomainTraceRole.SUPPORTING,
        references=(
            DomainTraceReference(
                ref_id="result:2",
                kind=DomainTraceReferenceKind.DOMAIN_RESULT,
                domain_id="domain:health",
            ),
        ),
    )
    return DomainTraceAssemblyRequest(
        request_id="request:1",
        goal_id="goal:1",
        primary_domain="domain:life-plan",
        supporting_domains=("domain:health",),
        contributions=(primary, supporting),
        references=DomainTraceReferences(
            resolution_context_id="resolution-context:1",
            resolution_result_id="resolution-result:1",
            composition_id="composition:1",
            presentation_result_ids=("pres:1",),
        ),
        domain_results=(
            DomainResultTraceReference("result:1", "domain:life-plan"),
            DomainResultTraceReference("result:2", "domain:health"),
        ),
        started_at=NOW,
        completed_at=datetime(2026, 8, 2, 12, 0, 1, tzinfo=timezone.utc),
        metadata={"category": "audit-v5"},
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
        started_at=NOW,
        completed_at=datetime(2026, 8, 2, 12, 0, 1, tzinfo=timezone.utc),
    )

    trace = DomainTraceAssembler().assemble(request)

    assert trace.id == f"domain-trace:{trace.digest[:24]}"
    assert trace.duration_ms == 1000
    assert "objective" not in trace.to_dict()


def test_shared_preassembly_identity_matches_assembly() -> None:
    request = _sample_request()

    identity = calculate_domain_trace_identity(request)
    identity_from_cls = DomainTraceAssembler.identity_for(request)
    trace = DomainTraceAssembler().assemble(request)

    assert isinstance(identity, DomainTraceIdentity)
    assert identity == identity_from_cls
    assert identity.trace_id == trace.id
    assert identity.digest == trace.digest
    assert identity.trace_id == f"domain-trace:{identity.digest[:24]}"

    # Also check mapping support
    identity_from_mapping = calculate_domain_trace_identity(request.to_dict())
    assert identity_from_mapping == identity


def test_shared_preassembly_identity_is_deterministic() -> None:
    request = _sample_request()

    id1 = calculate_domain_trace_identity(request)
    id2 = calculate_domain_trace_identity(request)

    assert id1 == id2
    assert id1.trace_id == id2.trace_id
    assert id1.digest == id2.digest


def test_shared_preassembly_identity_canonicalizes_participant_ordering() -> None:
    primary = DomainTraceContribution(
        domain_id="domain:life-plan",
        role=DomainTraceRole.PRIMARY,
        references=(
            DomainTraceReference(
                "result:1", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:life-plan"
            ),
        ),
    )
    sup_health = DomainTraceContribution(
        domain_id="domain:health",
        role=DomainTraceRole.SUPPORTING,
        references=(
            DomainTraceReference(
                "result:2", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:health"
            ),
        ),
    )
    sup_nutrition = DomainTraceContribution(
        domain_id="domain:nutrition",
        role=DomainTraceRole.SUPPORTING,
        references=(
            DomainTraceReference(
                "result:3", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:nutrition"
            ),
        ),
    )

    req1 = DomainTraceAssemblyRequest(
        request_id="request:1",
        primary_domain="domain:life-plan",
        supporting_domains=("domain:health", "domain:nutrition"),
        contributions=(primary, sup_health, sup_nutrition),
        references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
        domain_results=(
            DomainResultTraceReference("result:1", "domain:life-plan"),
            DomainResultTraceReference("result:2", "domain:health"),
            DomainResultTraceReference("result:3", "domain:nutrition"),
        ),
        started_at=NOW,
        completed_at=NOW,
    )
    req2 = DomainTraceAssemblyRequest(
        request_id="request:1",
        primary_domain="domain:life-plan",
        supporting_domains=("domain:nutrition", "domain:health"),
        contributions=(primary, sup_nutrition, sup_health),
        references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
        domain_results=(
            DomainResultTraceReference("result:3", "domain:nutrition"),
            DomainResultTraceReference("result:1", "domain:life-plan"),
            DomainResultTraceReference("result:2", "domain:health"),
        ),
        started_at=NOW,
        completed_at=NOW,
    )

    id1 = calculate_domain_trace_identity(req1)
    id2 = calculate_domain_trace_identity(req2)

    assert id1 == id2


def test_shared_preassembly_identity_mutations_change_identity() -> None:
    base = _sample_request()
    base_id = calculate_domain_trace_identity(base)

    mutated_req_id = DomainTraceAssemblyRequest(
        request_id="request:2",
        goal_id=base.goal_id,
        primary_domain=base.primary_domain,
        supporting_domains=base.supporting_domains,
        contributions=base.contributions,
        references=base.references,
        domain_results=base.domain_results,
        started_at=base.started_at,
        completed_at=base.completed_at,
        metadata=base.metadata,
    )
    assert calculate_domain_trace_identity(mutated_req_id) != base_id

    mutated_goal = DomainTraceAssemblyRequest(
        request_id=base.request_id,
        goal_id="goal:different",
        primary_domain=base.primary_domain,
        supporting_domains=base.supporting_domains,
        contributions=base.contributions,
        references=base.references,
        domain_results=base.domain_results,
        started_at=base.started_at,
        completed_at=base.completed_at,
        metadata=base.metadata,
    )
    assert calculate_domain_trace_identity(mutated_goal) != base_id

    mutated_meta = DomainTraceAssemblyRequest(
        request_id=base.request_id,
        goal_id=base.goal_id,
        primary_domain=base.primary_domain,
        supporting_domains=base.supporting_domains,
        contributions=base.contributions,
        references=base.references,
        domain_results=base.domain_results,
        started_at=base.started_at,
        completed_at=base.completed_at,
        metadata={"category": "other"},
    )
    assert calculate_domain_trace_identity(mutated_meta) != base_id


def test_shared_preassembly_identity_fails_consistently_on_invalid_inputs() -> None:
    with pytest.raises(TypeError, match="DomainTraceAssemblyRequest or a mapping"):
        calculate_domain_trace_identity(12345)  # type: ignore[arg-type]

    with pytest.raises(DomainTraceContractError):
        DomainTraceAssemblyRequest(
            request_id="invalid ID with spaces",
            primary_domain="domain:life-plan",
            contributions=(),
            references=DomainTraceReferences("ctx:1", "res:1", "comp:1"),
            started_at=NOW,
            completed_at=NOW,
        )

    invalid_mapping = {
        "request_id": "invalid ID with spaces",
        "primary_domain": "domain:life-plan",
        "contributions": [],
        "references": {
            "resolution_context_id": "ctx:1",
            "resolution_result_id": "res:1",
            "composition_id": "comp:1",
        },
        "started_at": NOW.isoformat(),
        "completed_at": NOW.isoformat(),
    }
    with pytest.raises(DomainTraceSerializationError):
        calculate_domain_trace_identity(invalid_mapping)
