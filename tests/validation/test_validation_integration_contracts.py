"""Unit tests for Validation Integration Contracts (Subphase 7.13)."""

from datetime import datetime, timezone

from cmm.validation.enums import ValidationStatus
from cmm.validation.findings import ValidationFinding, ValidationSeverity
from cmm.validation.integration.contracts import (
    ValidationAction,
    ValidationDecision,
    ValidationEventPayload,
    ValidationMemoryRecord,
    ValidationPhase,
    ValidationPlanNode,
    ValidationTrigger,
)
from cmm.validation.results import ValidationResult


def test_validation_enums():
    assert ValidationPhase.BEFORE_EXECUTION == "before_execution"
    assert ValidationPhase.AFTER_EXECUTION == "after_execution"
    assert ValidationAction.CONTINUE == "continue"
    assert ValidationAction.ROLLBACK == "rollback"
    assert ValidationAction.STOP == "stop"


def test_validation_trigger():
    trig = ValidationTrigger(phase=ValidationPhase.AFTER_EXECUTION, actor="test_actor")
    assert trig.phase == ValidationPhase.AFTER_EXECUTION
    assert trig.actor == "test_actor"


def test_validation_decision_from_passed_result():
    res = ValidationResult(
        id="val-123",
        status=ValidationStatus.PASSED,
        duration_ms=10,
    )
    dec = ValidationDecision.from_validation_result(res)
    assert dec.validation_id == "val-123"
    assert dec.allowed_to_continue is True
    assert dec.recommended_action == ValidationAction.CONTINUE
    assert dec.requires_rollback is False


def test_validation_decision_from_failed_result():
    finding = ValidationFinding(
        code="ERR_SYNTAX",
        message="Syntax error in module",
        severity=ValidationSeverity.ERROR,
        source="syntax_check",
    )
    res = ValidationResult(
        id="val-456",
        status=ValidationStatus.FAILED,
        blocking_findings=(finding,),
        duration_ms=20,
    )
    dec = ValidationDecision.from_validation_result(
        res, phase=ValidationPhase.AFTER_EXECUTION
    )
    assert dec.validation_id == "val-456"
    assert dec.allowed_to_continue is False
    assert dec.recommended_action == ValidationAction.ROLLBACK
    assert dec.requires_rollback is True


def test_validation_plan_node_serialization():
    node = ValidationPlanNode(
        id="node-1",
        phase=ValidationPhase.AFTER_EXECUTION,
        policy_name="default",
        steps=("syntax_check",),
        depends_on=("step-0",),
        on_pass=ValidationAction.CONTINUE,
        on_failure=ValidationAction.ROLLBACK,
    )
    serialized = node.serialize()
    assert serialized["id"] == "node-1"
    assert serialized["on_pass"] == "continue"

    deserialized = ValidationPlanNode.deserialize(serialized)
    assert deserialized.id == "node-1"
    assert deserialized.on_pass == ValidationAction.CONTINUE


def test_validation_event_payload_sanitization():
    payload = ValidationEventPayload(
        event_type="validation.started",
        validation_id="val-789",
        metadata={"safe_key": "safe_val", "api_token": "secret_token_123"},
    )
    serialized = payload.serialize()
    assert "safe_key" in serialized["metadata"]
    assert "api_token" not in serialized["metadata"]


def test_validation_memory_record_serialization():
    record = ValidationMemoryRecord(
        validation_id="val-100",
        timestamp=datetime.now(timezone.utc).isoformat(),
        policy="default",
        change_type="code_modification",
        status="failed",
        decision="rollback",
        recurring_finding_codes=("ERR_SYNTAX",),
        affected_files=("src/main.py",),
    )
    serialized = record.serialize()
    assert serialized["validation_id"] == "val-100"
    assert serialized["recurring_finding_codes"] == ["ERR_SYNTAX"]
