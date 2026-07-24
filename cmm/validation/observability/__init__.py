"""Phase 7.11 — Observability and Persistence public API.

Exports all stable contracts, implementations, and the
observability service.  Internal helpers are not exported.
"""

from .exceptions import (
    UnsupportedValidationSchemaError,
    ValidationArtifactStorageError,
    ValidationPersistenceError,
    ValidationRecordConflictError,
    ValidationRecordNotFoundError,
    ValidationStorageCorruptionError,
)
from .history import ValidationHistoryPage, ValidationHistoryQuery
from .metrics import ValidationMetrics, ValidationMetricsCalculator
from .models import ValidationExecutionRecord, ValidationLogEntry
from .protocols import ValidationRepositoryProtocol
from .repository import LocalValidationRepository
from .sanitization import sanitize_validation_data
from .service import ValidationObservabilityService

__all__ = [  # noqa: RUF022 - grouped by category for readability
    # Exceptions
    "UnsupportedValidationSchemaError",
    "ValidationArtifactStorageError",
    "ValidationPersistenceError",
    "ValidationRecordConflictError",
    "ValidationRecordNotFoundError",
    "ValidationStorageCorruptionError",
    # History
    "ValidationHistoryPage",
    "ValidationHistoryQuery",
    # Metrics
    "ValidationMetrics",
    "ValidationMetricsCalculator",
    # Models
    "ValidationExecutionRecord",
    "ValidationLogEntry",
    # Protocol
    "ValidationRepositoryProtocol",
    # Repository
    "LocalValidationRepository",
    # Sanitization
    "sanitize_validation_data",
    # Service
    "ValidationObservabilityService",
]
