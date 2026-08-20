"""Shared workflow regression tests for executable ``VALIDATE`` gates.

Phase 10.24 Audit V1-I8 remediation: the shared runtime must make ``VALIDATE``
nodes with a declared ``wait_condition`` executable and fail-closed (absent,
malformed, unknown or false condition blocks), while a ``VALIDATE`` node without
a declared condition — and all non-``VALIDATE`` nodes — remain adapter-driven so
existing domain-pack workflows are preserved unchanged.

These are pure shared-runtime tests (no Reflection dependency).
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import WorkflowNodeStatus, WorkflowRunStatus


def _make_definition(*, validate_condition):
    return WorkflowDefinition(
        "validate.gate", "1.0.0", "ValidateGate",
        nodes=(
            WorkflowNode("producer", "execute_operation", "Producer",
                         operation_id="op.x", operation_version="1.0.0"),
            WorkflowNode("validate", "validate", "Validate",
                         dependencies=("producer",), wait_condition=validate_condition),
            WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
        ),
        metadata={},
    )


def _run(validate_condition, *, producer_output, adapter_kind="gate"):
    def adapter(node, run):
        if node.node_id == "producer":
            return NodeExecution.complete(producer_output)
        if adapter_kind == "gate":
            return NodeExecution.complete({"ok": True})
        return NodeExecution.complete({"from_adapter": node.node_id})

    engine = WorkflowEngine(
        _make_definition(validate_condition=validate_condition),
        id_factory=lambda: "run-1",
        clock=lambda: datetime.now(timezone.utc),
        node_adapter=adapter,
    )
    return engine.start({})


def test_validate_gate_true_completes():
    result = _run({"flag": True}, producer_output={"flag": True})
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_validate_gate_false_blocks_fail_closed():
    result = _run({"flag": False}, producer_output={"flag": True})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.error_code == "validate.condition_false"


def test_validate_gate_absent_condition_blocked():
    result = _run({}, producer_output={"flag": True})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.error_code == "validate.condition_missing"


def test_validate_gate_unknown_condition_blocked():
    result = _run({"missing": True}, producer_output={"other": 1})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.error_code == "validate.condition_unknown"


def test_validate_gate_matches_accumulated_output():
    # The gate validates the accumulated state, not the raw node output alone.
    result = _run({"flag": True, "extra": 2}, producer_output={"flag": True, "extra": 2})
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_validate_without_wait_condition_stays_adapter_driven():
    # A VALIDATE node with no declared condition is NOT a gate: it remains
    # adapter-driven, preserving existing domain-pack behavior.
    definition = WorkflowDefinition(
        "validate.no_condition", "1.0.0", "NoCondition",
        nodes=(
            WorkflowNode("validate", "validate", "Validate", wait_condition=None),
            WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
        ),
        metadata={},
    )

    def adapter(node, run):
        return NodeExecution.complete({"from_adapter": node.node_id})

    engine = WorkflowEngine(
        definition,
        id_factory=lambda: "run-2",
        clock=lambda: datetime.now(timezone.utc),
        node_adapter=adapter,
    )
    result = engine.start({})
    assert result.run.status is WorkflowRunStatus.COMPLETED
    validate_result = result.node_results["validate"]
    assert validate_result.status is WorkflowNodeStatus.COMPLETED
    assert validate_result.output == {"from_adapter": "validate"}


def test_non_validate_nodes_still_use_adapter():
    definition = WorkflowDefinition(
        "plain.exec", "1.0.0", "PlainExec",
        nodes=(
            WorkflowNode("a", "execute_operation", "A", operation_id="op.a",
                         operation_version="1.0.0"),
            WorkflowNode("b", "complete", "B", dependencies=("a",)),
        ),
        metadata={},
    )

    def adapter(node, run):
        return NodeExecution.complete({"echo": node.node_id})

    engine = WorkflowEngine(
        definition,
        id_factory=lambda: "run-3",
        clock=lambda: datetime.now(timezone.utc),
        node_adapter=adapter,
    )
    result = engine.start({})
    assert result.run.status is WorkflowRunStatus.COMPLETED
    assert result.node_results["a"].output == {"echo": "a"}


# ── Phase 10.24 Audit V2-I1: literal-boolean + conflict-aware ───────────────


def _make_two_producer_definition(*, validate_condition):
    return WorkflowDefinition(
        "validate.gate.v2", "1.0.0", "ValidateGateV2",
        nodes=(
            WorkflowNode("producer_a", "execute_operation", "ProducerA",
                         operation_id="op.a", operation_version="1.0.0"),
            WorkflowNode("producer_z", "execute_operation", "ProducerZ",
                         operation_id="op.z", operation_version="1.0.0"),
            WorkflowNode("validate", "validate", "Validate",
                         dependencies=("producer_a", "producer_z"),
                         wait_condition=validate_condition),
            WorkflowNode("finish", "complete", "Finish", dependencies=("validate",)),
        ),
        metadata={},
    )


def _run_two_producers(validate_condition, *, a_output, z_output):
    def adapter(node, run):
        if node.node_id == "producer_a":
            return NodeExecution.complete(a_output)
        if node.node_id == "producer_z":
            return NodeExecution.complete(z_output)
        return NodeExecution.complete({"ok": True})

    engine = WorkflowEngine(
        _make_two_producer_definition(validate_condition=validate_condition),
        id_factory=lambda: "run-v2",
        clock=lambda: datetime.now(timezone.utc),
        node_adapter=adapter,
    )
    return engine.start({})


def test_validate_gate_rejects_numeric_one_for_expected_true():
    """Numeric ``1`` must not satisfy a boolean ``True`` expectation."""
    result = _run({"flag": True}, producer_output={"flag": 1})
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_false"


def test_validate_gate_rejects_string_true_for_expected_true():
    """String ``"true"`` must not satisfy a boolean ``True`` expectation."""
    result = _run({"flag": True}, producer_output={"flag": "true"})
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_false"


def test_validate_gate_rejects_numeric_zero_for_expected_false():
    """Numeric ``0`` must not satisfy a boolean ``False`` expectation."""
    result = _run({"flag": False}, producer_output={"flag": 0})
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_false"


def test_validate_gate_accepts_literal_true_for_expected_true():
    """Literal ``True`` is the only thing that satisfies a boolean ``True``."""
    result = _run({"flag": True}, producer_output={"flag": True})
    assert result.run.status is WorkflowRunStatus.COMPLETED


def test_validate_gate_fails_closed_on_conflicting_dependency_values():
    """Two dependencies disagreeing on the same field must fail closed."""
    result = _run_two_producers(
        {"safe": True},
        a_output={"safe": False},
        z_output={"safe": True},
    )
    assert result.run.status is not WorkflowRunStatus.COMPLETED
    assert result.run.error_code == "validate.condition_conflict"


def test_validate_gate_passes_when_dependencies_agree():
    """Two dependencies agreeing on the same field must pass the gate."""
    result = _run_two_producers(
        {"safe": True},
        a_output={"safe": True},
        z_output={"safe": True},
    )
    assert result.run.status is WorkflowRunStatus.COMPLETED
