from __future__ import annotations

from enum import Enum


class CommitGateReasonCode(str, Enum):
    VALIDATION_NOT_PASSED = "validation_not_passed"
    VALIDATION_INCOMPLETE = "validation_incomplete"
    PIPELINE_CANCELLED = "pipeline_cancelled"
    REQUIRED_STEP_FAILED = "required_step_failed"
    REQUIRED_STEP_MISSING = "required_step_missing"
    REQUIRED_STEP_SKIPPED = "required_step_skipped"
    BLOCKING_FINDING = "blocking_finding"
    CRITICAL_ERROR = "critical_error"
    REQUIRED_STEP_TIMEOUT = "required_step_timeout"
    REQUIRED_ARTIFACT_MISSING = "required_artifact_missing"
    POLICY_UNRESOLVED = "policy_unresolved"
    POLICY_INCOMPLETE = "policy_incomplete"
    POLICY_FORBIDS_COMMIT = "policy_forbids_commit"
    SECURITY_VIOLATION = "security_violation"
    AUTHORIZATION_REQUIRED = "authorization_required"
    AUTHORIZATION_DENIED = "authorization_denied"
    REPOSITORY_NOT_CLEAN = "repository_not_clean"
    REPOSITORY_STATE_UNSAFE = "repository_state_unsafe"
    INVALID_COMMIT_MESSAGE = "invalid_commit_message"
    COMMIT_FAILED = "commit_failed"
    INVALID_CONTRACT = "invalid_contract"
    UNMATCHED_VALIDATION_ID = "unmatched_validation_id"
    UNAUTHORIZED_FILES_STAGED = "unauthorized_files_staged"
    NO_CHANGES_TO_COMMIT = "no_changes_to_commit"


__all__ = ["CommitGateReasonCode"]
