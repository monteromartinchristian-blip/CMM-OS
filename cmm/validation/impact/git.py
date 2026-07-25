from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import FileVersion, ProjectSnapshot


class GitChangeSetError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GitSnapshotBundle:
    before: ProjectSnapshot
    after: ProjectSnapshot
    rename_hints: tuple[tuple[str, str], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class GitChangeSetAdapter:
    def snapshot_pair(self, project_root: Path, ref: str) -> GitSnapshotBundle:
        root = Path(project_root).resolve(strict=True)
        statuses = self._run(root, "diff", "--name-status", "-M", ref, "--").splitlines()
        before_files: list[FileVersion] = []
        after_files: list[FileVersion] = []
        rename_hints: list[tuple[str, str]] = []

        for line in statuses:
            if not line.strip():
                continue
            parts = line.split("\t")
            status = parts[0]
            if status.startswith("R") and len(parts) >= 3:
                old_path, new_path = parts[1], parts[2]
                rename_hints.append((old_path, new_path))
                before_files.append(self._version_from_git(root, ref, old_path, source="before"))
                after_files.append(self._version_from_worktree(root, new_path, source="after"))
                continue
            if len(parts) < 2:
                continue
            path = parts[1]
            if status == "D":
                before_files.append(self._version_from_git(root, ref, path, source="before"))
            elif status == "A":
                after_files.append(self._version_from_worktree(root, path, source="after"))
            else:
                before_files.append(self._version_from_git(root, ref, path, source="before"))
                after_files.append(self._version_from_worktree(root, path, source="after"))

        return GitSnapshotBundle(
            before=ProjectSnapshot(root=root, source="git", files=tuple(before_files), metadata={"ref": ref, "side": "before"}),
            after=ProjectSnapshot(root=root, source="git", files=tuple(after_files), metadata={"ref": ref, "side": "after"}),
            rename_hints=tuple(rename_hints),
            metadata={"ref": ref, "changed_paths": len(statuses)},
        )

    def _version_from_git(self, root: Path, ref: str, relative_path: str, *, source: str) -> FileVersion:
        try:
            content = self._run(root, "show", f"{ref}:{relative_path}")
            exists = True
        except GitChangeSetError:
            content = ""
            exists = False
        path = Path(relative_path)
        return FileVersion(
            path=path,
            exists=exists,
            content_hash=self._sha256(content.encode("utf-8")),
            source=source,
            content=content or None,
            metadata={"git_ref": ref},
        )

    def _version_from_worktree(self, root: Path, relative_path: str, *, source: str) -> FileVersion:
        path = root / relative_path
        if not path.exists() or not path.is_file():
            return FileVersion(
                path=Path(relative_path),
                exists=False,
                content_hash="",
                source=source,
                content=None,
                metadata={"missing": True},
            )
        content = path.read_text(encoding="utf-8", errors="replace")
        return FileVersion(
            path=Path(relative_path),
            exists=True,
            content_hash=self._sha256(content.encode("utf-8")),
            source=source,
            content=content,
            metadata={"git_ref": "WORKTREE"},
        )

    def _run(self, cwd: Path, *args: str) -> str:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise GitChangeSetError("git is not available") from exc
        if completed.returncode != 0:
            raise GitChangeSetError((completed.stderr or completed.stdout or "git command failed").strip())
        return completed.stdout or ""

    def _sha256(self, data: bytes) -> str:
        import hashlib

        return hashlib.sha256(data).hexdigest()
