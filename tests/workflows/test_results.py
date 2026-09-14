
from datetime import datetime, timezone

import pytest

from cmm.workflows.contracts import WorkflowNodeResult, WorkflowResult, WorkflowRun
from cmm.workflows.enums import WorkflowNodeStatus, WorkflowNodeType, WorkflowRunStatus
from cmm.workflows.errors import WorkflowContractError


def test_node_and_workflow_results_round_trip_and_invariants():
    node = WorkflowNodeResult("n", WorkflowNodeType.COMPLETE, WorkflowNodeStatus.COMPLETED, output={"ok": True})
    now = datetime.now(timezone.utc)
    run = WorkflowRun("r", "w", "1.0.0", status=WorkflowRunStatus.COMPLETED, completed_nodes=("n",), started_at=now, completed_at=now)
    result = WorkflowResult(run=run, node_results={"n": node}, output={"ok": True})
    assert WorkflowResult.from_dict(result.to_dict()).to_dict() == result.to_dict()
    with pytest.raises(WorkflowContractError):
        WorkflowNodeResult("n", WorkflowNodeType.COMPLETE, WorkflowNodeStatus.FAILED)
