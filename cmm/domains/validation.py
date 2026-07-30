"""Phase 10.5 – Domain Validation Service."""

from __future__ import annotations

import math
import time as _time_module
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import (
    DomainValidationBlocked,
    DomainValidationExecutionError,
)
from cmm.domains.validation_context import build_domain_validation_context
from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
    DomainValidationResult,
)
from cmm.domains.validation_scan import DomainValidationScanSession
from cmm.domains.validation_steps import (
    STEP_COMPATIBILITY,
    STEP_CONTRACTS,
    STEP_DEPENDENCIES,
    STEP_FRAGMENTATION,
    STEP_MANIFEST,
    STEP_PERMISSIONS,
    STEP_SECURITY,
    STEP_TESTS,
    build_domain_validation_steps,
)
from cmm.domains.validation_validators import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_TOTAL_BYTES,
    DomainCompatibilityValidator,
    DomainContractsValidator,
    DomainDependenciesValidator,
    DomainFragmentationValidator,
    DomainManifestValidator,
    DomainPermissionsValidator,
    DomainSecurityValidator,
    DomainTestsValidator,
)
from cmm.validation.enums import ValidationStatus
from cmm.validation.executor import ValidationExecutor
from cmm.validation.pipeline import ValidationPipeline
from cmm.validation.registry import ValidationRegistry
from cmm.validation.results import ValidationResult
from cmm.validation.steps import ValidationStepResult

_DOMAIN_STEP_NAMES = frozenset(
    {
        STEP_MANIFEST,
        STEP_CONTRACTS,
        STEP_PERMISSIONS,
        STEP_DEPENDENCIES,
        STEP_COMPATIBILITY,
        STEP_SECURITY,
        STEP_FRAGMENTATION,
        STEP_TESTS,
    }
)


def _map_status(vs: ValidationStatus) -> DomainValidationStatus:
    mapping: dict[ValidationStatus, DomainValidationStatus] = {
        ValidationStatus.PASSED: DomainValidationStatus.PASSED,
        ValidationStatus.WARNING: DomainValidationStatus.WARNING,
        ValidationStatus.FAILED: DomainValidationStatus.FAILED,
        ValidationStatus.ERROR: DomainValidationStatus.ERROR,
        ValidationStatus.CANCELLED: DomainValidationStatus.ERROR,
        ValidationStatus.TIMED_OUT: DomainValidationStatus.ERROR,
        ValidationStatus.SKIPPED: DomainValidationStatus.ERROR,
        ValidationStatus.PENDING: DomainValidationStatus.PENDING,
        ValidationStatus.RUNNING: DomainValidationStatus.RUNNING,
    }
    return mapping.get(vs, DomainValidationStatus.ERROR)


def _derive_step_flag(
    step_name: str, step_results: tuple[ValidationStepResult, ...]
) -> bool:
    for sr in step_results:
        if sr.name == step_name:
            if sr.status in (ValidationStatus.PASSED, ValidationStatus.WARNING):
                return not any(f.blocking for f in sr.findings)
            return False
    return False


class PipelineDomainValidator:
    """Public domain validator service with full DI and temporary handler lifecycle."""

    def __init__(
        self,
        *,
        current_cmm_version: str = "0.1.0",
        registry: ValidationRegistry | None = None,
        executor: ValidationExecutor | None = None,
        pipeline: ValidationPipeline | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        max_files: int = DEFAULT_MAX_FILES,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        _validate_limits(max_files, max_file_bytes, max_total_bytes, max_depth)

        self.current_cmm_version = current_cmm_version
        self._requested_registry = registry
        self._requested_executor = executor
        self._requested_pipeline = pipeline
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        self.max_depth = max_depth
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or _time_module.monotonic

    def validate(self, request: DomainValidationRequest) -> DomainValidationResult:
        t0 = self._monotonic()
        if not isinstance(t0, (int, float)) or not math.isfinite(t0):
            raise DomainValidationExecutionError(
                "monotonic clock returned non-finite initial value",
                details={"t0": str(t0)},
            )

        # Resolve DI with identity checks
        effective_registry, _effective_executor, effective_pipeline, own_handlers = (
            _resolve_di(
                self._requested_pipeline,
                self._requested_registry,
                self._requested_executor,
            )
        )

        validation_context = build_domain_validation_context(request)
        steps = build_domain_validation_steps(request)

        # Build shared scan session for security + fragmentation
        scan_session = DomainValidationScanSession(
            root=Path(request.root_path).resolve(),
            max_files=self.max_files,
            max_file_bytes=self.max_file_bytes,
            max_total_bytes=self.max_total_bytes,
            max_depth=self.max_depth,
        )

        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=validation_context,
            scan_session=scan_session,
        )

        # Register validators temporarily
        _register_temp_validators(
            effective_registry,
            exec_ctx,
            self.current_cmm_version,
            self.max_files,
            self.max_file_bytes,
            self.max_total_bytes,
            self.max_depth,
        )

        try:
            result: ValidationResult = effective_pipeline.run(
                context=validation_context,
                steps=steps,
            )
        except Exception as exc:
            raise DomainValidationExecutionError(
                "Domain validation pipeline execution failed",
                details={"error_type": type(exc).__name__},
            ) from exc
        finally:
            # Remove only the handlers we added
            for name in own_handlers:
                effective_registry.unregister(name)

        t1 = self._monotonic()
        if not isinstance(t1, (int, float)) or not math.isfinite(t1):
            raise DomainValidationExecutionError(
                "monotonic clock returned non-finite final value",
                details={"t1": str(t1)},
            )
        if t1 < t0:
            raise DomainValidationExecutionError(
                "monotonic clock went backwards",
                details={"t0": t0, "t1": t1},
            )
        duration_ms = int((t1 - t0) * 1000)

        return build_domain_validation_result(
            request=request,
            result=result,
            duration_ms=duration_ms,
            clock=self._clock,
        )


def _validate_limits(
    files: object, fbytes: object, total: object, depth: object
) -> None:
    for name, val in (
        ("max_files", files),
        ("max_file_bytes", fbytes),
        ("max_total_bytes", total),
        ("max_depth", depth),
    ):
        if isinstance(val, bool) or not isinstance(val, int):
            raise DomainValidationExecutionError(
                f"{name} must be an int", details={"field": name}
            )
        if val <= 0:
            raise DomainValidationExecutionError(
                f"{name} must be positive", details={"field": name, "value": val}
            )


def _resolve_di(
    pipeline: ValidationPipeline | None,
    registry: ValidationRegistry | None,
    executor: ValidationExecutor | None,
) -> tuple[ValidationRegistry, ValidationExecutor, ValidationPipeline, list[str]]:
    if pipeline is not None:
        if registry is not None and pipeline.registry is not registry:
            raise DomainValidationExecutionError(
                "Injected pipeline registry differs from injected registry",
                details={"reason": "registry_mismatch"},
            )
        if executor is not None and pipeline.executor is not executor:
            raise DomainValidationExecutionError(
                "Injected pipeline executor differs from injected executor",
                details={"reason": "executor_mismatch"},
            )
        effective_registry = pipeline.registry
        effective_executor = pipeline.executor
        effective_pipeline = pipeline
    else:
        effective_registry = registry or ValidationRegistry()
        effective_executor = executor or ValidationExecutor()
        effective_pipeline = ValidationPipeline(
            executor=effective_executor, registry=effective_registry
        )

    # Check for existing domain.* handlers — reject collision
    own_handlers: list[str] = []
    for name in _DOMAIN_STEP_NAMES:
        if effective_registry.has(name):
            raise DomainValidationExecutionError(
                f"Handler collision: '{name}' already registered in target registry",
                details={"handler": name},
            )
        own_handlers.append(name)

    return effective_registry, effective_executor, effective_pipeline, own_handlers


def _register_temp_validators(
    registry: ValidationRegistry,
    exec_ctx: DomainValidationExecutionContext,
    current_cmm_version: str,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
    max_depth: int,
) -> None:
    scan = exec_ctx.scan_session
    registry.register("domain.manifest", DomainManifestValidator(exec_ctx))
    registry.register("domain.contracts", DomainContractsValidator(exec_ctx))
    registry.register("domain.permissions", DomainPermissionsValidator(exec_ctx))
    registry.register("domain.dependencies", DomainDependenciesValidator(exec_ctx))
    registry.register(
        "domain.compatibility",
        DomainCompatibilityValidator(exec_ctx, current_cmm_version=current_cmm_version),
    )
    registry.register(
        "domain.security",
        DomainSecurityValidator(
            exec_ctx,
            scan_session=scan,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            max_files=max_files,
            max_depth=max_depth,
        ),
    )
    registry.register(
        "domain.fragmentation",
        DomainFragmentationValidator(exec_ctx, scan_session=scan, max_depth=max_depth),
    )
    registry.register("domain.tests", DomainTestsValidator(exec_ctx))


def build_domain_validation_result(
    request: DomainValidationRequest,
    result: ValidationResult,
    *,
    duration_ms: int | None = None,
    clock: Callable[[], datetime] | None = None,
) -> DomainValidationResult:
    step_results = result.steps

    manifest_valid = _derive_step_flag(STEP_MANIFEST, step_results)
    contracts_valid = _derive_step_flag(STEP_CONTRACTS, step_results)
    permissions_valid = _derive_step_flag(STEP_PERMISSIONS, step_results)
    dependencies_valid = _derive_step_flag(STEP_DEPENDENCIES, step_results)
    compatibility_valid = _derive_step_flag(STEP_COMPATIBILITY, step_results)
    security_valid = _derive_step_flag(STEP_SECURITY, step_results)
    fragmentation_valid = _derive_step_flag(STEP_FRAGMENTATION, step_results)
    tests_valid = _derive_step_flag(STEP_TESTS, step_results)

    operations_valid = contracts_valid
    workflows_valid = contracts_valid

    status = _map_status(result.status)

    domain_id = "unknown"
    version = "unknown"
    if request.pack is not None:
        if getattr(request.pack, "definition", None) is not None:
            domain_id = str(request.pack.definition.id)
            version = request.pack.definition.version
        elif getattr(request.pack, "manifest", None) is not None:
            m = request.pack.manifest
            domain_id = str(getattr(m, "domain_id", "unknown"))
            version = str(getattr(m, "package_version", "unknown"))

    findings = tuple(result.blocking_findings)
    warnings = tuple(result.warnings)
    dur = duration_ms if duration_ms is not None else result.duration_ms
    validated_at = clock() if clock else datetime.now(timezone.utc)
    if validated_at.tzinfo is None:
        validated_at = validated_at.replace(tzinfo=timezone.utc)

    # tests_evaluated from step metadata
    tests_evaluated = False
    for sr in step_results:
        if sr.name == STEP_TESTS:
            tests_evaluated = bool(sr.metadata.get("tests_evaluated", False))
            break

    metadata: dict[str, object] = {
        "strict": request.strict,
        "run_tests": request.run_tests,
        "tests_evaluated": tests_evaluated,
    }

    return DomainValidationResult(
        domain_id=domain_id,
        version=version,
        status=status,
        manifest_valid=manifest_valid,
        compatibility_valid=compatibility_valid,
        dependencies_valid=dependencies_valid,
        contracts_valid=contracts_valid,
        permissions_valid=permissions_valid,
        operations_valid=operations_valid,
        workflows_valid=workflows_valid,
        security_valid=security_valid,
        fragmentation_valid=fragmentation_valid,
        tests_valid=tests_valid,
        findings=findings,
        warnings=warnings,
        step_results=step_results,
        duration_ms=dur,
        validated_at=validated_at,
        metadata=metadata,
    )


def ensure_domain_validation_allows_install(result: DomainValidationResult) -> None:
    reason_codes: list[str] = []
    blocking_codes: list[str] = []

    if result.status in (DomainValidationStatus.FAILED, DomainValidationStatus.ERROR):
        reason_codes.append("status_failed_or_error")

    if not result.manifest_valid:
        reason_codes.append("manifest_invalid")
    if not result.contracts_valid:
        reason_codes.append("contracts_invalid")
    if not result.dependencies_valid:
        reason_codes.append("dependencies_invalid")
    if not result.permissions_valid:
        reason_codes.append("permissions_invalid")
    if not result.security_valid:
        reason_codes.append("security_invalid")
    if not result.compatibility_valid:
        reason_codes.append("compatibility_invalid")
    if not result.fragmentation_valid:
        reason_codes.append("fragmentation_invalid")

    strict = bool(result.metadata.get("strict", True))
    tests_evaluated = bool(result.metadata.get("tests_evaluated", False))
    if strict and not tests_evaluated:
        reason_codes.append("tests_not_evaluated_strict")
    if strict and not result.tests_valid:
        reason_codes.append("tests_invalid_strict")

    for f in result.findings:
        if getattr(f, "blocking", False):
            blocking_codes.append(getattr(f, "code", "unknown"))

    if reason_codes or blocking_codes:
        raise DomainValidationBlocked(
            "Domain validation blocks installation",
            details={
                "domain_id": result.domain_id,
                "version": result.version,
                "status": result.status.value,
                "reason_codes": tuple(reason_codes),
                "blocking_finding_codes": tuple(blocking_codes),
            },
        )


__all__ = [
    "PipelineDomainValidator",
    "build_domain_validation_result",
    "ensure_domain_validation_allows_install",
]
