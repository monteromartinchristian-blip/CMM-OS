"""Executor for real selected-symbol module extraction."""

import libcst as cst

from cmm.execution.execution_result import ExecutionResult
from cmm.execution.operation_executor import OperationExecutor
from cmm.execution.python.python_module_editor import PythonModuleEditor
from cmm.execution.python.python_module_writer import PythonModuleWriter
from cmm.execution.python.semantic_context import SemanticContext
from cmm.execution.python.visitors import (
    AppendSelectedSymbolsTransformer,
    DeleteSelectedSymbolsTransformer,
    UpdateSelectedImportsTransformer,
)
from cmm.transformations.execution_request import ExecutionRequest
from cmm.transformations.operation import TransformationOperation
from cmm.transformations.operations import ExtractModuleOperation


class PythonExtractModuleExecutor(OperationExecutor):
    @property
    def operation_type(self) -> type[TransformationOperation]:
        return ExtractModuleOperation

    def __init__(self, writer: PythonModuleWriter | None = None) -> None:
        self._writer = writer or PythonModuleWriter()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        operation = request.operation
        if not isinstance(operation, ExtractModuleOperation):
            return ExecutionResult(False, operation, ("Unsupported operation",))
        context = request.metadata.get("semantic_context")
        if not isinstance(context, SemanticContext):
            return ExecutionResult(False, operation, ("Missing SemanticContext",))
        source = next((item for item in context.snapshot.modules if item.module_name == operation.source_module), None)
        target = next((item for item in context.snapshot.modules if item.module_name == operation.target_module), None)
        if source is None or source.parsed_module is None or target is None or target.parsed_module is None:
            return ExecutionResult(False, operation, ("Source or target module not found",))
        selected = []
        names = frozenset(operation.symbols)
        for statement in source.parsed_module.body:
            if isinstance(statement, (cst.FunctionDef, cst.ClassDef)) and statement.name.value in names:
                selected.append(statement)
        if len(selected) != len(names):
            return ExecutionResult(False, operation, ("Selected symbol not found",))
        selected_symbols = tuple(selected)
        selected_loaded = set()
        for symbol in selected_symbols:
            selected_loaded.update(self._loaded_names(symbol))
        imports = []
        existing_import_code = {
            cst.Module(body=(statement,)).code
            for statement in target.parsed_module.body
            if isinstance(statement, cst.SimpleStatementLine)
            and any(isinstance(small, (cst.Import, cst.ImportFrom)) for small in statement.body)
        }
        for statement in source.parsed_module.body:
            if not isinstance(statement, cst.SimpleStatementLine):
                continue
            for small in statement.body:
                if not isinstance(small, (cst.Import, cst.ImportFrom)):
                    continue
                if isinstance(small, cst.ImportFrom) and (small.relative or isinstance(small.names, cst.ImportStar)):
                    return ExecutionResult(False, operation, ("Unsupported source import dependency",))
                imported_names = {
                    self._name(item.name) for item in small.names
                } if isinstance(small, cst.ImportFrom) and not isinstance(small.names, cst.ImportStar) else {
                    self._name(item.name).split(".", 1)[0] for item in small.names
                }
                if imported_names & selected_loaded and cst.Module(body=(statement,)).code not in existing_import_code:
                    imports.append(statement)
        updated_target = PythonModuleEditor(target).apply(
            AppendSelectedSymbolsTransformer(selected_symbols, tuple(imports))
        )
        updated_source = PythonModuleEditor(source).apply(
            DeleteSelectedSymbolsTransformer(names)
        )
        written = []
        if self._writer.write(updated_target):
            written.append(updated_target.path)
        if self._writer.write(updated_source):
            written.append(updated_source.path)
        for module in context.snapshot.modules:
            if module.parsed_module is None:
                continue
            transformer = UpdateSelectedImportsTransformer(
                operation.source_module,
                operation.target_module,
                names,
            )
            updated = PythonModuleEditor(module).apply(transformer)
            if transformer.changed and self._writer.write(updated):
                written.append(updated.path)
        return ExecutionResult(True, operation, created_paths=tuple(written))

    def _loaded_names(self, node: cst.CSTNode) -> set[str]:
        names = set()

        class Collector(cst.CSTVisitor):
            def visit_Name(self, name: cst.Name) -> None:
                names.add(name.value)

        node.visit(Collector())
        return names

    def _name(self, node: cst.Name | cst.Attribute) -> str:
        if isinstance(node, cst.Name):
            return node.value
        return f"{self._name(node.value)}.{node.attr.value}"
