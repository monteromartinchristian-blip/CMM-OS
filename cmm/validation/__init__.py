"""Validation contracts for CMM OS (Phase 7.1).

Public API surfaces as cmm.validation.*
"""
from .enums import ValidationStatus, ValidationSeverity
from .errors import ValidationContractError
from .findings import ValidationFinding
from .artifacts import ValidationArtifact
from .steps import ValidationStep, ValidationStepType, ValidationStepResult
from .context import ValidationContext
from .results import ValidationResult
from .exceptions import (
    ValidationErrorBase,
    ValidationRegistryError,
    ValidationDependencyError,
    ValidationExecutionError,
    ValidationPipelineError,
)
from .protocols import InternalValidator
from .registry import ValidationRegistry
from .executor import ValidationExecutor
from .pipeline import ValidationPipeline, CancellationToken
from .catalog import (
    formatter_check_step,
    formatter_fix_step,
    lint_check_step,
    lint_fix_step,
    syntax_step,
    ast_step,
    structural_step,
    default_structural_steps,
    build_default_validation_registry,
    select_python_files,
)
from .defaults import build_default_pipeline, build_default_validation_pipeline
from .command_parsers import CommandResultParser
from .testing_catalog import default_testing_steps, affected_tests_step, unit_tests_step, integration_tests_step, full_suite_step
from .testing_defaults import default_validation_steps

__all__ = [
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
    "build_default_validation_registry",
    "select_python_files",
    "build_default_pipeline",
    "build_default_validation_pipeline",
    "CommandResultParser",
    "affected_tests_step",
    "unit_tests_step",
    "integration_tests_step",
    "full_suite_step",
    "default_testing_steps",
    "default_validation_steps",
]
