"""Semantic Engine Validation Adapter for CMM OS (Subphase 7.13).

Provides seamless validation integration for semantic operations and change sets
without modifying Git repositories or altering historical execution paths.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..enums import ValidationSeverity, ValidationStatus
from ..findings import ValidationFinding
from ..interfaces.application import ValidationApplicationService
from ..interfaces.contracts import StartValidationRequest
from ..results import ValidationResult
from .contracts import (
    ValidationAction,
    ValidationDecision,
    ValidationIntegrationResult,
    ValidationPhase,
    ValidationTrigger,
)


def _get_validation_result(
    app_service: ValidationApplicationService, validation_id: str
) -> ValidationResult:
    record = app_service._repo.load_execution(validation_id)
    if record is not None:
        st = (
            ValidationStatus(record.status)
            if record.status in ValidationStatus._value2member_map_
            else ValidationStatus.ERROR
        )
        findings_objs: list[ValidationFinding] = []
        for f in record.findings or ():
            if isinstance(f, dict):
                sev = f.get("severity", "error")
                sev_enum = (
                    ValidationSeverity(sev)
                    if sev in ValidationSeverity._value2member_map_
                    else ValidationSeverity.ERROR
                )
                findings_objs.append(
                    ValidationFinding(
                        code=str(f.get("code", "ERR_VALIDATION")),
                        message=str(f.get("message", "Validation finding")),
                        severity=sev_enum,
                        source=str(f.get("source", "system")),
                    )
                )
        blocking = tuple(
            f
            for f in findings_objs
            if f.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
        )
        warnings = tuple(
            f for f in findings_objs if f.severity == ValidationSeverity.WARNING
        )

        return ValidationResult(
            id=record.id,
            status=st,
            policy=record.policy or "default",
            blocking_findings=blocking,
            warnings=warnings,
            changed_files=tuple(Path(p) for p in (record.changed_files or ())),
            affected_tests=tuple(record.affected_tests or ()),
            duration_ms=0,
            started_at=record.started_at,
            completed_at=record.completed_at,
            can_commit=bool(record.gate_result and record.gate_result.get("allowed")),
            metadata=dict(record.metadata or {}),
        )

    res_resp = app_service.get_result(validation_id)
    st = (
        ValidationStatus(res_resp.status)
        if res_resp.status in ValidationStatus._value2member_map_
        else ValidationStatus.ERROR
    )
    return ValidationResult(
        id=res_resp.validation_id,
        status=st,
        policy=res_resp.policy,
        duration_ms=res_resp.duration_ms,
        started_at=res_resp.started_at,
        completed_at=res_resp.completed_at,
        can_commit=res_resp.can_commit,
        metadata=dict(res_resp.metadata or {}),
    )


class SemanticValidationAdapter:
    """Adapter connecting Semantic Engine operations and change sets to Continuous Validation."""

    def __init__(
        self,
        application_service: ValidationApplicationService | None = None,
        validation_enabled: bool = True,
    ) -> None:
        self._application_service = application_service
        self._validation_enabled = validation_enabled

    @property
    def validation_enabled(self) -> bool:
        return self._validation_enabled

    def validate_semantic_operation(
        self,
        project_root: Path | str,
        operation: Any = None,
        changed_files: Sequence[Path | str] = (),
        policy_name: str | None = None,
        workflow_id: str | None = None,
        actor: str = "semantic_engine",
        enable_gate: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> ValidationIntegrationResult:
        """Validate a semantic operation or change set.

        If validation is disabled or application_service is None, returns a pass-through
        continue decision preserving legacy compatibility.
        """
        root = Path(project_root).resolve(strict=False)

        # Path traversal guard
        resolved_files: list[Path] = []
        for file_path in changed_files:
            p = Path(file_path).resolve(strict=False)
            try:
                p.relative_to(root)
            except ValueError as exc:
                raise ValueError(
                    f"Changed file '{file_path}' is outside project root '{root}'"
                ) from exc
            resolved_files.append(p)

        if not self._validation_enabled or self._application_service is None:
            # Legacy opt-in behavior: return pass-through decision without validating
            decision = ValidationDecision(
                validation_id="legacy-opt-in-skipped",
                status=ValidationStatus.PASSED,
                allowed_to_continue=True,
                recommended_action=ValidationAction.CONTINUE,
                reasons=("Validation is disabled or opt-in service is absent",),
                metadata=dict(metadata or {}),
            )
            return ValidationIntegrationResult(
                decision=decision,
                metadata=dict(metadata or {}),
            )

        # Determine effective changed files if operation has affected_files attribute
        if not resolved_files and hasattr(operation, "affected_files"):
            for file_path in getattr(operation, "affected_files", ()):
                p = Path(file_path).resolve(strict=False)
                try:
                    p.relative_to(root)
                    resolved_files.append(p)
                except ValueError:
                    pass

        effective_policy = policy_name
        request = StartValidationRequest(
            project_root=root,
            policy_name=effective_policy,
            files=tuple(resolved_files),
            actor=actor,
        )

        val_response = self._application_service.start_validation(request)
        val_result = _get_validation_result(
            self._application_service, val_response.validation_id
        )

        gate_res = None
        if enable_gate and val_result is not None:
            try:
                gate_resp = self._application_service.evaluate_gate(val_result.id)
                gate_res = getattr(gate_resp, "result", None)
            except Exception:  # noqa: BLE001, S110
                pass

        trigger = ValidationTrigger(
            phase=ValidationPhase.AFTER_EXECUTION,
            source="semantic_engine",
            actor=actor,
            workflow_id=workflow_id,
            metadata=dict(metadata or {}),
        )

        decision = ValidationDecision.from_validation_result(
            result=val_result,
            gate_result=gate_res,
            phase=ValidationPhase.AFTER_EXECUTION,
            trigger=trigger,
        )

        return ValidationIntegrationResult(
            decision=decision,
            validation_result=val_result,
            gate_result=gate_res,
            metadata={
                "operation": str(
                    getattr(
                        operation,
                        "__class__",
                        getattr(operation, "name", str(operation)),
                    )
                ),
                "changed_files": [str(f) for f in resolved_files],
                "effective_policy": effective_policy,
                **(metadata or {}),
            },
        )
