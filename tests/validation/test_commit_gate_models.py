from datetime import datetime, timezone

import pytest

from cmm.validation.commit_gate.enums import CommitGateReasonCode
from cmm.validation.commit_gate.models import CommitGateReason, CommitGateResult
from cmm.validation.enums import ValidationSeverity
from cmm.validation.errors import ValidationContractError
from cmm.validation.findings import ValidationFinding


def test_commit_gate_reason_basic() -> None:
    finding = ValidationFinding(
        code="E501",
        message="Line too long",
        severity=ValidationSeverity.WARNING,
        source="linter",
    )
    reason = CommitGateReason(
        code=CommitGateReasonCode.REQUIRED_STEP_FAILED,
        message="Step 'lint' failed",
        step="lint",
        finding=finding,
        metadata={"detail": "info"},
    )

    assert reason.code == CommitGateReasonCode.REQUIRED_STEP_FAILED
    assert reason.message == "Step 'lint' failed"
    assert reason.step == "lint"

    serialized = reason.serialize()
    assert serialized["code"] == "required_step_failed"
    assert serialized["finding"]["code"] == "E501"

    deserialized = CommitGateReason.from_mapping(serialized)
    assert deserialized.code == CommitGateReasonCode.REQUIRED_STEP_FAILED
    assert deserialized.finding is not None
    assert deserialized.finding.code == "E501"


def test_commit_gate_reason_invalid() -> None:
    with pytest.raises(ValidationContractError):
        CommitGateReason(code="non_existent_code", message="msg")

    with pytest.raises(ValidationContractError):
        CommitGateReason(code=CommitGateReasonCode.REQUIRED_STEP_FAILED, message="")


def test_commit_gate_result_invariants() -> None:
    # Empty validation_result_id
    with pytest.raises(
        ValidationContractError, match="validation_result_id must not be empty"
    ):
        CommitGateResult(allowed=True, validation_result_id="")

    # commit_created=True requires commit_hash
    with pytest.raises(ValidationContractError, match="requires non-empty commit_hash"):
        CommitGateResult(
            allowed=True,
            validation_result_id="v-1",
            authorized=True,
            commit_requested=True,
            commit_created=True,
            commit_hash=None,
            commit_message="msg",
        )

    # commit_created=True requires authorized=True
    with pytest.raises(ValidationContractError, match="authorized=False"):
        CommitGateResult(
            allowed=True,
            validation_result_id="v-1",
            authorized=False,
            commit_requested=True,
            commit_created=True,
            commit_hash="abc",
            commit_message="msg",
        )

    # commit_created=True requires allowed=True
    with pytest.raises(ValidationContractError, match="allowed=False"):
        CommitGateResult(
            allowed=False,
            validation_result_id="v-1",
            authorized=True,
            commit_requested=True,
            commit_created=True,
            commit_hash="abc",
            commit_message="msg",
        )

    # commit_created=False cannot have commit_hash
    with pytest.raises(ValidationContractError, match="commit_hash must be None"):
        CommitGateResult(
            allowed=True,
            validation_result_id="v-1",
            commit_created=False,
            commit_hash="abc",
        )


def test_commit_gate_result_serialization() -> None:
    now = datetime.now(timezone.utc)
    res = CommitGateResult(
        allowed=True,
        validation_result_id="v-100",
        policy_name="small_change",
        evaluated_at=now,
        metadata={"key": "value"},
    )

    serialized = res.serialize()
    assert serialized["allowed"] is True
    assert serialized["validation_result_id"] == "v-100"
    assert serialized["policy_name"] == "small_change"

    roundtrip = CommitGateResult.from_mapping(serialized)
    assert roundtrip.allowed is True
    assert roundtrip.validation_result_id == "v-100"
    assert roundtrip.policy_name == "small_change"
    assert roundtrip.metadata == {"key": "value"}
