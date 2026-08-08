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
    assert (
        ops["health.build_medical_timeline"].operation_type
        is DomainOperationType.ANALYSIS
    )
    assert (
        ops["health.prepare_questions"].operation_type
        is DomainOperationType.PREPARATION
    )
    assert (
        ops["health.register_symptom_update"].operation_type
        is DomainOperationType.MEMORY
    )
    # export_medical_context prepares context for a clinician; it must never
    # be an EXTERNAL/transmit operation (no outbound side effect).
    assert ops["health.export_medical_context"].operation_type in (
        DomainOperationType.ANALYSIS,
        DomainOperationType.PREPARATION,
    )
    assert (
        ops["health.review_medication_changes"].operation_type
        is DomainOperationType.SENSITIVE
    )
    assert (
        ops["health.review_medication_changes"].operation_id
        == "health.review_medication_changes"
    )


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


def test_export_medical_context_prepares_context_not_proposal_binding():
    """The export op describes what was gathered for a clinician; its output is
    context/references/provenance/uncertainty, never a proposal+binding, and it
    has no external transmission effect."""
    export = _ops()["health.export_medical_context"]
    output_keys = set(export.output_schema["properties"].keys())
    assert "context" in output_keys
    assert "references" in output_keys
    assert "provenance" in output_keys
    assert "uncertainty" in output_keys
    assert not ({"proposal", "binding"} <= output_keys)
    assert _is_closed(export.output_schema)
    assert export.requires_approval is True


def test_proposal_only_only_for_register_symptom_update():
    """proposal_only describes a write-proposal op and is independent of
    requires_approval; only register_symptom_update is proposal_only."""
    for op in health.build_health_operation_definitions():
        proposal_only = op.metadata.get("proposal_only", False)
        assert proposal_only is (op.operation_id == "health.register_symptom_update")


def test_required_resources_only_where_structurally_valid():
    """required_resources uses AND semantics — an op only declares a resource it
    structurally consumes; not every op is mechanically non-empty."""
    ops = {op.operation_id: op for op in health.build_health_operation_definitions()}
    materialized = {rid for rid in _health_resource_ids()}
    for op_id, op in ops.items():
        for resource_id in op.required_resources:
            assert resource_id in materialized


def test_operation_schemas_are_not_all_identical():
    """The twelve Health operations must carry meaningfully distinct closed
    input/output schemas — not a single copy-pasted shape."""
    input_shapes = {
        op.operation_id: (
            op.input_schema["required"],
            tuple(op.input_schema["properties"]),
        )
        for op in health.build_health_operation_definitions()
    }
    output_shapes = {
        op.operation_id: tuple(op.output_schema["properties"])
        for op in health.build_health_operation_definitions()
    }
    assert len(set(input_shapes.values())) > 1
    assert len(set(output_shapes.values())) > 1


def test_no_medication_autonomous_action_operation():
    """No Health operation encodes an autonomous start/stop/dose/treatment
    medication action."""
    review = _ops()["health.review_medication_changes"]
    for op in health.build_health_operation_definitions():
        assert "dose" not in op.operation_id
        assert "change" not in review.output_schema.get("properties", {})
        assert not (
            {"prescribed", "dose_intent", "therapy_started", "start_dose", "stop_dose"}
            & set(review.output_schema.get("properties", {}))
        )
    assert not (
        {"health.start_medication", "health.stop_medication", "health.adjust_dose"}
        & {op.operation_id for op in health.build_health_operation_definitions()}
    )


def test_no_definitive_diagnosis_output_field():
    for op in health.build_health_operation_definitions():
        props = op.output_schema.get("properties", {})
        assert not (
            {"confirmed_diagnosis", "definitive_diagnosis", "diagnosis"} & set(props)
        )


def _is_closed(schema):
    return schema.get("additionalProperties", True) is False


def _health_resource_ids():
    return tuple(r.id for r in health.build_health_resource_definitions())


def _ops():
    return {op.operation_id: op for op in health.build_health_operation_definitions()}
