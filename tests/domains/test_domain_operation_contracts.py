from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains import (
    DomainOperationContractError,
    DomainOperationDefinition,
    DomainOperationError,
    DomainOperationRequest,
    DomainOperationResult,
    DomainOperationRollbackResult,
    DomainOperationSerializationError,
    DomainOperationStatus,
    DomainOperationTraceEntry,
    DomainOperationType,
    validate_domain_operation_transition,
)


def _definition(**overrides: object) -> DomainOperationDefinition:
    values: dict[str, object] = {
        "operation_id": "health.prepare_medical_appointment",
        "domain_id": "domain:health",
        "version": "1.0.0",
        "name": "Prepare medical appointment",
        "description": "Prepare a structured consultation summary",
        "operation_type": DomainOperationType.PREPARATION,
        "input_schema": {
            "type": "object",
            "properties": {"notes": {"type": "string"}},
            "required": ["notes"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object"},
        "required_resources": ("resource:health.notes",),
        "required_permissions": ("health.read",),
        "risk_level": PolicyRiskLevel.HIGH,
        "reversible": True,
        "requires_approval": False,
        "metadata": {"nested": {"safe": [True, None]}},
    }
    values.update(overrides)
    return DomainOperationDefinition(**values)  # type: ignore[arg-type]


def test_operation_types_and_statuses_are_closed() -> None:
    assert [item.value for item in DomainOperationType] == [
        "read",
        "analysis",
        "preparation",
        "memory",
        "planning",
        "external",
        "sensitive",
        "destructive",
    ]
    assert [item.value for item in DomainOperationStatus] == [
        "registered",
        "available",
        "unavailable",
        "blocked",
        "waiting_for_approval",
        "running",
        "completed",
        "failed",
        "rolled_back",
        "cancelled",
    ]
    with pytest.raises(ValueError):
        DomainOperationType("invalid")


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("registered", "available"),
        ("registered", "unavailable"),
        ("registered", "blocked"),
        ("registered", "waiting_for_approval"),
        ("available", "running"),
        ("waiting_for_approval", "available"),
        ("running", "completed"),
        ("running", "failed"),
        ("running", "cancelled"),
        ("failed", "rolled_back"),
    ],
)
def test_valid_state_transitions(source: str, target: str) -> None:
    assert validate_domain_operation_transition(
        source, target
    ) is DomainOperationStatus(target)


@pytest.mark.parametrize(
    ("source", "target"),
    [("completed", "running"), ("cancelled", "available"), ("registered", "completed")],
)
def test_invalid_state_transitions_raise(source: str, target: str) -> None:
    with pytest.raises(DomainOperationContractError, match="transition"):
        validate_domain_operation_transition(source, target)


def test_definition_is_strict_immutable_serializable_and_maps_to_common_descriptor() -> (
    None
):
    definition = _definition()
    with pytest.raises(TypeError):
        definition.metadata["nested"]["safe"] += (False,)  # type: ignore[index,operator]
    with pytest.raises(FrozenInstanceError):
        definition.enabled = False  # type: ignore[misc]
    restored = DomainOperationDefinition.from_dict(definition.to_dict())
    assert restored == definition
    assert json.loads(json.dumps(definition.to_dict())) == definition.to_dict()
    descriptor = definition.to_operation_descriptor()
    assert descriptor.name == definition.operation_id
    assert descriptor.version == "1.0.0"
    assert descriptor.required_permissions == ("health.read",)


@pytest.mark.parametrize("version", ["1", "1.0", "01.0.0", "1.0.0-"])
def test_definition_rejects_invalid_semver(version: str) -> None:
    with pytest.raises(DomainOperationContractError, match="semantic version"):
        _definition(version=version)


def test_definition_rejects_domain_mismatch_and_false_rollback_claims() -> None:
    with pytest.raises(DomainOperationContractError, match="domain"):
        _definition(operation_id="project.prepare", domain_id="domain:health")
    with pytest.raises(DomainOperationContractError, match="rollback"):
        _definition(reversible=False, rollback_policy_id="rollback:health")
    with pytest.raises(DomainOperationContractError, match="approval"):
        _definition(operation_type="destructive", requires_approval=False)


def test_contracts_reject_unknown_fields_nonfinite_and_callables() -> None:
    payload = _definition().to_dict()
    payload["unknown"] = True
    with pytest.raises(DomainOperationSerializationError, match="unknown fields"):
        DomainOperationDefinition.from_dict(payload)
    with pytest.raises(DomainOperationContractError, match="JSON-safe"):
        _definition(metadata={"value": float("nan")})
    with pytest.raises(DomainOperationContractError, match="JSON-safe"):
        _definition(metadata={"callable": lambda: None})


def test_request_fingerprint_binds_inputs_and_context() -> None:
    request = DomainOperationRequest(
        request_id="request:1",
        operation_id="health.prepare_medical_appointment",
        operation_version="1.0.0",
        inputs={"notes": "headache"},
        agent_run_id="run:1",
        task_id="task:1",
        primary_domain_id="domain:health",
        supporting_domain_ids=("domain:general",),
        granted_permissions=("health.read",),
        available_resources=("resource:health.notes",),
        idempotency_key="idem:1",
    )
    restored = DomainOperationRequest.from_dict(request.to_dict())
    assert restored == request
    assert request.calculate_fingerprint() == restored.calculate_fingerprint()
    changed = DomainOperationRequest.from_dict(
        {**request.to_dict(), "inputs": {"notes": "changed"}}
    )
    assert changed.calculate_fingerprint() != request.calculate_fingerprint()


def test_result_round_trip_temporal_and_error_invariants() -> None:
    started = datetime(2026, 8, 1, 10, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=1)
    trace = DomainOperationTraceEntry(
        code="operation.completed",
        status=DomainOperationStatus.COMPLETED,
        occurred_at=completed,
        reason_code="execution.validated",
    )
    result = DomainOperationResult(
        result_id="result:1",
        request_id="request:1",
        operation_id="health.prepare_medical_appointment",
        operation_version="1.0.0",
        domain_id="domain:health",
        status=DomainOperationStatus.COMPLETED,
        output={"summary": "safe"},
        started_at=started,
        completed_at=completed,
        trace_entries=(trace,),
    )
    assert DomainOperationResult.from_dict(result.to_dict()) == result
    json.dumps(result.to_dict(), allow_nan=False)
    with pytest.raises(DomainOperationContractError, match="timezone-aware"):
        DomainOperationResult.from_dict(
            {**result.to_dict(), "started_at": "2026-08-01T10:00:00"}
        )
    with pytest.raises(DomainOperationContractError, match="before"):
        DomainOperationResult.from_dict(
            {
                **result.to_dict(),
                "completed_at": (started - timedelta(seconds=1)).isoformat(),
            }
        )


def test_error_hierarchy_has_stable_safe_serialization() -> None:
    error = DomainOperationContractError("invalid contract", details={"field": "id"})
    assert isinstance(error, DomainOperationError)
    assert error.to_dict() == {
        "code": "DOMAIN_OPERATION_CONTRACT_ERROR",
        "message": "invalid contract",
        "details": {"field": "id"},
    }


def _result_values(**overrides: object) -> dict[str, object]:
    started = datetime(2026, 8, 1, 10, tzinfo=timezone.utc)
    values: dict[str, object] = {
        "result_id": "result:invariant",
        "request_id": "request:invariant",
        "operation_id": "general.prepare_structured_summary",
        "operation_version": "1.0.0",
        "domain_id": "domain:general",
        "status": DomainOperationStatus.COMPLETED,
        "started_at": started,
        "completed_at": started,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    "overrides",
    [
        {"error": {"code": "E_CANCELLED"}},
        {
            "rollback_result": DomainOperationRollbackResult(
                attempted=True, succeeded=True, policy_id="rollback:1", error=None
            )
        },
        {
            "status": DomainOperationStatus.ROLLED_BACK,
            "rollback_result": DomainOperationRollbackResult(
                attempted=True, succeeded=False, policy_id="rollback:1", error={}
            ),
        },
        {"status": DomainOperationStatus.FAILED},
        {
            "status": DomainOperationStatus.FAILED,
            "error": {"code": "E_FAILED"},
            "rollback_result": DomainOperationRollbackResult(
                attempted=True, succeeded=True, policy_id="rollback:1", error=None
            ),
        },
        {"status": DomainOperationStatus.WAITING_FOR_APPROVAL},
        {
            "status": DomainOperationStatus.BLOCKED,
            "transaction_id": "transaction:open",
        },
    ],
)
def test_result_rejects_impossible_status_field_combinations(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(DomainOperationContractError):
        DomainOperationResult(**_result_values(**overrides))  # type: ignore[arg-type]


def test_result_invariants_apply_through_round_trip() -> None:
    rollback = DomainOperationRollbackResult(
        attempted=True,
        succeeded=False,
        policy_id="rollback:1",
        error={"code": "E_ROLLBACK", "details": {}},
    )
    result = DomainOperationResult(
        **_result_values(
            status=DomainOperationStatus.FAILED,
            error={"code": "E_CANCELLED", "details": {}},
            rollback_result=rollback,
        )
    )
    assert DomainOperationResult.from_dict(result.to_dict()) == result

    waiting = DomainOperationResult(
        **_result_values(
            status=DomainOperationStatus.WAITING_FOR_APPROVAL,
            metadata={"approval": {"status": "pending"}},
        )
    )
    assert DomainOperationResult.from_dict(waiting.to_dict()) == waiting

    completed = DomainOperationResult(**_result_values())
    invalid_payload = {**completed.to_dict(), "error": {"code": "E_LATE"}}
    with pytest.raises(DomainOperationContractError):
        DomainOperationResult.from_dict(invalid_payload)
