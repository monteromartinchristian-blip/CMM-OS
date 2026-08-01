from enum import Enum


class WorkflowAvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"
    WAITING_FOR_APPROVAL = "waiting_for_approval"


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_RESOURCE = "waiting_for_resource"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"
    ROLLED_BACK = "rolled_back"


class WorkflowNodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class WorkflowNodeType(str, Enum):
    COMPLETE = "complete"
    EXECUTE_OPERATION = "execute_operation"
    REQUEST_APPROVAL = "request_approval"
    WAIT_FOR_RESOURCE = "wait_for_resource"
    ASK_QUESTION = "ask_question"
    INVOKE_SUBWORKFLOW = "invoke_subworkflow"
    PAUSE = "pause"
    VALIDATE = "validate"
    PROPOSE_MEMORY = "propose_memory"
    UPDATE_SESSION = "update_session"
    LOAD_RESOURCE = "load_resource"
    SEARCH_KNOWLEDGE = "search_knowledge"
    RESOLVE_ENTITY = "resolve_entity"
    APPLY_PROFILE = "apply_profile"
    REASON = "reason"
    DETECT_GAPS = "detect_gaps"
    EVALUATE_OUTCOME = "evaluate_outcome"
    ESCALATE = "escalate"


_RUN_TRANSITIONS = {
    WorkflowRunStatus.PENDING: frozenset({WorkflowRunStatus.RUNNING, WorkflowRunStatus.CANCELLED}),
    WorkflowRunStatus.RUNNING: frozenset({WorkflowRunStatus.PAUSED, WorkflowRunStatus.WAITING_FOR_RESOURCE, WorkflowRunStatus.WAITING_FOR_INPUT, WorkflowRunStatus.WAITING_FOR_APPROVAL, WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED}),
    WorkflowRunStatus.PAUSED: frozenset({WorkflowRunStatus.RUNNING, WorkflowRunStatus.CANCELLED}),
    WorkflowRunStatus.WAITING_FOR_RESOURCE: frozenset({WorkflowRunStatus.RUNNING, WorkflowRunStatus.CANCELLED}),
    WorkflowRunStatus.WAITING_FOR_INPUT: frozenset({WorkflowRunStatus.RUNNING, WorkflowRunStatus.CANCELLED}),
    WorkflowRunStatus.WAITING_FOR_APPROVAL: frozenset({WorkflowRunStatus.RUNNING, WorkflowRunStatus.CANCELLED}),
    WorkflowRunStatus.FAILED: frozenset({WorkflowRunStatus.RECOVERING}),
    WorkflowRunStatus.RECOVERING: frozenset({WorkflowRunStatus.RUNNING, WorkflowRunStatus.FAILED}),
    WorkflowRunStatus.COMPLETED: frozenset(), WorkflowRunStatus.CANCELLED: frozenset(), WorkflowRunStatus.ROLLED_BACK: frozenset(),
}


def validate_workflow_run_transition(source: WorkflowRunStatus | str, target: WorkflowRunStatus | str) -> WorkflowRunStatus:
    source_value = WorkflowRunStatus(source)
    target_value = WorkflowRunStatus(target)
    if target_value not in _RUN_TRANSITIONS[source_value]:
        raise ValueError(f"invalid workflow run transition: {source_value.value} -> {target_value.value}")
    return target_value
