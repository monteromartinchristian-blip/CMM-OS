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
from cmm.transformations import ExecutionPlanner, MoveClassTransformation
from cmm.transformations.execution_request import ExecutionRequest


def _registry(update_executor=None, delete_executor=None, validate_executor=None):
    registry = OperationExecutorRegistry()
    registry.register_many(
        [
            PythonCopySymbolExecutor(),
            PythonRenameSymbolExecutor(),
            update_executor or PythonUpdateImportsExecutor(),
            delete_executor or PythonDeleteSymbolExecutor(),
            validate_executor or PythonValidateProjectExecutor(),
        ]
    )
    return registry


def _execute(
    root: Path,
    *,
    new_name: str | None = None,
    registry: OperationExecutorRegistry | None = None,
):
    snapshot = PythonProjectParser().parse(root)
    context = SemanticContextBuilder().build(snapshot, build_reference_index=True)
    transformation = MoveClassTransformation(
        class_name="MyClass",
        source_module="package.source",
        target_module="package.target",
        new_name=new_name,
    )
    plan = ExecutionPlanner().build(transformation.create_plan("move class"))
    return ExecutionPipeline(registry or _registry(), context, root).execute(plan)


def _project(root: Path, consumer: str = "from package.source import MyClass\nitem = MyClass()\n"):
    package = root / "package"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from package.source import MyClass\n",
        encoding="utf-8",
    )
    source = package / "source.py"
    target = package / "target.py"
    consumer_path = package / "consumer.py"
    source.write_text(
        "from package.support import Base, class_decorator\n"
        "\n"
        "@class_decorator\n"
        "class MyClass(Base):\n"
        '    """A class to move."""\n'
        "    value: int = 3\n"
        "\n"
        "    def method(self, value: int = 1) -> int:\n"
        "        return self.value + value\n"
        "\n"
        "    async def async_method(self) -> int:\n"
        "        return self.value\n"
        "\n"
        "    @classmethod\n"
        "    def make(cls) -> 'MyClass':\n"
        "        return cls()\n"
        "\n"
        "    @staticmethod\n"
        "    def static() -> int:\n"
        "        return 1\n"
        "\n"
        "    @property\n"
        "    def prop(self) -> int:\n"
        "        return self.value\n"
        "\n"
        "    class Nested:\n"
        "        pass\n",
        encoding="utf-8",
    )
    target.write_text(
        "from package.support import Base, class_decorator\n",
        encoding="utf-8",
    )
    consumer_path.write_text(consumer, encoding="utf-8")
    (package / "support.py").write_text(
        "class Base:\n    pass\n\n"
        "def class_decorator(cls):\n    return cls\n",
        encoding="utf-8",
    )
    return source, target, consumer_path, package / "__init__.py"


def test_move_class_simple_e2e_updates_consumer_and_reexport(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    result = _execute(tmp_path)

    assert result.success
    assert "class MyClass" not in source.read_text(encoding="utf-8")
    assert "class MyClass" in target.read_text(encoding="utf-8")
    assert "from package.target import MyClass" in consumer.read_text(encoding="utf-8")
    assert "from package.target import MyClass" in package_init.read_text(encoding="utf-8")
    assert result.executed_steps == (
        "move-class-1",
        "move-class-2",
        "move-class-3",
        "move-class-4",
    )
    assert all(item.success for item in result.precondition_results)
    assert result.validations[0].success


def test_move_class_preserves_complex_structure(tmp_path) -> None:
    _, target, _, _ = _project(tmp_path)
    result = _execute(tmp_path)
    code = target.read_text(encoding="utf-8")

    assert result.success
    for fragment in (
        "@class_decorator",
        "class MyClass(Base):",
        '"""A class to move."""',
        "value: int = 3",
        "async def async_method",
        "@classmethod",
        "@staticmethod",
        "@property",
        "class Nested:",
    ):
        assert fragment in code


def test_move_class_preserves_metaclass_keyword_and_external_annotations(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = package / "source.py"
    target = package / "target.py"
    consumer = package / "consumer.py"
    source.write_text(
        "from package.support import Base, ExternalType, Meta\n"
        "\n"
        "class MyClass(Base, metaclass=Meta):\n"
        "    value: ExternalType\n",
        encoding="utf-8",
    )
    target.write_text(
        "from package.support import Base, ExternalType, Meta\n",
        encoding="utf-8",
    )
    consumer.write_text("from package.source import MyClass\nitem = MyClass()\n", encoding="utf-8")
    (package / "support.py").write_text(
        "class Base:\n    pass\n\n"
        "class ExternalType:\n    pass\n\n"
        "class Meta(type):\n    pass\n",
        encoding="utf-8",
    )

    result = _execute(tmp_path)

    assert result.success
    code = target.read_text(encoding="utf-8")
    assert "class MyClass(Base, metaclass=Meta):" in code
    assert "value: ExternalType" in code


def test_move_class_renames_and_updates_alias(tmp_path) -> None:
    _, target, consumer, _ = _project(
        tmp_path,
        "from package.source import MyClass as LocalClass\nitem = LocalClass()\n",
    )
    result = _execute(tmp_path, new_name="RenamedClass")

    assert result.success
    assert "class RenamedClass" in target.read_text(encoding="utf-8")
    assert "from package.target import RenamedClass as LocalClass" in consumer.read_text(encoding="utf-8")


def test_move_class_updates_inheritance_reference(tmp_path) -> None:
    _, _, consumer, _ = _project(
        tmp_path,
        "from package.source import MyClass\n\nclass Child(MyClass):\n    pass\n",
    )
    result = _execute(tmp_path)

    assert result.success
    assert "from package.target import MyClass" in consumer.read_text(encoding="utf-8")
    assert "class Child(MyClass):" in consumer.read_text(encoding="utf-8")


def test_move_class_renames_unaliased_inheritance_reference(tmp_path) -> None:
    _, _, consumer, _ = _project(
        tmp_path,
        "from package.source import MyClass\n\nclass Child(MyClass):\n    pass\n",
    )
    result = _execute(tmp_path, new_name="RenamedClass")

    assert result.success
    code = consumer.read_text(encoding="utf-8")
    assert "from package.target import RenamedClass" in code
    assert "class Child(RenamedClass):" in code


def test_move_class_rejects_ambiguous_local_homonym_before_mutation(tmp_path) -> None:
    source, target, consumer, package_init = _project(
        tmp_path,
        "from package.source import MyClass\n\n"
        "def build(MyClass):\n"
        "    return MyClass\n",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path, new_name="RenamedClass")

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "Ambiguous local binding" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


def test_move_class_conflict_fails_before_mutation(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    target.write_text("class MyClass:\n    pass\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert result.executed_steps == ()
    assert {path: path.read_bytes() for path in before} == before


def test_move_class_rejects_nested_class_before_mutation(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    source.write_text("class Outer:\n    class MyClass:\n        pass\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_move_class_rejects_duplicate_top_level_class_before_mutation(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    source.write_text(
        "class MyClass:\n    pass\n\nclass MyClass:\n    pass\n",
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "Ambiguous symbol" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


def test_move_class_rejects_missing_source_module(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "target.py").write_text("", encoding="utf-8")

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert result.executed_steps == ()


def test_move_class_rejects_missing_target_module(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "source.py").write_text("class MyClass:\n    pass\n", encoding="utf-8")

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert result.executed_steps == ()


def test_move_class_rejects_unsupported_global_dependency(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    source.write_text("@missing_decorator\nclass MyClass:\n    pass\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path)

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert "missing_decorator" in result.error.message
    assert {path: path.read_bytes() for path in before} == before


class FailingUpdateImportsExecutor(PythonUpdateImportsExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        return ExecutionResult(
            success=False,
            operation=result.operation,
            diagnostics=("Injected update-imports failure",),
            created_paths=result.created_paths,
        )


class FailingDeleteSymbolExecutor(PythonDeleteSymbolExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        return ExecutionResult(
            success=False,
            operation=result.operation,
            diagnostics=("Injected delete-symbol failure",),
            created_paths=result.created_paths,
        )


class CorruptingValidationExecutor(PythonValidateProjectExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = super().execute(request)
        context = request.metadata["execution_context"]
        target = context.module_path("package.target")
        target.write_text("def broken(:\n", encoding="utf-8")
        return result


def test_move_class_rolls_back_after_import_failure(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path, registry=_registry(update_executor=FailingUpdateImportsExecutor()))

    assert not result.success
    assert result.rollback_attempted
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before


def test_move_class_rolls_back_after_delete_failure(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path, registry=_registry(delete_executor=FailingDeleteSymbolExecutor()))

    assert not result.success
    assert result.rollback_attempted
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before


def test_move_class_final_validation_failure_rolls_back(tmp_path) -> None:
    source, target, consumer, package_init = _project(tmp_path)
    before = {path: path.read_bytes() for path in (source, target, consumer, package_init)}

    result = _execute(tmp_path, registry=_registry(validate_executor=CorruptingValidationExecutor()))

    assert not result.success
    assert result.error.code == "final_validation_failed"
    assert result.rollback_attempted
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before
