class WorkflowError(Exception):
    code = "WORKFLOW_ERROR"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = {} if details is None else dict(details)


class WorkflowContractError(WorkflowError, ValueError):
    code = "WORKFLOW_CONTRACT_ERROR"


class WorkflowSerializationError(WorkflowContractError):
    code = "WORKFLOW_SERIALIZATION_ERROR"


class WorkflowGraphError(WorkflowContractError):
    code = "WORKFLOW_GRAPH_ERROR"


class WorkflowRegistryError(WorkflowError):
    code = "WORKFLOW_REGISTRY_ERROR"


class WorkflowStateError(WorkflowError):
    code = "WORKFLOW_STATE_ERROR"


class WorkflowExecutionError(WorkflowError):
    code = "WORKFLOW_EXECUTION_ERROR"


class WorkflowRetryableError(WorkflowExecutionError):
    code = "WORKFLOW_RETRYABLE_ERROR"
