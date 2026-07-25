"""Phase 9.14 – Validation Integration Contracts.

Defines immutable, serializable contracts for agent runtime validation integration,
including requirements, requests, findings, decisions, commit gate evaluations, and results.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import (
    AgentValidationDecision,
    AgentValidationStage,
    AgentValidationStatus,
    ValidationFailureClass,
    ValidationRequirementKind,
)
from cmm.agent_runtime.errors import (
    InvalidAgentContractError,
    ValidationRequirementError,
    ValidationResultInvalidError,
)

# Alias for explicit decision type
ValidationDecision = AgentValidationDecision


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_timezone(iso_string: str) -> None:
    try:
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            raise InvalidAgentContractError(
                f"Timestamp '{iso_string}' must be timezone-aware."
            )
    except (ValueError, TypeError) as exc:
        raise InvalidAgentContractError(
            f"Invalid timestamp '{iso_string}': {exc}"
        ) from exc


def _freeze_mapping(data: Mapping[str, Any]) -> MappingProxyType:
    normalized = {}
    for k, v in data.items():
        if isinstance(v, dict):
            normalized[k] = _freeze_mapping(v)
        elif isinstance(v, list):
            normalized[k] = tuple(
                _freeze_mapping(x) if isinstance(x, dict) else x for x in v
            )
        else:
            normalized[k] = v
    return MappingProxyType(normalized)


@dataclass(frozen=True)
class ValidationRequirement:
    """Represents a specific validation check required before, during, or after an operation."""

    requirement_id: str
    validation_kind: ValidationRequirementKind
    stage: AgentValidationStage
    required: bool = True
    blocking: bool = True
    policy_id: str | None = None
    validator_ids: tuple[str, ...] = ()
    resource_scope: tuple[str, ...] = ()
    operation_name: str = ""
    operation_version: str = "1"
    timeout_seconds: float = 30.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.requirement_id
            or not isinstance(self.requirement_id, str)
            or not self.requirement_id.strip()
        ):
            raise ValidationRequirementError("requirement_id cannot be empty.")
        if not isinstance(self.validation_kind, ValidationRequirementKind):
            if isinstance(self.validation_kind, str):
                object.__setattr__(
                    self,
                    "validation_kind",
                    ValidationRequirementKind(self.validation_kind),
                )
            else:
                raise ValidationRequirementError("Invalid validation_kind.")
        if not isinstance(self.stage, AgentValidationStage):
            if isinstance(self.stage, str):
                object.__setattr__(self, "stage", AgentValidationStage(self.stage))
            else:
                raise ValidationRequirementError("Invalid stage.")
        if self.timeout_seconds <= 0:
            raise ValidationRequirementError("timeout_seconds must be positive.")

        if not isinstance(self.validator_ids, tuple):
            object.__setattr__(self, "validator_ids", tuple(self.validator_ids))
        if not isinstance(self.resource_scope, tuple):
            object.__setattr__(self, "resource_scope", tuple(self.resource_scope))

        if isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "validation_kind": self.validation_kind.value,
            "stage": self.stage.value,
            "required": self.required,
            "blocking": self.blocking,
            "policy_id": self.policy_id,
            "validator_ids": list(self.validator_ids),
            "resource_scope": list(self.resource_scope),
            "operation_name": self.operation_name,
            "operation_version": self.operation_version,
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationRequirement:
        return cls(
            requirement_id=data["requirement_id"],
            validation_kind=ValidationRequirementKind(data["validation_kind"]),
            stage=AgentValidationStage(data["stage"]),
            required=data.get("required", True),
            blocking=data.get("blocking", True),
            policy_id=data.get("policy_id"),
            validator_ids=tuple(data.get("validator_ids", ())),
            resource_scope=tuple(data.get("resource_scope", ())),
            operation_name=data.get("operation_name", ""),
            operation_version=data.get("operation_version", "1"),
            timeout_seconds=data.get("timeout_seconds", 30.0),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class ValidationFinding:
    """Represents an individual finding, issue, or error detected by a validator."""

    finding_id: str
    rule_id: str
    severity: str
    message: str
    failure_class: ValidationFailureClass
    location: str = ""
    remediation_hint: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not self.finding_id
            or not isinstance(self.finding_id, str)
            or not self.finding_id.strip()
        ):
            raise InvalidAgentContractError("finding_id cannot be empty.")
        if not isinstance(self.failure_class, ValidationFailureClass):
            if isinstance(self.failure_class, str):
                object.__setattr__(
                    self, "failure_class", ValidationFailureClass(self.failure_class)
                )
            else:
                raise InvalidAgentContractError("Invalid failure_class.")
        if isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "failure_class": self.failure_class.value,
            "location": self.location,
            "remediation_hint": self.remediation_hint,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationFinding:
        return cls(
            finding_id=data["finding_id"],
            rule_id=data.get("rule_id", "unknown"),
            severity=data.get("severity", "ERROR"),
            message=data.get("message", ""),
            failure_class=ValidationFailureClass(data["failure_class"]),
            location=data.get("location", ""),
            remediation_hint=data.get("remediation_hint", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class ValidationExecutionContext:
    """Contextual metadata surrounding a validation execution request."""

    run_id: str
    iteration_id: str
    operation_name: str
    resource_scope: tuple[str, ...] = ()
    environment: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id or not self.run_id.strip():
            raise InvalidAgentContractError("run_id cannot be empty.")
        if not isinstance(self.resource_scope, tuple):
            object.__setattr__(self, "resource_scope", tuple(self.resource_scope))
        if isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "iteration_id": self.iteration_id,
            "operation_name": self.operation_name,
            "resource_scope": list(self.resource_scope),
            "environment": self.environment,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationExecutionContext:
        return cls(
            run_id=data["run_id"],
            iteration_id=data.get("iteration_id", ""),
            operation_name=data.get("operation_name", ""),
            resource_scope=tuple(data.get("resource_scope", ())),
            environment=data.get("environment", "default"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class CommitGateEvaluation:
    """Result of evaluating the Commit Gate for a set of changes or operation."""

    authorized: bool
    decision: AgentValidationDecision
    commit_authorization: Mapping[str, Any] | None = None
    reason_codes: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evaluated_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        _ensure_timezone(self.evaluated_at)
        if not isinstance(self.decision, AgentValidationDecision):
            if isinstance(self.decision, str):
                object.__setattr__(
                    self, "decision", AgentValidationDecision(self.decision)
                )
            else:
                raise InvalidAgentContractError("Invalid decision.")
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if not isinstance(self.blocking_reasons, tuple):
            object.__setattr__(self, "blocking_reasons", tuple(self.blocking_reasons))
        if not isinstance(self.warnings, tuple):
            object.__setattr__(self, "warnings", tuple(self.warnings))
        if self.commit_authorization is not None and isinstance(
            self.commit_authorization, dict
        ):
            object.__setattr__(
                self, "commit_authorization", _freeze_mapping(self.commit_authorization)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorized": self.authorized,
            "decision": self.decision.value,
            "commit_authorization": dict(self.commit_authorization)
            if self.commit_authorization
            else None,
            "reason_codes": list(self.reason_codes),
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "evaluated_at": self.evaluated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommitGateEvaluation:
        return cls(
            authorized=data["authorized"],
            decision=AgentValidationDecision(data["decision"]),
            commit_authorization=data.get("commit_authorization"),
            reason_codes=tuple(data.get("reason_codes", ())),
            blocking_reasons=tuple(data.get("blocking_reasons", ())),
            warnings=tuple(data.get("warnings", ())),
            evaluated_at=data.get("evaluated_at", _now_iso()),
        )


@dataclass(frozen=True)
class ValidationPolicySelection:
    """Selection of policy requirements derived for a given agent operation execution context."""

    policy_id: str
    requirements: tuple[ValidationRequirement, ...]
    rationale: tuple[str, ...]
    cumulative: bool = True

    def __post_init__(self) -> None:
        if not self.policy_id or not self.policy_id.strip():
            raise InvalidAgentContractError("policy_id cannot be empty.")
        if not isinstance(self.requirements, tuple):
            object.__setattr__(self, "requirements", tuple(self.requirements))
        if not isinstance(self.rationale, tuple):
            object.__setattr__(self, "rationale", tuple(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "requirements": [r.to_dict() for r in self.requirements],
            "rationale": list(self.rationale),
            "cumulative": self.cumulative,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValidationPolicySelection:
        return cls(
            policy_id=data["policy_id"],
            requirements=tuple(
                ValidationRequirement.from_dict(r) for r in data.get("requirements", [])
            ),
            rationale=tuple(data.get("rationale", ())),
            cumulative=data.get("cumulative", True),
        )


@dataclass(frozen=True)
class AgentValidationRequest:
    """Request to validate an agent operation state or environment."""

    id: str
    run_id: str
    iteration_id: str
    operation_request_id: str
    stage: AgentValidationStage
    requirements: tuple[ValidationRequirement, ...] = ()
    idempotency_key: str = ""
    context_data: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str) or not self.id.strip():
            raise InvalidAgentContractError("Request id cannot be empty.")
        if not self.run_id or not self.run_id.strip():
            raise InvalidAgentContractError("run_id cannot be empty.")
        if not self.iteration_id or not self.iteration_id.strip():
            raise InvalidAgentContractError("iteration_id cannot be empty.")
        if not self.operation_request_id or not self.operation_request_id.strip():
            raise InvalidAgentContractError("operation_request_id cannot be empty.")

        _ensure_timezone(self.created_at)

        if not isinstance(self.stage, AgentValidationStage):
            if isinstance(self.stage, str):
                object.__setattr__(self, "stage", AgentValidationStage(self.stage))
            else:
                raise InvalidAgentContractError("Invalid stage.")

        if not isinstance(self.requirements, tuple):
            object.__setattr__(self, "requirements", tuple(self.requirements))

        if isinstance(self.context_data, dict):
            object.__setattr__(self, "context_data", _freeze_mapping(self.context_data))

        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", self.calculate_fingerprint())

    def calculate_fingerprint(self) -> str:
        payload = {
            "id": self.id,
            "run_id": self.run_id,
            "iteration_id": self.iteration_id,
            "operation_request_id": self.operation_request_id,
            "stage": self.stage.value,
            "requirements": [r.to_dict() for r in self.requirements],
            "idempotency_key": self.idempotency_key,
            "context_data": dict(self.context_data),
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "iteration_id": self.iteration_id,
            "operation_request_id": self.operation_request_id,
            "stage": self.stage.value,
            "requirements": [r.to_dict() for r in self.requirements],
            "idempotency_key": self.idempotency_key,
            "context_data": dict(self.context_data),
            "created_at": self.created_at,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentValidationRequest:
        return cls(
            id=data["id"],
            run_id=data["run_id"],
            iteration_id=data["iteration_id"],
            operation_request_id=data["operation_request_id"],
            stage=AgentValidationStage(data["stage"]),
            requirements=tuple(
                ValidationRequirement.from_dict(r) for r in data.get("requirements", [])
            ),
            idempotency_key=data.get("idempotency_key", ""),
            context_data=data.get("context_data", {}),
            created_at=data.get("created_at", _now_iso()),
            fingerprint=data.get("fingerprint", ""),
        )


@dataclass(frozen=True)
class AgentValidationResult:
    """Structured result of executing an AgentValidationRequest."""

    request_id: str
    run_id: str
    iteration_id: str
    operation_request_id: str
    stage: AgentValidationStage
    status: AgentValidationStatus
    decision: AgentValidationDecision
    findings: tuple[ValidationFinding, ...] = ()
    validation_report: Mapping[str, Any] = field(default_factory=dict)
    commit_gate_result: Mapping[str, Any] | None = None
    started_at: str = field(default_factory=_now_iso)
    completed_at: str = field(default_factory=_now_iso)
    duration: float = 0.0
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.request_id or not self.request_id.strip():
            raise ValidationResultInvalidError("request_id cannot be empty.")
        if not self.run_id or not self.run_id.strip():
            raise ValidationResultInvalidError("run_id cannot be empty.")

        try:
            _ensure_timezone(self.started_at)
            _ensure_timezone(self.completed_at)
        except InvalidAgentContractError as exc:
            raise ValidationResultInvalidError(str(exc)) from exc

        if not isinstance(self.stage, AgentValidationStage):
            if isinstance(self.stage, str):
                object.__setattr__(self, "stage", AgentValidationStage(self.stage))
            else:
                raise ValidationResultInvalidError("Invalid stage.")

        if not isinstance(self.status, AgentValidationStatus):
            if isinstance(self.status, str):
                object.__setattr__(self, "status", AgentValidationStatus(self.status))
            else:
                raise ValidationResultInvalidError("Invalid status.")

        if not isinstance(self.decision, AgentValidationDecision):
            if isinstance(self.decision, str):
                object.__setattr__(
                    self, "decision", AgentValidationDecision(self.decision)
                )
            else:
                raise ValidationResultInvalidError("Invalid decision.")

        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))

        if not isinstance(self.blocking_reasons, tuple):
            object.__setattr__(self, "blocking_reasons", tuple(self.blocking_reasons))

        if not isinstance(self.warnings, tuple):
            object.__setattr__(self, "warnings", tuple(self.warnings))

        if isinstance(self.validation_report, dict):
            object.__setattr__(
                self, "validation_report", _freeze_mapping(self.validation_report)
            )

        if self.commit_gate_result is not None and isinstance(
            self.commit_gate_result, dict
        ):
            object.__setattr__(
                self, "commit_gate_result", _freeze_mapping(self.commit_gate_result)
            )

        if isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", self.calculate_fingerprint())

    def calculate_fingerprint(self) -> str:
        payload = {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "iteration_id": self.iteration_id,
            "operation_request_id": self.operation_request_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "decision": self.decision.value,
            "findings": [f.to_dict() for f in self.findings],
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "iteration_id": self.iteration_id,
            "operation_request_id": self.operation_request_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "decision": self.decision.value,
            "findings": [f.to_dict() for f in self.findings],
            "validation_report": dict(self.validation_report),
            "commit_gate_result": dict(self.commit_gate_result)
            if self.commit_gate_result
            else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentValidationResult:
        return cls(
            request_id=data["request_id"],
            run_id=data["run_id"],
            iteration_id=data.get("iteration_id", ""),
            operation_request_id=data.get("operation_request_id", ""),
            stage=AgentValidationStage(data["stage"]),
            status=AgentValidationStatus(data["status"]),
            decision=AgentValidationDecision(data["decision"]),
            findings=tuple(
                ValidationFinding.from_dict(f) for f in data.get("findings", [])
            ),
            validation_report=data.get("validation_report", {}),
            commit_gate_result=data.get("commit_gate_result"),
            started_at=data.get("started_at", _now_iso()),
            completed_at=data.get("completed_at", _now_iso()),
            duration=data.get("duration", 0.0),
            blocking_reasons=tuple(data.get("blocking_reasons", ())),
            warnings=tuple(data.get("warnings", ())),
            metadata=data.get("metadata", {}),
            fingerprint=data.get("fingerprint", ""),
        )


@dataclass(frozen=True)
class AgentValidationEvent:
    """Structured event emitted during validation lifecycle operations."""

    event_id: str
    event_type: str
    run_id: str
    goal_id: str = ""
    iteration_id: str = ""
    operation_request_id: str = ""
    validation_request_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    timestamp: str = field(default_factory=_now_iso)
    decision: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_id.strip():
            raise InvalidAgentContractError("event_id cannot be empty.")
        if not self.event_type or not self.event_type.strip():
            raise InvalidAgentContractError("event_type cannot be empty.")
        if not self.run_id or not self.run_id.strip():
            raise InvalidAgentContractError("run_id cannot be empty.")
        _ensure_timezone(self.timestamp)
        if isinstance(self.metadata, dict):
            object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "goal_id": self.goal_id,
            "iteration_id": self.iteration_id,
            "operation_request_id": self.operation_request_id,
            "validation_request_id": self.validation_request_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "timestamp": self.timestamp,
            "decision": self.decision,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentValidationEvent:
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            run_id=data["run_id"],
            goal_id=data.get("goal_id", ""),
            iteration_id=data.get("iteration_id", ""),
            operation_request_id=data.get("operation_request_id", ""),
            validation_request_id=data.get("validation_request_id", ""),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            timestamp=data.get("timestamp", _now_iso()),
            decision=data.get("decision", ""),
            metadata=data.get("metadata", {}),
        )
