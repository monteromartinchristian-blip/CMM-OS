"""Tests for Phase 10.20 Health Domain operations."""

from __future__ import annotations

from cmm.domains import health
from cmm.domains.enums import DomainOperationType
from cmm.domains.health.catalog import CANONICAL_HEALTH_OPERATION_IDS


def test_twelve_operations_and_canonical_order():
    ops = health.build_health_operation_definitions()
    assert len(ops) == 12
    assert [op.operation_id for op in ops] == list(CANONICAL_HEALTH_OPERATION_IDS)


def test_classification():
    ops = {op.operation_id: op for op in health.build_health_operation_definitions()}
    assert ops["health.build_medical_timeline"].operation_type is DomainOperationType.ANALYSIS
    assert ops["health.prepare_questions"].operation_type is DomainOperationType.PREPARATION
    assert ops["health.register_symptom_update"].operation_type is DomainOperationType.MEMORY
    assert ops["health.export_medical_context"].operation_type is DomainOperationType.EXTERNAL
    assert ops["health.review_medication_changes"].operation_type is DomainOperationType.SENSITIVE


def test_approval_gated_operations():
    ops = {op.operation_id: op for op in health.build_health_operation_definitions()}
    assert ops["health.export_medical_context"].requires_approval is True
    assert ops["health.register_symptom_update"].requires_approval is True


def test_no_destructive_operations():
    ops = health.build_health_operation_definitions()
    assert all(op.operation_type is not DomainOperationType.DESTRUCTIVE for op in ops)
    assert all(op.reversible is False for op in ops)


def test_schemas_and_metadata():
    for op in health.build_health_operation_definitions():
        assert op.input_schema.get("type") == "object"
        assert op.output_schema.get("type") == "object"
        assert op.domain_id == "domain:health"
        assert op.version == "1.0.0"
