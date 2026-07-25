"""Validation Integration Service for CMM OS (Subphase 7.13).

Public coordinator uniting Semantic, Execution, Planner, Events, and Memory validation capabilities.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..commit_gate.models import CommitGateResult
from ..interfaces.application import ValidationApplicationService
from ..results import ValidationResult
from .contracts import (
    ValidationDecision,
    ValidationIntegrationResult,
    ValidationPhase,
    ValidationTrigger,
)
from .events import KernelEventPublisher
from .execution import ExecutionValidationCoordinator
from .memory import ValidationMemoryAdapter
from .semantic import SemanticValidationAdapter


class ValidationIntegrationService:
    """High-level facade providing integrated continuous validation across CMM OS."""

    def __init__(
        self,
        application_service: ValidationApplicationService | None = None,
        event_publisher: KernelEventPublisher | None = None,
        memory_adapter: ValidationMemoryAdapter | None = None,
    ) -> None:
        self._application_service = application_service
        self._event_publisher = event_publisher
        self._memory_adapter = memory_adapter

        self._semantic_adapter = SemanticValidationAdapter(
            application_service=self._application_service,
            validation_enabled=True,
        )
        self._execution_coordinator = ExecutionValidationCoordinator(
            application_service=self._application_service,
            event_publisher=self._event_publisher,
            memory_adapter=self._memory_adapter,
        )

    @property
    def application_service(self) -> ValidationApplicationService | None:
        return self._application_service

    @property
    def event_publisher(self) -> KernelEventPublisher | None:
        return self._event_publisher

    @property
    def memory_adapter(self) -> ValidationMemoryAdapter | None:
        return self._memory_adapter

    def validate_before_execution(
        self,
        project_root: Path | str,
        changed_files: Sequence[Path | str] = (),
        policy_name: str | None = None,
        workflow_id: str | None = None,
        actor: str = "execution_engine",
        metadata: Mapping[str, Any] | None = None,
    ) -> ValidationIntegrationResult:
        """Validate pre-execution requirements before applying changes."""
        return self._execution_coordinator.validate_pre_execution(
            project_root=project_root,
            changed_files=changed_files,
            policy_name=policy_name,
            workflow_id=workflow_id,
            actor=actor,
            metadata=metadata,
        )

    def validate_after_execution(
        self,
        project_root: Path | str,
        changed_files: Sequence[Path | str] = (),
        policy_name: str | None = "default",
        rollback_handler: Callable[[], bool] | None = None,
        workflow_id: str | None = None,
        actor: str = "execution_engine",
        enable_gate: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> ValidationIntegrationResult:
        """Validate post-execution results after applying changes."""
        return self._execution_coordinator.validate_post_execution(
            project_root=project_root,
            changed_files=changed_files,
            policy_name=policy_name,
            rollback_handler=rollback_handler,
            workflow_id=workflow_id,
            actor=actor,
            enable_gate=enable_gate,
            metadata=metadata,
        )

    def validate_semantic_change(
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
        """Validate changes produced by a Semantic Engine operation."""
        res = self._semantic_adapter.validate_semantic_operation(
            project_root=project_root,
            operation=operation,
            changed_files=changed_files,
            policy_name=policy_name,
            workflow_id=workflow_id,
            actor=actor,
            enable_gate=enable_gate,
            metadata=metadata,
        )
        if res.validation_result and self._event_publisher:
            self.publish_events(res.validation_result)
        if res.validation_result and self._memory_adapter:
            self.remember_result(res.validation_result, decision=res.decision)
        return res

    def evaluate_execution_result(
        self,
        execution_result: Any,
        project_root: Path | str,
        policy_name: str = "default",
    ) -> ValidationIntegrationResult:
        """Evaluate an execution result object produced by Runtime or Execution Engine."""
        changed = getattr(execution_result, "changed_files", ())
        if not changed and hasattr(execution_result, "executions"):
            changed = [
                getattr(ex, "path", None)
                for ex in getattr(execution_result, "executions", ())
                if getattr(ex, "path", None)
            ]

        return self.validate_after_execution(
            project_root=project_root,
            changed_files=changed,
            policy_name=policy_name,
            metadata={"execution_success": getattr(execution_result, "success", True)},
        )

    def evaluate_validation_result(
        self,
        result: ValidationResult,
        gate_result: CommitGateResult | None = None,
        phase: ValidationPhase = ValidationPhase.AFTER_EXECUTION,
    ) -> ValidationDecision:
        """Derive a structured decision directly from a ValidationResult."""
        return self.create_decision(result, gate_result=gate_result, phase=phase)

    def create_decision(
        self,
        result: ValidationResult,
        gate_result: CommitGateResult | None = None,
        phase: ValidationPhase = ValidationPhase.AFTER_EXECUTION,
        trigger: ValidationTrigger | None = None,
    ) -> ValidationDecision:
        """Create a ValidationDecision from validation and gate outputs."""
        return ValidationDecision.from_validation_result(
            result=result,
            gate_result=gate_result,
            phase=phase,
            trigger=trigger,
        )

    def publish_events(
        self,
        result: ValidationResult,
        trigger: ValidationTrigger | None = None,
    ) -> Sequence[str]:
        """Publish events for a ValidationResult if event publisher is configured."""
        if self._event_publisher is None:
            return ()
        return self._event_publisher.publish_validation_events(result, trigger=trigger)

    def remember_result(
        self,
        result: ValidationResult,
        decision: ValidationDecision | None = None,
        rollback_requested: bool = False,
        rollback_success: bool | None = None,
    ) -> Any:
        """Persist structured summary to technical memory if adapter is configured."""
        if self._memory_adapter is None:
            return None
        return self._memory_adapter.remember_validation(
            result=result,
            decision=decision,
            rollback_requested=rollback_requested,
            rollback_success=rollback_success,
        )
