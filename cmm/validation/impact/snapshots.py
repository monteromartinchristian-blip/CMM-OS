from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from cmm.validation.context import ValidationContext
from cmm.validation.errors import ValidationContractError

from .contracts import (
    ChangeSet,
    ChangeType,
    FileChange,
    FileChangeKind,
    FileVersion,
    ProjectSnapshot,
)
from .git import GitChangeSetAdapter, GitSnapshotBundle

_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "site-packages",
}


@dataclass(frozen=True, slots=True)
class ChangeSetBuilder:
    git_adapter: GitChangeSetAdapter | None = None

    def build(
        self,
        *,
        project_root: Path,
        before_root: Path | None = None,
        after_root: Path | None = None,
        changed_files: Iterable[Path | str] | None = None,
        git_ref: str | None = None,
    ) -> ChangeSet:
        root = Path(project_root).resolve(strict=False)

        if git_ref is not None:
            adapter = self.git_adapter or GitChangeSetAdapter()
            bundle = adapter.snapshot_pair(root, git_ref)
            return self._compare_snapshots(
                project_root=root,
                before=bundle.before,
                after=bundle.after,
                source="git",
                rename_hints=bundle.rename_hints,
                uncertainty=(f"git_ref:{git_ref}",),
                requires_full_suite=False,
            )

        if before_root is not None or after_root is not None:
            before = _scan_project_snapshot(before_root or root, source="before")
            after = _scan_project_snapshot(after_root or root, source="after")
            return self._compare_snapshots(
                project_root=root,
                before=before,
                after=after,
                source="snapshots",
                requires_full_suite=False,
            )

        if changed_files is not None:
            after = _snapshot_selected_files(root, changed_files, source="after")
            return self._compare_explicit_files(
                project_root=root,
                after=after,
                changed_files=tuple(Path(str(item)) for item in changed_files),
            )

        after = _scan_project_snapshot(root, source="after")
        return self._compare_snapshots(
            project_root=root,
            before=ProjectSnapshot(root=root, source="before", files=()),
            after=after,
            source="snapshots",
            requires_full_suite=False,
        )

    def _compare_explicit_files(
        self,
        *,
        project_root: Path,
        after: ProjectSnapshot,
        changed_files: tuple[Path, ...],
    ) -> ChangeSet:
        file_changes: list[FileChange] = []
        after_map = {str(item.path): item for item in after.files}
        for raw_path in sorted({Path(str(path)) for path in changed_files}, key=str):
            key = str(raw_path)
            after_version = after_map.get(key)
            if after_version is None:
                if (project_root / raw_path).exists():
                    after_version = _version_from_path(
                        project_root / raw_path, source="after"
                    )
            file_changes.append(
                FileChange(
                    before_path=None,
                    after_path=raw_path,
                    kind=FileChangeKind.MODIFIED
                    if after_version is not None
                    else FileChangeKind.UNKNOWN,
                    before=None,
                    after=after_version,
                    confidence=0.6 if after_version is not None else 0.4,
                    reasons=("explicit_changed_file",),
                )
            )
        change_type = _classify_change(file_changes)
        return ChangeSet(
            project_root=project_root,
            before_root=None,
            after_root=project_root,
            file_changes=tuple(file_changes),
            change_type=change_type,
            confidence=0.6 if file_changes else 1.0,
            requires_full_suite=bool(file_changes),
            source="explicit",
            uncertainty=("no_before_snapshot",),
            metadata={"changed_files": [str(path) for path in changed_files]},
        )

    def _compare_snapshots(
        self,
        *,
        project_root: Path,
        before: ProjectSnapshot,
        after: ProjectSnapshot,
        source: str,
        rename_hints: tuple[tuple[str, str], ...] = (),
        uncertainty: tuple[str, ...] = (),
        requires_full_suite: bool,
    ) -> ChangeSet:
        before_map = {str(item.path): item for item in before.files}
        after_map = {str(item.path): item for item in after.files}
        deleted = {
            path: before_map[path]
            for path in sorted(before_map.keys() - after_map.keys())
        }
        added = {
            path: after_map[path]
            for path in sorted(after_map.keys() - before_map.keys())
        }
        modified = {
            path
            for path in sorted(before_map.keys() & after_map.keys())
            if before_map[path].content_hash != after_map[path].content_hash
        }
        rename_pairs: list[tuple[str, str]] = []
        used_added: set[str] = set()
        used_deleted: set[str] = set()

        hinted = {(old, new) for old, new in rename_hints}
        for old_path, new_path in sorted(hinted):
            if old_path in deleted and new_path in added:
                rename_pairs.append((old_path, new_path))
                used_deleted.add(old_path)
                used_added.add(new_path)

        if not rename_pairs:
            for old_path in sorted(deleted):
                old_version = deleted[old_path]
                for new_path in sorted(added):
                    if new_path in used_added:
                        continue
                    if (
                        old_version.content_hash
                        and old_version.content_hash == added[new_path].content_hash
                    ):
                        rename_pairs.append((old_path, new_path))
                        used_deleted.add(old_path)
                        used_added.add(new_path)
                        break

        file_changes: list[FileChange] = []
        for old_path, new_path in rename_pairs:
            file_changes.append(
                FileChange(
                    before_path=Path(old_path),
                    after_path=Path(new_path),
                    kind=FileChangeKind.RENAMED,
                    before=deleted[old_path],
                    after=added[new_path],
                    confidence=0.95,
                    reasons=("hash_match_rename",),
                )
            )

        for path in sorted(modified):
            file_changes.append(
                FileChange(
                    before_path=Path(path),
                    after_path=Path(path),
                    kind=FileChangeKind.MODIFIED,
                    before=before_map[path],
                    after=after_map[path],
                    confidence=0.95,
                    reasons=("content_hash_changed",),
                )
            )

        for path in sorted(deleted.keys() - used_deleted):
            file_changes.append(
                FileChange(
                    before_path=Path(path),
                    after_path=None,
                    kind=FileChangeKind.DELETED,
                    before=deleted[path],
                    after=None,
                    confidence=0.9,
                    reasons=("missing_after_snapshot",),
                )
            )

        for path in sorted(added.keys() - used_added):
            file_changes.append(
                FileChange(
                    before_path=None,
                    after_path=Path(path),
                    kind=FileChangeKind.ADDED,
                    before=None,
                    after=added[path],
                    confidence=0.9,
                    reasons=("missing_before_snapshot",),
                )
            )

        change_type = _classify_change(file_changes)
        confidence = 1.0
        if rename_pairs:
            confidence -= 0.05
        if modified:
            confidence -= 0.05
        if file_changes and not (rename_pairs or modified):
            confidence -= 0.1
        confidence = max(0.0, confidence)
        return ChangeSet(
            project_root=project_root,
            before_root=before.root,
            after_root=after.root,
            file_changes=tuple(
                sorted(
                    file_changes,
                    key=lambda item: str(item.after_path or item.before_path),
                )
            ),
            change_type=change_type,
            confidence=confidence,
            requires_full_suite=requires_full_suite,
            source=source,
            uncertainty=tuple(sorted(dict.fromkeys(uncertainty))),
            metadata={
                "rename_hints": [list(pair) for pair in rename_hints],
                "before_count": len(before.files),
                "after_count": len(after.files),
            },
        )


def _scan_project_snapshot(root: Path, *, source: str) -> ProjectSnapshot:
    project_root = Path(root).resolve(strict=False)
    files: list[FileVersion] = []
    if not project_root.exists():
        return ProjectSnapshot(root=project_root, source=source, files=tuple())
    for current_root, dirs, filenames in os.walk(
        project_root, topdown=True, followlinks=False
    ):
        dirs[:] = [
            d
            for d in sorted(dirs)
            if d not in _EXCLUDED_DIRS
            and not os.path.islink(os.path.join(current_root, d))
        ]
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            if path.is_symlink() or not path.is_file():
                continue
            try:
                relative = path.relative_to(project_root)
            except ValueError:
                continue
            files.append(
                _version_from_path(path, source=source, relative_path=relative)
            )
    return ProjectSnapshot(
        root=project_root,
        source=source,
        files=tuple(sorted(files, key=lambda item: str(item.path))),
    )


def _snapshot_selected_files(
    root: Path, changed_files: Iterable[Path | str], *, source: str
) -> ProjectSnapshot:
    project_root = Path(root).resolve(strict=False)
    files: list[FileVersion] = []
    for raw_path in sorted({Path(str(item)) for item in changed_files}, key=str):
        path = raw_path if raw_path.is_absolute() else project_root / raw_path
        if not path.exists() or not path.is_file():
            files.append(
                FileVersion(
                    path=raw_path,
                    exists=False,
                    content_hash="",
                    source=source,
                    content=None,
                    metadata={"missing": True},
                )
            )
            continue
        relative = (
            raw_path if not raw_path.is_absolute() else path.relative_to(project_root)
        )
        files.append(_version_from_path(path, source=source, relative_path=relative))
    return ProjectSnapshot(
        root=project_root,
        source=source,
        files=tuple(sorted(files, key=lambda item: str(item.path))),
    )


def _version_from_path(
    path: Path, *, source: str, relative_path: Path | None = None
) -> FileVersion:
    current = Path(path)
    data = current.read_bytes()
    content = data.decode("utf-8", errors="replace")
    try:
        relative = relative_path or current
    except Exception:
        relative = current
    try:
        exists = current.exists()
    except OSError:
        exists = False
    return FileVersion(
        path=relative if isinstance(relative, Path) else Path(str(relative)),
        exists=exists,
        content_hash=hashlib.sha256(data).hexdigest(),
        source=source,
        content=content,
        metadata={"size": len(data)},
    )


def _classify_change(file_changes: list[FileChange]) -> ChangeType:
    if not file_changes:
        return ChangeType.UNKNOWN
    kinds = {item.kind for item in file_changes}
    if FileChangeKind.RENAMED in kinds:
        return ChangeType.RENAMED_FILE
    if FileChangeKind.MODIFIED in kinds:
        return ChangeType.STRUCTURAL_CHANGE
    if kinds == {FileChangeKind.ADDED}:
        return ChangeType.NEW_FILE
    if kinds == {FileChangeKind.DELETED}:
        return ChangeType.DELETED_FILE
    if FileChangeKind.ADDED in kinds or FileChangeKind.DELETED in kinds:
        return ChangeType.STRUCTURAL_CHANGE
    return ChangeType.UNKNOWN
