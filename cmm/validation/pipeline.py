from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .commit_gate.models import CommitGateResult
    from .observability.service import ValidationObservabilityService
    from .policy import ValidationPolicy

from .artifacts import ValidationArtifact
from .context import ValidationContext
from .enums import ValidationSeverity, ValidationStatus
from .errors import ValidationContractError
from .exceptions import (
    ValidationDependencyError,
)
from .executor import ValidationExecutor
from .findings import ValidationFinding
from .policy import canonical_validation_policy_name, resolve_validation_policy
from .registry import ValidationRegistry
from .results import ValidationResult
from .steps import ValidationStep, ValidationStepResult


@dataclass(slots=True)
class CancellationToken:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True

    def is_cancelled(self) -> bool:
        return self.cancelled


def _subset_with_dependencies(
    all_steps: tuple[ValidationStep, ...], requested: tuple[str, ...]
) -> tuple[ValidationStep, ...]:
    by_name: dict[str, ValidationStep] = {s.name: s for s in all_steps}
    missing = [n for n in requested if n not in by_name]
    if missing:
        raise ValidationDependencyError(
            code="unknown_requested_step",
            message=f"Unknown requested steps: {', '.join(missing)}",
        )
    result: dict[str, ValidationStep] = {}

    def visit(name: str) -> None:
        if name in result:
            return
        step = by_name[name]
        for dep in step.dependencies:
            if dep not in by_name:
                raise ValidationDependencyError(
                    code="missing_dependency",
                    message=f"Missing dependency '{dep}' for step '{name}'",
                )
            visit(dep)
        result[name] = step

    for n in requested:
        visit(n)
    # preserve original order
    ordered = [s for s in all_steps if s.name in result]
    return tuple(ordered)


def _topological_sort(steps: tuple[ValidationStep, ...]) -> tuple[ValidationStep, ...]:
    by_name: dict[str, ValidationStep] = {}
    for s in steps:
        if s.name in by_name:
            raise ValidationDependencyError(
                code="duplicate_step", message=f"Duplicate step '{s.name}'"
            )
        by_name[s.name] = s
    # verify dependencies exist
    for s in steps:
        for dep in s.dependencies:
            if dep not in by_name:
                raise ValidationDependencyError(
                    code="missing_dependency",
                    message=f"Missing dependency '{dep}' for step '{s.name}'",
                )
    # Kahn's algorithm with deterministic order based on input sequence
    in_degree: dict[str, int] = {s.name: 0 for s in steps}
    for s in steps:
        for dep in s.dependencies:
            in_degree[s.name] += 1
    ready: list[str] = [name for name, deg in in_degree.items() if deg == 0]
    # stable order by original order
    ready.sort(key=lambda n: next(i for i, s in enumerate(steps) if s.name == n))

    order: list[str] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for s in steps:
            if n in s.dependencies:
                in_degree[s.name] -= 1
                if in_degree[s.name] == 0:
                    ready.append(s.name)
                    ready.sort(
                        key=lambda name: next(
                            i for i, s in enumerate(steps) if s.name == name
                        )
                    )

    if len(order) != len(steps):
        raise ValidationDependencyError(
            code="dependency_cycle", message="Dependency cycle detected"
        )

    return tuple(by_name[name] for name in order)


@dataclass(slots=True)
class ValidationPipeline:
    executor: ValidationExecutor
    registry: ValidationRegistry
    observability: ValidationObservabilityService | None = field(
        default=None,
    )

    def run(
        self,
        context: ValidationContext,
        steps: Iterable[ValidationStep],
        *,
        cancel: CancellationToken | None = None,
        validation_id: str | None = None,
    ) -> ValidationResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        cancel = cancel or CancellationToken()

        # --- Observability: record execution start ---
        obs = self.observability
        if obs is not None:
            try:
                validation_id = obs.start_execution(
                    context=context,
                    validation_id=validation_id,
                )
            except Exception:  # noqa: BLE001
                obs = None  # disable observability on failure; don't break pipeline
        try:
            try:
                resolved_policy = resolve_validation_policy(context)
            except ValidationContractError as exc:
                policy_name = canonical_validation_policy_name(
                    context.requested_policy or context.change_type or "full"
                )
                return ValidationResult(
                    id=f"validation-result-{int(t0)}",
                    status=ValidationStatus.ERROR,
                    policy=policy_name,
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
                    metadata={"error": {"code": "invalid_policy", "message": str(exc)}},
                )

            policy_name = (
                resolved_policy.name
                if resolved_policy is not None
                else canonical_validation_policy_name(
                    context.requested_policy or context.change_type or "full"
                )
            )
            steps_tuple = tuple(steps)
            # filter steps if requested
            if context.requested_steps is not None:
                try:
                    steps_tuple = _subset_with_dependencies(
                        steps_tuple, context.requested_steps
                    )
                except ValidationDependencyError as exc:
                    return ValidationResult(
                        id=f"validation-result-{int(t0)}",
                        status=ValidationStatus.ERROR,
                        policy=policy_name,
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
                        metadata={
                            "error": {"code": exc.code, "message": exc.message},
                            "policy": None
                            if resolved_policy is None
                            else resolved_policy.serialize(),
                        },
                    )
            # order and validate dependencies
            try:
                ordered = _topological_sort(steps_tuple)
            except ValidationDependencyError as exc:
                return ValidationResult(
                    id=f"validation-result-{int(t0)}",
                    status=ValidationStatus.ERROR,
                    policy=policy_name,
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
                    metadata={
                        "error": {"code": exc.code, "message": exc.message},
                        "policy": None
                        if resolved_policy is None
                        else resolved_policy.serialize(),
                    },
                )

            results: list[ValidationStepResult] = []
            stopped_early = False
            cancelled = False
            name_to_step: dict[str, ValidationStep] = {s.name: s for s in ordered}
            affected_tests: list[str] = []

            for step in ordered:
                if cancel.is_cancelled():
                    cancelled = True
                    # mark this and remaining as CANCELLED
                    remaining = [
                        s for s in ordered if s.name not in {r.name for r in results}
                    ]
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

                metadata_affected = step.metadata.get("affected_tests")
                if isinstance(metadata_affected, (list, tuple)):
                    for item in metadata_affected:
                        path = str(item)
                        if path not in affected_tests:
                            affected_tests.append(path)

                # Stop semantics:
                # - Always stop on internal ERROR
                # - Stop on blockers regardless of step flags
                # - Stop on FAILED/TIMED_OUT/CANCELLED only if step is required and stop_on_failure
                stop_due_to_internal_error = res.status == ValidationStatus.ERROR
                stop_due_to_step_policy = (
                    step.required and step.stop_on_failure and not res.is_successful
                )
                stop_due_to_blockers = any(f.blocking for f in res.findings)

                if (
                    stop_due_to_internal_error
                    or stop_due_to_step_policy
                    or stop_due_to_blockers
                ):
                    stopped_early = True
                    # mark remaining as SKIPPED
                    remaining = [
                        s for s in ordered if s.name not in {r.name for r in results}
                    ]
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

            artifacts: list[ValidationArtifact] = []
            blocking: list[ValidationFinding] = []
            warnings: list[ValidationFinding] = []
            for r in results:
                for f in r.findings:
                    if f.blocking:
                        blocking.append(f)
                    elif f.severity in (ValidationSeverity.WARNING,):
                        warnings.append(f)
                artifacts.extend(r.artifacts)

            # aggregate status with distinction between required vs optional failures
            failed_like = {
                ValidationStatus.FAILED,
                ValidationStatus.TIMED_OUT,
                ValidationStatus.CANCELLED,
            }
            has_internal_error = any(
                r.status == ValidationStatus.ERROR for r in results
            )
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

            # Use the stable validation_id if observability assigned one;
            # otherwise fall back to the old monotonic-timestamp ID.
            result_id = validation_id or f"validation-result-{int(t0)}"

            final_result = ValidationResult(
                id=result_id,
                status=overall,
                policy=policy_name,
                steps=tuple(results),
                artifacts=tuple(artifacts),
                blocking_findings=tuple(blocking),
                warnings=tuple(warnings),
                changed_files=tuple(context.changed_files),
                affected_tests=tuple(affected_tests),
                duration_ms=int((time.monotonic() - t0) * 1000),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                can_commit=bool(
                    context.allow_commit
                    and resolved_policy is not None
                    and resolved_policy.allow_commit
                    and overall == ValidationStatus.PASSED
                    and not blocking
                ),
                metadata={
                    "pipeline": {
                        "stopped_early": stopped_early,
                        "cancelled": cancelled,
                        "non_blocking_failures": non_blocking_failures,
                    },
                    "policy": None
                    if resolved_policy is None
                    else resolved_policy.serialize(),
                },
            )

            # --- Observability: record completion ---
            if obs is not None and validation_id is not None:
                try:
                    obs.complete_execution(
                        validation_id=validation_id,
                        result=final_result,
                    )
                except Exception:  # noqa: BLE001, S110
                    pass  # observability failure must not alter result

            return final_result
        except (
            Exception
        ) as exc:  # pragma: no cover - unexpected safety net  # noqa: BLE001
            return ValidationResult(
                id=f"validation-result-{int(t0)}",
                status=ValidationStatus.ERROR,
                policy=canonical_validation_policy_name(
                    context.requested_policy or context.change_type or "full"
                ),
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
                metadata={
                    "error": {"code": "unexpected_exception", "message": str(exc)}
                },
            )

    def evaluate_commit_gate(
        self,
        result: ValidationResult,
        policy: ValidationPolicy | None = None,
        *,
        required_artifacts: Sequence[str] | None = None,
    ) -> CommitGateResult:
        from .commit_gate.evaluator import CommitGateEvaluator

        return CommitGateEvaluator.evaluate(
            result, policy, required_artifacts=required_artifacts
        )


__all__ = ["CancellationToken", "ValidationPipeline"]
