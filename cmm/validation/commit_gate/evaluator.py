from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ..enums import ValidationSeverity, ValidationStatus
from ..errors import ValidationContractError
from ..findings import ValidationFinding
from ..policy import (
    DEFAULT_VALIDATION_POLICIES,
    ValidationPolicy,
    canonical_validation_policy_name,
    expand_validation_step_labels,
)
from ..results import ValidationResult
from .enums import CommitGateReasonCode
from .models import CommitGateReason, CommitGateResult


class CommitGateEvaluator:
    """Pure evaluator for commit gate eligibility.

    Performs complete evaluation without I/O, Git modifications, or side effects.
    """

    @classmethod
    def evaluate(
        cls,
        validation_result: ValidationResult,
        policy: ValidationPolicy | None = None,
        *,
        required_artifacts: Sequence[str] | None = None,
        evaluated_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> CommitGateResult:
        dt = evaluated_at or datetime.now(timezone.utc)
        meta = dict(metadata or {})

        # Contract validity checks
        if (
            not isinstance(validation_result, ValidationResult)
            or not validation_result.id
        ):
            reason = CommitGateReason(
                code=CommitGateReasonCode.INVALID_CONTRACT,
                message="Invalid or corrupt ValidationResult object",
            )
            return CommitGateResult(
                allowed=False,
                validation_result_id=getattr(validation_result, "id", "")
                or "invalid-result-id",
                reasons=(reason,),
                evaluated_at=dt,
                metadata=meta,
            )

        reasons: list[CommitGateReason] = []
        blocking_findings_set: list[ValidationFinding] = list(
            validation_result.blocking_findings
        )

        # 1. Resolve policy
        resolved_policy: ValidationPolicy | None = policy
        if resolved_policy is None and validation_result.policy:
            policy_canonical = canonical_validation_policy_name(
                validation_result.policy
            )
            resolved_policy = DEFAULT_VALIDATION_POLICIES.get(policy_canonical or "")

        if resolved_policy is None:
            reasons.append(
                CommitGateReason(
                    code=CommitGateReasonCode.POLICY_UNRESOLVED,
                    message=f"Validation policy '{validation_result.policy}' could not be resolved",
                )
            )
            policy_name = validation_result.policy or "unknown"
        else:
            policy_name = resolved_policy.name
            # Check if policy forbids commit
            if not resolved_policy.allow_commit:
                reasons.append(
                    CommitGateReason(
                        code=CommitGateReasonCode.POLICY_FORBIDS_COMMIT,
                        message=f"Policy '{resolved_policy.name}' has allow_commit=False",
                    )
                )

        # 2. Check overall pipeline status & execution completeness
        status = validation_result.status
        if status in (ValidationStatus.PENDING, ValidationStatus.RUNNING):
            reasons.append(
                CommitGateReason(
                    code=CommitGateReasonCode.VALIDATION_INCOMPLETE,
                    message=f"Validation pipeline execution is incomplete (status: {status.value})",
                )
            )
        elif status == ValidationStatus.CANCELLED:
            reasons.append(
                CommitGateReason(
                    code=CommitGateReasonCode.PIPELINE_CANCELLED,
                    message="Validation pipeline execution was cancelled",
                )
            )
        elif status == ValidationStatus.ERROR:
            reasons.append(
                CommitGateReason(
                    code=CommitGateReasonCode.CRITICAL_ERROR,
                    message="Validation pipeline completed with a critical execution error",
                )
            )
        elif status not in (ValidationStatus.PASSED, ValidationStatus.WARNING):
            reasons.append(
                CommitGateReason(
                    code=CommitGateReasonCode.VALIDATION_NOT_PASSED,
                    message=f"Validation result status is '{status.value}'",
                )
            )

        # Check metadata for cancellation signal
        pipeline_meta = validation_result.metadata.get("pipeline", {})
        if (
            isinstance(pipeline_meta, Mapping)
            and pipeline_meta.get("cancelled")
            and not any(
                r.code == CommitGateReasonCode.PIPELINE_CANCELLED for r in reasons
            )
        ):
            reasons.append(
                CommitGateReason(
                    code=CommitGateReasonCode.PIPELINE_CANCELLED,
                    message="Pipeline cancellation flag is active in metadata",
                )
            )

        # 3. Step completeness and required steps verification
        if resolved_policy is not None and resolved_policy.required_steps:
            try:
                expanded_required = expand_validation_step_labels(
                    resolved_policy.required_steps
                )
            except ValidationContractError as exc:
                reasons.append(
                    CommitGateReason(
                        code=CommitGateReasonCode.POLICY_INCOMPLETE,
                        message=f"Error expanding required step labels: {exc}",
                    )
                )
                expanded_required = ()

            steps_by_name = {s.name: s for s in validation_result.steps}

            for req_label in expanded_required:
                step_res = steps_by_name.get(req_label)
                if step_res is None:
                    reasons.append(
                        CommitGateReason(
                            code=CommitGateReasonCode.REQUIRED_STEP_MISSING,
                            message=f"Required step '{req_label}' was not executed",
                            step=req_label,
                        )
                    )
                else:
                    if step_res.status == ValidationStatus.FAILED:
                        reasons.append(
                            CommitGateReason(
                                code=CommitGateReasonCode.REQUIRED_STEP_FAILED,
                                message=f"Required step '{req_label}' failed",
                                step=req_label,
                            )
                        )
                    elif step_res.status == ValidationStatus.SKIPPED:
                        reasons.append(
                            CommitGateReason(
                                code=CommitGateReasonCode.REQUIRED_STEP_SKIPPED,
                                message=f"Required step '{req_label}' was skipped",
                                step=req_label,
                            )
                        )
                    elif step_res.status == ValidationStatus.TIMED_OUT:
                        reasons.append(
                            CommitGateReason(
                                code=CommitGateReasonCode.REQUIRED_STEP_TIMEOUT,
                                message=f"Required step '{req_label}' timed out",
                                step=req_label,
                            )
                        )
                    elif step_res.status == ValidationStatus.CANCELLED:
                        reasons.append(
                            CommitGateReason(
                                code=CommitGateReasonCode.PIPELINE_CANCELLED,
                                message=f"Required step '{req_label}' was cancelled",
                                step=req_label,
                            )
                        )
                    elif step_res.status == ValidationStatus.ERROR:
                        reasons.append(
                            CommitGateReason(
                                code=CommitGateReasonCode.CRITICAL_ERROR,
                                message=f"Required step '{req_label}' encountered a critical error",
                                step=req_label,
                            )
                        )

        # 4. Findings inspection (step findings, artifact findings)
        for s in validation_result.steps:
            for f in s.findings:
                if f.blocking or f.severity == ValidationSeverity.CRITICAL:
                    if f not in blocking_findings_set:
                        blocking_findings_set.append(f)
                    is_sec = (
                        "security" in f.source.lower()
                        or "bandit" in f.source.lower()
                        or "audit" in f.source.lower()
                    )
                    code = (
                        CommitGateReasonCode.SECURITY_VIOLATION
                        if is_sec
                        else CommitGateReasonCode.BLOCKING_FINDING
                    )
                    reasons.append(
                        CommitGateReason(
                            code=code,
                            message=f"Blocking finding in step '{s.name}': {f.message}",
                            step=s.name,
                            finding=f,
                        )
                    )

        for a in validation_result.artifacts:
            for f in a.findings:
                if f.blocking or f.severity == ValidationSeverity.CRITICAL:
                    if f not in blocking_findings_set:
                        blocking_findings_set.append(f)
                    is_sec = (
                        "security" in f.source.lower()
                        or "bandit" in f.source.lower()
                        or "audit" in f.source.lower()
                    )
                    code = (
                        CommitGateReasonCode.SECURITY_VIOLATION
                        if is_sec
                        else CommitGateReasonCode.BLOCKING_FINDING
                    )
                    reasons.append(
                        CommitGateReason(
                            code=code,
                            message=f"Blocking finding in artifact '{a.id}': {f.message}",
                            artifact=a.id,
                            finding=f,
                        )
                    )

        if validation_result.blocking_findings and not any(
            r.code
            in (
                CommitGateReasonCode.BLOCKING_FINDING,
                CommitGateReasonCode.SECURITY_VIOLATION,
            )
            for r in reasons
        ):
            for f in validation_result.blocking_findings:
                is_sec = (
                    "security" in f.source.lower()
                    or "bandit" in f.source.lower()
                    or "audit" in f.source.lower()
                )
                code = (
                    CommitGateReasonCode.SECURITY_VIOLATION
                    if is_sec
                    else CommitGateReasonCode.BLOCKING_FINDING
                )
                reasons.append(
                    CommitGateReason(
                        code=code,
                        message=f"Blocking finding: {f.message}",
                        finding=f,
                    )
                )

        # 5. Required artifacts inspection
        req_artifacts: list[str] = []
        if required_artifacts is not None:
            req_artifacts.extend(required_artifacts)
        if resolved_policy is not None and isinstance(
            resolved_policy.metadata, Mapping
        ):
            pol_artifacts = resolved_policy.metadata.get("required_artifacts")
            if isinstance(pol_artifacts, (list, tuple)):
                req_artifacts.extend(str(a) for a in pol_artifacts)

        val_artifact_kinds = {a.kind for a in validation_result.artifacts}
        val_artifact_ids = {a.id for a in validation_result.artifacts}

        for req_art in req_artifacts:
            if req_art not in val_artifact_kinds and req_art not in val_artifact_ids:
                reasons.append(
                    CommitGateReason(
                        code=CommitGateReasonCode.REQUIRED_ARTIFACT_MISSING,
                        message=f"Required artifact '{req_art}' is missing from validation result",
                        artifact=req_art,
                    )
                )

        # 6. Fallback safety check against can_commit
        if not validation_result.can_commit and not reasons:
            reasons.append(
                CommitGateReason(
                    code=CommitGateReasonCode.VALIDATION_NOT_PASSED,
                    message="ValidationResult.can_commit is False",
                )
            )

        is_allowed = len(reasons) == 0

        return CommitGateResult(
            allowed=is_allowed,
            validation_result_id=validation_result.id,
            reasons=tuple(reasons),
            blocking_findings=tuple(blocking_findings_set),
            policy_name=policy_name,
            evaluated_at=dt,
            authorization_required=True,
            authorized=False,
            commit_requested=False,
            commit_created=False,
            metadata=meta,
        )


__all__ = ["CommitGateEvaluator"]
