from __future__ import annotations

from pathlib import Path

from cmm.execution import ExecutionPipeline, ExecutionResult, OperationExecutorRegistry
from cmm.execution.python import (
    PythonCreateModuleExecutor,
    PythonExtractModuleExecutor,
    PythonProjectParser,
    PythonValidateProjectExecutor,
    SemanticContextBuilder,
)
from cmm.transformations import ExecutionPlanner, ExtractModuleTransformation
from cmm.transformations.execution_request import ExecutionRequest


def _registry(validate_executor=None):
    registry = OperationExecutorRegistry()
    registry.register_many([
        PythonCreateModuleExecutor(),
        PythonExtractModuleExecutor(),
        validate_executor or PythonValidateProjectExecutor(),
    ])
    return registry


def _execute(root: Path, symbols: tuple[str, ...], *, create_target=False, validate_executor=None):
    context = SemanticContextBuilder().build(
        PythonProjectParser().parse(root), build_reference_index=True
    )
    plan = ExecutionPlanner().build(
        ExtractModuleTransformation(
            "package.source", "package.target", symbols, create_target=create_target
        ).create_plan("extract module")
    )
    return ExecutionPipeline(_registry(validate_executor), context, root).execute(plan)


def _project(root: Path) -> tuple[Path, Path, Path, Path]:
    package = root / "package"
    package.mkdir()
    init = package / "__init__.py"
    source = package / "source.py"
    target = package / "target.py"
    consumer = package / "consumer.py"
    init.write_text("from package.source import foo\n", encoding="utf-8")
    source.write_text(
        "from package.support import Base\n\n"
        "def foo(value):\n"
        "    return value + 1\n\n"
        "class Service(Base):\n"
        "    pass\n\n"
        "def unrelated():\n"
        "    return 3\n",
        encoding="utf-8",
    )
    target.write_text("", encoding="utf-8")
    consumer.write_text(
        "from package.source import foo\n"
        "value = foo(1)\n"
        "service = Service()\n",
        encoding="utf-8",
    )
    (package / "support.py").write_text("class Base:\n    pass\n", encoding="utf-8")
    return source, target, consumer, init


def test_extract_module_function_updates_consumers_and_reexport(tmp_path) -> None:
    source, target, consumer, init = _project(tmp_path)
    result = _execute(tmp_path, ("foo",))
    assert result.success
    assert "def foo" not in source.read_text(encoding="utf-8")
    assert "def foo" in target.read_text(encoding="utf-8")
    assert "from package.target import foo" in consumer.read_text(encoding="utf-8")
    assert "from package.target import foo" in init.read_text(encoding="utf-8")


def test_extract_module_function_and_class_with_dependency_and_new_target(tmp_path) -> None:
    source, target, consumer, init = _project(tmp_path)
    target.unlink()
    consumer.write_text(
        "from package.source import foo, Service\nvalue = foo(1)\nservice = Service()\n",
        encoding="utf-8",
    )
    init.write_text("from package.source import foo, Service\n", encoding="utf-8")
    result = _execute(tmp_path, ("foo", "Service"), create_target=True)
    target = tmp_path / "package" / "target.py"
    assert result.success
    code = target.read_text(encoding="utf-8")
    assert "def foo" in code and "class Service(Base)" in code
    assert "from package.support import Base" in code
    assert "from package.target import foo, Service" in consumer.read_text(encoding="utf-8")
    assert "def foo" not in source.read_text(encoding="utf-8")


def test_extract_module_multiple_consumers(tmp_path) -> None:
    _project(tmp_path)
    second = tmp_path / "package" / "second.py"
    second.write_text("from package.source import foo\nvalue = foo(2)\n", encoding="utf-8")
    result = _execute(tmp_path, ("foo",))
    assert result.success
    assert "from package.target import foo" in second.read_text(encoding="utf-8")


def test_extract_module_conflict_has_no_mutations(tmp_path) -> None:
    source, target, consumer, init = _project(tmp_path)
    target.write_text("def foo(value):\n    return value\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target, consumer, init)}
    result = _execute(tmp_path, ("foo",))
    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_extract_module_unselected_dependency_has_no_mutations(tmp_path) -> None:
    source, target, consumer, init = _project(tmp_path)
    source.write_text(
        "def helper():\n    return 1\n\n"
        "def foo():\n    return helper()\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, init)}
    result = _execute(tmp_path, ("foo",))
    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_extract_module_rejects_direct_source_module_import(tmp_path) -> None:
    source, target, consumer, init = _project(tmp_path)
    source.write_text(
        "import package.source\n\n"
        "def foo():\n"
        "    return package.source.value\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, init)}
    result = _execute(tmp_path, ("foo",))
    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


class FailingExtractModuleExecutor(PythonExtractModuleExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        return ExecutionResult(False, result.operation, ("Injected extraction failure",), result.created_paths)


class CorruptingValidationExecutor(PythonValidateProjectExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        request.metadata["execution_context"].module_path("package.target").write_text(
            "def broken(:\n", encoding="utf-8"
        )
        return result


def test_extract_module_intermediate_failure_rolls_back_bytes(tmp_path) -> None:
    source, target, consumer, init = _project(tmp_path)
    before = {path: path.read_bytes() for path in (source, target, consumer, init)}
    registry = OperationExecutorRegistry()
    registry.register_many([PythonCreateModuleExecutor(), FailingExtractModuleExecutor(), PythonValidateProjectExecutor()])
    context = SemanticContextBuilder().build(PythonProjectParser().parse(tmp_path), build_reference_index=True)
    plan = ExecutionPlanner().build(ExtractModuleTransformation("package.source", "package.target", ("foo",)).create_plan("x"))
    result = ExecutionPipeline(registry, context, tmp_path).execute(plan)
    assert not result.success and result.rollback_attempted and result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before


def test_extract_module_validation_failure_rolls_back_bytes(tmp_path) -> None:
    source, target, consumer, init = _project(tmp_path)
    before = {path: path.read_bytes() for path in (source, target, consumer, init)}
    result = _execute(tmp_path, ("foo",), validate_executor=CorruptingValidationExecutor())
    assert not result.success
    assert result.error.code == "final_validation_failed"
    assert result.rollback_attempted and result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before
