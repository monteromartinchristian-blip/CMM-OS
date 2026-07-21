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

    def module_contains_symbol(
        self,
        module_name: str,
        symbol_name: str,
        symbol_kind: str | None = None,
    ) -> bool:
        """Return whether a parsed module contains a top-level symbol."""

    def validate_symbol_move_references(
        self,
        source_module: str,
        symbol_name: str,
        target_module: str,
        new_symbol_name: str,
    ) -> tuple[bool, str]:
        """Validate supported references for moving one symbol."""

    def validate_function_dependencies(
        self,
        source_module: str,
        target_module: str,
        symbol_name: str,
    ) -> tuple[bool, str]:
        """Validate dependencies needed by a moved top-level function."""


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
    symbol_kind: str | None = None

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
            self.symbol_kind,
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


@dataclass(frozen=True)
class SymbolAbsentPrecondition:
    """Require that a top-level Python symbol is absent from a module."""

    module_name: str
    symbol_name: str

    @property
    def name(self) -> str:
        return "symbol_absent"

    def evaluate(
        self,
        context: PreconditionContext,
        step_id: str | None = None,
    ) -> PreconditionResult:
        present = context.module_contains_symbol(self.module_name, self.symbol_name)
        return PreconditionResult(
            name=self.name,
            success=not present,
            message=(
                f"Symbol absent: {self.module_name}.{self.symbol_name}"
                if not present
                else f"Symbol already exists: {self.module_name}.{self.symbol_name}"
            ),
            step_id=step_id,
        )


@dataclass(frozen=True)
class SupportedSymbolReferencesPrecondition:
    """Require that references to a moved symbol use supported import forms."""

    source_module: str
    symbol_name: str
    target_module: str
    new_symbol_name: str

    @property
    def name(self) -> str:
        return "supported_symbol_references"

    def evaluate(
        self,
        context: PreconditionContext,
        step_id: str | None = None,
    ) -> PreconditionResult:
        success, message = context.validate_symbol_move_references(
            self.source_module,
            self.symbol_name,
            self.target_module,
            self.new_symbol_name,
        )
        return PreconditionResult(
            name=self.name,
            success=success,
            message=message,
            step_id=step_id,
        )


@dataclass(frozen=True)
class FunctionDependenciesPrecondition:
    """Require moved-function globals to be available in the destination."""

    source_module: str
    target_module: str
    symbol_name: str

    @property
    def name(self) -> str:
        return "function_dependencies"

    def evaluate(
        self,
        context: PreconditionContext,
        step_id: str | None = None,
    ) -> PreconditionResult:
        success, message = context.validate_function_dependencies(
            self.source_module,
            self.target_module,
            self.symbol_name,
        )
        return PreconditionResult(
            name=self.name,
            success=success,
            message=message,
            step_id=step_id,
        )
