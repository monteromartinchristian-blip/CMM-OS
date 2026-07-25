"""Validation Integration Contracts for CMM OS (Subphase 7.13).

Provides typed contracts connecting continuous validation to Semantic Engine,
Execution Engine, Planner, Kernel Events, and Technical Memory.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from ..commit_gate.models import CommitGateResult
from ..enums import ValidationStatus
from ..findings import ValidationFinding
from ..results import ValidationResult


class ValidationPhase(str, Enum):
    """Lifecycle phase at which validation is triggered."""

    BEFORE_EXECUTION = "before_execution"
    AFTER_EXECUTION = "after_execution"
    BEFORE_COMMIT = "before_commit"
    MANUAL = "manual"


class ValidationAction(str, Enum):
    """Structured action recommended by the validation decision engine."""

    CONTINUE = "continue"
    RETRY = "retry"
    REPLAN = "replan"
    ROLLBACK = "rollback"
    STOP = "stop"
    ASK_USER = "ask_user"
    ESCALATE = "escalate"
    PAUSE = "pause"
    ABORT = "abort"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class ValidationTrigger:
    """Metadata describing the origin of a validation request."""

    phase: ValidationPhase
    source: str = "system"
    actor: str = "system"
    workflow_id: str | None = None
    plan_node_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.phase, str) and not isinstance(self.phase, ValidationPhase):
            object.__setattr__(self, "phase", ValidationPhase(self.phase))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class ValidationDecision:
    """Structured decision derived from ValidationResult and optional CommitGateResult."""

    validation_id: str
    status: ValidationStatus
    allowed_to_continue: bool
    recommended_action: ValidationAction
    reasons: tuple[str, ...] = ()
    blocking_findings: tuple[ValidationFinding, ...] = ()
    warnings: tuple[ValidationFinding, ...] = ()
    gate_result: CommitGateResult | None = None
    requires_rollback: bool = False
    requires_user_input: bool = False
    retryable: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.validation_id:
            raise ValueError("ValidationDecision.validation_id must not be empty")
        if isinstance(self.status, str) and not isinstance(
            self.status, ValidationStatus
        ):
            object.__setattr__(self, "status", ValidationStatus(self.status))
        if isinstance(self.recommended_action, str) and not isinstance(
            self.recommended_action, ValidationAction
        ):
            object.__setattr__(
                self, "recommended_action", ValidationAction(self.recommended_action)
            )

        object.__setattr__(self, "reasons", tuple(self.reasons or ()))
        object.__setattr__(
            self, "blocking_findings", tuple(self.blocking_findings or ())
        )
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_validation_result(
        cls,
        result: ValidationResult,
        gate_result: CommitGateResult | None = None,
        phase: ValidationPhase = ValidationPhase.AFTER_EXECUTION,
        trigger: ValidationTrigger | None = None,
        override_action: ValidationAction | None = None,
    ) -> ValidationDecision:
        """Derive a structured decision deterministically from validation and gate results."""
        reasons: list[str] = []
        blocking = tuple(result.blocking_findings)
        warnings = tuple(result.warnings)

        gate_approved = gate_result.approved if gate_result is not None else True
        has_blocking = len(blocking) > 0 or result.status == ValidationStatus.FAILED

        if has_blocking:
            reasons.append(f"Validation failed with status {result.status.value}")
            for finding in blocking:
                reasons.append(f"[{finding.code}] {finding.message}")
        if gate_result is not None and not gate_approved:
            reasons.append(
                f"Commit gate rejected execution: {gate_result.summary.primary_reason or 'Gate check failed'}"
            )

        passed = (result.status == ValidationStatus.PASSED) and gate_approved
        allowed_to_continue = passed

        if override_action is not None:
            recommended_action = override_action
        elif passed:
            recommended_action = ValidationAction.CONTINUE
        elif phase == ValidationPhase.AFTER_EXECUTION and has_blocking:
            recommended_action = ValidationAction.ROLLBACK
        elif phase == ValidationPhase.BEFORE_EXECUTION and has_blocking:
            recommended_action = ValidationAction.STOP
        else:
            recommended_action = ValidationAction.STOP

        requires_rollback = (
            phase == ValidationPhase.AFTER_EXECUTION
            and not passed
            and recommended_action == ValidationAction.ROLLBACK
        )
        requires_user_input = recommended_action in (
            ValidationAction.ASK_USER,
            ValidationAction.ESCALATE,
        )
        retryable = any(
            "transient" in r.lower() or "timeout" in r.lower() for r in reasons
        )

        meta = dict(result.metadata or {})
        if trigger is not None:
            meta["trigger"] = {
                "phase": trigger.phase.value,
                "source": trigger.source,
                "actor": trigger.actor,
                "workflow_id": trigger.workflow_id,
                "plan_node_id": trigger.plan_node_id,
            }

        return cls(
            validation_id=result.id,
            status=result.status,
            allowed_to_continue=allowed_to_continue,
            recommended_action=recommended_action,
            reasons=tuple(reasons),
            blocking_findings=blocking,
            warnings=warnings,
            gate_result=gate_result,
            requires_rollback=requires_rollback,
            requires_user_input=requires_user_input,
            retryable=retryable,
            metadata=meta,
        )


@dataclass(frozen=True, slots=True)
class ValidationIntegrationRequest:
    """Request payload for running integrated validation."""

    project_root: Path
    phase: ValidationPhase = ValidationPhase.AFTER_EXECUTION
    policy_name: str | None = None
    changed_files: tuple[Path, ...] = ()
    trigger_source: str = "integration"
    actor: str = "system"
    workflow_id: str | None = None
    plan_node_id: str | None = None
    enable_gate: bool = False
    enable_events: bool = True
    enable_memory: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "project_root", Path(self.project_root).resolve(strict=False)
        )
        if isinstance(self.phase, str) and not isinstance(self.phase, ValidationPhase):
            object.__setattr__(self, "phase", ValidationPhase(self.phase))
        object.__setattr__(
            self,
            "changed_files",
            tuple(Path(f).resolve(strict=False) for f in (self.changed_files or ())),
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class ValidationIntegrationResult:
    """Result payload of an integrated validation execution."""

    decision: ValidationDecision
    validation_result: ValidationResult | None = None
    gate_result: CommitGateResult | None = None
    execution_result: Any | None = None
    rollback_requested: bool = False
    rollback_executed: bool = False
    rollback_success: bool | None = None
    rollback_error: str | None = None
    events_emitted: tuple[str, ...] = ()
    memory_recorded: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "events_emitted", tuple(self.events_emitted or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class ValidationPlanNode:
    """A validation node inside a planner execution graph or DAG."""

    id: str
    phase: ValidationPhase = ValidationPhase.AFTER_EXECUTION
    policy_name: str | None = None
    steps: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    on_pass: ValidationAction = ValidationAction.CONTINUE
    on_failure: ValidationAction = ValidationAction.STOP
    required: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ValidationPlanNode.id must not be empty")
        if isinstance(self.phase, str) and not isinstance(self.phase, ValidationPhase):
            object.__setattr__(self, "phase", ValidationPhase(self.phase))
        if isinstance(self.on_pass, str) and not isinstance(
            self.on_pass, ValidationAction
        ):
            object.__setattr__(self, "on_pass", ValidationAction(self.on_pass))
        if isinstance(self.on_failure, str) and not isinstance(
            self.on_failure, ValidationAction
        ):
            object.__setattr__(self, "on_failure", ValidationAction(self.on_failure))

        object.__setattr__(self, "steps", tuple(self.steps or ()))
        object.__setattr__(self, "depends_on", tuple(self.depends_on or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        """Serialize node to a clean dictionary representation."""
        return {
            "id": self.id,
            "phase": self.phase.value,
            "policy_name": self.policy_name,
            "steps": list(self.steps),
            "depends_on": list(self.depends_on),
            "on_pass": self.on_pass.value,
            "on_failure": self.on_failure.value,
            "required": self.required,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def deserialize(cls, payload: Mapping[str, Any]) -> ValidationPlanNode:
        """Deserialize node from payload dictionary."""
        return cls(
            id=str(payload["id"]),
            phase=ValidationPhase(
                payload.get("phase", ValidationPhase.AFTER_EXECUTION.value)
            ),
            policy_name=payload.get("policy_name"),
            steps=tuple(payload.get("steps", ())),
            depends_on=tuple(payload.get("depends_on", ())),
            on_pass=ValidationAction(
                payload.get("on_pass", ValidationAction.CONTINUE.value)
            ),
            on_failure=ValidationAction(
                payload.get("on_failure", ValidationAction.STOP.value)
            ),
            required=bool(payload.get("required", True)),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ValidationEventPayload:
    """Structured event payload emitted to Kernel Event System."""

    event_type: str
    schema_version: str = "1.0.0"
    validation_id: str = ""
    timestamp: str = ""
    actor: str = "system"
    project_root: str = "."
    policy: str = "default"
    execution_mode: str = "integrated"
    workflow_id: str | None = None
    plan_node_id: str | None = None
    step_name: str | None = None
    status: str = "unknown"
    duration_ms: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type:
            raise ValueError("ValidationEventPayload.event_type must not be empty")
        if not self.timestamp:
            object.__setattr__(
                self, "timestamp", datetime.now(timezone.utc).isoformat()
            )
        meta = dict(self.metadata or {})
        sanitized_meta = {
            k: v
            for k, v in meta.items()
            if not any(
                secret in k.lower()
                for secret in (
                    "token",
                    "password",
                    "secret",
                    "auth",
                    "credential",
                    "api_key",
                )
            )
        }
        object.__setattr__(self, "metadata", sanitized_meta)

    def serialize(self) -> dict[str, Any]:
        """Serialize payload to dict, ensuring secrecy sanitization."""
        meta = dict(self.metadata)
        # Strip potential secret keys
        sanitized_meta = {
            k: v
            for k, v in meta.items()
            if not any(
                secret in k.lower()
                for secret in (
                    "token",
                    "password",
                    "secret",
                    "auth",
                    "credential",
                    "api_key",
                )
            )
        }
        return {
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "validation_id": self.validation_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "project_root": self.project_root,
            "policy": self.policy,
            "execution_mode": self.execution_mode,
            "workflow_id": self.workflow_id,
            "plan_node_id": self.plan_node_id,
            "step_name": self.step_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "metadata": sanitized_meta,
        }


@dataclass(frozen=True, slots=True)
class ValidationMemoryRecord:
    """Structured memory record for technical memory persistence."""

    validation_id: str
    timestamp: str
    policy: str
    change_type: str
    status: str
    decision: str
    recurring_finding_codes: tuple[str, ...] = ()
    affected_files: tuple[str, ...] = ()
    affected_modules: tuple[str, ...] = ()
    gate_approved: bool | None = None
    rollback_requested: bool = False
    rollback_successful: bool | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    artifact_reference: str | None = None
    commit_hash: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.validation_id:
            raise ValueError("ValidationMemoryRecord.validation_id must not be empty")
        object.__setattr__(
            self, "recurring_finding_codes", tuple(self.recurring_finding_codes or ())
        )
        object.__setattr__(self, "affected_files", tuple(self.affected_files or ()))
        object.__setattr__(self, "affected_modules", tuple(self.affected_modules or ()))
        object.__setattr__(self, "metrics", dict(self.metrics or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        """Serialize record to dictionary format."""
        return {
            "validation_id": self.validation_id,
            "timestamp": self.timestamp,
            "policy": self.policy,
            "change_type": self.change_type,
            "status": self.status,
            "decision": self.decision,
            "recurring_finding_codes": list(self.recurring_finding_codes),
            "affected_files": list(self.affected_files),
            "affected_modules": list(self.affected_modules),
            "gate_approved": self.gate_approved,
            "rollback_requested": self.rollback_requested,
            "rollback_successful": self.rollback_successful,
            "metrics": dict(self.metrics),
            "artifact_reference": self.artifact_reference,
            "commit_hash": self.commit_hash,
            "metadata": dict(self.metadata),
        }
