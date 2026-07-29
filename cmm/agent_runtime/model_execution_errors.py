class ModelExecutionError(Exception):
    """Base error for model execution records."""


class InvalidModelExecutionRecordError(ModelExecutionError, ValueError):
    pass


class ModelExecutionDuplicateError(ModelExecutionError, ValueError):
    pass


class ModelExecutionNotFoundError(ModelExecutionError, LookupError):
    pass


class ModelExecutionIdempotencyConflictError(ModelExecutionError, ValueError):
    pass
