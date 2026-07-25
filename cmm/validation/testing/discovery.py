from __future__ import annotations

import os
from pathlib import Path

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


def _is_test_filename(name: str) -> bool:
    lower = name.lower()
    return (lower.startswith("test_") and lower.endswith(".py")) or lower.endswith(
        "_test.py"
    )


def discover_tests(project_root: Path) -> tuple[Path, ...]:
    root = project_root.resolve(strict=False)
    tests_root = root / "tests"
    if not tests_root.exists():
        return ()

    discovered: list[Path] = []
    seen: set[Path] = set()

    for current_root, dirs, files in os.walk(
        tests_root, topdown=True, followlinks=False
    ):
        dirs[:] = [
            d
            for d in sorted(dirs)
            if d not in _EXCLUDED_DIRS
            and not os.path.islink(os.path.join(current_root, d))
        ]
        for filename in sorted(files):
            if not _is_test_filename(filename):
                continue
            full_path = Path(current_root) / filename
            if full_path.is_symlink() or not full_path.is_file():
                continue
            try:
                rel_path = full_path.resolve(strict=False).relative_to(root)
            except Exception:
                continue
            if rel_path in seen:
                continue
            seen.add(rel_path)
            discovered.append(rel_path)

    return tuple(sorted(discovered, key=str))


def classify_test_path(path: Path) -> str:
    normalized = str(path).replace("\\", "/").lower()
    parts = [part.lower() for part in Path(path).parts]
    if "integration" in parts or "e2e" in parts:
        return "integration"
    name = Path(path).name.lower()
    if "integration" in name or "e2e" in name:
        return "integration"
    if normalized.startswith("tests/") and "/integration/" in normalized:
        return "integration"
    return "unit"
