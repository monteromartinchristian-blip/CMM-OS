"""Contract tests for the final reference-only Domain Trace."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    CrossDomainTraceReference,
    DomainResultTraceReference,
    DomainTrace,
    DomainTraceAssemblyRequest,
    DomainTraceContractError,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceSerializationError,
)

NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


def _request() -> DomainTraceAssemblyRequest:
    primary = DomainTraceContribution(
        "domain:life-plan", DomainTraceRole.PRIMARY,
        (DomainTraceReference("domain-result:1", DomainTraceReferenceKind.DOMAIN_RESULT, "domain:life-plan"),),
    )
    supporting = DomainTraceContribution(
        "domain:health", DomainTraceRole.SUPPORTING,
        (DomainTraceReference("warning:1", DomainTraceReferenceKind.WARNING, "domain:health"),),
    )
    return DomainTraceAssemblyRequest(
        request_id="request:1", goal_id="goal:1", primary_domain="domain:life-plan",
        supporting_domains=("domain:health",), contributions=(primary, supporting),
        references=DomainTraceReferences("resolution-context:1", "resolution-result:1", "composition:1"),
        domain_results=(DomainResultTraceReference("domain-result:1", "domain:life-plan"),),
        started_at=NOW, completed_at=NOW.replace(second=1), metadata={"phase": "phase-10"},
    )


def test_contract_round_trip_is_final_frozen_and_reference_only() -> None:
    trace = DomainTraceAssembler().assemble(_request())

    restored = trace.from_dict(trace.to_dict())

    assert restored == trace
    assert trace.id == trace.canonical_id
    assert "objective" not in trace.to_dict()
    assert not hasattr(__import__("cmm.domains.trace_contracts", fromlist=["*"]), "CrossDomain" + "TransferTrace")
    with pytest.raises(FrozenInstanceError):
        trace.request_id = "request:other"  # type: ignore[misc]


def test_contributions_require_one_exact_primary_and_every_supporting_domain() -> None:
    request = _request()
    duplicate_primary = DomainTraceContribution("domain:health", DomainTraceRole.PRIMARY)

    with pytest.raises(DomainTraceContractError):
        DomainTraceAssemblyRequest(
            request_id=request.request_id, primary_domain=request.primary_domain,
            supporting_domains=request.supporting_domains,
            contributions=(request.contributions[0], duplicate_primary), references=request.references,
            started_at=request.started_at, completed_at=request.completed_at,
        )


def test_request_rejects_a_primary_or_supporting_contribution_with_the_wrong_role() -> None:
    request = _request()
    inverted = (
        DomainTraceContribution("domain:life-plan", DomainTraceRole.SUPPORTING),
        DomainTraceContribution("domain:health", DomainTraceRole.PRIMARY),
    )

    with pytest.raises(DomainTraceContractError):
        DomainTraceAssemblyRequest(
            request_id=request.request_id, primary_domain=request.primary_domain,
            supporting_domains=request.supporting_domains, contributions=inverted,
            references=request.references, started_at=request.started_at,
            completed_at=request.completed_at,
        )


def test_reference_category_is_strictly_tied_to_domain_ownership() -> None:
    with pytest.raises(DomainTraceContractError):
        DomainTraceReference("resolution-context:1", DomainTraceReferenceKind.RESOLUTION_CONTEXT, "domain:health")
    with pytest.raises(DomainTraceContractError):
        DomainTraceReference("warning:1", DomainTraceReferenceKind.WARNING)


def test_inventory_rejects_duplicate_result_pairing_ids() -> None:
    pairing = DomainResultTraceReference("domain-result:1", "domain:life-plan", "domain-trace:1")

    with pytest.raises(DomainTraceContractError):
        DomainTraceReferenceInventory(
            references=(), domain_results=(pairing, pairing),
            expected_primary_domain="domain:life-plan",
            resolution_result_domains=DomainTraceDomainSelection("resolution-result:1", "domain:life-plan"),
            composition_domains=DomainTraceDomainSelection("composition:1", "domain:life-plan"),
        )


@pytest.mark.parametrize("trace_id", (None, "", "bad trace id"))
def test_cross_domain_pairing_requires_a_safe_trace_id(trace_id) -> None:
    with pytest.raises(DomainTraceContractError):
        CrossDomainTraceReference("cross-domain-result:1", trace_id)  # type: ignore[arg-type]


def test_cross_domain_pairing_rejects_legacy_mapping_without_trace_id_cleanly() -> None:
    with pytest.raises(DomainTraceSerializationError):
        CrossDomainTraceReference.from_dict({"result_id": "cross-domain-result:1"})


@pytest.mark.parametrize(
    "mutate",
    (
        lambda data: data.update(supporting_domains=["domain:health", "domain:life-plan"]),
        lambda data: data.update(supporting_domains=["domain:health", "domain:health"]),
        lambda data: data["contributions"].append(data["contributions"][1]),
        lambda data: data["contributions"].pop(),
        lambda data: data["contributions"].append({"domain_id": "domain:foreign", "role": "supporting", "references": []}),
        lambda data: data["contributions"][0].update(role="supporting"),
    ),
)
def test_final_trace_rejects_invalid_participant_invariants(mutate) -> None:
    payload = DomainTraceAssembler().assemble(_request()).to_dict()
    mutate(payload)

    with pytest.raises(DomainTraceSerializationError):
        DomainTrace.from_dict(payload)


@pytest.mark.parametrize("key", (1, ("extra",), "extra"))
def test_from_dict_rejects_unknown_or_non_string_keys_without_type_errors(key) -> None:
    payload = DomainTraceAssembler().assemble(_request()).to_dict()
    payload[key] = "sensitive value must not be echoed"

    with pytest.raises(DomainTraceSerializationError) as error:
        DomainTrace.from_dict(payload)

    assert "sensitive value must not be echoed" not in str(error.value)


def test_from_dict_accepts_a_valid_mapping_after_strict_key_validation() -> None:
    trace = DomainTraceAssembler().assemble(_request())

    assert DomainTrace.from_dict(trace.to_dict()) == trace


def test_from_dict_rejects_mixed_unknown_key_types_without_type_error() -> None:
    payload = DomainTraceAssembler().assemble(_request()).to_dict()
    payload[1] = "private value"
    payload["extra"] = "another private value"

    with pytest.raises(DomainTraceSerializationError) as error:
        DomainTrace.from_dict(payload)

    assert "private value" not in str(error.value)
