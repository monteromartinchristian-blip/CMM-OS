from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
from cmm.memory import TechnicalMemory
from cmm.transformations import (
    ExecutionPlanner,
    MoveClassTransformation,
    MoveFunctionTransformation,
)
from cmm.transformations.execution_request import ExecutionRequest


def _registry(update_executor=None) -> OperationExecutorRegistry:
    registry = OperationExecutorRegistry()
    registry.register_many([
        PythonCopySymbolExecutor(),
        PythonRenameSymbolExecutor(),
        update_executor or PythonUpdateImportsExecutor(),
        PythonDeleteSymbolExecutor(),
        PythonValidateProjectExecutor(),
    ])
    return registry


def _execute(
    root: Path,
    *,
    transformation=None,
    registry: OperationExecutorRegistry | None = None,
    technical_memory=None,
):
    snapshot = PythonProjectParser().parse(root)
    semantic = SemanticContextBuilder().build(snapshot, build_reference_index=True)
    transformation = transformation or MoveFunctionTransformation(
            "package.source", "package.target", "foo"
        )
    plan = ExecutionPlanner().build(transformation.create_plan("impact move"))
    return ExecutionPipeline(
        registry or _registry(), semantic, root, technical_memory=technical_memory
    ).execute(plan)


def test_move_function_pipeline_exposes_impact_analysis(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("from package.source import foo\n", encoding="utf-8")
    (package / "source.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")
    (package / "consumer.py").write_text("from package.source import foo\nfoo()\n", encoding="utf-8")

    result = _execute(tmp_path)

    assert result.success
    assert result.impact_analysis is not None
    assert result.impact_analysis.success
    assert "package.consumer" in result.impact_analysis.consumer_modules
    assert "package" in result.impact_analysis.consumer_modules


def test_cycle_is_rejected_before_move_mutation(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    source.write_text("from package.target import value\ndef foo():\n    return value\n", encoding="utf-8")
    target.write_text("from package.source import foo\nvalue = foo\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert result.impact_analysis is not None
    assert result.impact_analysis.cycles
    assert {path: path.read_bytes() for path in before} == before


def test_qualified_module_alias_is_rewritten_end_to_end(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "source.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")
    consumer = package / "consumer.py"
    consumer.write_text(
        "import package.source as source\nvalue = source.foo()\n",
        encoding="utf-8",
    )

    result = _execute(tmp_path)

    assert result.success
    assert consumer.read_text(encoding="utf-8") == (
        "import package.target as source\nvalue = source.foo()\n"
    )
    assert result.post_impact_validation is not None
    assert result.post_impact_validation.success


def test_move_class_rewrites_qualified_inheritance_and_annotation(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "source.py").write_text("class MyClass:\n    pass\n", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")
    consumer = package / "consumer.py"
    consumer.write_text(
        "import package.source as source\n"
        "class Child(source.MyClass):\n    pass\n"
        "value: source.MyClass\n",
        encoding="utf-8",
    )

    result = _execute(
        tmp_path,
        transformation=MoveClassTransformation(
            "MyClass", "package.source", "package.target"
        ),
    )

    assert result.success
    code = consumer.read_text(encoding="utf-8")
    assert "import package.target as source" in code
    assert "class Child(source.MyClass):" in code
    assert "value: source.MyClass" in code


def test_relative_reexport_and_literal_all_follow_renamed_symbol(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    package_init = package / "__init__.py"
    package_init.write_text(
        "from .source import foo\n__all__ = ['foo']\n", encoding="utf-8"
    )
    (package / "source.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")

    result = _execute(
        tmp_path,
        transformation=MoveFunctionTransformation(
            "package.source", "package.target", "foo", new_name="bar"
        ),
    )

    assert result.success
    code = package_init.read_text(encoding="utf-8")
    assert "from .target import bar" in code
    assert "__all__ = ['bar']" in code


def test_aliased_reexport_preserves_public_name_and_tuple_all(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    package_init = package / "__init__.py"
    package_init.write_text(
        "from .source import foo as public_foo\n"
        "__all__ = ('public_foo', 'untouched')\n",
        encoding="utf-8",
    )
    (package / "source.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")

    result = _execute(
        tmp_path,
        transformation=MoveFunctionTransformation(
            "package.source", "package.target", "foo", new_name="bar"
        ),
    )

    assert result.success
    code = package_init.read_text(encoding="utf-8")
    assert "from .target import bar as public_foo" in code
    assert "__all__ = ('public_foo', 'untouched')" in code


class NoopUpdateImportsExecutor(PythonUpdateImportsExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(True, request.operation)


class CorruptPublicAPIExecutor(PythonUpdateImportsExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        package_init = request.metadata["execution_context"].module_path("package.__init__")
        if not package_init.exists():
            package_init = request.metadata["execution_context"].project_root / "package" / "__init__.py"
        package_init.write_text(
            package_init.read_text(encoding="utf-8").replace("['bar']", "['foo']"),
            encoding="utf-8",
        )
        return result


def test_post_impact_discrepancy_rolls_back_all_changed_files(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    consumer = package / "consumer.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    consumer.write_text("from package.source import foo\nfoo()\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target, consumer)}

    result = _execute(tmp_path, registry=_registry(NoopUpdateImportsExecutor()))

    assert not result.success
    assert result.error.code == "post_impact_validation_failed"
    assert result.rollback_attempted and result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before
    assert result.post_impact_validation.rollback_graph_matches
    assert not result.post_impact_validation.rollback_discrepancies
    assert any(
        item.code.value == "stale_import"
        for item in result.post_impact_validation.discrepancies
    )


def test_shadowed_module_alias_is_rejected_before_mutation(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    consumer = package / "consumer.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    consumer.write_text(
        "import package.source as source\n"
        "def call(source):\n    return source.foo()\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_colliding_import_binding_is_rejected_before_mutation(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    consumer = package / "consumer.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    (package / "other.py").write_text("def foo():\n    return 2\n", encoding="utf-8")
    consumer.write_text(
        "from package.source import foo\nfrom package.other import foo\nfoo()\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_unrelated_qualified_module_import_is_left_unchanged(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "source.py").write_text(
        "def foo():\n    return 1\n\ndef other():\n    return 2\n",
        encoding="utf-8",
    )
    (package / "target.py").write_text("", encoding="utf-8")
    consumer = package / "consumer.py"
    original = "import package.source as source\nvalue = source.other()\n"
    consumer.write_text(original, encoding="utf-8")

    result = _execute(tmp_path)

    assert result.success
    assert consumer.read_text(encoding="utf-8") == original


def test_mixed_qualified_module_usage_is_rejected_before_mutation(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    consumer = package / "consumer.py"
    source.write_text(
        "def foo():\n    return 1\n\ndef other():\n    return 2\n",
        encoding="utf-8",
    )
    target.write_text("", encoding="utf-8")
    consumer.write_text(
        "import package.source as source\nsource.foo()\nsource.other()\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_relative_import_that_cannot_be_preserved_is_rejected(tmp_path) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    (one / "__init__.py").write_text("", encoding="utf-8")
    (two / "__init__.py").write_text("", encoding="utf-8")
    source = one / "source.py"
    target = two / "target.py"
    consumer = one / "consumer.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    consumer.write_text("from .source import foo\nfoo()\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target, consumer)}

    result = _execute(
        tmp_path,
        transformation=MoveFunctionTransformation(
            "one.source", "two.target", "foo"
        ),
    )

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "cannot be preserved" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


def test_public_api_discrepancy_triggers_rollback(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    package_init = package / "__init__.py"
    source = package / "source.py"
    target = package / "target.py"
    package_init.write_text(
        "from .source import foo\n__all__ = ['foo']\n", encoding="utf-8"
    )
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    before = {path: path.read_bytes() for path in (package_init, source, target)}

    result = _execute(
        tmp_path,
        transformation=MoveFunctionTransformation(
            "package.source", "package.target", "foo", new_name="bar"
        ),
        registry=_registry(CorruptPublicAPIExecutor()),
    )

    assert not result.success
    assert result.error.code == "post_impact_validation_failed"
    assert any(
        item.code.value == "public_api_mismatch"
        for item in result.post_impact_validation.discrepancies
    )
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before


def test_technical_memory_is_created_and_refreshed_after_success(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "source.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)

    result = _execute(tmp_path, technical_memory=memory)

    assert result.success
    assert (tmp_path / ".cmm" / "memory.json").is_file()
    assert result.impact_analysis.memory_used
    assert result.impact_analysis.memory_refreshed
    assert not result.impact_analysis.memory_stale
    assert memory.find_function("foo") is not None


def test_existing_technical_memory_is_refreshed_end_to_end(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "source.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)
    memory.load()
    (package / "consumer.py").write_text(
        "from package.source import foo\nfoo()\n", encoding="utf-8"
    )

    result = _execute(tmp_path, technical_memory=memory)

    assert result.success
    assert result.impact_analysis.memory_used
    assert result.impact_analysis.memory_refreshed
    assert not result.impact_analysis.memory_errors
    assert memory.find_function("foo") is not None


def test_failed_final_memory_refresh_rolls_back_and_reports_error(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target)}

    class Memory:
        def __init__(self) -> None:
            self.calls = 0

        def refresh(self):
            self.calls += 1
            if self.calls == 2:
                return SimpleNamespace(success=False, errors=("persistence failed",))
            return SimpleNamespace(
                success=True,
                rebuilt=self.calls == 1,
                persisted=self.calls == 3,
                change_set=SimpleNamespace(empty=True),
            )

    memory = Memory()
    result = _execute(tmp_path, technical_memory=memory)

    assert not result.success
    assert result.error.code == "technical_memory_refresh_failed"
    assert result.error.message == "persistence failed"
    assert result.impact_analysis.memory_errors == ("persistence failed",)
    assert result.rollback_applied
    assert not result.rollback_errors
    assert memory.calls == 3
    assert {path: path.read_bytes() for path in before} == before


def test_failed_memory_recovery_marks_rollback_partial(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target)}

    class Memory:
        def __init__(self) -> None:
            self.calls = 0

        def refresh(self):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    success=True,
                    rebuilt=True,
                    change_set=SimpleNamespace(empty=True),
                )
            return SimpleNamespace(success=False, errors=("memory unavailable",))

    result = _execute(tmp_path, technical_memory=Memory())

    assert not result.success
    assert result.error.code == "technical_memory_refresh_failed"
    assert result.rollback_attempted and not result.rollback_applied
    assert "memory unavailable" in result.rollback_errors
    assert {path: path.read_bytes() for path in before} == before


def test_rollback_leaves_technical_memory_at_pre_execution_state(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    consumer = package / "consumer.py"
    source.write_text("def foo():\n    return 1\n", encoding="utf-8")
    target.write_text("", encoding="utf-8")
    consumer.write_text("from package.source import foo\nfoo()\n", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)

    result = _execute(
        tmp_path,
        registry=_registry(NoopUpdateImportsExecutor()),
        technical_memory=memory,
    )

    assert not result.success and result.rollback_applied
    reloaded = TechnicalMemory.for_project(tmp_path)
    reloaded.load()
    symbol = reloaded.find_function("foo")
    assert symbol is not None
    assert "source" in str(symbol.source_path)
