"""Phase 10.5 – Shared scan session for security + fragmentation.

Single walk + read cache shared across validators.
"""

from __future__ import annotations

import os
from pathlib import Path


class ScanIssue:
    __slots__ = ("category", "extra", "path")

    def __init__(self, category: str, path: str | None = None, **extra: object) -> None:
        self.category = category
        self.path = path
        self.extra = extra


class DomainValidationScanSession:
    """Shared, immutable scan state built once per validation.

    Responsibilities:
    - walk once with symlink safety
    - max_files, max_depth
    - deterministic order
    - cache read bytes
    - enforce max_file_bytes, max_total_bytes
    """

    def __init__(
        self,
        root: Path,
        *,
        max_files: int,
        max_file_bytes: int,
        max_total_bytes: int,
        max_depth: int,
    ) -> None:
        root_resolved = root.resolve()
        self.root = root_resolved
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes

        # Walk
        files, issues = _safe_walk(
            root_resolved, max_files=max_files, max_depth=max_depth
        )
        self.files: tuple[Path, ...] = tuple(files)
        self.issues: tuple[ScanIssue, ...] = tuple(
            ScanIssue(i["category"], i.get("path"), **i.get("extra", {}))
            for i in issues
        )

        self._cache: dict[Path, bytes] = {}
        self.bytes_read: int = 0
        self._closed: bool = False

    def read(self, rel_path: Path) -> bytes:
        """Read file content, caching and enforcing total_bytes."""
        if rel_path in self._cache:
            return self._cache[rel_path]

        abs_path = self.root / rel_path
        # Bounded read
        with abs_path.open("rb") as handle:
            data = handle.read(self.max_file_bytes + 1)
        if len(data) > self.max_file_bytes:
            raise _FileTooLargeError(abs_path, self.max_file_bytes, len(data))

        content = data[: self.max_file_bytes]
        self.bytes_read += len(content)
        if self.bytes_read > self.max_total_bytes:
            raise _TotalBytesExceededError(self.max_total_bytes, self.bytes_read)

        self._cache[rel_path] = content
        return content

    @property
    def exceeded_total(self) -> bool:
        return self.bytes_read > self.max_total_bytes


class _FileTooLargeError(Exception):
    def __init__(self, path: Path, max_bytes: int, actual: int) -> None:
        super().__init__(f"File {path} exceeds max size")
        self.path = path
        self.max_bytes = max_bytes
        self.actual = actual


class _TotalBytesExceededError(Exception):
    def __init__(self, max_total: int, actual: int) -> None:
        super().__init__(f"Total bytes exceeded {max_total}")
        self.max_total = max_total
        self.actual = actual


def _safe_walk(
    root: Path,
    *,
    max_files: int,
    max_depth: int,
) -> tuple[list[Path], list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    files: list[Path] = []
    visited_dirs: set[Path] = set()

    try:
        for dirpath_str, dirnames, filenames in os.walk(str(root)):
            dirpath = Path(dirpath_str)
            dir_real = dirpath.resolve()

            if dir_real in visited_dirs:
                dirnames.clear()
                continue
            visited_dirs.add(dir_real)

            try:
                dir_real.relative_to(root)
            except ValueError:
                dirnames.clear()
                issues.append({"category": "directory_escape", "path": str(dirpath)})
                continue

            try:
                rel = dirpath.relative_to(root)
            except ValueError:
                rel = dirpath
            if len(rel.parts) > max_depth:
                dirnames.clear()
                continue

            dirnames.sort()
            filenames.sort()

            for fname in filenames:
                if len(files) >= max_files:
                    issues.append(
                        {"category": "too_many_files", "extra": {"limit": max_files}}
                    )
                    return files, issues

                filepath = dirpath / fname
                file_real = filepath.resolve()
                try:
                    file_real.relative_to(root)
                except ValueError:
                    issues.append(
                        {
                            "category": "symlink_escape",
                            "path": str(filepath.relative_to(root)),
                        }
                    )
                    continue
                files.append(filepath.relative_to(root))
    except OSError:
        issues.append({"category": "walk_error"})
        return files, issues

    return files, issues


__all__ = ["DomainValidationScanSession", "ScanIssue"]
