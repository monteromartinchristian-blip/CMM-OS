from cmm.workflows.errors import WorkflowError


class DomainWorkflowError(WorkflowError):
    code = "DOMAIN_WORKFLOW_ERROR"


class DomainWorkflowValidationError(DomainWorkflowError):
    code = "DOMAIN_WORKFLOW_VALIDATION_ERROR"


class DomainWorkflowResolutionError(DomainWorkflowError):
    code = "DOMAIN_WORKFLOW_RESOLUTION_ERROR"


class DomainWorkflowRegistryError(DomainWorkflowError):
    code = "DOMAIN_WORKFLOW_REGISTRY_ERROR"


class DomainWorkflowUnavailableError(DomainWorkflowError):
    code = "DOMAIN_WORKFLOW_UNAVAILABLE_ERROR"


class DomainWorkflowStateError(DomainWorkflowError):
    code = "DOMAIN_WORKFLOW_STATE_ERROR"


class DomainWorkflowExecutionError(DomainWorkflowError):
    code = "DOMAIN_WORKFLOW_EXECUTION_ERROR"


class DomainWorkflowNodeError(DomainWorkflowExecutionError):
    code = "DOMAIN_WORKFLOW_NODE_ERROR"


class DomainWorkflowApprovalError(DomainWorkflowExecutionError):
    code = "DOMAIN_WORKFLOW_APPROVAL_ERROR"


class DomainWorkflowCancellationError(DomainWorkflowExecutionError):
    code = "DOMAIN_WORKFLOW_CANCELLATION_ERROR"


class DomainWorkflowRecoveryError(DomainWorkflowExecutionError):
    code = "DOMAIN_WORKFLOW_RECOVERY_ERROR"


class DomainWorkflowSubworkflowError(DomainWorkflowExecutionError):
    code = "DOMAIN_WORKFLOW_SUBWORKFLOW_ERROR"


class DomainWorkflowSerializationError(DomainWorkflowValidationError):
    code = "DOMAIN_WORKFLOW_SERIALIZATION_ERROR"
