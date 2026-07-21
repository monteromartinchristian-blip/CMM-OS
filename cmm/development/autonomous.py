"""Bounded autonomous development cycle built on the supervised service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Protocol

from cmm.development.analyzer import ProjectContext
from cmm.development.models import DevelopmentPlan, DevelopmentResult
from cmm.development.providers import PlanningProvider
from cmm.development.service import DevelopmentService


class CycleState(str, Enum):
    ANALYSIS = "analysis"
    PLAN = "plan"
    IMPLEMENT = "implementation"
    VALIDATE = "validation"
    CLASSIFY = "failure_classification"
    CORRECT = "correction"
    COMPLETE = "complete"
    ABANDONED = "abandoned"


class FailureKind(str, Enum):
    NONE = "none"
    PLANNING = "planning"
    EXECUTION = "execution"
    VALIDATION = "validation"
    HUMAN_ABORT = "human_abort"
    LIMIT = "attempt_limit"


class CorrectionProvider(Protocol):
    def generate_correction(
        self,
        goal: str,
        context: ProjectContext,
        previous_plan: DevelopmentPlan | None,
        previous_result: DevelopmentResult,
        failure: "FailureClassification",
    ) -> DevelopmentPlan | Mapping[str, Any] | None:
        """Return a corrected plan, or None to use the normal planning hook."""


@dataclass(frozen=True, slots=True)
class FailureClassification:
    kind: FailureKind
    message: str
    recoverable: bool

    def serialize(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "message": self.message,
            "recoverable": self.recoverable,
        }


@dataclass(frozen=True, slots=True)
class AutonomousAttempt:
    number: int
    states: tuple[CycleState, ...]
    result: DevelopmentResult
    failure: FailureClassification
    correction_requested: bool = False

    @property
    def success(self) -> bool:
        return self.result.success and (self.result.approved or self.result.dry_run)

    def serialize(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "states": [state.value for state in self.states],
            "result": self.result.serialize(),
            "failure": self.failure.serialize(),
            "correction_requested": self.correction_requested,
        }


@dataclass(frozen=True, slots=True)
class AutonomousDevelopmentResult:
    """Structured result for the complete bounded development cycle."""

    success: bool
    goal: str
    attempts: tuple[AutonomousAttempt, ...]
    final_result: DevelopmentResult | None
    stop_reason: str
    max_attempts: int
    duration_seconds: float = 0.0

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def rollback_applied(self) -> bool:
        return any(attempt.result.rollback_applied for attempt in self.attempts)

    def serialize(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "goal": self.goal,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "attempts": [attempt.serialize() for attempt in self.attempts],
            "final_result": self.final_result.serialize() if self.final_result else None,
            "stop_reason": self.stop_reason,
            "rollback_applied": self.rollback_applied,
            "duration_seconds": self.duration_seconds,
        }


class FailureClassifier:
    """Classify one Fase 2 result without inspecting unstructured text."""

    def classify(self, result: DevelopmentResult) -> FailureClassification:
        if result.success and (result.approved or result.dry_run):
            return FailureClassification(FailureKind.NONE, "Development succeeded.", False)
        if not result.approved and result.plan is not None:
            message = result.warnings[0] if result.warnings else "Human approval was not granted."
            return FailureClassification(FailureKind.HUMAN_ABORT, message, False)
        if result.validations and any(not item.success for item in result.validations):
            return FailureClassification(
                FailureKind.VALIDATION,
                "; ".join(item.message for item in result.validations if not item.success),
                True,
            )
        if result.operations_executed and any(not item.success for item in result.operations_executed):
            message = next(item.message for item in result.operations_executed if not item.success)
            return FailureClassification(FailureKind.EXECUTION, message, True)
        if result.plan is None:
            message = "; ".join(result.errors) or "No executable plan was produced."
            return FailureClassification(FailureKind.PLANNING, message, True)
        message = "; ".join(result.errors) or "Development attempt failed."
        return FailureClassification(FailureKind.EXECUTION, message, True)


class AutonomousDevelopmentService:
    """Run bounded plan/execute/validate iterations with no autonomous retry policy."""

    def __init__(
        self,
        provider: PlanningProvider,
        development: DevelopmentService | None = None,
        classifier: FailureClassifier | None = None,
    ) -> None:
        self.provider = provider
        self.development = development or DevelopmentService(provider)
        self.classifier = classifier or FailureClassifier()

    def develop(
        self,
        goal: str,
        project: Path,
        *,
        yes: bool = False,
        dry_run: bool = False,
        max_files: int = 40,
        validations: tuple[str, ...] | None = None,
        max_attempts: int = 3,
        isolate: bool = False,
        branch_name: str | None = None,
        keep_changes: bool = True,
        restore: bool = False,
    ) -> AutonomousDevelopmentResult:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")

        started = perf_counter()
        attempts: list[AutonomousAttempt] = []
        plan_override: DevelopmentPlan | Mapping[str, Any] | None = None
        final_result: DevelopmentResult | None = None

        for number in range(1, max_attempts + 1):
            options = {
                "yes": yes,
                "dry_run": dry_run,
                "max_files": max_files,
                "validations": validations,
                "plan_override": plan_override,
            }
            if getattr(self.development, "supports_project_actions", False):
                options.update(isolate=isolate, branch_name=branch_name, keep_changes=keep_changes, restore=restore)
            result = self.development.develop(goal, project, **options)
            final_result = result
            failure = self.classifier.classify(result)
            states = [CycleState.ANALYSIS, CycleState.PLAN]
            if result.plan is not None and result.approved:
                states.extend((CycleState.IMPLEMENT, CycleState.VALIDATE))
            if failure.kind == FailureKind.NONE:
                states.append(CycleState.COMPLETE)
                attempts.append(AutonomousAttempt(number, tuple(states), result, failure))
                return self._result(started, goal, attempts, result, "success", max_attempts)

            states.append(CycleState.CLASSIFY)
            if not failure.recoverable or dry_run:
                states.append(CycleState.ABANDONED)
                attempts.append(AutonomousAttempt(number, tuple(states), result, failure))
                return self._result(started, goal, attempts, result, failure.message, max_attempts)

            if number == max_attempts:
                limit_failure = FailureClassification(
                    FailureKind.LIMIT,
                    f"Maximum attempts reached ({max_attempts}). Last failure: {failure.message}",
                    False,
                )
                states.append(CycleState.ABANDONED)
                attempts.append(AutonomousAttempt(number, tuple(states), result, limit_failure))
                return self._result(started, goal, attempts, result, limit_failure.message, max_attempts)

            states.append(CycleState.CORRECT)
            try:
                plan_override = self._generate_correction(goal, project, max_files, result, failure)
            except Exception as error:
                correction_failure = FailureClassification(
                    FailureKind.PLANNING,
                    f"Correction generation failed: {error}",
                    False,
                )
                failed_result = DevelopmentResult(
                    success=False,
                    goal=goal,
                    plan=result.plan,
                    operations_executed=result.operations_executed,
                    modified_files=result.modified_files,
                    diff=result.diff,
                    validations=result.validations,
                    warnings=result.warnings,
                    errors=(correction_failure.message,),
                    approved=result.approved,
                    rollback_applied=result.rollback_applied,
                )
                attempts.append(AutonomousAttempt(number, tuple(states[:-1] + [CycleState.ABANDONED]), failed_result, correction_failure))
                return self._result(started, goal, attempts, failed_result, correction_failure.message, max_attempts)

            attempts.append(AutonomousAttempt(number, tuple(states), result, failure, correction_requested=True))

        raise AssertionError("Autonomous cycle exited without a result.")

    def _generate_correction(
        self,
        goal: str,
        project: Path,
        max_files: int,
        result: DevelopmentResult,
        failure: FailureClassification,
    ) -> DevelopmentPlan | Mapping[str, Any] | None:
        context = self.development.analyzer.analyze(
            self.development._validate_project(project),
            goal,
            max_files=max_files,
        )
        correction = getattr(self.provider, "generate_correction", None)
        if callable(correction):
            return correction(goal, context, result.plan, result, failure)
        return None

    def _result(
        self,
        started: float,
        goal: str,
        attempts: list[AutonomousAttempt],
        final_result: DevelopmentResult,
        stop_reason: str,
        max_attempts: int,
    ) -> AutonomousDevelopmentResult:
        success = bool(final_result.success and (final_result.approved or final_result.dry_run))
        return AutonomousDevelopmentResult(
            success=success,
            goal=goal,
            attempts=tuple(attempts),
            final_result=final_result,
            stop_reason=stop_reason,
            max_attempts=max_attempts,
            duration_seconds=perf_counter() - started,
        )
