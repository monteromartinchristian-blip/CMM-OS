"""Phase 10.5 – Domain Validation Validators.

Eight internal validators. Security + fragmentation share a DomainValidationScanSession.
"""

from __future__ import annotations

import time as _time_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cmm.domains.errors import DomainContractValidationError
from cmm.domains.registry_contracts import parse_semver
from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
)
from cmm.domains.validation_fragmentation import analyze_fragmentation
from cmm.domains.validation_scan import (
    DomainValidationScanSession,
    _FileTooLargeError,
    _TotalBytesExceededError,
)
from cmm.domains.validation_security import (
    check_file_safety,
    scan_forbidden_commands,
    scan_prompt_injection_risks,
    scan_secrets,
    scan_unauthorized_imports,
)
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import ValidationStep, ValidationStepResult

DEFAULT_MAX_FILES = 500
DEFAULT_MAX_FILE_BYTES = 1_048_576
DEFAULT_MAX_TOTAL_BYTES = 50_000_000
DEFAULT_MAX_DEPTH = 20


def _mfinding(
    code: str,
    message: str,
    *,
    severity: ValidationSeverity = ValidationSeverity.ERROR,
    file_path: str | Path | None = None,
    line: int | None = None,
    blocking: bool = True,
    source_prefix: str = "domains.validation",
    **meta: object,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        message=message,
        severity=severity,
        source=source_prefix,
        file_path=Path(file_path) if file_path else None,
        line=line,
        blocking=blocking,
        metadata=dict(meta),
    )


def _success(
    step_name: str,
    duration_ms: int,
    *,
    metadata: dict[str, object] | None = None,
) -> ValidationStepResult:
    now = datetime.now(timezone.utc)
    return ValidationStepResult(
        name=step_name,
        status=ValidationStatus.PASSED,
        exit_code=0,
        duration_ms=duration_ms,
        stdout="",
        stderr="",
        findings=(),
        started_at=now,
        completed_at=now,
        metadata=dict(metadata) if metadata else {},
    )


def _failure(
    step_name: str,
    findings: tuple[ValidationFinding, ...],
    duration_ms: int,
    *,
    metadata: dict[str, object] | None = None,
) -> ValidationStepResult:
    now = datetime.now(timezone.utc)
    has_blocking = any(f.blocking for f in findings)
    return ValidationStepResult(
        name=step_name,
        status=ValidationStatus.FAILED if has_blocking else ValidationStatus.WARNING,
        exit_code=1 if has_blocking else 0,
        duration_ms=duration_ms,
        stdout="",
        stderr="",
        findings=findings,
        started_at=now,
        completed_at=now,
        metadata=dict(metadata) if metadata else {},
    )


def _warning(
    step_name: str,
    findings: tuple[ValidationFinding, ...],
    duration_ms: int,
    *,
    metadata: dict[str, object] | None = None,
) -> ValidationStepResult:
    now = datetime.now(timezone.utc)
    return ValidationStepResult(
        name=step_name,
        status=ValidationStatus.WARNING,
        exit_code=0,
        duration_ms=duration_ms,
        stdout="",
        stderr="",
        findings=findings,
        started_at=now,
        completed_at=now,
        metadata=dict(metadata) if metadata else {},
    )


def _safe_int(d: dict[str, object], key: str) -> int | None:
    v = d.get(key)
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    return None


# ── validators ────────────────────────────────────────────────────────────────


class DomainManifestValidator:
    name = "domain.manifest"

    def __init__(self, execution_context: DomainValidationExecutionContext) -> None:
        self._ctx = execution_context

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        request = self._ctx.request
        root = Path(request.root_path).resolve()
        findings: list[ValidationFinding] = []
        pack = request.pack
        if pack is None:
            findings.append(
                _mfinding(
                    "DOMAIN_MANIFEST_INVALID",
                    "Pack is None",
                    source_prefix="domains.validation.manifest",
                )
            )
            return _failure(
                step.name, tuple(findings), int((_time_module.monotonic() - t0) * 1000)
            )
        manifest = getattr(pack, "manifest", None)
        if manifest is None:
            findings.append(
                _mfinding(
                    "DOMAIN_MANIFEST_INVALID",
                    "No manifest",
                    source_prefix="domains.validation.manifest",
                )
            )
            return _failure(
                step.name, tuple(findings), int((_time_module.monotonic() - t0) * 1000)
            )

        if not root.exists():
            findings.append(
                _mfinding(
                    "DOMAIN_MANIFEST_PATH_MISSING",
                    "Root does not exist",
                    source_prefix="domains.validation.manifest",
                )
            )

        declared = _collect_paths(manifest)
        for p in declared:
            try:
                r = (root / p).resolve()
                r.relative_to(root)
                if not r.exists():
                    findings.append(
                        _mfinding(
                            "DOMAIN_MANIFEST_PATH_MISSING",
                            f"Path missing: {p}",
                            file_path=p,
                            source_prefix="domains.validation.manifest",
                        )
                    )
                elif r.is_symlink():
                    r.resolve().relative_to(root)
            except ValueError:
                findings.append(
                    _mfinding(
                        "DOMAIN_MANIFEST_PATH_INVALID",
                        f"Path escapes: {p}",
                        source_prefix="domains.validation.manifest",
                    )
                )

        dur = int((_time_module.monotonic() - t0) * 1000)
        if findings:
            return _failure(step.name, tuple(findings), dur)
        return _success(step.name, dur)


class DomainContractsValidator:
    name = "domain.contracts"

    def __init__(self, execution_context: DomainValidationExecutionContext) -> None:
        self._ctx = execution_context

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        request = self._ctx.request
        findings: list[ValidationFinding] = []
        pack = request.pack
        if pack is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_CONTRACT_INVALID",
                        "Pack is None",
                        source_prefix="domains.validation.contracts",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )
        d = getattr(pack, "definition", None)
        m = getattr(pack, "manifest", None)
        if d is None or m is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_CONTRACT_INVALID",
                        "Missing definition/manifest",
                        source_prefix="domains.validation.contracts",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )

        if str(d.id) != str(m.domain_id):
            findings.append(
                _mfinding(
                    "DOMAIN_CONTRACT_INVALID",
                    "ID mismatch",
                    source_prefix="domains.validation.contracts",
                )
            )
        if d.version != m.package_version:
            findings.append(
                _mfinding(
                    "DOMAIN_CONTRACT_INVALID",
                    "Version mismatch",
                    source_prefix="domains.validation.contracts",
                )
            )
        for rid in d.resources:
            if rid not in m.resources:
                findings.append(
                    _mfinding(
                        "DOMAIN_RESOURCE_CONTRACT_INVALID",
                        f"Resource '{rid}' not in manifest",
                        severity=ValidationSeverity.WARNING,
                        blocking=False,
                        source_prefix="domains.validation.contracts",
                    )
                )
        for op_id in d.operations:
            if op_id not in m.operations:
                findings.append(
                    _mfinding(
                        "DOMAIN_OPERATION_CONTRACT_INVALID",
                        f"Operation '{op_id}' not in manifest",
                        source_prefix="domains.validation.contracts",
                    )
                )
        for wf_id in d.workflows:
            if wf_id not in m.workflows:
                findings.append(
                    _mfinding(
                        "DOMAIN_WORKFLOW_CONTRACT_INVALID",
                        f"Workflow '{wf_id}' not in manifest",
                        source_prefix="domains.validation.contracts",
                    )
                )
        dur = int((_time_module.monotonic() - t0) * 1000)
        if findings:
            return _failure(step.name, tuple(findings), dur)
        return _success(step.name, dur)


class DomainPermissionsValidator:
    name = "domain.permissions"

    def __init__(self, execution_context: DomainValidationExecutionContext) -> None:
        self._ctx = execution_context

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        request = self._ctx.request
        findings: list[ValidationFinding] = []
        pack = request.pack
        if pack is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_PERMISSION_UNDECLARED",
                        "Pack is None",
                        source_prefix="domains.validation.permissions",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )
        d = getattr(pack, "definition", None)
        if d is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_PERMISSION_UNDECLARED",
                        "No definition",
                        source_prefix="domains.validation.permissions",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )

        declared = set(d.permissions)
        for perm in declared:
            if perm in ("*", "all"):
                findings.append(
                    _mfinding(
                        "DOMAIN_PERMISSION_ESCALATION",
                        "Wildcard permission",
                        severity=ValidationSeverity.WARNING,
                        blocking=True,
                        source_prefix="domains.validation.permissions",
                    )
                )
        dur = int((_time_module.monotonic() - t0) * 1000)
        if findings:
            return _failure(step.name, tuple(findings), dur)
        return _success(step.name, dur)


class DomainDependenciesValidator:
    name = "domain.dependencies"

    def __init__(self, execution_context: DomainValidationExecutionContext) -> None:
        self._ctx = execution_context

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        request = self._ctx.request
        findings: list[ValidationFinding] = []
        pack = request.pack
        if pack is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_DEPENDENCY_MISSING",
                        "Pack is None",
                        source_prefix="domains.validation.dependencies",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )
        d = getattr(pack, "definition", None)
        if d is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_DEPENDENCY_MISSING",
                        "No definition",
                        source_prefix="domains.validation.dependencies",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )

        snapshot = request.registry_snapshot
        records = getattr(snapshot, "records", ()) if snapshot is not None else ()
        smap: dict[str, object] = {}
        for rec in records:
            smap[str(getattr(rec, "domain_id", ""))] = rec

        for dep in d.dependencies:
            did = str(dep.domain_id)
            rec = smap.get(did)
            if rec is None:
                findings.append(
                    _mfinding(
                        "DOMAIN_DEPENDENCY_MISSING",
                        f"Required dep missing: {did}",
                        source_prefix="domains.validation.dependencies",
                    )
                )
            elif getattr(rec, "status", "") in ("disabled", "incompatible"):
                findings.append(
                    _mfinding(
                        "DOMAIN_DEPENDENCY_MISSING",
                        f"Dep {did} is disabled/incompatible",
                        source_prefix="domains.validation.dependencies",
                    )
                )

        for dep in d.optional_dependencies:
            did = str(dep.domain_id)
            if did not in smap and snapshot is not None:
                findings.append(
                    _mfinding(
                        "DOMAIN_DEPENDENCY_VERSION_INCOMPATIBLE",
                        f"Optional dep missing: {did}",
                        severity=ValidationSeverity.WARNING,
                        blocking=False,
                        source_prefix="domains.validation.dependencies",
                    )
                )

        dur = int((_time_module.monotonic() - t0) * 1000)
        if findings:
            return _failure(step.name, tuple(findings), dur)
        return _success(step.name, dur)


class DomainCompatibilityValidator:
    name = "domain.compatibility"

    def __init__(
        self,
        execution_context: DomainValidationExecutionContext,
        *,
        current_cmm_version: str = "0.1.0",
    ) -> None:
        self._ctx = execution_context
        self.cv = current_cmm_version

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        request = self._ctx.request
        findings: list[ValidationFinding] = []
        pack = request.pack
        if pack is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_COMPATIBILITY_UNSUPPORTED",
                        "Pack is None",
                        source_prefix="domains.validation.compatibility",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )
        m = getattr(pack, "manifest", None)
        if m is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_COMPATIBILITY_UNSUPPORTED",
                        "No manifest",
                        source_prefix="domains.validation.compatibility",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )
        compat = getattr(m, "compatibility", None)
        if compat is not None:
            for attr, op in (
                ("minimum_cmm_version", ">="),
                ("maximum_cmm_version", "<="),
            ):
                v = getattr(compat, attr, None)
                if v:
                    r = _version_matches(self.cv, f"{op}{v}")
                    if r is None or not r:
                        findings.append(
                            _mfinding(
                                "DOMAIN_COMPATIBILITY_UNSUPPORTED",
                                f"CMM {self.cv} not compatible with {attr}={v}",
                                source_prefix="domains.validation.compatibility",
                            )
                        )

        dur = int((_time_module.monotonic() - t0) * 1000)
        if findings:
            return _failure(step.name, tuple(findings), dur)
        return _success(step.name, dur)


class DomainSecurityValidator:
    name = "domain.security"

    def __init__(
        self,
        execution_context: DomainValidationExecutionContext,
        *,
        scan_session: DomainValidationScanSession | None = None,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
        max_files: int = DEFAULT_MAX_FILES,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        self._ctx = execution_context
        self._scan = scan_session

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        findings: list[ValidationFinding] = []
        scan = self._scan
        if scan is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_SECURITY_LIMITS_MISSING",
                        "No scan session",
                        source_prefix="domains.validation.security",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )

        for issue in scan.issues:
            findings.append(
                _mfinding(
                    "DOMAIN_SECURITY_LIMITS_MISSING",
                    f"Walk issue: {issue.category}",
                    source_prefix="domains.validation.security",
                )
            )

        for rel_path in scan.files:
            try:
                content = scan.read(rel_path)
            except (_FileTooLargeError, _TotalBytesExceededError, OSError):
                findings.append(
                    _mfinding(
                        "DOMAIN_SECURITY_READ_FAILED",
                        f"Failed to read file: {rel_path}",
                        file_path=rel_path,
                        blocking=True,
                        severity=ValidationSeverity.ERROR,
                        source_prefix="domains.validation.security",
                    )
                )
                continue

            try:
                text = content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                findings.append(
                    _mfinding(
                        "DOMAIN_SECURITY_LIMITS_MISSING",
                        f"Invalid UTF-8: {rel_path}",
                        file_path=rel_path,
                        blocking=False,
                        severity=ValidationSeverity.WARNING,
                        source_prefix="domains.validation.security",
                    )
                )
                continue

            safety = check_file_safety(str(rel_path), content, max_file_bytes=1_000_000)
            for sf in safety:
                findings.append(
                    _mfinding(
                        f"DOMAIN_SECURITY_{str(sf['category']).upper()}",
                        f"Safety: {sf['category']}",
                        file_path=rel_path,
                        source_prefix="domains.validation.security",
                    )
                )

            for sec in scan_secrets(text, str(rel_path)):
                findings.append(
                    _mfinding(
                        "DOMAIN_SECURITY_SECRET_DETECTED",
                        f"Potential secret in {rel_path}",
                        file_path=rel_path,
                        line=_safe_int(sec, "line"),
                        source_prefix="domains.validation.security",
                    )
                )

            for cmd in scan_forbidden_commands(text, str(rel_path)):
                findings.append(
                    _mfinding(
                        "DOMAIN_SECURITY_FORBIDDEN_COMMAND",
                        f"Forbidden command in {rel_path}",
                        file_path=rel_path,
                        line=_safe_int(cmd, "line"),
                        source_prefix="domains.validation.security",
                    )
                )

            if rel_path.suffix == ".py":
                for imp in scan_unauthorized_imports(text, str(rel_path)):
                    findings.append(
                        _mfinding(
                            "DOMAIN_SECURITY_UNAUTHORIZED_IMPORT",
                            f"Unauthorized import in {rel_path}",
                            file_path=rel_path,
                            line=_safe_int(imp, "line"),
                            source_prefix="domains.validation.security",
                        )
                    )

            if rel_path.suffix in (".md", ".txt", ".prompt", ".yaml", ".yml", ".json"):
                for pf in scan_prompt_injection_risks(text, str(rel_path)):
                    is_blocking = bool(pf.get("blocking", False))
                    findings.append(
                        _mfinding(
                            "DOMAIN_SECURITY_PROMPT_INJECTION_RISK",
                            f"Prompt risk in {rel_path}",
                            file_path=rel_path,
                            line=_safe_int(pf, "line"),
                            blocking=is_blocking,
                            severity=ValidationSeverity.ERROR
                            if is_blocking
                            else ValidationSeverity.WARNING,
                            source_prefix="domains.validation.security",
                        )
                    )

        dur = int((_time_module.monotonic() - t0) * 1000)
        if findings:
            return _failure(step.name, tuple(findings), dur)
        return _success(step.name, dur)


class DomainFragmentationValidator:
    name = "domain.fragmentation"

    def __init__(
        self,
        execution_context: DomainValidationExecutionContext,
        *,
        scan_session: DomainValidationScanSession | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        self._ctx = execution_context
        self._scan = scan_session

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        findings: list[ValidationFinding] = []
        scan = self._scan
        if scan is None:
            return _failure(
                step.name,
                (
                    _mfinding(
                        "DOMAIN_FRAGMENTATION_PROVENANCE_OMITTED",
                        "No scan session",
                        source_prefix="domains.validation.fragmentation",
                    ),
                ),
                int((_time_module.monotonic() - t0) * 1000),
            )

        for rel_path in scan.files:
            if rel_path.suffix != ".py":
                continue
            try:
                content = scan.read(rel_path)
            except (_FileTooLargeError, _TotalBytesExceededError, OSError):
                strict = self._ctx.request.strict
                findings.append(
                    _mfinding(
                        "DOMAIN_FRAGMENTATION_READ_FAILED",
                        f"Failed to read file: {rel_path}",
                        file_path=rel_path,
                        blocking=strict,
                        severity=ValidationSeverity.ERROR
                        if strict
                        else ValidationSeverity.WARNING,
                        source_prefix="domains.validation.fragmentation",
                    )
                )
                continue

            try:
                text = content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                strict = self._ctx.request.strict
                findings.append(
                    _mfinding(
                        "DOMAIN_FRAGMENTATION_UTF8_INVALID",
                        f"Invalid UTF-8 encoding: {rel_path}",
                        file_path=rel_path,
                        blocking=strict,
                        severity=ValidationSeverity.ERROR
                        if strict
                        else ValidationSeverity.WARNING,
                        source_prefix="domains.validation.fragmentation",
                    )
                )
                continue

            frags = analyze_fragmentation(text, str(rel_path))
            for frag in frags:
                code = str(frag.get("code", "DOMAIN_FRAGMENTATION_PROVENANCE_OMITTED"))
                findings.append(
                    _mfinding(
                        code,
                        f"{code}: {rel_path}",
                        file_path=rel_path,
                        line=_safe_int(frag, "line"),
                        source_prefix="domains.validation.fragmentation",
                    )
                )

        dur = int((_time_module.monotonic() - t0) * 1000)
        if findings:
            return _failure(step.name, tuple(findings), dur)
        return _success(step.name, dur)


class DomainTestsValidator:
    name = "domain.tests"

    def __init__(self, execution_context: DomainValidationExecutionContext) -> None:
        self._ctx = execution_context

    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        t0 = _time_module.monotonic()
        request = self._ctx.request
        root = Path(request.root_path).resolve()
        test_dir = root / "tests"

        structure_valid = (
            test_dir.exists()
            and test_dir.is_dir()
            and bool(
                list(test_dir.glob("test_*.py")) + list(test_dir.glob("*_test.py"))
            )
        )

        # Tests are never executed in 10.5 — always deferred
        findings: list[ValidationFinding] = []
        if not structure_valid:
            findings.append(
                _mfinding(
                    "DOMAIN_TESTS_MISSING",
                    "No tests found",
                    severity=ValidationSeverity.WARNING,
                    blocking=request.strict,
                    source_prefix="domains.validation.tests",
                    tests_evaluated=False,
                    structure_valid=False,
                    not_evaluated=True,
                    reason="execution_deferred",
                )
            )
            # Additional strict-mode blocker: tests required but not present
            if request.strict:
                findings.append(
                    _mfinding(
                        "DOMAIN_TESTS_BLOCKING",
                        "Strict mode requires tests but none found",
                        severity=ValidationSeverity.ERROR,
                        blocking=True,
                        source_prefix="domains.validation.tests",
                        tests_evaluated=False,
                        structure_valid=False,
                        not_evaluated=True,
                        reason="execution_deferred",
                    )
                )
        else:
            # Even with structure, tests are never executed; strict always blocks
            findings.append(
                _mfinding(
                    "DOMAIN_TESTS_NOT_RUN",
                    "Tests not executed (deferred to future phase)",
                    severity=ValidationSeverity.WARNING,
                    blocking=request.strict,
                    source_prefix="domains.validation.tests",
                    tests_evaluated=False,
                    structure_valid=True,
                    not_evaluated=True,
                    reason="execution_deferred",
                )
            )

        dur = int((_time_module.monotonic() - t0) * 1000)
        metadata: dict[str, object] = {
            "tests_evaluated": False,
            "structure_valid": structure_valid,
            "not_evaluated": True,
            "reason": "execution_deferred",
        }
        if findings:
            return _failure(step.name, tuple(findings), dur, metadata=metadata)
        return _success(step.name, dur, metadata=metadata)


# ── helpers ────────────────────────────────────────────────────────────────────


def _version_matches(version: str, constraint: str) -> bool | None:
    try:
        v = parse_semver(version)
    except DomainContractValidationError:
        return None
    c = constraint.strip()
    try:
        if c.startswith(">="):
            return v >= parse_semver(c[2:].strip())
        if c.startswith("<="):
            return v <= parse_semver(c[2:].strip())
        if c.startswith("=="):
            return v == parse_semver(c[2:].strip())
        if c.startswith("!="):
            return v != parse_semver(c[2:].strip())
        if c.startswith(">"):
            return v > parse_semver(c[1:].strip())
        if c.startswith("<"):
            return v < parse_semver(c[1:].strip())
        if c.startswith("~="):
            cv = parse_semver(c[2:].strip())
            return v >= cv and v < parse_semver(f"{cv.major + 1}.0.0")
        return v == parse_semver(c)
    except DomainContractValidationError:
        return None


def _collect_paths(manifest: Any) -> set[str]:
    paths: set[str] = set()
    for attr in (
        "resources",
        "rules",
        "operations",
        "workflows",
        "validators",
        "profiles",
        "prompts",
    ):
        value = getattr(manifest, attr, None)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, str):
                    paths.add(item)
                elif hasattr(item, "path"):
                    paths.add(str(item.path))
    return paths


__all__ = [
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_FILES",
    "DEFAULT_MAX_FILE_BYTES",
    "DEFAULT_MAX_TOTAL_BYTES",
    "DomainCompatibilityValidator",
    "DomainContractsValidator",
    "DomainDependenciesValidator",
    "DomainFragmentationValidator",
    "DomainManifestValidator",
    "DomainPermissionsValidator",
    "DomainSecurityValidator",
    "DomainTestsValidator",
]
