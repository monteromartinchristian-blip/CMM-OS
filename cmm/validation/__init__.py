"""Validation contracts for CMM OS (Phase 7.1).

Public API surfaces as cmm.validation.*
"""

from .artifacts import ValidationArtifact
from .catalog import (
    ast_step,
    bandit_step,
    build_default_validation_registry,
    default_security_steps,
    default_structural_steps,
    formatter_check_step,
    formatter_fix_step,
    lint_check_step,
    lint_fix_step,
    pip_audit_step,
    security_step,
    select_python_files,
    structural_step,
    syntax_step,
)
from .command_parsers import CommandResultParser
from .commit_gate import (
    CommitAuthorization,
    CommitGateError,
    CommitGateEvaluator,
    CommitGateReason,
    CommitGateReasonCode,
    CommitGateRepositoryError,
    CommitGateResult,
    GitRepositoryProtocol,
    ProvisionalCommitError,
    ProvisionalCommitService,
    RepositoryState,
    SubprocessGitRepository,
    UnsafeRepositoryStateError,
)
from .context import ValidationContext
from .custom import (
    CustomValidator,
    CustomValidatorRegistry,
    build_custom_validation_step,
    custom_validator_step,
)
from .custom_validators import (
    ProjectManifestValidator,
    PublicApiValidator,
    TestLayoutValidator,
    ValidationContractValidator,
    build_default_custom_validator_registry,
    default_custom_validators,
)
from .defaults import build_default_pipeline, build_default_validation_pipeline
from .enums import ValidationSeverity, ValidationStatus
from .errors import ValidationContractError
from .exceptions import (
    ValidationDependencyError,
    ValidationErrorBase,
    ValidationExecutionError,
    ValidationPipelineError,
    ValidationRegistryError,
)
from .executor import ValidationExecutor
from .findings import ValidationFinding
from .impact import (
    ChangeImpactAnalyzer,
    ChangeImpactResult,
    ChangeSet,
    ChangeSetBuilder,
    ChangeType,
    change_impact_step,
    default_impact_steps,
)
from .observability import (
    LocalValidationRepository,
    UnsupportedValidationSchemaError,
    ValidationArtifactStorageError,
    ValidationExecutionRecord,
    ValidationHistoryPage,
    ValidationHistoryQuery,
    ValidationLogEntry,
    ValidationMetrics,
    ValidationMetricsCalculator,
    ValidationObservabilityService,
    ValidationPersistenceError,
    ValidationRecordConflictError,
    ValidationRecordNotFoundError,
    ValidationRepositoryProtocol,
    ValidationStorageCorruptionError,
    sanitize_validation_data,
)
from .pipeline import CancellationToken, ValidationPipeline
from .planning import (
    ValidationPlan,
    build_default_validation_plan,
    build_validation_plan,
    validate_custom_policy,
)
from .policy import (
    DEFAULT_VALIDATION_POLICIES,
    ValidationPolicy,
    canonical_validation_policy_name,
    default_validation_policies,
    expand_validation_step_labels,
    resolve_validation_policy,
)
from .protocols import InternalValidator
from .registry import ValidationRegistry
from .results import ValidationResult
from .security import (
    CommandPolicy,
    SecurityAnalysisPlan,
    SecurityScope,
    SecurityValidator,
    build_security_plan,
    default_command_policy,
    evaluate_command_policy,
)
from .static_analysis import (
    StaticAnalysisPlan,
    StaticAnalysisScope,
    build_static_analysis_plan,
    default_static_analysis_steps,
    static_dead_code_step,
    static_type_check_step,
)
from .steps import ValidationStep, ValidationStepResult, ValidationStepType
from .testing_catalog import (
    affected_tests_step,
    default_testing_steps,
    full_suite_step,
    integration_tests_step,
    unit_tests_step,
)
from .testing_defaults import default_validation_steps

__all__ = [  # noqa: RUF022 - grouped by phase
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationContractError",
    "ValidationFinding",
    "ValidationArtifact",
    "ValidationStep",
    "ValidationStepType",
    "ValidationStepResult",
    "ValidationContext",
    "ValidationResult",
    # 7.2
    "ValidationErrorBase",
    "ValidationRegistryError",
    "ValidationDependencyError",
    "ValidationExecutionError",
    "ValidationPipelineError",
    "InternalValidator",
    "ValidationRegistry",
    "ValidationExecutor",
    "ValidationPipeline",
    "CancellationToken",
    # 7.3
    "formatter_check_step",
    "formatter_fix_step",
    "lint_check_step",
    "lint_fix_step",
    "syntax_step",
    "ast_step",
    "structural_step",
    "default_structural_steps",
    "default_security_steps",
    "bandit_step",
    "pip_audit_step",
    "build_default_validation_registry",
    "select_python_files",
    "build_default_pipeline",
    "build_default_validation_pipeline",
    "CommandResultParser",
    "security_step",
    "affected_tests_step",
    "unit_tests_step",
    "integration_tests_step",
    "full_suite_step",
    "default_testing_steps",
    "default_validation_steps",
    "ValidationPolicy",
    "DEFAULT_VALIDATION_POLICIES",
    "default_validation_policies",
    "resolve_validation_policy",
    "canonical_validation_policy_name",
    "expand_validation_step_labels",
    "StaticAnalysisPlan",
    "StaticAnalysisScope",
    "build_static_analysis_plan",
    "default_static_analysis_steps",
    "static_dead_code_step",
    "static_type_check_step",
    "ChangeSetBuilder",
    "ChangeImpactAnalyzer",
    "ChangeImpactResult",
    "ChangeSet",
    "ChangeType",
    "change_impact_step",
    "default_impact_steps",
    "CommandPolicy",
    "SecurityAnalysisPlan",
    "SecurityScope",
    "default_command_policy",
    "build_security_plan",
    "evaluate_command_policy",
    "SecurityValidator",
    "CustomValidator",
    "CustomValidatorRegistry",
    "build_custom_validation_step",
    "custom_validator_step",
    "ProjectManifestValidator",
    "ValidationContractValidator",
    "PublicApiValidator",
    "TestLayoutValidator",
    "default_custom_validators",
    "build_default_custom_validator_registry",
    # 7.9 Block 3
    "ValidationPlan",
    "build_default_validation_plan",
    "build_validation_plan",
    "validate_custom_policy",
    # 7.10 Commit Gate
    "CommitAuthorization",
    "CommitGateError",
    "CommitGateEvaluator",
    "CommitGateReason",
    "CommitGateReasonCode",
    "CommitGateRepositoryError",
    "CommitGateResult",
    "GitRepositoryProtocol",
    "ProvisionalCommitError",
    "ProvisionalCommitService",
    "RepositoryState",
    "SubprocessGitRepository",
    "UnsafeRepositoryStateError",
    # 7.11 Observability and Persistence
    "LocalValidationRepository",
    "UnsupportedValidationSchemaError",
    "ValidationArtifactStorageError",
    "ValidationExecutionRecord",
    "ValidationHistoryPage",
    "ValidationHistoryQuery",
    "ValidationLogEntry",
    "ValidationMetrics",
    "ValidationMetricsCalculator",
    "ValidationObservabilityService",
    "ValidationPersistenceError",
    "ValidationRecordConflictError",
    "ValidationRecordNotFoundError",
    "ValidationRepositoryProtocol",
    "ValidationStorageCorruptionError",
    "sanitize_validation_data",
]
