"""Read-only LibCST parser for reusable Python project snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

import libcst as cst


@dataclass(frozen=True)
class PythonModuleInfo:
    """Parse information for one Python module."""

    path: Path
    module_name: str
    parsed_module: cst.Module | None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class PythonProjectSnapshot:
    """Immutable parse snapshot of a Python project."""

    modules: tuple[PythonModuleInfo, ...]
    errors: tuple[str, ...] = ()


class PythonProjectParser:
    """Build read-only LibCST snapshots while skipping generated directories."""

    _EXCLUDED_DIRECTORIES = {".venv", "__pycache__", ".git", "build", "dist"}

    def parse(self, project_root: Path) -> PythonProjectSnapshot:
        """Parse every Python source file below ``project_root``."""
        modules = []
        errors = []
        for path in self._python_files(project_root):
            module_info = self._parse_module(project_root, path)
            modules.append(module_info)
            errors.extend(module_info.diagnostics)

        return PythonProjectSnapshot(
            modules=tuple(modules),
            errors=tuple(errors),
        )

    def _python_files(self, project_root: Path) -> tuple[Path, ...]:
        paths = []
        for directory, directories, files in os.walk(project_root):
            directories[:] = sorted(
                name
                for name in directories
                if name not in self._EXCLUDED_DIRECTORIES
            )
            current_directory = Path(directory)
            paths.extend(
                current_directory / filename
                for filename in sorted(files)
                if filename.endswith(".py")
            )
        return tuple(paths)

    def _parse_module(self, project_root: Path, path: Path) -> PythonModuleInfo:
        try:
            parsed_module = cst.parse_module(path.read_text(encoding="utf-8"))
        except (OSError, cst.ParserSyntaxError) as error:
            diagnostic = f"{path}: {error}"
            return PythonModuleInfo(
                path=path,
                module_name=self._module_name(project_root, path),
                parsed_module=None,
                diagnostics=(diagnostic,),
            )

        return PythonModuleInfo(
            path=path,
            module_name=self._module_name(project_root, path),
            parsed_module=parsed_module,
        )

    def _module_name(self, project_root: Path, path: Path) -> str:
        parts = list(path.relative_to(project_root).with_suffix("").parts)
        if len(parts) > 1 and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)
