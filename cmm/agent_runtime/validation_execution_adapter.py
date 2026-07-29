"""Phase 9.14 – Agent Validation Adapter and Decision Resolver.

Bridges Agent Runtime operations with the existing Phase 7 Validation Pipeline
and Commit Gate Evaluator. This module never executes shell commands,
subprocesses, or test runners directly: all concrete validation work is
delegated to registered Phase 7 `ValidationStep` implementations and to
`CommitGateEvaluator`, which is the single, non-duplicated source of commit
authorization truth.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cmm.agent_runtime.enums import (
    AgentValidationDecision,
    AgentValidationStage,
    AgentValidationStatus,
    ValidationFailureClass,
    ValidationRequirementKind,
)
from cmm.agent_runtime.errors import (
    ValidationAdapterError,
    ValidationInfrastructureError,
    ValidationRepositoryError,
)
from cmm.agent_runtime.validation_integration_contracts import (
    AgentValidationRequest,
    AgentValidationResult,
    CommitGateEvaluation,
    ValidationExecutionContext,
    ValidationFinding,
)
from cmm.agent_runtime.validation_integration_repository import (
    AgentValidationRepository,
    InMemoryAgentValidationRepository,
)
from cmm.agent_runtime.validation_policy_adapter import AgentValidationPolicyAdapter
from cmm.validation import (
    DEFAULT_VALIDATION_POLICIES,
    CommitGateEvaluator,
    ValidationContext,
    ValidationContractError,
    ValidationPipeline,
    ValidationPolicy,
    ValidationResult,
    ValidationStatus,
    ValidationStep,
    affected_tests_step,
    ast_step,
    build_default_validation_pipeline,
    resolve_validation_policy,
    syntax_step,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resource_fingerprint(paths: Sequence[str]) -> str:
    """Compute a deterministic content fingerprint over a set of resource paths."""
    hasher = hashlib.sha256()
    for raw_path in sorted(set(paths)):
        path_obj = Path(raw_path)
        hasher.update(raw_path.encode("utf-8"))
        if path_obj.is_file():
            hasher.update(path_obj.read_bytes())
        else:
            hasher.update(b"<absent>")
    return hasher.hexdigest()


# Maps abstract `ValidationRequirement.validator_ids` entries to concrete Phase 7
# `ValidationStep` builders. This is the only translation Phase 9.14 performs;
# execution itself always runs through the real `ValidationPipeline`.
_STEP_BUILDERS: dict[str, Callable[[ValidationContext], ValidationStep | None]] = {
    "syntax_validator": lambda ctx: syntax_step(),
    "ast_validator": lambda ctx: ast_step(),
    "affected_tests_step": lambda ctx: affected_tests_step(ctx),
}

_ESCALATE_GATE_CODES = frozenset({"authorization_required", "authorization_denied"})
_ROLLBACK_GATE_CODES = frozenset({"repository_not_clean", "repository_state_unsafe"})

_PIPELINE_STATUS_TO_AGENT_STATUS: dict[ValidationStatus, AgentValidationStatus] = {
    ValidationStatus.PASSED: AgentValidationStatus.PASSED,
    ValidationStatus.WARNING: AgentValidationStatus.PASSED_WITH_WARNINGS,
    ValidationStatus.FAILED: AgentValidationStatus.FAILED,
    ValidationStatus.ERROR: AgentValidationStatus.ERROR,
    ValidationStatus.TIMED_OUT: AgentValidationStatus.TIMED_OUT,
    ValidationStatus.CANCELLED: AgentValidationStatus.CANCELLED,
}


class ValidationDecisionResolver:
    """Evaluates validation findings, commit gate output, and context to produce a deterministic decision."""

    def resolve(
        self,
        stage: AgentValidationStage,
        status: AgentValidationStatus,
        findings: tuple[ValidationFinding, ...] = (),
        commit_gate_eval: CommitGateEvaluation | None = None,
        context_data: dict[str, Any] | None = None,
    ) -> AgentValidationDecision:
        ctx = context_data or {}

        # 1. Pre-execution stage blocking decisions
        if stage == AgentValidationStage.PRE_EXECUTION:
            if status in (
                AgentValidationStatus.BLOCKED,
                AgentValidationStatus.FAILED,
                AgentValidationStatus.ERROR,
            ):
                return AgentValidationDecision.BLOCK
            if status == AgentValidationStatus.TIMED_OUT:
                return (
                    AgentValidationDecision.RETRY
                    if ctx.get("retryable", False)
                    else AgentValidationDecision.BLOCK
                )
            return AgentValidationDecision.CONTINUE

        # 2. Pre-commit / Commit Gate evaluation decisions
        if commit_gate_eval is not None and not commit_gate_eval.authorized:
            if any(
                code in _ESCALATE_GATE_CODES for code in commit_gate_eval.reason_codes
            ):
                return AgentValidationDecision.ESCALATE
            if any(
                code in _ROLLBACK_GATE_CODES for code in commit_gate_eval.reason_codes
            ):
                return AgentValidationDecision.ROLLBACK
            return AgentValidationDecision.BLOCK

        # 3. Post-execution & Post-rollback stage decisions
        if status == AgentValidationStatus.TIMED_OUT:
            if ctx.get("retryable", True):
                return AgentValidationDecision.RETRY
            return AgentValidationDecision.BLOCK

        if status == AgentValidationStatus.BLOCKED:
            if ctx.get("requires_approval") or any(
                f.failure_class == ValidationFailureClass.POLICY for f in findings
            ):
                return AgentValidationDecision.ESCALATE
            if ctx.get("requires_pause"):
                return AgentValidationDecision.PAUSE
            return AgentValidationDecision.BLOCK

        if status in (AgentValidationStatus.FAILED, AgentValidationStatus.ERROR):
            has_regression = any(
                f.failure_class
                in (
                    ValidationFailureClass.REGRESSION,
                    ValidationFailureClass.COMMIT_GATE,
                )
                for f in findings
            )
            rollback_available = ctx.get("rollback_available", False)
            if (
                has_regression or ctx.get("rollback_required", False)
            ) and rollback_available:
                return AgentValidationDecision.ROLLBACK

            if ctx.get("transient_failure", False) or ctx.get("retry_allowed", False):
                return AgentValidationDecision.RETRY

            if ctx.get("plan_invalid", False):
                return AgentValidationDecision.REPLAN

            if ctx.get("requires_human", False):
                return AgentValidationDecision.ESCALATE

            if ctx.get("fatal", False):
                return AgentValidationDecision.ABORT

            return AgentValidationDecision.BLOCK

        if status in (
            AgentValidationStatus.PASSED,
            AgentValidationStatus.PASSED_WITH_WARNINGS,
        ):
            return AgentValidationDecision.CONTINUE

        return AgentValidationDecision.BLOCK


def _classify_failure(finding: Any, step_name: str) -> ValidationFailureClass:
    source = str(getattr(finding, "source", "")).lower()
    severity = getattr(finding, "severity", None)
    severity_val = str(getattr(severity, "value", severity)).upper()

    if "security" in source or "bandit" in source or "audit" in source:
        return ValidationFailureClass.SECURITY
    if step_name == "syntax":
        return ValidationFailureClass.SYNTAX
    if step_name == "ast":
        return ValidationFailureClass.AST
    if "lint" in source or "ruff" in source or "format" in source:
        return ValidationFailureClass.LINT
    if "pytest" in source or "test" in step_name:
        return ValidationFailureClass.UNIT_TEST
    if severity_val == "CRITICAL":
        return ValidationFailureClass.STATIC_ANALYSIS
    return ValidationFailureClass.UNKNOWN


class AgentValidationAdapter:
    """Adapter bridging Agent Runtime execution with Phase 7 Validation Pipeline and Commit Gate."""

    def __init__(
        self,
        pipeline: ValidationPipeline | None = None,
        repository: AgentValidationRepository | None = None,
        policy_adapter: AgentValidationPolicyAdapter | None = None,
        commit_gate_evaluator: type[CommitGateEvaluator]
        | CommitGateEvaluator
        | None = None,
        decision_resolver: ValidationDecisionResolver | None = None,
    ) -> None:
        self._pipeline = pipeline or build_default_validation_pipeline()
        self._repository = repository or InMemoryAgentValidationRepository()
        self._policy_adapter = policy_adapter or AgentValidationPolicyAdapter()
        self._commit_gate_evaluator = commit_gate_evaluator or CommitGateEvaluator
        self._decision_resolver = decision_resolver or ValidationDecisionResolver()

    @property
    def repository(self) -> AgentValidationRepository:
        return self._repository

    def validate(
        self,
        request: AgentValidationRequest,
        exec_context: ValidationExecutionContext | None = None,
    ) -> AgentValidationResult:
        started_at = _now_iso()

        # Idempotency check
        if request.idempotency_key:
            existing = self._repository.find_by_idempotency_key(request.idempotency_key)
            if existing is not None:
                prev_req = self._repository.get_request(existing.request_id)
                if prev_req.fingerprint == request.fingerprint:
                    return existing
                raise ValidationRepositoryError(
                    f"Idempotency key '{request.idempotency_key}' reused with conflicting fingerprint."
                )

        self._repository.add_request(request)

        try:
            return self._execute_validation(request, exec_context, started_at)
        except (
            ValidationRepositoryError,
            ValidationAdapterError,
            ValidationInfrastructureError,
        ):
            raise
        except Exception as exc:
            raise ValidationInfrastructureError(
                f"Unexpected infrastructure error during validation: {exc}"
            ) from exc

    def _resolve_steps(
        self, request: AgentValidationRequest, v_context: ValidationContext
    ) -> tuple[ValidationStep, ...]:
        steps: list[ValidationStep] = []
        seen_names: set[str] = set()
        for req in request.requirements:
            for validator_id in req.validator_ids:
                builder = _STEP_BUILDERS.get(validator_id)
                if builder is None:
                    if req.required:
                        raise ValidationAdapterError(
                            f"Requirement '{req.requirement_id}' mandates validator "
                            f"'{validator_id}', but no corresponding Phase 7 validation "
                            "step adapter is registered."
                        )
                    continue
                try:
                    step = builder(v_context)
                except Exception as exc:
                    raise ValidationAdapterError(
                        f"Failed to build validation step for validator '{validator_id}': {exc}"
                    ) from exc
                if step is not None and step.name not in seen_names:
                    steps.append(step)
                    seen_names.add(step.name)
        return tuple(steps)

    def _resolve_commit_policy(
        self, v_context: ValidationContext
    ) -> ValidationPolicy | None:
        try:
            policy = resolve_validation_policy(v_context)
        except ValidationContractError:
            # Unresolvable/unknown policy name: fail safe to the strictest known
            # policy rather than silently authorizing with no required checks.
            policy = None
        return policy or DEFAULT_VALIDATION_POLICIES.get("full")

    def _execute_validation(
        self,
        request: AgentValidationRequest,
        exec_context: ValidationExecutionContext | None,
        started_at: str,
    ) -> AgentValidationResult:
        findings: list[ValidationFinding] = []
        blocking_reasons: list[str] = []
        warnings: list[str] = []
        validation_report_dict: dict[str, Any] = {}
        commit_gate_eval: CommitGateEvaluation | None = None
        commit_gate_eval_dict: dict[str, Any] | None = None

        resource_scope: tuple[str, ...] = (
            tuple(exec_context.resource_scope) if exec_context else ()
        )
        if not resource_scope:
            merged: list[str] = []
            for req in request.requirements:
                merged.extend(req.resource_scope)
            resource_scope = tuple(dict.fromkeys(merged))

        requires_commit_gate = request.stage == AgentValidationStage.PRE_COMMIT or any(
            r.validation_kind == ValidationRequirementKind.COMMIT_GATE
            for r in request.requirements
        )

        requested_policy = (
            request.context_data.get("policy_name") if request.context_data else None
        )
        project_root_raw = (
            request.context_data.get("project_root") if request.context_data else None
        )

        v_context = ValidationContext(
            project_root=Path(project_root_raw) if project_root_raw else Path("."),
            changed_files=tuple(Path(p) for p in resource_scope),
            execution_mode=exec_context.environment if exec_context else "local",
            allow_commit=requires_commit_gate,
            requested_policy=requested_policy,
        )

        steps = self._resolve_steps(request, v_context)

        pipeline_status: ValidationStatus = ValidationStatus.PASSED
        pipeline_res: ValidationResult | None = None
        if steps or requires_commit_gate:
            try:
                pipeline_res = self._pipeline.run(
                    v_context, steps, validation_id=request.id
                )
            except Exception as exc:
                raise ValidationInfrastructureError(
                    f"Unexpected infrastructure error executing Phase 7 validation pipeline: {exc}"
                ) from exc

            validation_report_dict = pipeline_res.serialize()
            pipeline_status = pipeline_res.status

            for step_result in pipeline_res.steps:
                for f in step_result.findings:
                    finding = ValidationFinding(
                        finding_id=f"f-{uuid.uuid4().hex[:8]}",
                        rule_id=str(getattr(f, "code", "unknown")),
                        severity=str(
                            f.severity.value
                            if hasattr(f.severity, "value")
                            else f.severity
                        ),
                        message=str(getattr(f, "message", "")),
                        failure_class=_classify_failure(f, step_result.name),
                        location=f"{f.file_path}:{f.line}"
                        if getattr(f, "file_path", None)
                        else "",
                    )
                    findings.append(finding)

            blocking_reasons.extend(
                f"{f.source}:{f.code}: {f.message}"
                for f in pipeline_res.blocking_findings
            )
            warnings.extend(
                f"{f.source}:{f.code}: {f.message}" for f in pipeline_res.warnings
            )

        status = _PIPELINE_STATUS_TO_AGENT_STATUS.get(
            pipeline_status, AgentValidationStatus.FAILED
        )

        # Evaluate Commit Gate using the real Phase 7 evaluator (no parallel gate logic).
        if requires_commit_gate:
            assert pipeline_res is not None  # steps-or-gate guard above guarantees this
            policy = self._resolve_commit_policy(v_context)
            try:
                gate_res = self._commit_gate_evaluator.evaluate(pipeline_res, policy)
            except Exception as exc:
                raise ValidationInfrastructureError(
                    f"Unexpected infrastructure error evaluating Commit Gate: {exc}"
                ) from exc

            gate_reason_codes = [r.code.value for r in gate_res.reasons]
            gate_messages = [r.message for r in gate_res.reasons]

            expected_fingerprint = (
                request.context_data.get("expected_resource_fingerprint")
                if request.context_data
                else None
            )
            authorized = gate_res.allowed
            if expected_fingerprint and resource_scope:
                actual_fingerprint = _resource_fingerprint(resource_scope)
                if actual_fingerprint != expected_fingerprint:
                    authorized = False
                    gate_reason_codes.append("resource_fingerprint_mismatch")
                    gate_messages.append(
                        "Resource fingerprint changed since checkpoint; commit authorization denied."
                    )

            commit_gate_eval = CommitGateEvaluation(
                authorized=authorized,
                decision=(
                    AgentValidationDecision.CONTINUE
                    if authorized
                    else AgentValidationDecision.BLOCK
                ),
                commit_authorization={"policy": policy.name if policy else None},
                reason_codes=tuple(gate_reason_codes),
                blocking_reasons=tuple(gate_messages),
                evaluated_at=_now_iso(),
            )
            commit_gate_eval_dict = commit_gate_eval.to_dict()

            if not authorized:
                status = AgentValidationStatus.BLOCKED
                blocking_reasons.extend(gate_messages)

        # Resolve final decision
        ctx_data = dict(request.context_data)
        if exec_context:
            ctx_data.update(exec_context.metadata)

        decision = self._decision_resolver.resolve(
            stage=request.stage,
            status=status,
            findings=tuple(findings),
            commit_gate_eval=commit_gate_eval,
            context_data=ctx_data,
        )

        completed_at = _now_iso()

        result = AgentValidationResult(
            request_id=request.id,
            run_id=request.run_id,
            iteration_id=request.iteration_id,
            operation_request_id=request.operation_request_id,
            stage=request.stage,
            status=status,
            decision=decision,
            findings=tuple(findings),
            validation_report=validation_report_dict,
            commit_gate_result=commit_gate_eval_dict,
            started_at=started_at,
            completed_at=completed_at,
            duration=0.0,
            blocking_reasons=tuple(blocking_reasons),
            warnings=tuple(warnings),
        )

        self._repository.add_result(result)
        return result
