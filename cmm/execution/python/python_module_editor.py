"""Immutable LibCST editor for parsed Python module information."""

from __future__ import annotations

from dataclasses import dataclass, replace

import libcst as cst

from cmm.execution.python.python_project_parser import PythonModuleInfo


@dataclass(frozen=True)
class PythonModuleEditor:
    """Apply LibCST transformers without mutating the source module information."""

    module_info: PythonModuleInfo

    @property
    def module(self) -> cst.Module:
        """Return the parsed module exposed by this editor."""
        if self.module_info.parsed_module is None:
            raise ValueError("PythonModuleInfo must contain a parsed module.")
        return self.module_info.parsed_module

    def apply(self, transformer: cst.CSTTransformer) -> PythonModuleInfo:
        """Apply ``transformer`` and return new immutable module information."""
        updated_module = self.module.visit(transformer)
        if not isinstance(updated_module, cst.Module):
            raise TypeError("Module transformer must return a LibCST Module.")
        return replace(self.module_info, parsed_module=updated_module)
