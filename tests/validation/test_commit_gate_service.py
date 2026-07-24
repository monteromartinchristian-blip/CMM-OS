from collections.abc import Sequence
from pathlib import Path

from cmm.validation.commit_gate.authorization import CommitAuthorization
from cmm.validation.commit_gate.enums import CommitGateReasonCode
from cmm.validation.commit_gate.models import CommitGateResult
from cmm.validation.commit_gate.repository import (
    GitRepositoryProtocol,
    ProvisionalCommitError,
    RepositoryState,
)
from cmm.validation.commit_gate.service import ProvisionalCommitService


class FakeGitRepository(GitRepositoryProtocol):
    def __init__(
        self, state: RepositoryState, commit_hash: str = "1234567890abcdef"
    ) -> None:
        self.state = state
        self.commit_hash = commit_hash
        self.staged_calls: list[list[Path]] = []
        self.commit_calls: list[str] = []
        self.fail_commit = False

    def inspect_state(self, repository_path: Path) -> RepositoryState:
        return self.state

    def stage_files(self, repository_path: Path, files: Sequence[Path]) -> None:
        self.staged_calls.append(list(files))
        # update state staged_files
        self.state = RepositoryState(
            is_git_repository=self.state.is_git_repository,
            is_clean=False,
            work_tree_exists=self.state.work_tree_exists,
            is_merge_in_progress=self.state.is_merge_in_progress,
            is_rebase_in_progress=self.state.is_rebase_in_progress,
            is_cherry_pick_in_progress=self.state.is_cherry_pick_in_progress,
            is_revert_in_progress=self.state.is_revert_in_progress,
            has_index_lock=self.state.has_index_lock,
            staged_files=tuple(
                list(self.state.staged_files) + [Path(f) for f in files]
            ),
        )

    def create_commit(self, repository_path: Path, message: str) -> str:
        if self.fail_commit:
            raise ProvisionalCommitError(
                code="git_commit_failed", message="git commit returned exit code 1"
            )
        self.commit_calls.append(message)
        return self.commit_hash


def test_service_create_commit_approved_flow(tmp_path: Path) -> None:
    initial_state = RepositoryState(
        is_git_repository=True,
        is_clean=False,
        work_tree_exists=True,
        is_merge_in_progress=False,
        is_rebase_in_progress=False,
        is_cherry_pick_in_progress=False,
        is_revert_in_progress=False,
        has_index_lock=False,
        unstaged_files=(Path("file1.py"),),
    )
    fake_repo = FakeGitRepository(initial_state, commit_hash="deadbeef1234")
    service = ProvisionalCommitService(fake_repo)

    gate_result = CommitGateResult(
        allowed=True,
        validation_result_id="val-999",
        policy_name="small_change",
    )
    auth = CommitAuthorization(
        authorized=True,
        actor="human:christian",
        reason="Deploy feature 7.10",
        validation_result_id="val-999",
    )

    res = service.create_commit(
        gate_result=gate_result,
        authorization=auth,
        repository_path=tmp_path,
        files_to_commit=[Path("file1.py")],
    )

    assert res.allowed is True
    assert res.authorized is True
    assert res.commit_requested is True
    assert res.commit_created is True
    assert res.commit_hash == "deadbeef1234"
    assert "Authorized-By: human:christian" in res.commit_message
    assert "Validation-ID: val-999" in res.commit_message
    assert len(fake_repo.commit_calls) == 1


def test_service_create_commit_gate_denied(tmp_path: Path) -> None:
    fake_repo = FakeGitRepository(
        RepositoryState(
            is_git_repository=True,
            is_clean=False,
            work_tree_exists=True,
            is_merge_in_progress=False,
            is_rebase_in_progress=False,
            is_cherry_pick_in_progress=False,
            is_revert_in_progress=False,
            has_index_lock=False,
        )
    )
    service = ProvisionalCommitService(fake_repo)

    gate_result = CommitGateResult(
        allowed=False,
        validation_result_id="val-000",
    )
    auth = CommitAuthorization(authorized=True, actor="human:christian")

    res = service.create_commit(gate_result, auth, tmp_path)

    assert res.allowed is False
    assert res.commit_created is False
    assert any(
        r.code == CommitGateReasonCode.VALIDATION_NOT_PASSED for r in res.reasons
    )


def test_service_create_commit_unmatched_validation_id(tmp_path: Path) -> None:
    fake_repo = FakeGitRepository(
        RepositoryState(
            is_git_repository=True,
            is_clean=False,
            work_tree_exists=True,
            is_merge_in_progress=False,
            is_rebase_in_progress=False,
            is_cherry_pick_in_progress=False,
            is_revert_in_progress=False,
            has_index_lock=False,
        )
    )
    service = ProvisionalCommitService(fake_repo)

    gate_result = CommitGateResult(allowed=True, validation_result_id="val-111")
    auth = CommitAuthorization(
        authorized=True, actor="human:christian", validation_result_id="val-222"
    )

    res = service.create_commit(gate_result, auth, tmp_path)

    assert res.allowed is False
    assert res.commit_created is False
    assert any(
        r.code == CommitGateReasonCode.UNMATCHED_VALIDATION_ID for r in res.reasons
    )


def test_service_create_commit_unsafe_repo_state(tmp_path: Path) -> None:
    unsafe_state = RepositoryState(
        is_git_repository=True,
        is_clean=False,
        work_tree_exists=True,
        is_merge_in_progress=True,  # MERGE IN PROGRESS
        is_rebase_in_progress=False,
        is_cherry_pick_in_progress=False,
        is_revert_in_progress=False,
        has_index_lock=False,
    )
    fake_repo = FakeGitRepository(unsafe_state)
    service = ProvisionalCommitService(fake_repo)

    gate_result = CommitGateResult(allowed=True, validation_result_id="val-333")
    auth = CommitAuthorization(authorized=True, actor="human:christian")

    res = service.create_commit(gate_result, auth, tmp_path)

    assert res.allowed is False
    assert res.commit_created is False
    assert any(
        r.code == CommitGateReasonCode.REPOSITORY_STATE_UNSAFE for r in res.reasons
    )
