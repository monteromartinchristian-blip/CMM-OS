from __future__ import annotations

from pathlib import Path

from cmm.execution import ExecutionPipeline, ExecutionResult, OperationExecutorRegistry
from cmm.execution.python import (
    PythonCopySymbolExecutor,
    PythonDeleteSymbolExecutor,
    PythonProjectParser,
    PythonRenameSymbolExecutor,
    PythonUpdateImportsExecutor,
    PythonValidateProjectExecutor,
    SemanticContextBuilder,
)
from cmm.transformations import (
    ExecutionPlanner,
    MoveFunctionTransformation,
)
from cmm.transformations.execution_request import ExecutionRequest


def _project(tmp_path: Path, consumer: str) -> tuple[Path, Path, Path, Path]:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    consumer_path = package / "consumer.py"
    source.write_text(
        "def foo(value: int = 1) -> int:\n"
        '    """Return the supplied value."""\n'
        "    return value\n",
        encoding="utf-8",
    )
    target.write_text("", encoding="utf-8")
    consumer_path.write_text(consumer, encoding="utf-8")
    return source, target, consumer_path, package / "__init__.py"


def _registry(update_executor=None, delete_executor=None) -> OperationExecutorRegistry:
    registry = OperationExecutorRegistry()
    registry.register_many(
        [
            PythonCopySymbolExecutor(),
            PythonRenameSymbolExecutor(),
            update_executor or PythonUpdateImportsExecutor(),
            delete_executor or PythonDeleteSymbolExecutor(),
            PythonValidateProjectExecutor(),
        ]
    )
    return registry


def _execute(tmp_path: Path, registry: OperationExecutorRegistry | None = None, *, new_name: str | None = None):
    snapshot = PythonProjectParser().parse(tmp_path)
    context = SemanticContextBuilder().build(snapshot, build_reference_index=True)
    transformation = MoveFunctionTransformation(
        source_module="package.source",
        target_module="package.target",
        function_name="foo",
        new_name=new_name,
    )
    plan = ExecutionPlanner().build(transformation.create_plan("move foo"))
    return ExecutionPipeline(registry or _registry(), context, tmp_path).execute(plan)


class FailingUpdateImportsExecutor(PythonUpdateImportsExecutor):
    """Perform the real update, then fail to exercise transactional rollback."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        return ExecutionResult(
            success=False,
            operation=result.operation,
            diagnostics=("Injected update-imports failure",),
            created_paths=result.created_paths,
        )


class FailingDeleteSymbolExecutor(PythonDeleteSymbolExecutor):
    """Perform the real deletion, then fail to exercise transactional rollback."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        return ExecutionResult(
            success=False,
            operation=result.operation,
            diagnostics=("Injected delete-symbol failure",),
            created_paths=result.created_paths,
        )


def test_move_function_simple_e2e_updates_consumer_and_deletes_source(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import foo\nvalue = foo()\n",
    )
    package_init.write_text("from package.source import foo\n", encoding="utf-8")

    result = _execute(tmp_path)

    assert result.success
    assert "def foo" not in source.read_text(encoding="utf-8")
    assert "def foo" in target.read_text(encoding="utf-8")
    assert "from package.target import foo" in consumer.read_text(encoding="utf-8")
    assert "from package.target import foo" in package_init.read_text(encoding="utf-8")
    assert result.executed_steps == (
        "move-function-1",
        "move-function-2",
        "move-function-3",
        "move-function-4",
    )
    assert all(item.success for item in result.precondition_results)
    assert all(item.success for item in result.operation_results)
    assert result.validations[0].success


def test_move_function_preserves_async_decorator_docstring_and_annotations(tmp_path) -> None:
    source, target, _, _ = _project(
        tmp_path,
        "from package.source import foo\n",
    )
    source.write_text(
        "def decorator(function):\n"
        "    return function\n\n"
        "@decorator\n"
        "async def foo(value: int = 1) -> int:\n"
        '    """An async function with metadata."""\n'
        "    return value\n",
        encoding="utf-8",
    )
    target.write_text(
        "def decorator(function):\n"
        "    return function\n",
        encoding="utf-8",
    )

    result = _execute(tmp_path)
    target_code = target.read_text(encoding="utf-8")

    assert result.success
    assert "@decorator" in target_code
    assert "async def foo(value: int = 1) -> int:" in target_code
    assert '"""An async function with metadata."""' in target_code


def test_move_function_supports_simple_from_import_alias(tmp_path) -> None:
    _, _, consumer, _ = _project(
        tmp_path,
        "from package.source import foo as local_foo\nvalue = local_foo()\n",
    )

    result = _execute(tmp_path)

    assert result.success
    assert "from package.target import foo as local_foo" in consumer.read_text(encoding="utf-8")


def test_move_function_updates_multiple_consumers_and_multiline_import(tmp_path) -> None:
    _, _, first_consumer, _ = _project(
        tmp_path,
        "from package.source import (\n    foo,\n)\nvalue = foo()\n",
    )
    second_consumer = tmp_path / "second_consumer.py"
    second_consumer.write_text(
        "from package.source import foo\nvalue = foo()\n",
        encoding="utf-8",
    )

    result = _execute(tmp_path)

    assert result.success
    assert "from package.target import (\n    foo,\n)" in first_consumer.read_text(encoding="utf-8")
    assert "from package.target import foo" in second_consumer.read_text(encoding="utf-8")


def test_move_function_rejects_relative_import_before_mutation(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from .source import foo\n",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_move_function_supports_renaming_and_updates_imported_name(tmp_path) -> None:
    _, target, consumer, _ = _project(
        tmp_path,
        "from package.source import foo\nvalue = foo()\n",
    )

    result = _execute(tmp_path, new_name="bar")

    assert result.success
    assert "def bar" in target.read_text(encoding="utf-8")
    assert "from package.target import bar" in consumer.read_text(encoding="utf-8")


def test_move_function_rejects_missing_source_module(tmp_path) -> None:
    source, _, _, _ = _project(tmp_path, "")
    source.unlink()

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert result.precondition_results[0].name == "module_exists"


def test_move_function_rejects_missing_source_function(tmp_path) -> None:
    source, _, _, _ = _project(tmp_path, "")
    source.write_text("value = 1\n", encoding="utf-8")

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert any(item.name == "symbol_exists" and not item.success for item in result.precondition_results)


def test_move_function_rejects_missing_target_module(tmp_path) -> None:
    _, target, _, _ = _project(tmp_path, "")
    target.unlink()

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert any(item.name == "module_exists" and not item.success for item in result.precondition_results)


def test_move_function_conflict_fails_before_mutation(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import foo\n",
    )
    target.write_text("def foo():\n    return 99\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert result.failed_step is None
    assert {path: path.read_bytes() for path in before} == before


def test_move_function_rejects_unsupported_direct_import_before_mutation(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "import package.source\nvalue = package.source.foo()\n",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "Direct module import is unsupported" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


def test_move_function_rejects_multiple_symbols_in_one_import(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import foo, other\n",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "Multiple imported symbols are unsupported" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


def test_move_function_rejects_destination_import_collision(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import foo\nfrom package.target import foo\n",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "Import collision" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


def test_move_function_rejects_unavailable_global_dependency(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import foo\n",
    )
    source.write_text(
        "def helper():\n    return 1\n\n"
        "def foo():\n    return helper()\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "helper" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


def test_move_function_rolls_back_after_real_import_update_failure(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import foo\nvalue = foo()\n",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path, _registry(update_executor=FailingUpdateImportsExecutor()))

    assert not result.success
    assert result.error.code == "operation_failed"
    assert result.failed_step == "move-function-2"
    assert result.rollback_attempted
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before


def test_move_function_rolls_back_after_real_delete_failure(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import foo\nvalue = foo()\n",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path, _registry(delete_executor=FailingDeleteSymbolExecutor()))

    assert not result.success
    assert result.error.code == "operation_failed"
    assert result.failed_step == "move-function-3"
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before
