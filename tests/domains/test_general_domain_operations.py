"""Tests for General Domain operations."""

from __future__ import annotations

import json
from collections.abc import Mapping

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.general import (
    GENERAL_OPERATION_IDS,
    build_general_operation_definitions,
)
from cmm.domains.operation_contracts import DomainOperationDefinition


def _plain(value):
    """Recursively convert frozen mappings/lists into plain JSON-serializable data."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical(schema) -> str:
    """Return a stable canonical string for a JSON schema mapping."""
    return json.dumps(_plain(schema), sort_keys=True, separators=(",", ":"))


def _by_id() -> dict[str, DomainOperationDefinition]:
    return {op.operation_id: op for op in build_general_operation_definitions()}


def test_all_operations_built():
    operations = build_general_operation_definitions()
    assert len(operations) == 8


def test_operation_ids_match():
    operations = build_general_operation_definitions()
    ids = tuple(o.operation_id for o in operations)
    assert ids == GENERAL_OPERATION_IDS


def test_operation_domain_ids():
    operations = build_general_operation_definitions()
    for op in operations:
        assert op.domain_id == "domain:general"


def test_operation_versions():
    operations = build_general_operation_definitions()
    for op in operations:
        assert op.version == "1.0.0"


def test_operation_types():
    operations = build_general_operation_definitions()
    types = {op.operation_id: op.operation_type for op in operations}
    assert types["general.create_summary"] is DomainOperationType.ANALYSIS
    assert types["general.build_timeline"] is DomainOperationType.ANALYSIS
    assert types["general.compare_items"] is DomainOperationType.ANALYSIS
    assert types["general.prepare_questions"] is DomainOperationType.PREPARATION
    assert types["general.create_task"] is DomainOperationType.PLANNING
    assert types["general.update_goal"] is DomainOperationType.PLANNING
    assert types["general.generate_report"] is DomainOperationType.PREPARATION
    assert types["general.search_knowledge"] is DomainOperationType.READ


def test_operation_risk_levels():
    operations = build_general_operation_definitions()
    for op in operations:
        assert op.risk_level is PolicyRiskLevel.LOW


def test_approval_required():
    operations = build_general_operation_definitions()
    by_id = {op.operation_id: op for op in operations}
    assert by_id["general.create_task"].requires_approval is True
    assert by_id["general.update_goal"].requires_approval is True
    assert by_id["general.create_summary"].requires_approval is False
    assert by_id["general.search_knowledge"].requires_approval is False


def test_no_operations_reversible():
    operations = build_general_operation_definitions()
    for op in operations:
        assert op.reversible is False


def test_each_operation_has_own_input_schema():
    """A: each of the eight operations has its own (distinct) input_schema."""
    operations = build_general_operation_definitions()
    assert len({id(op.input_schema) for op in operations}) == len(operations)


def test_each_operation_has_own_output_schema():
    """B: each of the eight operations has its own (distinct) output_schema."""
    operations = build_general_operation_definitions()
    assert len({id(op.output_schema) for op in operations}) == len(operations)


def test_all_schemas_object_with_properties_and_no_additional():
    """C: all schemas are object, have properties, and forbid additional."""
    operations = build_general_operation_definitions()
    for op in operations:
        for schema in (op.input_schema, op.output_schema):
            assert schema.get("type") == "object"
            assert schema.get("properties")
            assert schema["additionalProperties"] is False


def test_schemas_are_not_uniform():
    """D: the schemas are not all identical."""
    operations = build_general_operation_definitions()
    input_canonicals = {_canonical(op.input_schema) for op in operations}
    output_canonicals = {_canonical(op.output_schema) for op in operations}
    assert len(input_canonicals) > 1
    assert len(output_canonicals) > 1


def test_required_resources_empty_and_dynamic():
    """E: required_resources stays empty; resources are selected dynamically."""
    operations = build_general_operation_definitions()
    for op in operations:
        assert op.required_resources == ()


def test_create_summary_schema_semantics():
    """general.create_summary requires source_ids input and summary output."""
    op = _by_id()["general.create_summary"]
    assert set(op.input_schema["required"]) == {"source_ids"}
    assert set(op.output_schema["required"]) == {"summary"}


def test_build_timeline_schema_semantics():
    """general.build_timeline requires source_ids input and events output."""
    op = _by_id()["general.build_timeline"]
    assert set(op.input_schema["required"]) == {"source_ids"}
    assert set(op.output_schema["required"]) == {"events"}


def test_compare_items_schema_semantics():
    """general.compare_items requires item_ids input and comparison output."""
    op = _by_id()["general.compare_items"]
    assert set(op.input_schema["required"]) == {"item_ids"}
    assert set(op.output_schema["required"]) == {"comparison"}


def test_prepare_questions_schema_semantics():
    """general.prepare_questions requires topic input and questions output."""
    op = _by_id()["general.prepare_questions"]
    assert set(op.input_schema["required"]) == {"topic"}
    assert set(op.output_schema["required"]) == {"questions"}


def test_create_task_schema_semantics():
    """general.create_task requires title input and proposal+binding output."""
    op = _by_id()["general.create_task"]
    assert set(op.input_schema["required"]) == {"title"}
    assert set(op.output_schema["required"]) == {"proposal", "binding"}


def test_update_goal_schema_semantics():
    """general.update_goal requires goal_id input and proposal+binding output."""
    op = _by_id()["general.update_goal"]
    assert set(op.input_schema["required"]) == {"goal_id"}
    assert set(op.output_schema["required"]) == {"proposal", "binding"}


def test_generate_report_schema_semantics():
    """general.generate_report requires source_ids input and report output."""
    op = _by_id()["general.generate_report"]
    assert set(op.input_schema["required"]) == {"source_ids"}
    assert set(op.output_schema["required"]) == {"report"}


def test_search_knowledge_schema_semantics():
    """general.search_knowledge requires query input and results output."""
    op = _by_id()["general.search_knowledge"]
    assert set(op.input_schema["required"]) == {"query"}
    assert set(op.output_schema["required"]) == {"results"}


def test_operation_serialization_round_trip():
    operations = build_general_operation_definitions()
    for op in operations:
        restored = DomainOperationDefinition.from_dict(op.to_dict())
        assert restored == op


def test_operation_deterministic():
    a = build_general_operation_definitions()
    b = build_general_operation_definitions()
    assert [op.operation_id for op in a] == [op.operation_id for op in b]


def test_operation_unique_ids():
    operations = build_general_operation_definitions()
    ids = [op.operation_id for op in operations]
    assert len(set(ids)) == len(ids)


def test_operation_can_be_registered():
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    for op in build_general_operation_definitions():
        registry.register(op, _FakeImplementation(op))
    assert len(registry.list_definitions()) == 8


def test_search_knowledge_is_read_only():
    operations = build_general_operation_definitions()
    search = next(op for op in operations if op.operation_id == "general.search_knowledge")
    assert search.operation_type is DomainOperationType.READ
    assert "memory.read" in search.required_permissions


def test_create_task_is_proposal_only():
    operations = build_general_operation_definitions()
    create_task = next(op for op in operations if op.operation_id == "general.create_task")
    assert create_task.metadata.get("proposal_only") is True


class _FakeImplementation:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request):
        return {"success": True, "output": {}, "effects": ()}
