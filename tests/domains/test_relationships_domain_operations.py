"""Tests for Phase 10.21 Relationships Domain operations."""

from __future__ import annotations

from cmm.domains import relationships
from cmm.domains.enums import DomainOperationType
from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_OPERATION_IDS


def test_ten_operations_and_canonical_order():
    ops = relationships.build_relationships_operation_definitions()
    assert len(ops) == 10
    assert [op.operation_id for op in ops] == list(
        CANONICAL_RELATIONSHIPS_OPERATION_IDS
    )


def test_classification():
    ops = {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }
    assert (
        ops["relationships.build_timeline"].operation_type
        is DomainOperationType.ANALYSIS
    )
    assert (
        ops["relationships.prepare_conversation"].operation_type
        is DomainOperationType.PREPARATION
    )
    assert (
        ops["relationships.review_boundaries"].operation_type
        is DomainOperationType.SENSITIVE
    )
    # prepare_conversation is PREPARATION, never EXTERNAL/send.
    assert (
        ops["relationships.prepare_conversation"].operation_type
        is not DomainOperationType.EXTERNAL
    )


def test_approval_gated_operations():
    ops = {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }
    assert ops["relationships.prepare_conversation"].requires_approval is True
    assert ops["relationships.review_boundaries"].requires_approval is True


def test_no_external_or_destructive_operations():
    ops = relationships.build_relationships_operation_definitions()
    assert all(op.operation_type is not DomainOperationType.EXTERNAL for op in ops)
    assert all(op.operation_type is not DomainOperationType.DESTRUCTIVE for op in ops)
    assert all(op.reversible is False for op in ops)


def test_schemas_and_metadata():
    for op in relationships.build_relationships_operation_definitions():
        assert op.input_schema.get("type") == "object"
        assert op.output_schema.get("type") == "object"
        assert op.domain_id == "domain:relationships"
        assert op.version == "1.0.0"


def test_prepare_conversation_prepares_material_not_send():
    """The prepare op describes what was prepared for a conversation; its output
    is preparation, never a send/contact/initiate effect."""
    prepare = _ops()["relationships.prepare_conversation"]
    output_keys = set(prepare.output_schema["properties"].keys())
    assert "preparation" in output_keys
    assert not ({"sent", "contacted", "initiated"} <= output_keys)
    assert _is_closed(prepare.output_schema)
    assert prepare.requires_approval is True


def test_no_proposal_only_operations():
    """The domain memory policy is read-only; no operation is proposal_only."""
    for op in relationships.build_relationships_operation_definitions():
        assert op.metadata.get("proposal_only", False) is False


def test_required_resources_only_where_structurally_valid():
    """required_resources uses AND semantics — an op only declares a resource it
    structurally consumes; not every op is mechanically non-empty."""
    ops = {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }
    materialized = {rid for rid in _resource_ids()}
    for op in ops.values():
        for resource_id in op.required_resources:
            assert resource_id in materialized


def test_operation_schemas_are_not_all_identical():
    """The ten Relationships operations must carry meaningfully distinct closed
    input/output schemas — not a single copy-pasted shape."""
    input_shapes = {
        op.operation_id: (
            op.input_schema["required"],
            tuple(op.input_schema["properties"]),
        )
        for op in relationships.build_relationships_operation_definitions()
    }
    output_shapes = {
        op.operation_id: tuple(op.output_schema["properties"])
        for op in relationships.build_relationships_operation_definitions()
    }
    assert len(set(input_shapes.values())) > 1
    assert len(set(output_shapes.values())) > 1


def test_no_autonomous_relational_action_operation():
    """No Relationships operation encodes an autonomous send/contact/end/boundary
    action."""
    op_ids = {
        op.operation_id
        for op in relationships.build_relationships_operation_definitions()
    }
    assert not any(
        word in op
        for op in op_ids
        for word in ("send", "contact", "initiate", "adopt", "end_relationship")
    )


def _is_closed(schema):
    return schema.get("additionalProperties", True) is False


def _resource_ids():
    return tuple(r.id for r in relationships.build_relationships_resource_definitions())


def _ops():
    return {
        op.operation_id: op
        for op in relationships.build_relationships_operation_definitions()
    }
