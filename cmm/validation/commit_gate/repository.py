from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..exceptions import ValidationErrorBase


class CommitGateRepositoryError(ValidationErrorBase):
    pass


class UnsafeRepositoryStateError(CommitGateRepositoryError):
    pass


class ProvisionalCommitError(CommitGateRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class RepositoryState:
    is_git_repository: bool
    is_clean: bool
    work_tree_exists: bool
    is_merge_in_progress: bool
    is_rebase_in_progress: bool
    is_cherry_pick_in_progress: bool
    is_revert_in_progress: bool
    has_index_lock: bool
    staged_files: tuple[Path, ...] = ()
    unstaged_files: tuple[Path, ...] = ()
    untracked_files: tuple[Path, ...] = ()
    head_commit: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "staged_files", tuple(self.staged_files or ()))
        object.__setattr__(self, "unstaged_files", tuple(self.unstaged_files or ()))
        object.__setattr__(self, "untracked_files", tuple(self.untracked_files or ()))

    @property
    def is_safe_for_commit(self) -> bool:
        return (
            self.is_git_repository
            and self.work_tree_exists
            and not self.is_merge_in_progress
            and not self.is_rebase_in_progress
            and not self.is_cherry_pick_in_progress
            and not self.is_revert_in_progress
            and not self.has_index_lock
        )


class GitRepositoryProtocol(Protocol):
    """Protocol defining required Git operations for provisional commit creation."""

    def inspect_state(self, repository_path: Path) -> RepositoryState: ...

    def stage_files(self, repository_path: Path, files: Sequence[Path]) -> None: ...

    def create_commit(self, repository_path: Path, message: str) -> str: ...


class SubprocessGitRepository:
    """Concrete Subprocess-based implementation of GitRepositoryProtocol.

    Enforces strict security rules:
    - Never uses shell=True
    - Restricts commands to git status, diff, rev-parse, add, commit
    - Validates file paths to prevent traversal or outside-repo additions
    - Strictly checks process output and timeouts
    """

    def __init__(self, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def _run_git(
        self, repository_path: Path, args: Sequence[str]
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["git"] + list(args)
        try:
            res = subprocess.run(
                cmd,
                cwd=str(repository_path),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return res
        except Exception as exc:
            raise ProvisionalCommitError(
                code="git_subprocess_failure",
                message=f"Failed to execute command '{' '.join(cmd)}': {exc}",
            ) from exc

    def _get_git_dir(self, repository_path: Path) -> Path | None:
        res = self._run_git(repository_path, ["rev-parse", "--git-dir"])
        if res.returncode != 0:
            return None
        git_dir_str = res.stdout.strip()
        git_dir = Path(git_dir_str)
        if not git_dir.is_absolute():
            git_dir = (repository_path / git_dir).resolve()
        return git_dir

    def inspect_state(self, repository_path: Path) -> RepositoryState:
        if not repository_path.exists() or not repository_path.is_dir():
            return RepositoryState(
                is_git_repository=False,
                is_clean=False,
                work_tree_exists=False,
                is_merge_in_progress=False,
                is_rebase_in_progress=False,
                is_cherry_pick_in_progress=False,
                is_revert_in_progress=False,
                has_index_lock=False,
            )

        git_dir = self._get_git_dir(repository_path)
        if git_dir is None or not git_dir.exists():
            return RepositoryState(
                is_git_repository=False,
                is_clean=False,
                work_tree_exists=False,
                is_merge_in_progress=False,
                is_rebase_in_progress=False,
                is_cherry_pick_in_progress=False,
                is_revert_in_progress=False,
                has_index_lock=False,
            )

        is_merge = (git_dir / "MERGE_HEAD").exists()
        is_rebase = (git_dir / "rebase-merge").exists() or (
            git_dir / "rebase-apply"
        ).exists()
        is_cherry_pick = (git_dir / "CHERRY_PICK_HEAD").exists()
        is_revert = (git_dir / "REVERT_HEAD").exists()
        has_index_lock = (git_dir / "index.lock").exists()

        status_res = self._run_git(repository_path, ["status", "--porcelain", "-z"])
        staged: list[Path] = []
        unstaged: list[Path] = []
        untracked: list[Path] = []

        if status_res.returncode == 0:
            # Porcelain format with -z (NUL terminated)
            lines = status_res.stdout.split("\0")
            for line in lines:
                if not line or len(line) < 3:
                    continue
                x = line[0]
                y = line[1]
                file_str = line[3:]
                p = Path(file_str)
                if x in ("M", "A", "D", "R", "C"):
                    staged.append(p)
                if y in ("M", "D"):
                    unstaged.append(p)
                if x == "?" and y == "?":
                    untracked.append(p)

        head_res = self._run_git(repository_path, ["rev-parse", "HEAD"])
        head_commit = head_res.stdout.strip() if head_res.returncode == 0 else None

        is_clean = len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0

        return RepositoryState(
            is_git_repository=True,
            is_clean=is_clean,
            work_tree_exists=True,
            is_merge_in_progress=is_merge,
            is_rebase_in_progress=is_rebase,
            is_cherry_pick_in_progress=is_cherry_pick,
            is_revert_in_progress=is_revert,
            has_index_lock=has_index_lock,
            staged_files=tuple(staged),
            unstaged_files=tuple(unstaged),
            untracked_files=tuple(untracked),
            head_commit=head_commit,
        )

    def stage_files(self, repository_path: Path, files: Sequence[Path]) -> None:
        if not files:
            return
        repo_abs = repository_path.resolve()
        validated_paths: list[str] = []

        for f in files:
            p = Path(f)
            # Prevent path traversal
            if p.is_absolute():
                try:
                    rel = p.relative_to(repo_abs)
                    p_str = str(rel)
                except ValueError as exc:
                    raise UnsafeRepositoryStateError(
                        code="file_outside_repository",
                        message=f"Path '{f}' is outside repository '{repository_path}'",
                    ) from exc
            else:
                p_str = str(p)

            if ".." in Path(p_str).parts:
                raise UnsafeRepositoryStateError(
                    code="path_traversal_attempt",
                    message=f"Path traversal detected in path '{f}'",
                )
            validated_paths.append(p_str)

        # Execute git add -- file1 file2 ...
        res = self._run_git(repository_path, ["add", "--"] + validated_paths)
        if res.returncode != 0:
            raise ProvisionalCommitError(
                code="git_add_failed",
                message=f"git add failed: {res.stderr.strip()}",
            )

    def create_commit(self, repository_path: Path, message: str) -> str:
        if not message or not message.strip():
            raise ProvisionalCommitError(
                code="empty_commit_message", message="Commit message cannot be empty"
            )

        if "\x00" in message:
            raise ProvisionalCommitError(
                code="invalid_commit_message",
                message="Commit message contains null bytes",
            )

        res = self._run_git(repository_path, ["commit", "-m", message])
        if res.returncode != 0:
            raise ProvisionalCommitError(
                code="git_commit_failed",
                message=f"git commit failed: {res.stderr.strip() or res.stdout.strip()}",
            )

        head_res = self._run_git(repository_path, ["rev-parse", "HEAD"])
        if head_res.returncode != 0 or not head_res.stdout.strip():
            raise ProvisionalCommitError(
                code="git_rev_parse_failed",
                message="Could not retrieve commit hash after commit",
            )

        return head_res.stdout.strip()


__all__ = [
    "CommitGateRepositoryError",
    "GitRepositoryProtocol",
    "ProvisionalCommitError",
    "RepositoryState",
    "SubprocessGitRepository",
    "UnsafeRepositoryStateError",
]
