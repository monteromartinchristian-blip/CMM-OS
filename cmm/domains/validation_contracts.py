"""Phase 10.5 – Domain Validation Contracts.

Immutable, type-safe contracts for domain validation requests and results.
Integrates with Phase 7 Validation infrastructure.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _deep_unfreeze,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainContractValidationError, DomainSerializationError

# ── JSON-safe value type ───────────────────────────────────────────────────────

JSONValue = (
    str | int | float | bool | None | Mapping[str, "JSONValue"] | list["JSONValue"]
)


def _validate_json_safe(value: Any, field_name: str) -> Any:
    """Validate that a value is JSON-safe (recursively)."""
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise DomainContractValidationError(
                    f"{field_name}: all keys must be strings",
                    field=field_name,
                )
            result[k] = _validate_json_safe(v, f"{field_name}.{k}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _validate_json_safe(v, f"{field_name}[{i}]") for i, v in enumerate(value)
        ]
    raise DomainContractValidationError(
        f"{field_name}: value must be JSON-safe, got {type(value).__name__}: {value!r}",
        field=field_name,
    )


def _validate_metadata_json_safe(
    metadata: Any, field_name: str
) -> MappingProxyType[str, Any]:
    """Validate metadata is JSON-safe and deep-freeze it."""
    if metadata is None:
        return MappingProxyType({})
    validated = _validate_json_safe(metadata, field_name)
    return _deep_freeze(validated)


def _reject_credential_keys(metadata: Mapping[str, Any], field_name: str) -> None:
    """Scan for credential-like keys in metadata."""
    _CREDENTIAL_KEYS = frozenset(
        {"password", "secret", "token", "api_key", "private_key", "credential"}
    )
    for key in metadata:
        key_lower = key.lower()
        if key_lower in _CREDENTIAL_KEYS or any(
            ck in key_lower for ck in _CREDENTIAL_KEYS
        ):
            raise DomainContractValidationError(
                f"Credential-like key detected in {field_name}: '{key}'",
                field=field_name,
                details={"credential_key": key},
            )


# ── DomainValidationRequest ────────────────────────────────────────────────────

_REQUEST_KNOWN = frozenset(
    {
        "pack",
        "root_path",
        "candidate",
        "registry_snapshot",
        "requested_steps",
        "excluded_steps",
        "strict",
        "allow_untrusted",
        "run_tests",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainValidationRequest:
    """Immutable request for domain validation.

    This is the public boundary — ``pack`` is typed as DomainPack but is NOT
    serialized directly to JSON. Serialize metadata only; the pack object
    stays in-process.
    """

    pack: Any  # DomainPack — not serializable in from_dict, passed in-process
    root_path: str
    candidate: Any | None = None  # DomainCandidate | None
    registry_snapshot: Any | None = None  # DomainRegistrySnapshot | None
    requested_steps: tuple[str, ...] | None = None
    excluded_steps: tuple[str, ...] = ()
    strict: bool = True
    allow_untrusted: bool = False
    run_tests: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        # Validate root_path
        object.__setattr__(
            self, "root_path", _validate_non_empty_str(self.root_path, "root_path")
        )

        # Validate requested_steps
        if self.requested_steps is not None:
            steps = tuple(
                _validate_non_empty_str(s, "requested_steps")
                for s in self.requested_steps
            )
            object.__setattr__(self, "requested_steps", steps)

        # Validate excluded_steps
        object.__setattr__(
            self,
            "excluded_steps",
            tuple(
                _validate_non_empty_str(s, "excluded_steps")
                for s in self.excluded_steps
            ),
        )

        # Strict bools
        object.__setattr__(self, "strict", _validate_strict_bool(self.strict, "strict"))
        object.__setattr__(
            self,
            "allow_untrusted",
            _validate_strict_bool(self.allow_untrusted, "allow_untrusted"),
        )
        object.__setattr__(
            self, "run_tests", _validate_strict_bool(self.run_tests, "run_tests")
        )

        # Deep-freeze and validate metadata
        frozen_meta = _validate_metadata_json_safe(self.metadata, "metadata")
        _reject_credential_keys(frozen_meta, "metadata")
        object.__setattr__(self, "metadata", frozen_meta)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary (pack and runtime objects excluded)."""
        return {
            "root_path": self.root_path,
            "requested_steps": (
                list(self.requested_steps) if self.requested_steps is not None else None
            ),
            "excluded_steps": list(self.excluded_steps),
            "strict": self.strict,
            "allow_untrusted": self.allow_untrusted,
            "run_tests": self.run_tests,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainValidationRequest:
        """Deserialize from dictionary.

        Note: ``pack``, ``candidate``, and ``registry_snapshot`` are NOT
        deserialized from JSON. They must be provided separately. This
        method only reconstructs configuration fields.
        """
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainValidationRequest.from_dict requires a mapping", field="data"
            )
        from cmm.domains.contracts import _reject_unknown_fields as _reject

        _reject(data, _REQUEST_KNOWN, "DomainValidationRequest")
        if "root_path" not in data:
            raise DomainSerializationError(
                "DomainValidationRequest.from_dict missing required field 'root_path'",
                field="root_path",
            )

        requested_raw = data.get("requested_steps")
        requested = (
            tuple(str(s) for s in requested_raw) if requested_raw is not None else None
        )

        # Strict bool validation
        strict_raw = data.get("strict")
        untrusted_raw = data.get("allow_untrusted")
        tests_raw = data.get("run_tests")

        try:
            strict = (
                _validate_strict_bool(strict_raw, "strict")
                if strict_raw is not None
                else True
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

        try:
            allow_untrusted = (
                _validate_strict_bool(untrusted_raw, "allow_untrusted")
                if untrusted_raw is not None
                else False
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

        try:
            run_tests = (
                _validate_strict_bool(tests_raw, "run_tests")
                if tests_raw is not None
                else True
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

        excluded_raw = data.get("excluded_steps", ())
        excluded = tuple(str(s) for s in excluded_raw) if excluded_raw else ()

        # Construct with a sentinel pack — caller must replace
        return cls(
            pack=None,  # Sentinel; caller must provide DomainPack
            root_path=str(data["root_path"]),
            candidate=None,
            registry_snapshot=None,
            requested_steps=requested,
            excluded_steps=excluded,
            strict=strict,
            allow_untrusted=allow_untrusted,
            run_tests=run_tests,
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainValidationResult ─────────────────────────────────────────────────────

_RESULT_KNOWN = frozenset(
    {
        "domain_id",
        "version",
        "status",
        "manifest_valid",
        "compatibility_valid",
        "dependencies_valid",
        "contracts_valid",
        "permissions_valid",
        "operations_valid",
        "workflows_valid",
        "security_valid",
        "fragmentation_valid",
        "tests_valid",
        "findings",
        "warnings",
        "step_results",
        "duration_ms",
        "validated_at",
        "metadata",
    }
)


def _validate_strict_bool_flag(val: Any, field_name: str) -> bool:
    """Validate a strict boolean flag for result fields."""
    return _validate_strict_bool(val, field_name)


def _validate_positive_int(val: Any, field_name: str) -> int:
    """Validate a non-negative integer (not bool)."""
    if isinstance(val, bool):
        raise DomainContractValidationError(
            f"{field_name} must be an int, not a boolean", field=field_name
        )
    if not isinstance(val, int):
        raise DomainContractValidationError(
            f"{field_name} must be an int, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if val < 0:
        raise DomainContractValidationError(
            f"{field_name} must be >= 0, got {val}", field=field_name
        )
    return val


def _validate_tz_aware_datetime(val: Any, field_name: str) -> datetime:
    """Validate a timezone-aware datetime."""
    if not isinstance(val, datetime):
        raise DomainContractValidationError(
            f"{field_name} must be a datetime, got {type(val).__name__}",
            field=field_name,
        )
    if val.tzinfo is None:
        raise DomainContractValidationError(
            f"{field_name} must be timezone-aware", field=field_name
        )
    return val


@dataclass(frozen=True, slots=True)
class DomainValidationResult:
    """Immutable result of domain validation.

    All flags are derived from step results in :func:`build_domain_validation_result`.
    Invariants:
        - If status is PASSED, no blocking findings exist.
        - If a blocking finding exists, status cannot be PASSED.
        - duration_ms >= 0.
        - validated_at is timezone-aware.
    """

    domain_id: str
    version: str
    status: DomainValidationStatus
    manifest_valid: bool
    compatibility_valid: bool
    dependencies_valid: bool
    contracts_valid: bool
    permissions_valid: bool
    operations_valid: bool
    workflows_valid: bool
    security_valid: bool
    fragmentation_valid: bool
    tests_valid: bool
    findings: tuple[Any, ...] = ()  # tuple[ValidationFinding, ...]
    warnings: tuple[Any, ...] = ()  # tuple[ValidationFinding, ...]
    step_results: tuple[Any, ...] = ()  # tuple[ValidationStepResult, ...]
    duration_ms: int = 0
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_id", _validate_non_empty_str(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self, "version", _validate_non_empty_str(self.version, "version")
        )

        # Validate status
        if isinstance(self.status, str):
            object.__setattr__(self, "status", DomainValidationStatus(self.status))
        elif not isinstance(self.status, DomainValidationStatus):
            raise DomainContractValidationError(
                f"status must be DomainValidationStatus, got {type(self.status).__name__}",
                field="status",
            )

        # Validate all boolean flags
        for flag_name in (
            "manifest_valid",
            "compatibility_valid",
            "dependencies_valid",
            "contracts_valid",
            "permissions_valid",
            "operations_valid",
            "workflows_valid",
            "security_valid",
            "fragmentation_valid",
            "tests_valid",
        ):
            object.__setattr__(
                self,
                flag_name,
                _validate_strict_bool_flag(getattr(self, flag_name), flag_name),
            )

        # Validate duration_ms
        object.__setattr__(
            self, "duration_ms", _validate_positive_int(self.duration_ms, "duration_ms")
        )

        # Validate validated_at
        object.__setattr__(
            self,
            "validated_at",
            _validate_tz_aware_datetime(self.validated_at, "validated_at"),
        )

        # Deep-freeze metadata
        frozen_meta = _validate_metadata_json_safe(self.metadata, "metadata")
        object.__setattr__(self, "metadata", frozen_meta)

        # Invariants
        if self.status == DomainValidationStatus.PASSED:
            for f in self.findings:
                if getattr(f, "blocking", False):
                    raise DomainContractValidationError(
                        "status is PASSED but blocking finding exists",
                        field="status",
                        details={"finding_code": getattr(f, "code", "unknown")},
                    )
            for f in self.warnings:
                if getattr(f, "blocking", False):
                    raise DomainContractValidationError(
                        "status is PASSED but warning with blocking=True exists",
                        field="status",
                        details={"finding_code": getattr(f, "code", "unknown")},
                    )

    @property
    def has_blocking_findings(self) -> bool:
        """Check if any findings are blocking."""
        return any(
            getattr(f, "blocking", False)
            for f in tuple(self.findings) + tuple(self.warnings)
        )

    @property
    def is_install_allowed(self) -> bool:
        """Check if installation is allowed based on validation result."""
        if self.status in (DomainValidationStatus.FAILED, DomainValidationStatus.ERROR):
            return False
        if not self.manifest_valid:
            return False
        if not self.contracts_valid:
            return False
        if not self.dependencies_valid:
            return False
        if not self.permissions_valid:
            return False
        if not self.security_valid:
            return False
        if not self.compatibility_valid:
            return False
        return self.fragmentation_valid

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dictionary."""

        findings_list = []
        for f in self.findings:
            if hasattr(f, "serialize"):
                findings_list.append(f.serialize())
            elif hasattr(f, "to_dict"):
                findings_list.append(f.to_dict())
            else:
                findings_list.append(str(f))

        warnings_list = []
        for w in self.warnings:
            if hasattr(w, "serialize"):
                warnings_list.append(w.serialize())
            elif hasattr(w, "to_dict"):
                warnings_list.append(w.to_dict())
            else:
                warnings_list.append(str(w))

        step_results_list = []
        for sr in self.step_results:
            if hasattr(sr, "serialize"):
                step_results_list.append(sr.serialize())
            elif hasattr(sr, "to_dict"):
                step_results_list.append(sr.to_dict())
            else:
                step_results_list.append(str(sr))

        return {
            "domain_id": self.domain_id,
            "version": self.version,
            "status": self.status.value,
            "manifest_valid": self.manifest_valid,
            "compatibility_valid": self.compatibility_valid,
            "dependencies_valid": self.dependencies_valid,
            "contracts_valid": self.contracts_valid,
            "permissions_valid": self.permissions_valid,
            "operations_valid": self.operations_valid,
            "workflows_valid": self.workflows_valid,
            "security_valid": self.security_valid,
            "fragmentation_valid": self.fragmentation_valid,
            "tests_valid": self.tests_valid,
            "findings": findings_list,
            "warnings": warnings_list,
            "step_results": step_results_list,
            "duration_ms": self.duration_ms,
            "validated_at": self.validated_at.isoformat(),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainValidationResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainValidationResult.from_dict requires a mapping", field="data"
            )
        from cmm.domains.contracts import _reject_unknown_fields as _reject
        from cmm.validation.findings import ValidationFinding
        from cmm.validation.steps import ValidationStepResult

        _reject(data, _RESULT_KNOWN, "DomainValidationResult")
        required = {"domain_id", "version", "status"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainValidationResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )

        # Parse status
        status_raw = data["status"]
        try:
            status = DomainValidationStatus(status_raw)
        except ValueError as exc:
            raise DomainSerializationError(
                f"Invalid DomainValidationStatus: {status_raw!r}", field="status"
            ) from exc

        # Parse step_results
        step_results_raw = data.get("step_results", ())
        step_results = tuple(
            ValidationStepResult(
                name=sr.get("name", "unknown"),
                status=sr.get("status", "ERROR"),
                exit_code=sr.get("exit_code", -1),
                duration_ms=sr.get("duration_ms", 0),
                stdout=sr.get("stdout", ""),
                stderr=sr.get("stderr", ""),
                findings=tuple(
                    ValidationFinding(
                        code=f.get("code", "UNKNOWN"),
                        message=f.get("message", ""),
                        severity=f.get("severity", "WARNING"),
                        source=f.get("source", "unknown"),
                        file_path=f.get("file_path"),
                        line=f.get("line"),
                        column=f.get("column"),
                        blocking=f.get("blocking", False),
                        suggested_fix=f.get("suggested_fix"),
                        documentation_url=f.get("documentation_url"),
                        metadata=f.get("metadata", {}),
                    )
                    for f in sr.get("findings", ())
                ),
                artifacts=tuple(sr.get("artifacts", ())),
                metadata=sr.get("metadata", {}),
            )
            for sr in step_results_raw
        )

        # Parse findings
        findings_raw = data.get("findings", ())
        findings = tuple(
            ValidationFinding(
                code=f.get("code", "UNKNOWN"),
                message=f.get("message", ""),
                severity=f.get("severity", "WARNING"),
                source=f.get("source", "unknown"),
                file_path=f.get("file_path"),
                line=f.get("line"),
                column=f.get("column"),
                blocking=f.get("blocking", False),
                suggested_fix=f.get("suggested_fix"),
                documentation_url=f.get("documentation_url"),
                metadata=f.get("metadata", {}),
            )
            for f in findings_raw
        )

        # Parse warnings
        warnings_raw = data.get("warnings", ())
        warnings = tuple(
            ValidationFinding(
                code=w.get("code", "UNKNOWN"),
                message=w.get("message", ""),
                severity=w.get("severity", "WARNING"),
                source=w.get("source", "unknown"),
                file_path=w.get("file_path"),
                line=w.get("line"),
                column=w.get("column"),
                blocking=w.get("blocking", False),
                suggested_fix=w.get("suggested_fix"),
                documentation_url=w.get("documentation_url"),
                metadata=w.get("metadata", {}),
            )
            for w in warnings_raw
        )

        # Parse validated_at
        validated_at_raw = data.get("validated_at")
        if isinstance(validated_at_raw, str):
            validated_at = datetime.fromisoformat(validated_at_raw)
            if validated_at.tzinfo is None:
                validated_at = validated_at.replace(tzinfo=timezone.utc)
        else:
            validated_at = datetime.now(timezone.utc)

        return cls(
            domain_id=str(data["domain_id"]),
            version=str(data["version"]),
            status=status,
            manifest_valid=_validate_strict_bool_flag(
                data.get("manifest_valid", False), "manifest_valid"
            ),
            compatibility_valid=_validate_strict_bool_flag(
                data.get("compatibility_valid", False), "compatibility_valid"
            ),
            dependencies_valid=_validate_strict_bool_flag(
                data.get("dependencies_valid", False), "dependencies_valid"
            ),
            contracts_valid=_validate_strict_bool_flag(
                data.get("contracts_valid", False), "contracts_valid"
            ),
            permissions_valid=_validate_strict_bool_flag(
                data.get("permissions_valid", False), "permissions_valid"
            ),
            operations_valid=_validate_strict_bool_flag(
                data.get("operations_valid", False), "operations_valid"
            ),
            workflows_valid=_validate_strict_bool_flag(
                data.get("workflows_valid", False), "workflows_valid"
            ),
            security_valid=_validate_strict_bool_flag(
                data.get("security_valid", False), "security_valid"
            ),
            fragmentation_valid=_validate_strict_bool_flag(
                data.get("fragmentation_valid", False), "fragmentation_valid"
            ),
            tests_valid=_validate_strict_bool_flag(
                data.get("tests_valid", False), "tests_valid"
            ),
            findings=findings,
            warnings=warnings,
            step_results=step_results,
            duration_ms=_validate_positive_int(
                data.get("duration_ms", 0), "duration_ms"
            ),
            validated_at=validated_at,
            metadata=_deep_freeze(data.get("metadata")),
        )


# ── DomainValidationExecutionContext ───────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainValidationExecutionContext:
    """Private context linking domain request to validation infrastructure.

    Gives validators explicit access to the DomainValidationRequest
    without hiding runtime objects behind magic metadata keys.

    Includes shared scan session for security + fragmentation validators.
    """

    request: DomainValidationRequest
    validation_context: Any  # ValidationContext
    scan_session: Any = None  # DomainValidationScanSession | None


__all__ = [
    "DomainValidationExecutionContext",
    "DomainValidationRequest",
    "DomainValidationResult",
    "JSONValue",
]
