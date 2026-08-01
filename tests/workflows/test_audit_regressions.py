from datetime import datetime, timezone

import pytest

from cmm.workflows.contracts import (
    ApprovalDecision,
    ApprovalRequest,
    WaitRequest,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowNode,
    WorkflowNodeResult,
    WorkflowResult,
    WorkflowRun,
)
from cmm.workflows.engine import NodeExecution, WorkflowEngine
from cmm.workflows.enums import WorkflowNodeStatus, WorkflowNodeType, WorkflowRunStatus
from cmm.workflows.errors import (
    WorkflowExecutionError,
    WorkflowGraphError,
    WorkflowStateError,
)
from cmm.workflows.registry import InMemoryWorkflowRegistry


def test_plain_mapping_and_not_applicable_cannot_complete_required_node():
    definition = WorkflowDefinition("capacity", "1.0.0", "Capacity", nodes=(WorkflowNode("n", "complete", "N"),))
    with pytest.raises(WorkflowExecutionError):
        WorkflowEngine(definition, id_factory=lambda: "r", node_adapter=lambda node, run: {"status": "not_applicable"}).start({})

    optional = WorkflowDefinition("optional", "1.0.0", "Optional", nodes=(WorkflowNode("n", "complete", "N", required=False),))
    result = WorkflowEngine(optional, id_factory=lambda: "r", node_adapter=lambda node, run: NodeExecution.not_applicable("capability.not_configured")).start({})
    assert result.run.status is WorkflowRunStatus.COMPLETED
    assert result.run.completed_nodes == ()
    assert result.run.skipped_nodes == ("n",)


def test_optional_skips_resolve_dependencies_but_do_not_count_as_completed():
    calls: list[str] = []
    definition = WorkflowDefinition(
        "optional-chain", "1.0.0", "Optional chain",
        nodes=(
            WorkflowNode("first", "load_resource", "First", required=False),
            WorkflowNode("second", "load_resource", "Second", dependencies=("first",), required=False),
            WorkflowNode("finish", "complete", "Finish", dependencies=("second",)),
        ),
        completion_criteria={"minimum_successful_nodes": 1},
    )

    def adapter(node, run):
        calls.append(node.node_id)
        if node.node_id != "finish":
            return NodeExecution.not_applicable("capability.not_configured")
        return NodeExecution.complete({"done": True})

    result = WorkflowEngine(definition, id_factory=lambda: "r", node_adapter=adapter).start({})
    assert result.run.status is WorkflowRunStatus.COMPLETED
    assert result.run.completed_nodes == ("finish",)
    assert result.run.skipped_nodes == ("first", "second")
    assert calls == ["first", "second", "finish"]


def test_required_skip_does_not_resolve_dependencies():
    calls: list[str] = []
    definition = WorkflowDefinition(
        "required-skip", "1.0.0", "Required skip",
        nodes=(
            WorkflowNode("required", "load_resource", "Required"),
            WorkflowNode("downstream", "complete", "Downstream", dependencies=("required",)),
        ),
    )

    def adapter(node, run):
        calls.append(node.node_id)
        return NodeExecution.not_applicable("capability.not_configured")

    result = WorkflowEngine(definition, id_factory=lambda: "r", node_adapter=adapter).start({})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.failed_nodes == ("required",)
    assert result.node_results["required"].status is WorkflowNodeStatus.FAILED
    assert calls == ["required"]


def test_optional_failure_is_normalized_to_skipped_and_unblocks_dependents():
    definition = WorkflowDefinition(
        "optional-failure", "1.0.0", "Optional failure",
        nodes=(
            WorkflowNode("optional", "load_resource", "Optional", required=False),
            WorkflowNode("finish", "complete", "Finish", dependencies=("optional",)),
        ),
    )

    def adapter(node, run):
        if node.node_id == "optional":
            return NodeExecution.failure("provider.unavailable")
        return NodeExecution.complete()

    result = WorkflowEngine(definition, id_factory=lambda: "r", node_adapter=adapter).start({})
    optional = result.node_results["optional"]
    assert result.run.status is WorkflowRunStatus.COMPLETED
    assert result.run.failed_nodes == ()
    assert result.run.skipped_nodes == ("optional",)
    assert optional.status is WorkflowNodeStatus.SKIPPED
    assert optional.reason_code == "provider.unavailable"
    assert result.run.completed_nodes == ("finish",)


def test_required_failure_remains_blocking():
    definition = WorkflowDefinition("required-failure", "1.0.0", "Required failure", nodes=(WorkflowNode("required", "load_resource", "Required"),))
    result = WorkflowEngine(definition, id_factory=lambda: "r", node_adapter=lambda node, run: NodeExecution.failure("provider.unavailable")).start({})
    assert result.run.status is WorkflowRunStatus.FAILED
    assert result.run.failed_nodes == ("required",)
    assert result.node_results["required"].status is WorkflowNodeStatus.FAILED


def test_approval_node_waits_when_reached_and_resume_requires_matching_decision():
    definition = WorkflowDefinition("approval", "1.0.0", "Approval", nodes=(WorkflowNode("gate", "request_approval", "Gate", approval_gate="gate"),))
    approval = ApprovalRequest("a", "approval", "1.0.0", "r", "gate", {"x": 1})

    def adapter(node, run):
        return NodeExecution.wait(WaitRequest("approval", "approval required", node.node_id, {"approval": approval.to_dict()}, approval_request=approval))

    engine = WorkflowEngine(definition, id_factory=lambda: "r", node_adapter=adapter)
    waiting = engine.start({"x": 1})
    assert waiting.run.status is WorkflowRunStatus.WAITING_FOR_APPROVAL
    assert waiting.wait_request is not None
    with pytest.raises(WorkflowStateError):
        engine.resume(waiting.run, condition_resolved=True, approval=ApprovalRequest("a", "approval", "1.0.0", "r", "gate", {"x": 2}).decide(ApprovalDecision("u", True)))


def test_workflow_result_round_trip_preserves_events_and_wait_request():
    now = datetime.now(timezone.utc)
    wait = WaitRequest("input", "answer", "n", {"field": "answer"})
    run = WorkflowRun("r", "w", "1.0.0", status=WorkflowRunStatus.WAITING_FOR_INPUT, waiting_nodes=("n",), checkpoint_id="cp", wait_request=wait)
    result = WorkflowResult(run, {"n": WorkflowNodeResult("n", WorkflowNodeType.ASK_QUESTION, WorkflowNodeStatus.WAITING, wait_request=wait)}, wait_request=wait, events=(WorkflowEvent("e", "workflow.waiting", "w", "r", now, {"reason": "input"}),), defined_node_ids=("n",))
    restored = WorkflowResult.from_dict(result.to_dict())
    assert restored.to_dict() == result.to_dict()
    assert restored.events[0].event_id == "e"


def test_versioned_registry_rejects_missing_reference_and_detects_versioned_cycle():
    registry = InMemoryWorkflowRegistry()
    registry.register(WorkflowDefinition("a", "1.0.0", "A", nodes=(WorkflowNode("call", "invoke_subworkflow", "Call", subworkflow_id="b", subworkflow_version="1.0.0"),)))
    with pytest.raises(WorkflowGraphError):
        registry.validate_registry()
    registry.register(WorkflowDefinition("b", "1.0.0", "B", nodes=(WorkflowNode("call", "invoke_subworkflow", "Call", subworkflow_id="a", subworkflow_version="1.0.0"),)))
    with pytest.raises(WorkflowGraphError):
        registry.validate_registry()
