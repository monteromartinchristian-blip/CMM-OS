"""Read-only Git service used by execution-layer executors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass(frozen=True)
class GitServiceError(Exception):
    """Structured error raised by GitService operations."""

    code: str
    message: str


class GitService:
    """Run read-only Git commands for a repository root."""

    def status(self, path: Path) -> dict[str, object]:
        repository_root = self._repository_root(path)
        porcelain = self._run(repository_root, "status", "--porcelain")
        short = self._run(repository_root, "status", "--short", "--branch")
        return {
            "repository": str(repository_root),
            "porcelain": porcelain,
            "short": short,
        }

    def current_branch(self, path: Path) -> dict[str, object]:
        repository_root = self._repository_root(path)
        branch = self._run(repository_root, "branch", "--show-current")
        return {
            "repository": str(repository_root),
            "branch": branch,
        }

    def list_branches(self, path: Path) -> dict[str, object]:
        repository_root = self._repository_root(path)
        output = self._run(repository_root, "branch", "--format=%(refname:short)")
        branches = [line for line in output.splitlines() if line.strip()]
        return {
            "repository": str(repository_root),
            "branches": branches,
        }

    def log(self, path: Path, limit: int) -> dict[str, object]:
        repository_root = self._repository_root(path)
        output = self._run(
            repository_root,
            "log",
            f"--max-count={limit}",
            "--pretty=format:%H%x1f%an%x1f%ad%x1f%s",
            "--date=iso-strict",
        )
        entries = []
        for line in output.splitlines():
            if not line.strip():
                continue
            commit, author, date, subject = (line.split("\x1f", maxsplit=3) + ["", "", "", ""])[:4]
            entries.append(
                {
                    "commit": commit,
                    "author": author,
                    "date": date,
                    "subject": subject,
                }
            )

        return {
            "repository": str(repository_root),
            "entries": entries,
        }

    def diff(self, path: Path, ref: str) -> dict[str, object]:
        repository_root = self._repository_root(path)
        output = self._run(repository_root, "diff", ref)
        return {
            "repository": str(repository_root),
            "ref": ref,
            "diff": output,
        }

    def show(self, path: Path, git_object: str) -> dict[str, object]:
        repository_root = self._repository_root(path)
        output = self._run(repository_root, "show", "--no-color", git_object)
        return {
            "repository": str(repository_root),
            "object": git_object,
            "output": output,
        }

    def list_tags(self, path: Path) -> dict[str, object]:
        repository_root = self._repository_root(path)
        output = self._run(repository_root, "tag", "--list")
        tags = [line for line in output.splitlines() if line.strip()]
        return {
            "repository": str(repository_root),
            "tags": tags,
        }

    def _repository_root(self, path: Path) -> Path:
        candidate = Path(path)
        if not candidate.exists():
            raise GitServiceError("not_found", "Repository path not found.")

        directory = candidate if candidate.is_dir() else candidate.parent
        try:
            root = self._run(directory, "rev-parse", "--show-toplevel")
        except GitServiceError as error:
            if error.code in {"not_git_repository", "command_failed"}:
                raise GitServiceError("not_git_repository", "Path is not a Git repository.")
            raise

        return Path(root)

    def _run(self, cwd: Path, *args: str) -> str:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise GitServiceError("git_not_available", "Git command is not available.") from error
        except OSError as error:
            raise GitServiceError("os_error", f"Unable to execute git command: {error}") from error

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            if "not a git repository" in stderr.lower():
                raise GitServiceError("not_git_repository", "Path is not a Git repository.")
            raise GitServiceError("command_failed", stderr or "Git command failed.")

        return (completed.stdout or "").strip()
