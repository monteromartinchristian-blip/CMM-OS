"""Common helper functions for CMM OS custom validators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}


@dataclass(frozen=True, slots=True)
class FileReadResult:
    content: str | None
    is_missing: bool = False
    is_unreadable: bool = False
    error_type: str | None = None


def read_file_safe(path: Path, encoding: str = "utf-8") -> FileReadResult:
    """Read file safely, distinguishing missing, unreadable (I/O, permission, decode), and success states."""
    if not path.exists() or not path.is_file():
        return FileReadResult(content=None, is_missing=True)
    try:
        content = path.read_text(encoding=encoding)
        return FileReadResult(content=content)
    except UnicodeDecodeError:
        return FileReadResult(content=None, is_unreadable=True, error_type="UnicodeDecodeError")
    except PermissionError:
        return FileReadResult(content=None, is_unreadable=True, error_type="PermissionError")
    except OSError as exc:
        return FileReadResult(content=None, is_unreadable=True, error_type=type(exc).__name__)


def safe_read_text(path: Path, encoding: str = "utf-8") -> str | None:
    """Safely read text from a file, returning None on read error or missing file."""
    return read_file_safe(path, encoding=encoding).content


def is_ignored_path(path: Path | str) -> bool:
    """Check if a path or any of its components should be ignored."""
    p = Path(path)
    for part in p.parts:
        if part in IGNORED_DIRECTORIES or part.endswith(".egg-info"):
            return True
    return False


def aggregate_status(findings: Sequence[ValidationFinding]) -> ValidationStatus:
    """Determine ValidationStatus based on finding severities and blocking status."""
    if any(
        f.blocking or f.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
        for f in findings
    ):
        return ValidationStatus.FAILED
    if any(f.severity == ValidationSeverity.WARNING for f in findings):
        return ValidationStatus.WARNING
    return ValidationStatus.PASSED


def serialize_path(path: Path | str, project_root: Path) -> str:
    """Convert a path to a relative POSIX string from project_root if possible."""
    p = Path(path)
    try:
        rel = p.relative_to(project_root)
        return rel.as_posix()
    except ValueError:
        return p.as_posix()


def format_syntax_error_info(rel_path: str, exc: SyntaxError) -> Tuple[str, Dict[str, Any]]:
    """Format bounded syntax error message and metadata without exposing source code snippets."""
    line = exc.lineno or 1
    col = exc.offset or 1
    msg = f"Syntax error in '{rel_path}' at line {line}, column {col}."
    meta = {
        "line": line,
        "column": col,
        "exception_type": "SyntaxError",
    }
    return msg, meta
