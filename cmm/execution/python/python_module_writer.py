"""Writer for persisting generated LibCST module code."""

from __future__ import annotations

from cmm.execution.python.python_project_parser import PythonModuleInfo


class PythonModuleWriter:
    """Write a parsed module only when its generated code has changed."""

    def write(self, module_info: PythonModuleInfo) -> bool:
        """Persist ``module_info`` code and return whether a write occurred."""
        if module_info.parsed_module is None:
            raise ValueError("PythonModuleInfo must contain a parsed module.")

        code = module_info.parsed_module.code
        if (
            module_info.path.exists()
            and module_info.path.read_text(encoding="utf-8") == code
        ):
            return False

        module_info.path.write_text(code, encoding="utf-8")
        return True
