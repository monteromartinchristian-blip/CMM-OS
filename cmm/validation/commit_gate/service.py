from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .authorization import CommitAuthorization
from .enums import CommitGateReasonCode
from .models import CommitGateReason, CommitGateResult
from .repository import (
    CommitGateRepositoryError,
    GitRepositoryProtocol,
    ProvisionalCommitError,
    SubprocessGitRepository,
    UnsafeRepositoryStateError,
)


class ProvisionalCommitService:
    """Service that executes provisional commits only when explicit authorization and safe repository state exist."""

    def __init__(self, git_repository: GitRepositoryProtocol | None = None) -> None:
        self.git_repository = git_repository or SubprocessGitRepository()

    def create_commit(
        self,
        gate_result: CommitGateResult,
        authorization: CommitAuthorization,
        repository_path: Path,
        *,
        files_to_commit: Sequence[Path] | None = None,
        custom_message: str | None = None,
        validated_files: Sequence[Path] | None = None,
    ) -> CommitGateResult:
        meta = dict(gate_result.metadata or {})

        # 1. Gate permission check
        if not gate_result.allowed:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.VALIDATION_NOT_PASSED,
                        message="Cannot create commit: commit gate was denied",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=False,
                commit_requested=False,
                commit_created=False,
                metadata=meta,
            )

        # 2. Authorization validation
        if (
            not authorization.authorized
            or not authorization.actor
            or not authorization.actor.strip()
        ):
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.AUTHORIZATION_DENIED,
                        message="Explicit authorization is missing or denied",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=False,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        # 3. Match validation_result_id if present
        if (
            authorization.validation_result_id
            and authorization.validation_result_id != gate_result.validation_result_id
        ):
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.UNMATCHED_VALIDATION_ID,
                        message=f"Authorization target ID '{authorization.validation_result_id}' does not match gate validation ID '{gate_result.validation_result_id}'",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=False,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        # 4. Message validation & formatting
        raw_msg = (
            custom_message
            or authorization.reason
            or "chore(validation): provisional validated change"
        ).strip()
        if not raw_msg or "\x00" in raw_msg:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.INVALID_COMMIT_MESSAGE,
                        message="Commit message is empty or contains invalid characters",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=True,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        # Format message with trailers
        trailers = [
            f"Validation-ID: {gate_result.validation_result_id}",
            f"Validation-Policy: {gate_result.policy_name or 'unspecified'}",
            "Commit-Gate: passed",
            f"Authorized-By: {authorization.actor}",
        ]
        formatted_message = f"{raw_msg}\n\n" + "\n".join(trailers)

        # 5. Safe repository state check
        try:
            initial_state = self.git_repository.inspect_state(repository_path)
        except (CommitGateRepositoryError, OSError, ValueError) as exc:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.REPOSITORY_STATE_UNSAFE,
                        message=f"Failed inspecting repository state: {exc}",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=True,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        if not initial_state.is_safe_for_commit:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.REPOSITORY_STATE_UNSAFE,
                        message="Repository state is unsafe (e.g. merge/rebase in progress, index lock, or not git repo)",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=True,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        # 6. Resolve files to stage
        target_files: list[Path] = []
        if files_to_commit:
            target_files.extend(files_to_commit)
        if validated_files:
            for vf in validated_files:
                if vf not in target_files:
                    target_files.append(vf)

        try:
            if target_files:
                self.git_repository.stage_files(repository_path, target_files)
        except UnsafeRepositoryStateError as exc:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.REPOSITORY_STATE_UNSAFE,
                        message=f"Staging failed due to unsafe path: {exc.message}",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=True,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )
        except ProvisionalCommitError as exc:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.COMMIT_FAILED,
                        message=f"Staging failed: {exc.message}",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=True,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        # Inspect state after staging
        post_stage_state = self.git_repository.inspect_state(repository_path)
        if len(post_stage_state.staged_files) == 0:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.NO_CHANGES_TO_COMMIT,
                        message="No staged changes found in repository to commit",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=True,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        # Scope enforcement: verify staged files against target_files (if target_files specified)
        if target_files:
            target_set: set[Path] = set()
            repo_abs = repository_path.resolve()
            for tf in target_files:
                try:
                    rel = (
                        Path(tf).relative_to(repo_abs)
                        if Path(tf).is_absolute()
                        else Path(tf)
                    )
                except ValueError:
                    rel = Path(tf)
                target_set.add(rel)

            for staged_file in post_stage_state.staged_files:
                if staged_file not in target_set:
                    return CommitGateResult(
                        allowed=False,
                        validation_result_id=gate_result.validation_result_id,
                        reasons=gate_result.reasons
                        + (
                            CommitGateReason(
                                code=CommitGateReasonCode.UNAUTHORIZED_FILES_STAGED,
                                message=f"Index contains staged file '{staged_file}' outside authorized scope",
                                metadata={"unauthorized_file": str(staged_file)},
                            ),
                        ),
                        blocking_findings=gate_result.blocking_findings,
                        policy_name=gate_result.policy_name,
                        evaluated_at=gate_result.evaluated_at,
                        authorization_required=gate_result.authorization_required,
                        authorized=True,
                        commit_requested=True,
                        commit_created=False,
                        metadata=meta,
                    )

        # 7. Execute commit
        try:
            commit_hash = self.git_repository.create_commit(
                repository_path, formatted_message
            )
        except ProvisionalCommitError as exc:
            return CommitGateResult(
                allowed=False,
                validation_result_id=gate_result.validation_result_id,
                reasons=gate_result.reasons
                + (
                    CommitGateReason(
                        code=CommitGateReasonCode.COMMIT_FAILED,
                        message=f"Git commit failed: {exc.message}",
                    ),
                ),
                blocking_findings=gate_result.blocking_findings,
                policy_name=gate_result.policy_name,
                evaluated_at=gate_result.evaluated_at,
                authorization_required=gate_result.authorization_required,
                authorized=True,
                commit_requested=True,
                commit_created=False,
                metadata=meta,
            )

        meta["provisional_commit"] = {
            "created_by_actor": authorization.actor,
            "commit_hash": commit_hash,
            "staged_count": len(post_stage_state.staged_files),
        }

        return CommitGateResult(
            allowed=True,
            validation_result_id=gate_result.validation_result_id,
            reasons=gate_result.reasons,
            blocking_findings=gate_result.blocking_findings,
            policy_name=gate_result.policy_name,
            evaluated_at=gate_result.evaluated_at,
            authorization_required=gate_result.authorization_required,
            authorized=True,
            commit_requested=True,
            commit_created=True,
            commit_hash=commit_hash,
            commit_message=formatted_message,
            metadata=meta,
        )


__all__ = ["ProvisionalCommitService"]
