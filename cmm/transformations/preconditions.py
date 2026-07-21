"""Typed preconditions for transformation execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PreconditionResult:
    """Structured result of evaluating one transformation precondition."""

    name: str
    success: bool
    message: str
    step_id: str | None = None


class PreconditionContext(Protocol):
    """Project-aware context required by precondition evaluators."""

    project_root: Path

    def resolve_project_path(self, path: str | Path) -> Path:
        """Return an absolute in-project path or raise ValueError."""

    def module_path(self, module_name: str) -> Path:
        """Return the expected Python path for ``module_name``."""

    def module_contains_symbol(self, module_name: str, symbol_name: str) -> bool:
        """Return whether a parsed module contains a top-level symbol."""


@runtime_checkable
class TransformationPrecondition(Protocol):
    """Extensible contract for preconditions evaluated before mutation."""

    @property
    def name(self) -> str:
        """Return a stable precondition name."""

    def evaluate(
        self,
        context: PreconditionContext,
        step_id: str | None = None,
    ) -> PreconditionResult:
        """Evaluate the precondition in a project-aware context."""


@dataclass(frozen=True)
class FileExistsPrecondition:
    """Require an in-project file path to exist."""

    path: str

    @property
    def name(self) -> str:
        return "file_exists"

    def evaluate(
        self,
        context: PreconditionContext,
        step_id: str | None = None,
    ) -> PreconditionResult:
        path = context.resolve_project_path(self.path)
        success = path.is_file()
        return PreconditionResult(
            name=self.name,
            success=success,
            message=f"File exists: {self.path}" if success else f"File not found: {self.path}",
            step_id=step_id,
        )


@dataclass(frozen=True)
class ModuleExistsPrecondition:
    """Require a Python module to exist in the project."""

    module_name: str

    @property
    def name(self) -> str:
        return "module_exists"

    def evaluate(
        self,
        context: PreconditionContext,
        step_id: str | None = None,
    ) -> PreconditionResult:
        path = context.module_path(self.module_name)
        success = path.is_file()
        return PreconditionResult(
            name=self.name,
            success=success,
            message=(
                f"Module exists: {self.module_name}"
                if success
                else f"Module not found: {self.module_name}"
            ),
            step_id=step_id,
        )


@dataclass(frozen=True)
class SymbolExistsPrecondition:
    """Require a top-level Python symbol to exist inside a module."""

    module_name: str
    symbol_name: str

    @property
    def name(self) -> str:
        return "symbol_exists"

    def evaluate(
        self,
        context: PreconditionContext,
        step_id: str | None = None,
    ) -> PreconditionResult:
        module_path = context.module_path(self.module_name)
        success = module_path.is_file() and context.module_contains_symbol(
            self.module_name,
            self.symbol_name,
        )
        return PreconditionResult(
            name=self.name,
            success=success,
            message=(
                f"Symbol exists: {self.module_name}.{self.symbol_name}"
                if success
                else f"Symbol not found: {self.module_name}.{self.symbol_name}"
            ),
            step_id=step_id,
        )
