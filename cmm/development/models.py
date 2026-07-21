"""Structured models for supervised development plans and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from kernel.protocol.parser import PlanParser
from kernel.semantic import SemanticOperation, SemanticResult
from kernel.semantic_adapters import operation_from_legacy_action


class PlanValidationError(ValueError):
    """Raised when a planning provider returns an unsafe or invalid plan."""


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    """One ordered semantic operation plus its human-facing rationale."""

    domain: str
    operation_type: str
    parameters: Mapping[str, Any]
    reason: str = ""

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PlannedOperation":
        domain = payload.get("domain") or payload.get("tool")
        operation_type = payload.get("type") or payload.get("action")
        parameters = payload.get("parameters", {})
        if not isinstance(domain, str) or not domain.strip():
            raise PlanValidationError("Every operation requires a non-empty domain.")
        if not isinstance(operation_type, str) or not operation_type.strip():
            raise PlanValidationError("Every operation requires a non-empty type.")
        if not isinstance(parameters, Mapping):
            raise PlanValidationError("Operation parameters must be a mapping.")
        reason = payload.get("reason", "")
        if not isinstance(reason, str):
            raise PlanValidationError("Operation reason must be a string.")
        return cls(domain.strip(), operation_type.strip(), dict(parameters), reason.strip())

    def serialize(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "type": self.operation_type,
            "parameters": dict(self.parameters),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class DevelopmentPlan:
    """Validated, provider-independent development plan."""

    goal: str
    affected_files: tuple[str, ...]
    operations: tuple[PlannedOperation, ...]
    rationale: str
    validations: tuple[str, ...] = ("python_ast", "python_compile")
    risks: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any], expected_goal: str | None = None) -> "DevelopmentPlan":
        if not isinstance(payload, Mapping):
            raise PlanValidationError("The provider plan must be a mapping.")
        goal = payload.get("goal", expected_goal)
        affected_files = payload.get("affected_files")
        operations = payload.get("operations")
        rationale = payload.get("rationale", "")
        validations = payload.get("validations", ("python_ast", "python_compile"))
        risks = payload.get("risks", ())

        if not isinstance(goal, str) or not goal.strip():
            raise PlanValidationError("The plan requires a non-empty goal.")
        if expected_goal is not None and goal.strip() != expected_goal.strip():
            raise PlanValidationError("The plan goal does not match the requested goal.")
        if not isinstance(affected_files, Sequence) or isinstance(affected_files, (str, bytes)):
            raise PlanValidationError("affected_files must be a list of project-relative paths.")
        if not isinstance(operations, Sequence) or isinstance(operations, (str, bytes)) or not operations:
            raise PlanValidationError("The plan requires at least one structured operation.")
        if not isinstance(rationale, str) or not rationale.strip():
            raise PlanValidationError("The plan requires a brief rationale.")
        if not isinstance(validations, Sequence) or isinstance(validations, (str, bytes)):
            raise PlanValidationError("validations must be a list.")
        if not isinstance(risks, Sequence) or isinstance(risks, (str, bytes)):
            raise PlanValidationError("risks must be a list.")

        files = tuple(str(item) for item in affected_files)
        parsed_operations = tuple(PlannedOperation.from_mapping(item) for item in operations)
        plan = cls(
            goal=goal.strip(),
            affected_files=files,
            operations=parsed_operations,
            rationale=rationale.strip(),
            validations=tuple(str(item) for item in validations),
            risks=tuple(str(item) for item in risks),
        )
        plan.validate()
        return plan

    def validate(self) -> None:
        if not self.affected_files:
            raise PlanValidationError("The plan requires at least one affected file.")
        if any(not path.strip() for path in self.affected_files):
            raise PlanValidationError("Affected file paths must be non-empty.")
        operation_files = {
            str(operation.parameters["path"])
            for operation in self.operations
            if "path" in operation.parameters
        }
        missing = operation_files.difference(self.affected_files)
        if missing:
            raise PlanValidationError(
                "Operation paths must be listed in affected_files: " + ", ".join(sorted(missing))
            )

    def to_semantic_operations(self, parser: PlanParser | None = None) -> tuple[SemanticOperation, ...]:
        """Convert through the Phase 1 parser and compatibility adapters."""

        protocol_payload = {
            "version": 1,
            "actions": [
                {
                    "tool": operation.domain,
                    "action": operation.operation_type,
                    **dict(operation.parameters),
                }
                for operation in self.operations
            ],
        }
        try:
            legacy_plan = (parser or PlanParser()).parse(protocol_payload)
            semantic = tuple(operation_from_legacy_action(action) for action in legacy_plan.actions)
        except (KeyError, TypeError, ValueError) as error:
            raise PlanValidationError(f"Invalid executable plan: {error}") from error
        return tuple(
            SemanticOperation(
                operation_type=item.operation_type,
                domain=item.domain,
                parameters=item.parameters,
                metadata={**item.metadata, "goal": self.goal, "plan_order": index},
                operation_id=item.operation_id,
            )
            for index, item in enumerate(semantic, start=1)
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "affected_files": list(self.affected_files),
            "operations": [operation.serialize() for operation in self.operations],
            "rationale": self.rationale,
            "validations": list(self.validations),
            "risks": list(self.risks),
        }


@dataclass(frozen=True, slots=True)
class ValidationRecord:
    name: str
    success: bool
    message: str

    def serialize(self) -> dict[str, Any]:
        return {"name": self.name, "success": self.success, "message": self.message}


@dataclass(frozen=True, slots=True)
class DevelopmentResult:
    """Complete structured outcome of one supervised development attempt."""

    success: bool
    goal: str
    plan: DevelopmentPlan | None
    operations_executed: tuple[SemanticResult, ...] = ()
    modified_files: tuple[str, ...] = ()
    diff: str = ""
    validations: tuple[ValidationRecord, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    approved: bool = False
    dry_run: bool = False
    rollback_applied: bool = False
    duration_seconds: float = 0.0
    planned_actions: tuple[dict[str, Any], ...] = ()
    executed_actions: tuple[dict[str, Any], ...] = ()
    created_files: tuple[str, ...] = ()
    deleted_files: tuple[str, ...] = ()
    git_state: Mapping[str, Any] = field(default_factory=dict)
    memory_refreshed: bool = False
    review_ready: bool = False

    def serialize(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "goal": self.goal,
            "plan": self.plan.serialize() if self.plan else None,
            "operations_executed": [
                {
                    "success": result.success,
                    "message": result.message,
                    "errors": list(result.errors),
                    "changes": list(result.changes),
                    "operation": result.operation.serialize() if result.operation else None,
                }
                for result in self.operations_executed
            ],
            "modified_files": list(self.modified_files),
            "diff": self.diff,
            "validations": [record.serialize() for record in self.validations],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "approved": self.approved,
            "dry_run": self.dry_run,
            "rollback_applied": self.rollback_applied,
            "planned_actions": [dict(action) for action in self.planned_actions],
            "executed_actions": [dict(action) for action in self.executed_actions],
            "created_files": list(self.created_files),
            "deleted_files": list(self.deleted_files),
            "git_state": dict(self.git_state),
            "memory_refreshed": self.memory_refreshed,
            "review_ready": self.review_ready,
            "duration_seconds": self.duration_seconds,
        }
