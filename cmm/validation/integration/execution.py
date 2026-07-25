"""Execution Engine Validation Coordinator for CMM OS (Subphase 7.13).

Coordinates pre- and post-execution validation, controls workflow continuation,
and manages rollback triggering without altering underlying transaction engines.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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


class ExecutionValidationCoordinator:
    """Coordinator linking execution engines with pre/post validation and rollback."""

    def __init__(
        self,
        application_service: ValidationApplicationService | None = None,
        event_publisher: Any | None = None,
        memory_adapter: Any | None = None,
    ) -> None:
        self._application_service = application_service
        self._event_publisher = event_publisher
        self._memory_adapter = memory_adapter

    def validate_pre_execution(
        self,
        project_root: Path | str,
        changed_files: Sequence[Path | str] = (),
        policy_name: str | None = None,
        workflow_id: str | None = None,
        actor: str = "execution_engine",
        metadata: Mapping[str, Any] | None = None,
    ) -> ValidationIntegrationResult:
        """Execute pre-execution validation check.

        If pre-validation fails blockingly, execution must NOT proceed.
        Rollback is not requested since no changes have been applied.
        """
        root = Path(project_root).resolve(strict=False)
        resolved_files = [Path(f).resolve(strict=False) for f in changed_files]

        for f in resolved_files:
            try:
                f.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Path '{f}' outside project root '{root}'") from exc

        if self._application_service is None:
            decision = ValidationDecision(
                validation_id="pre-exec-skipped",
                status=ValidationStatus.PASSED,
                allowed_to_continue=True,
                recommended_action=ValidationAction.CONTINUE,
                reasons=(
                    "Application service absent; pre-execution validation skipped",
                ),
            )
            return ValidationIntegrationResult(decision=decision)

        req = StartValidationRequest(
            project_root=root,
            policy_name=policy_name,
            files=tuple(resolved_files) if resolved_files else None,
            actor=actor,
        )

        resp = self._application_service.start_validation(req)
        val_result = _get_validation_result(
            self._application_service, resp.validation_id
        )

        trigger = ValidationTrigger(
            phase=ValidationPhase.BEFORE_EXECUTION,
            source="execution_engine",
            actor=actor,
            workflow_id=workflow_id,
            metadata=dict(metadata or {}),
        )

        decision = ValidationDecision.from_validation_result(
            result=val_result,
            phase=ValidationPhase.BEFORE_EXECUTION,
            trigger=trigger,
            override_action=ValidationAction.STOP
            if val_result.status != ValidationStatus.PASSED
            else ValidationAction.CONTINUE,
        )

        if self._event_publisher is not None:
            try:
                self._event_publisher.publish_validation_events(
                    val_result, trigger=trigger
                )
            except Exception:  # noqa: BLE001, S110
                pass

        return ValidationIntegrationResult(
            decision=decision,
            validation_result=val_result,
            metadata=dict(metadata or {}),
        )

    def validate_post_execution(
        self,
        project_root: Path | str,
        changed_files: Sequence[Path | str] = (),
        policy_name: str | None = None,
        rollback_handler: Callable[[], bool] | None = None,
        workflow_id: str | None = None,
        actor: str = "execution_engine",
        enable_gate: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> ValidationIntegrationResult:
        """Execute post-execution validation check.

        If validation fails blockingly and rollback_handler is present, invokes rollback
        and records rollback state while preserving the original validation failure.
        """
        root = Path(project_root).resolve(strict=False)
        resolved_files = [Path(f).resolve(strict=False) for f in changed_files]

        for f in resolved_files:
            try:
                f.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Path '{f}' outside project root '{root}'") from exc

        if self._application_service is None:
            decision = ValidationDecision(
                validation_id="post-exec-skipped",
                status=ValidationStatus.PASSED,
                allowed_to_continue=True,
                recommended_action=ValidationAction.CONTINUE,
                reasons=(
                    "Application service absent; post-execution validation skipped",
                ),
            )
            return ValidationIntegrationResult(decision=decision)

        req = StartValidationRequest(
            project_root=root,
            policy_name=policy_name,
            files=tuple(resolved_files),
            actor=actor,
        )

        resp = self._application_service.start_validation(req)
        val_result = _get_validation_result(
            self._application_service, resp.validation_id
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
            source="execution_engine",
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

        rollback_requested = False
        rollback_executed = False
        rollback_success: bool | None = None
        rollback_error: str | None = None

        if not decision.allowed_to_continue and decision.requires_rollback:
            rollback_requested = True
            if rollback_handler is not None:
                rollback_executed = True
                try:
                    res = rollback_handler()
                    rollback_success = bool(res)
                    if not rollback_success:
                        rollback_error = "Rollback handler returned False"
                except Exception as exc:  # noqa: BLE001
                    rollback_success = False
                    rollback_error = str(exc)
            else:
                rollback_success = False
                rollback_error = "No rollback handler supplied to coordinator"

        if self._event_publisher is not None:
            try:
                self._event_publisher.publish_validation_events(
                    val_result, trigger=trigger
                )
            except Exception:  # noqa: BLE001, S110
                pass

        if self._memory_adapter is not None and val_result is not None:
            try:
                self._memory_adapter.remember_validation(
                    val_result,
                    decision=decision,
                    rollback_requested=rollback_requested,
                    rollback_success=rollback_success,
                )
            except Exception:  # noqa: BLE001, S110
                pass

        return ValidationIntegrationResult(
            decision=decision,
            validation_result=val_result,
            gate_result=gate_res,
            rollback_requested=rollback_requested,
            rollback_executed=rollback_executed,
            rollback_success=rollback_success,
            rollback_error=rollback_error,
            metadata=dict(metadata or {}),
        )
