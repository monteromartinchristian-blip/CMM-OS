from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional, Tuple, List, Dict, Set

from .context import ValidationContext
from .enums import ValidationStatus, ValidationSeverity
from .steps import ValidationStep, ValidationStepResult
from .results import ValidationResult
from .artifacts import ValidationArtifact
from .findings import ValidationFinding
from .exceptions import (
    ValidationDependencyError,
    ValidationPipelineError,
)
from .registry import ValidationRegistry
from .executor import ValidationExecutor


@dataclass(slots=True)
class CancellationToken:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True

    def is_cancelled(self) -> bool:
        return self.cancelled


def _subset_with_dependencies(all_steps: Tuple[ValidationStep, ...], requested: Tuple[str, ...]) -> Tuple[ValidationStep, ...]:
    by_name: Dict[str, ValidationStep] = {s.name: s for s in all_steps}
    missing = [n for n in requested if n not in by_name]
    if missing:
        raise ValidationDependencyError(code="unknown_requested_step", message=f"Unknown requested steps: {', '.join(missing)}")
    result: Dict[str, ValidationStep] = {}

    def visit(name: str) -> None:
        if name in result:
            return
        step = by_name[name]
        for dep in step.dependencies:
            if dep not in by_name:
                raise ValidationDependencyError(code="missing_dependency", message=f"Missing dependency '{dep}' for step '{name}'")
            visit(dep)
        result[name] = step

    for n in requested:
        visit(n)
    # preserve original order
    ordered = [s for s in all_steps if s.name in result]
    return tuple(ordered)


def _topological_sort(steps: Tuple[ValidationStep, ...]) -> Tuple[ValidationStep, ...]:
    by_name: Dict[str, ValidationStep] = {}
    for s in steps:
        if s.name in by_name:
            raise ValidationDependencyError(code="duplicate_step", message=f"Duplicate step '{s.name}'")
        by_name[s.name] = s
    # verify dependencies exist
    for s in steps:
        for dep in s.dependencies:
            if dep not in by_name:
                raise ValidationDependencyError(code="missing_dependency", message=f"Missing dependency '{dep}' for step '{s.name}'")
    # Kahn's algorithm with deterministic order based on input sequence
    in_degree: Dict[str, int] = {s.name: 0 for s in steps}
    for s in steps:
        for dep in s.dependencies:
            in_degree[s.name] += 1
    ready: List[str] = [name for name, deg in in_degree.items() if deg == 0]
    # stable order by original order
    ready.sort(key=lambda n: next(i for i, s in enumerate(steps) if s.name == n))

    order: List[str] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for s in steps:
            if n in s.dependencies:
                in_degree[s.name] -= 1
                if in_degree[s.name] == 0:
                    ready.append(s.name)
                    ready.sort(key=lambda name: next(i for i, s in enumerate(steps) if s.name == name))

    if len(order) != len(steps):
        raise ValidationDependencyError(code="dependency_cycle", message="Dependency cycle detected")

    return tuple(by_name[name] for name in order)


@dataclass(slots=True)
class ValidationPipeline:
    executor: ValidationExecutor
    registry: ValidationRegistry

    def run(self, context: ValidationContext, steps: Iterable[ValidationStep], *, cancel: Optional[CancellationToken] = None) -> ValidationResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        cancel = cancel or CancellationToken()
        try:
            steps_tuple = tuple(steps)
            # filter steps if requested
            if context.requested_steps is not None:
                try:
                    steps_tuple = _subset_with_dependencies(steps_tuple, context.requested_steps)
                except ValidationDependencyError as exc:
                    return ValidationResult(
                        id=f"validation-result-{int(t0)}",
                        status=ValidationStatus.ERROR,
                        policy=context.requested_policy,
                        steps=(),
                        artifacts=(),
                        blocking_findings=(),
                        warnings=(),
                        changed_files=tuple(context.changed_files),
                        affected_tests=(),
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        started_at=started_at,
                        completed_at=datetime.now(timezone.utc),
                        can_commit=False,
                        metadata={"error": {"code": exc.code, "message": exc.message}},
                    )
            # order and validate dependencies
            try:
                ordered = _topological_sort(steps_tuple)
            except ValidationDependencyError as exc:
                return ValidationResult(
                    id=f"validation-result-{int(t0)}",
                    status=ValidationStatus.ERROR,
                    policy=context.requested_policy,
                    steps=(),
                    artifacts=(),
                    blocking_findings=(),
                    warnings=(),
                    changed_files=tuple(context.changed_files),
                    affected_tests=(),
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    can_commit=False,
                    metadata={"error": {"code": exc.code, "message": exc.message}},
                )

            results: List[ValidationStepResult] = []
            stopped_early = False
            cancelled = False
            name_to_step: Dict[str, ValidationStep] = {s.name: s for s in ordered}

            for step in ordered:
                if cancel.is_cancelled():
                    cancelled = True
                    # mark this and remaining as CANCELLED
                    remaining = [s for s in ordered if s.name not in {r.name for r in results}]
                    for rem in remaining:
                        results.append(
                            ValidationStepResult(
                                name=rem.name,
                                status=ValidationStatus.CANCELLED,
                                stdout="",
                                stderr="",
                                duration_ms=0,
                                metadata={"reason": "cancelled"},
                            )
                        )
                    break

                # ensure dependencies succeeded where required
                dep_failed = False
                for dep in step.dependencies:
                    dep_res = next((r for r in results if r.name == dep), None)
                    if dep_res is None:
                        dep_failed = True
                        break
                    if not dep_res.is_successful:
                        dep_failed = True
                        break
                if dep_failed:
                    results.append(
                        ValidationStepResult(
                            name=step.name,
                            status=ValidationStatus.SKIPPED,
                            stdout="",
                            stderr="",
                            duration_ms=0,
                            metadata={"reason": "dependency_failed"},
                        )
                    )
                    continue

                res = self.executor.execute(context, step, self.registry)
                results.append(res)

                # Stop semantics:
                # - Always stop on internal ERROR
                # - Stop on blockers regardless of step flags
                # - Stop on FAILED/TIMED_OUT/CANCELLED only if step is required and stop_on_failure
                stop_due_to_internal_error = res.status == ValidationStatus.ERROR
                stop_due_to_step_policy = step.required and step.stop_on_failure and not res.is_successful
                stop_due_to_blockers = any(f.blocking for f in res.findings)

                if stop_due_to_internal_error or stop_due_to_step_policy or stop_due_to_blockers:
                    stopped_early = True
                    # mark remaining as SKIPPED
                    remaining = [s for s in ordered if s.name not in {r.name for r in results}]
                    for rem in remaining:
                        results.append(
                            ValidationStepResult(
                                name=rem.name,
                                status=ValidationStatus.SKIPPED,
                                stdout="",
                                stderr="",
                                duration_ms=0,
                                metadata={"reason": "stopped_early"},
                            )
                        )
                    break

            artifacts: List[ValidationArtifact] = []
            blocking: List[ValidationFinding] = []
            warnings: List[ValidationFinding] = []
            for r in results:
                for f in r.findings:
                    if f.blocking:
                        blocking.append(f)
                    elif f.severity in (ValidationSeverity.WARNING,):
                        warnings.append(f)
                for a in r.artifacts:
                    artifacts.append(a)

            # aggregate status with distinction between required vs optional failures
            failed_like = {ValidationStatus.FAILED, ValidationStatus.TIMED_OUT, ValidationStatus.CANCELLED}
            has_internal_error = any(r.status == ValidationStatus.ERROR for r in results)
            has_required_failure = False
            has_optional_failure = False
            for r in results:
                if r.status in failed_like:
                    step_def = name_to_step.get(r.name)
                    if step_def is not None and step_def.required:
                        has_required_failure = True
                    else:
                        has_optional_failure = True

            if has_internal_error:
                overall = ValidationStatus.ERROR
            elif blocking or has_required_failure:
                overall = ValidationStatus.FAILED
            elif warnings or has_optional_failure:
                overall = ValidationStatus.WARNING
            else:
                overall = ValidationStatus.PASSED

            non_blocking_failures = []
            for r in results:
                if r.status in failed_like:
                    step_def = name_to_step.get(r.name)
                    if step_def is None or not step_def.required:
                        non_blocking_failures.append(r.name)

            return ValidationResult(
                id=f"validation-result-{int(t0)}",
                status=overall,
                policy=context.requested_policy,
                steps=tuple(results),
                artifacts=tuple(artifacts),
                blocking_findings=tuple(blocking),
                warnings=tuple(warnings),
                changed_files=tuple(context.changed_files),
                affected_tests=(),
                duration_ms=int((time.monotonic() - t0) * 1000),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                can_commit=False,
                metadata={
                    "pipeline": {
                        "stopped_early": stopped_early,
                        "cancelled": cancelled,
                        "non_blocking_failures": non_blocking_failures,
                    }
                },
            )
        except Exception as exc:  # pragma: no cover - unexpected safety net
            return ValidationResult(
                id=f"validation-result-{int(t0)}",
                status=ValidationStatus.ERROR,
                policy=context.requested_policy,
                steps=(),
                artifacts=(),
                blocking_findings=(),
                warnings=(),
                changed_files=tuple(context.changed_files),
                affected_tests=(),
                duration_ms=int((time.monotonic() - t0) * 1000),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                can_commit=False,
                metadata={"error": {"code": "unexpected_exception", "message": str(exc)}},
            )


__all__ = ["ValidationPipeline", "CancellationToken"]
