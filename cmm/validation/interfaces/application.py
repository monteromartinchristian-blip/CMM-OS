"""Validation Application Service layer for CMM OS (Phase 7.12)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from ..artifacts import ValidationArtifact
from ..catalog import build_default_validation_registry, select_python_files
from ..commit_gate.evaluator import CommitGateEvaluator
from ..context import ValidationContext
from ..custom import build_custom_validation_step
from ..enums import ValidationSeverity, ValidationStatus
from ..findings import ValidationFinding
from ..impact import ChangeSetBuilder
from ..observability import (
    LocalValidationRepository,
    ValidationExecutionRecord,
    ValidationHistoryPage,
    ValidationHistoryQuery,
    ValidationObservabilityService,
)
from ..pipeline import ValidationPipeline
from ..policy import (
    DEFAULT_VALIDATION_POLICIES,
    canonical_validation_policy_name,
    expand_validation_step_labels,
    resolve_validation_policy,
)
from ..results import ValidationResult
from ..steps import ValidationStepResult
from .cancellation import ValidationCancellationRegistry
from .contracts import (
    StartValidationRequest,
    ValidationArtifactResponse,
    ValidationGateResponse,
    ValidationResultResponse,
    ValidationStatusResponse,
)
from .errors import (
    ValidationConflictError,
    ValidationNotFoundError,
    ValidationPolicyNotFoundError,
    ValidationStepNotFoundError,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ValidationApplicationService:
    """High-level application service uniting Validation Pipeline, Observability, and Commit Gate."""

    def __init__(
        self,
        project_root: Path | str | None = None,
        storage_root: Path | str | None = None,
        repository: LocalValidationRepository | None = None,
        pipeline: ValidationPipeline | None = None,
        cancellation_registry: ValidationCancellationRegistry | None = None,
    ) -> None:
        self._project_root = (
            Path(project_root).resolve() if project_root else Path.cwd()
        )
        self._storage_root = (
            Path(storage_root).resolve()
            if storage_root
            else (self._project_root / ".cmm" / "validation")
        )
        self._repo = repository or LocalValidationRepository(self._storage_root)
        self._obs = ValidationObservabilityService(self._repo)
        self._registry = build_default_validation_registry()
        from ..executor import ValidationExecutor

        self._pipeline = pipeline or ValidationPipeline(
            executor=ValidationExecutor(),
            registry=self._registry,
            observability=self._obs,
        )
        self._cancellation_registry = (
            cancellation_registry or ValidationCancellationRegistry()
        )

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    @property
    def cancellation_registry(self) -> ValidationCancellationRegistry:
        return self._cancellation_registry

    # ------------------------------------------------------------------
    # Start Validation
    # ------------------------------------------------------------------

    def start_validation(
        self, request: StartValidationRequest
    ) -> ValidationResultResponse:
        """Start and execute a validation pipeline run."""
        # 1. Check Idempotency if request_id is provided
        if request.request_id:
            existing = self._find_execution_by_request_id(request.request_id)
            if existing is not None:
                self._verify_idempotency_match(existing, request)
                return self._record_to_result_response(existing)

        # 2. Validate policy if explicitly requested
        resolved_policy_name = None
        if request.policy_name:
            canon = canonical_validation_policy_name(request.policy_name)
            if canon not in DEFAULT_VALIDATION_POLICIES:
                raise ValidationPolicyNotFoundError(request.policy_name)
            resolved_policy_name = canon

        # 3. Validate step names if explicitly requested
        if request.steps:
            for step_name in request.steps:
                try:
                    expanded = expand_validation_step_labels(step_name)
                    if not expanded:
                        raise ValidationStepNotFoundError(step_name)
                except Exception:  # noqa: BLE001
                    if not self._registry.has(step_name):
                        raise ValidationStepNotFoundError(step_name)

        # 4. Build context
        metadata = dict(request.metadata or {})
        if request.request_id:
            metadata["request_id"] = request.request_id

        context = ValidationContext(
            project_root=request.project_root,
            requested_policy=resolved_policy_name,
            requested_steps=request.steps,
            changed_files=request.files or (),
            actor=request.actor,
            metadata=metadata,
            execution_mode=request.execution_mode,
        )

        # 5. Resolve changed files using context
        changed_files: list[Path] = []
        if request.files:
            changed_files = list(request.files)
        elif request.use_git_changes:
            try:
                cs = ChangeSetBuilder(request.project_root).build()
                changed_files = [p for p in cs.all_paths if p.exists()]
            except Exception:  # noqa: BLE001
                changed_files = select_python_files(context)
        else:
            changed_files = select_python_files(context)

        if changed_files != list(context.changed_files):
            context = ValidationContext(
                project_root=context.project_root,
                requested_policy=context.requested_policy,
                requested_steps=context.requested_steps,
                changed_files=tuple(changed_files),
                actor=context.actor,
                metadata=context.metadata,
                execution_mode=context.execution_mode,
            )

        # 6. Prepare steps from policy / registry
        from ..custom_validators import build_default_custom_validator_registry
        from ..testing_defaults import default_validation_steps

        policy = (
            resolve_validation_policy(context) or DEFAULT_VALIDATION_POLICIES["full"]
        )
        candidate_steps = list(default_validation_steps(context))

        custom_reg = build_default_custom_validator_registry()
        for c_val in custom_reg.validators():
            step_name = f"custom.{c_val.name}"
            val_reg = self._registry if not self._registry.has(step_name) else None
            step = build_custom_validation_step(c_val, validation_registry=val_reg)
            if not any(s.name == step.name for s in candidate_steps):
                candidate_steps.append(step)

        if request.steps:
            expanded_step_names = set(expand_validation_step_labels(request.steps))
            all_steps = [s for s in candidate_steps if s.name in expanded_step_names]
        else:
            expanded_req = expand_validation_step_labels(policy.required_steps)
            expanded_opt = expand_validation_step_labels(policy.optional_steps)
            allowed = set(expanded_req).union(expanded_opt)
            all_steps = [s for s in candidate_steps if s.name in allowed]

        if not all_steps:
            all_steps = candidate_steps

        # 7. Configure observability pipeline
        pipeline_to_use = self._pipeline
        if not request.persist:
            pipeline_to_use = ValidationPipeline(
                executor=self._pipeline.executor,
                registry=self._pipeline.registry,
                observability=None,
            )

        # 8. Assign validation_id and cancellation token
        validation_id = f"val-{int(time.time() * 1000)}"
        token = self._cancellation_registry.register(validation_id)

        try:
            result = pipeline_to_use.run(
                context,
                all_steps,
                cancel=token,
                validation_id=validation_id,
            )
        finally:
            self._cancellation_registry.unregister(validation_id)

        if request.request_id:
            result.metadata["request_id"] = request.request_id
            rec = self._repo.load_execution(result.id)
            if rec is not None:
                updated_meta = dict(rec.metadata or {})
                updated_meta["request_id"] = request.request_id
                updated_rec = ValidationExecutionRecord(
                    id=rec.id,
                    schema_version=rec.schema_version,
                    status=rec.status,
                    policy=rec.policy,
                    actor=rec.actor,
                    execution_mode=rec.execution_mode,
                    project_root=rec.project_root,
                    branch=rec.branch,
                    base_commit=rec.base_commit,
                    changed_files=rec.changed_files,
                    affected_tests=rec.affected_tests,
                    step_results=rec.step_results,
                    findings=rec.findings,
                    artifacts=rec.artifacts,
                    metrics=rec.metrics,
                    gate_result=rec.gate_result,
                    commit_hash=rec.commit_hash,
                    started_at=rec.started_at,
                    completed_at=rec.completed_at,
                    created_at=rec.created_at,
                    metadata=updated_meta,
                )
                self._repo.save_execution(updated_rec)

        # 9. Format response
        resp = ValidationResultResponse(
            validation_id=result.id,
            status=result.status.value
            if hasattr(result.status, "value")
            else str(result.status),
            policy=result.policy,
            steps=tuple(s.serialize() for s in (result.steps or ())),
            artifacts=tuple(a.serialize() for a in (result.artifacts or ())),
            blocking_findings=tuple(
                f.serialize() for f in (result.blocking_findings or ())
            ),
            warnings=tuple(f.serialize() for f in (result.warnings or ())),
            duration_ms=result.duration_ms,
            started_at=result.started_at,
            completed_at=result.completed_at,
            can_commit=result.can_commit,
            metadata={
                **dict(result.metadata or {}),
                "persisted": request.persist,
            },
        )

        return resp

    # ------------------------------------------------------------------
    # Query & Status Methods
    # ------------------------------------------------------------------

    def get_validation(self, validation_id: str) -> ValidationStatusResponse:
        """Get status summary of a validation execution."""
        record = self._repo.load_execution(validation_id)
        if record is None:
            raise ValidationNotFoundError(validation_id)
        return self._record_to_status_response(record)

    def get_status(self, validation_id: str) -> ValidationStatusResponse:
        """Alias for get_validation."""
        return self.get_validation(validation_id)

    def get_result(self, validation_id: str) -> ValidationResultResponse:
        """Get full execution result of a validation execution."""
        record = self._repo.load_execution(validation_id)
        if record is None:
            raise ValidationNotFoundError(validation_id)
        return self._record_to_result_response(record)

    def cancel_validation(self, validation_id: str) -> ValidationStatusResponse:
        """Request cooperative cancellation of a running validation."""
        cancelled = self._cancellation_registry.cancel(validation_id)
        record = self._repo.load_execution(validation_id)

        if record is None and not cancelled:
            raise ValidationNotFoundError(validation_id)

        if record is not None:
            if cancelled and record.status == "running":
                # Update status record to cancelled if still running
                record = ValidationExecutionRecord(
                    id=record.id,
                    schema_version=record.schema_version,
                    status=ValidationStatus.CANCELLED.value,
                    policy=record.policy,
                    actor=record.actor,
                    execution_mode=record.execution_mode,
                    project_root=record.project_root,
                    branch=record.branch,
                    base_commit=record.base_commit,
                    changed_files=record.changed_files,
                    affected_tests=record.affected_tests,
                    step_results=record.step_results,
                    findings=record.findings,
                    artifacts=record.artifacts,
                    metrics=record.metrics,
                    gate_result=record.gate_result,
                    commit_hash=record.commit_hash,
                    started_at=record.started_at,
                    completed_at=_now_utc(),
                    created_at=record.created_at,
                    metadata=record.metadata,
                )
                self._repo.save_execution(record)
            return self._record_to_status_response(record)

        return ValidationStatusResponse(
            validation_id=validation_id,
            status=ValidationStatus.CANCELLED.value,
            policy="unknown",
        )

    def list_artifacts(self, validation_id: str) -> list[ValidationArtifactResponse]:
        """List all artifacts for a given validation ID."""
        record = self._repo.load_execution(validation_id)
        if record is None:
            raise ValidationNotFoundError(validation_id)

        responses: list[ValidationArtifactResponse] = []
        for art_dict in record.artifacts or ():
            if isinstance(art_dict, dict) and "id" in art_dict:
                responses.append(ValidationArtifactResponse.from_mapping(art_dict))
        return responses

    def get_artifact(
        self, validation_id: str, artifact_id: str
    ) -> ValidationArtifactResponse:
        """Retrieve a specific artifact by ID."""
        record = self._repo.load_execution(validation_id)
        if record is None:
            raise ValidationNotFoundError(validation_id)

        # Check repository artifact storage first
        art = self._obs.get_artifact(validation_id, artifact_id)
        if art is not None:
            return ValidationArtifactResponse.from_mapping(art.serialize())

        # Fallback to record artifacts tuple
        for art_dict in record.artifacts or ():
            if isinstance(art_dict, dict) and str(art_dict.get("id")) == artifact_id:
                return ValidationArtifactResponse.from_mapping(art_dict)

        raise ValidationNotFoundError(
            validation_id,
            f"Artifact '{artifact_id}' was not found for validation '{validation_id}'.",
        )

    def evaluate_gate(self, validation_id: str) -> ValidationGateResponse:
        """Evaluate the Commit Gate for a persisted validation execution."""
        record = self._repo.load_execution(validation_id)
        if record is None:
            raise ValidationNotFoundError(validation_id)

        # Reconstruct minimal ValidationResult for evaluator
        result = self._record_to_validation_result(record)
        policy_name = canonical_validation_policy_name(record.policy)
        policy = DEFAULT_VALIDATION_POLICIES.get(policy_name) if policy_name else None

        gate_res = CommitGateEvaluator.evaluate(result, policy)

        return ValidationGateResponse(
            allowed=gate_res.allowed,
            reasons=tuple(r.serialize() for r in gate_res.reasons),
            blocking_findings=tuple(f.serialize() for f in gate_res.blocking_findings),
            validation_result_id=gate_res.validation_result_id,
            commit_created=gate_res.commit_created,
            commit_hash=gate_res.commit_hash,
        )

    def query_history(
        self, query: ValidationHistoryQuery | None = None
    ) -> ValidationHistoryPage:
        """Query paginated execution history."""
        q = query or ValidationHistoryQuery()
        return self._repo.list_executions(q)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _find_execution_by_request_id(
        self, request_id: str
    ) -> ValidationExecutionRecord | None:
        """Find an execution record with matching request_id in metadata."""
        page = self._repo.list_executions(ValidationHistoryQuery(limit=100))
        for item in page.items:
            rec = self._repo.load_execution(item.id)
            if rec is not None and rec.metadata.get("request_id") == request_id:
                return rec
        return None

    def _verify_idempotency_match(
        self,
        existing: ValidationExecutionRecord,
        request: StartValidationRequest,
    ) -> None:
        """Verify request parameters match existing request_id record."""
        existing_policy = existing.policy
        req_policy = canonical_validation_policy_name(request.policy_name)
        if req_policy and existing_policy and req_policy != existing_policy:
            raise ValidationConflictError(
                f"Conflict for request_id '{request.request_id}': policy '{req_policy}' does not match existing policy '{existing_policy}'.",
                details={
                    "request_id": request.request_id,
                    "existing_policy": existing_policy,
                    "requested_policy": req_policy,
                },
            )

    def _record_to_status_response(
        self, record: ValidationExecutionRecord
    ) -> ValidationStatusResponse:
        gate_allowed = (
            record.gate_result.get("allowed")
            if record.gate_result
            else record.gate_allowed
        )
        return ValidationStatusResponse(
            validation_id=record.id,
            status=record.status,
            policy=record.policy,
            actor=record.actor,
            started_at=record.started_at,
            completed_at=record.completed_at,
            duration_ms=int(record.metrics.get("total_duration_ms", 0))
            if record.metrics
            else 0,
            gate_allowed=gate_allowed,
            commit_hash=record.commit_hash,
        )

    def _record_to_result_response(
        self, record: ValidationExecutionRecord
    ) -> ValidationResultResponse:
        blocking = [
            f for f in record.findings if isinstance(f, dict) and f.get("blocking")
        ]
        warnings = [
            f for f in record.findings if isinstance(f, dict) and not f.get("blocking")
        ]
        gate_allowed = (
            bool(record.gate_result.get("allowed")) if record.gate_result else False
        )

        return ValidationResultResponse(
            validation_id=record.id,
            status=record.status,
            policy=record.policy or "unknown",
            steps=tuple(record.step_results or ()),
            artifacts=tuple(record.artifacts or ()),
            blocking_findings=tuple(blocking),
            warnings=tuple(warnings),
            duration_ms=int(record.metrics.get("total_duration_ms", 0))
            if record.metrics
            else 0,
            started_at=record.started_at,
            completed_at=record.completed_at,
            can_commit=gate_allowed,
            metadata=dict(record.metadata or {}),
        )

    def _record_to_validation_result(
        self, record: ValidationExecutionRecord
    ) -> ValidationResult:
        def parse_datetime(value: object) -> datetime | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            raise ValueError(f"Invalid persisted datetime value: {value!r}")

        def parse_finding(payload: dict[str, object]) -> ValidationFinding:
            severity_value = str(
                payload.get("severity", ValidationSeverity.ERROR.value)
            )
            severity = (
                ValidationSeverity(severity_value)
                if severity_value in ValidationSeverity._value2member_map_
                else ValidationSeverity.ERROR
            )
            file_path = payload.get("file_path")

            return ValidationFinding(
                code=str(payload.get("code", "persisted_finding")),
                message=str(payload.get("message", "Persisted validation finding")),
                severity=severity,
                source=str(payload.get("source", "validation.persistence")),
                file_path=Path(str(file_path)) if file_path else None,
                line=payload.get("line")
                if isinstance(payload.get("line"), int)
                else None,
                column=(
                    payload.get("column")
                    if isinstance(payload.get("column"), int)
                    else None
                ),
                blocking=bool(payload.get("blocking", False)),
                suggested_fix=(
                    str(payload["suggested_fix"])
                    if payload.get("suggested_fix") is not None
                    else None
                ),
                documentation_url=(
                    str(payload["documentation_url"])
                    if payload.get("documentation_url") is not None
                    else None
                ),
                metadata=dict(payload.get("metadata") or {}),
            )

        def parse_artifact(payload: dict[str, object]) -> ValidationArtifact:
            artifact_path = payload.get("path")
            return ValidationArtifact(
                id=str(payload.get("id", "persisted-artifact")),
                kind=str(payload.get("kind", "unknown")),
                source=str(payload.get("source", "validation.persistence")),
                path=Path(str(artifact_path)) if artifact_path else None,
                content=dict(payload.get("content") or {}),
                findings=tuple(
                    parse_finding(dict(finding))
                    for finding in payload.get("findings", ())
                    if isinstance(finding, dict)
                ),
                metrics=dict(payload.get("metrics") or {}),
                created_at=(parse_datetime(payload.get("created_at")) or _now_utc()),
                metadata=dict(payload.get("metadata") or {}),
            )

        def parse_step(payload: dict[str, object]) -> ValidationStepResult:
            status_value = str(payload.get("status", ValidationStatus.ERROR.value))
            status = (
                ValidationStatus(status_value)
                if status_value in ValidationStatus._value2member_map_
                else ValidationStatus.ERROR
            )

            return ValidationStepResult(
                name=str(payload.get("name", "persisted_step")),
                status=status,
                exit_code=(
                    payload.get("exit_code")
                    if isinstance(payload.get("exit_code"), int)
                    else None
                ),
                duration_ms=(
                    payload.get("duration_ms")
                    if isinstance(payload.get("duration_ms"), int)
                    else 0
                ),
                stdout=str(payload.get("stdout", "")),
                stderr=str(payload.get("stderr", "")),
                findings=tuple(
                    parse_finding(dict(finding))
                    for finding in payload.get("findings", ())
                    if isinstance(finding, dict)
                ),
                artifacts=tuple(
                    parse_artifact(dict(artifact))
                    for artifact in payload.get("artifacts", ())
                    if isinstance(artifact, dict)
                ),
                started_at=parse_datetime(payload.get("started_at")),
                completed_at=parse_datetime(payload.get("completed_at")),
                metadata=dict(payload.get("metadata") or {}),
            )

        status = (
            ValidationStatus(record.status)
            if record.status in ValidationStatus._value2member_map_
            else ValidationStatus.ERROR
        )

        findings = tuple(
            parse_finding(dict(finding))
            for finding in record.findings
            if isinstance(finding, dict)
        )
        blocking_findings = tuple(finding for finding in findings if finding.blocking)
        warnings = tuple(finding for finding in findings if not finding.blocking)
        steps = tuple(
            parse_step(dict(step))
            for step in record.step_results
            if isinstance(step, dict)
        )
        artifacts = tuple(
            parse_artifact(dict(artifact))
            for artifact in record.artifacts
            if isinstance(artifact, dict)
        )

        can_commit = (
            status in (ValidationStatus.PASSED, ValidationStatus.WARNING)
            and not blocking_findings
        )

        return ValidationResult(
            id=record.id,
            status=status,
            policy=record.policy or "full",
            steps=steps,
            artifacts=artifacts,
            blocking_findings=blocking_findings,
            warnings=warnings,
            changed_files=tuple(Path(path) for path in record.changed_files or ()),
            affected_tests=tuple(record.affected_tests or ()),
            duration_ms=(
                int(record.metrics.get("total_duration_ms", 0)) if record.metrics else 0
            ),
            started_at=record.started_at,
            completed_at=record.completed_at,
            can_commit=can_commit,
            metadata=dict(record.metadata or {}),
        )


__all__ = ["ValidationApplicationService"]
