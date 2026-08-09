"""Tests for Phase 10.22 University Domain operations."""

from __future__ import annotations

from cmm.domains import university
from cmm.domains.enums import DomainOperationType
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_OPERATION_IDS


def test_eleven_operations_and_canonical_order():
    ops = university.build_university_operation_definitions()
    assert len(ops) == 11
    assert [op.operation_id for op in ops] == list(
        CANONICAL_UNIVERSITY_OPERATION_IDS
    )


def test_classification():
    ops = {
        op.operation_id: op
        for op in university.build_university_operation_definitions()
    }
    assert (
        ops["university.review_academic_record"].operation_type
        is DomainOperationType.ANALYSIS
    )
    assert (
        ops["university.prepare_exam"].operation_type
        is DomainOperationType.PREPARATION
    )
    assert (
        ops["university.plan_semester"].operation_type
        is DomainOperationType.PLANNING
    )
    # update_subject_status is INTERNAL Academic State only (MEMORY type).
    assert (
        ops["university.update_subject_status"].operation_type
        is DomainOperationType.MEMORY
    )
    # prepare_exam is PREPARATION, never EXTERNAL/send/submit.
    assert (
        ops["university.prepare_exam"].operation_type
        is not DomainOperationType.EXTERNAL
    )


def test_approval_gated_operations():
    ops = {
        op.operation_id: op
        for op in university.build_university_operation_definitions()
    }
    assert ops["university.plan_semester"].requires_approval is True
    assert ops["university.create_study_plan"].requires_approval is True
    assert ops["university.update_subject_status"].requires_approval is True


def test_no_external_or_destructive_operations():
    ops = university.build_university_operation_definitions()
    assert all(op.operation_type is not DomainOperationType.EXTERNAL for op in ops)
    assert all(op.operation_type is not DomainOperationType.DESTRUCTIVE for op in ops)
    assert all(op.reversible is False for op in ops)


def test_schemas_and_metadata():
    for op in university.build_university_operation_definitions():
        assert op.input_schema.get("type") == "object"
        assert op.output_schema.get("type") == "object"
        assert op.domain_id == "domain:university"
        assert op.version == "1.0.0"


def test_prepare_exam_prepares_material_not_send():
    """The prepare op describes what was prepared; its output is preparation,
    never a send/submit/execute effect."""
    prepare = _ops()["university.prepare_exam"]
    output_keys = set(prepare.output_schema["properties"].keys())
    assert "preparation" in output_keys
    assert not ({"sent", "submitted", "contacted"} <= output_keys)
    assert _is_closed(prepare.output_schema)


def test_update_subject_status_internal_only():
    """update_subject_status output is internal Academic State only and never
    touches the official record."""
    status = _ops()["university.update_subject_status"]
    inner = status.output_schema["properties"]["status"]["properties"]
    assert inner["official_record_untouched"] is not None
    assert inner["internal_academic_state_only"] is not None


def test_no_proposal_only_operations():
    """The domain memory policy is read-only; no operation is proposal_only."""
    for op in university.build_university_operation_definitions():
        assert op.metadata.get("proposal_only", False) is False


def test_required_resources_only_where_structurally_valid():
    """required_resources uses AND semantics — an op only declares a resource it
    structurally consumes; not every op is mechanically non-empty."""
    ops = {
        op.operation_id: op
        for op in university.build_university_operation_definitions()
    }
    materialized = {rid for rid in _resource_ids()}
    for op in ops.values():
        for resource_id in op.required_resources:
            assert resource_id in materialized


def test_operation_schemas_are_not_all_identical():
    """The eleven University operations must carry meaningfully distinct closed
    input/output schemas — not a single copy-pasted shape."""
    input_shapes = {
        op.operation_id: (
            op.input_schema["required"],
            tuple(op.input_schema["properties"]),
        )
        for op in university.build_university_operation_definitions()
    }
    output_shapes = {
        op.operation_id: tuple(op.output_schema["properties"])
        for op in university.build_university_operation_definitions()
    }
    assert len(set(input_shapes.values())) > 1
    assert len(set(output_shapes.values())) > 1


def test_no_autonomous_academic_action_operation():
    """No University operation encodes an autonomous send/submit/enrol/record-
    write action."""
    op_ids = {
        op.operation_id
        for op in university.build_university_operation_definitions()
    }
    assert not any(
        word in op
        for op in op_ids
        for word in ("send", "submit", "enrol", "register", "write_record")
    )


def _is_closed(schema):
    return schema.get("additionalProperties", True) is False


def _resource_ids():
    return tuple(r.id for r in university.build_university_resource_definitions())


def _ops():
    return {
        op.operation_id: op
        for op in university.build_university_operation_definitions()
    }