from __future__ import annotations

from pathlib import Path

from cmm.execution import ExecutionPipeline, ExecutionResult, OperationExecutorRegistry
from cmm.execution.python import (
    PythonMergeModulesExecutor,
    PythonMoveModuleExecutor,
    PythonMovePackageExecutor,
    PythonProjectParser,
    PythonRenameModuleExecutor,
    PythonRenamePackageExecutor,
    PythonSplitModuleExecutor,
    PythonValidateProjectExecutor,
    SemanticContextBuilder,
)
from cmm.memory import TechnicalMemory
from cmm.transformations import (
    ExecutionPlanner,
    MergeModulesTransformation,
    MoveModuleTransformation,
    MovePackageTransformation,
    RenameModuleTransformation,
    RenamePackageTransformation,
    SplitModuleGroup,
    SplitModuleTransformation,
)
from cmm.transformations.execution_request import ExecutionRequest


def _registry(rename_executor=None, validate_executor=None) -> OperationExecutorRegistry:
    registry = OperationExecutorRegistry()
    registry.register_many([
        rename_executor or PythonRenameModuleExecutor(),
        PythonMoveModuleExecutor(),
        PythonSplitModuleExecutor(),
        PythonMergeModulesExecutor(),
        PythonRenamePackageExecutor(),
        PythonMovePackageExecutor(),
        validate_executor or PythonValidateProjectExecutor(),
    ])
    return registry


def _execute(root: Path, transformation, *, registry=None, memory=None):
    semantic = SemanticContextBuilder().build(
        PythonProjectParser().parse(root), build_reference_index=True
    )
    plan = ExecutionPlanner().build(transformation.create_plan("reorganize project"))
    return ExecutionPipeline(
        registry or _registry(), semantic, root, technical_memory=memory
    ).execute(plan)


def _package(root: Path, name: str) -> Path:
    path = root.joinpath(*name.split("."))
    path.mkdir(parents=True)
    current = root
    for part in name.split("."):
        current /= part
        (current / "__init__.py").touch()
    return path


def test_rename_module_updates_consumers_reexport_all_and_qualified_reference(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "old.py").write_text("class Item:\n    pass\n", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from .old import Item\n__all__ = ['Item']\n", encoding="utf-8"
    )
    consumer = package / "consumer.py"
    consumer.write_text(
        "import package.old\nfrom .old import Item as Alias\n"
        "value = package.old.Item()\n",
        encoding="utf-8",
    )

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "package.renamed")
    )

    assert result.success
    assert not (package / "old.py").exists()
    assert (package / "renamed.py").is_file()
    assert "from .renamed import Item" in (package / "__init__.py").read_text()
    code = consumer.read_text(encoding="utf-8")
    assert "import package.renamed" in code
    assert "from .renamed import Item as Alias" in code
    assert "package.renamed.Item()" in code
    assert result.post_impact_validation.success


def test_rename_module_without_consumers(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "old.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "package.new")
    )

    assert result.success
    assert (package / "new.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_rename_module_preserves_package_level_multi_module_import(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "old.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
    consumer = package / "consumer.py"
    consumer.write_text("from package import old, other\n", encoding="utf-8")

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "package.new")
    )

    assert result.success
    assert consumer.read_text() == "from package import new as old, other\n"


def test_rename_module_preserves_multiline_import_comments(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "old.py").write_text("A = 1\nB = 2\n", encoding="utf-8")
    consumer = package / "consumer.py"
    consumer.write_text(
        "from package.old import (\n    A,  # first\n    B,\n)\n",
        encoding="utf-8",
    )

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "package.new")
    )

    assert result.success
    assert consumer.read_text() == (
        "from package.new import (\n    A,  # first\n    B,\n)\n"
    )


def test_unrelated_getattr_does_not_block_module_rename(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "old.py").write_text("VALUE = 1\n", encoding="utf-8")
    consumer = package / "consumer.py"
    consumer.write_text(
        "class Local:\n    value = 2\nresult = getattr(Local, 'value')\n",
        encoding="utf-8",
    )

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "package.new")
    )

    assert result.success
    assert "getattr(Local, 'value')" in consumer.read_text()


def test_rename_module_collision_fails_without_mutation(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "old.py"
    target = package / "new.py"
    source.write_bytes(b"VALUE = 1\n")
    target.write_bytes(b"VALUE = 2\n")
    before = {path: path.read_bytes() for path in (source, target)}

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "package.new")
    )

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_move_module_recalculates_internal_and_external_relative_imports(tmp_path) -> None:
    _package(tmp_path, "root.source")
    target = _package(tmp_path, "root.target")
    source = tmp_path / "root" / "source"
    (source / "dependency.py").write_text("VALUE = 2\n", encoding="utf-8")
    (source / "service.py").write_text(
        "from .dependency import VALUE\ndef value():\n    return VALUE\n", encoding="utf-8"
    )
    consumer = source / "consumer.py"
    consumer.write_text("from .service import value\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        MoveModuleTransformation("root.source.service", "root.target.service"),
    )

    assert result.success
    assert "from ..source.dependency import VALUE" in (target / "service.py").read_text()
    assert consumer.read_text() == "from ..target.service import value\n"


def test_move_module_can_create_explicit_target_package(tmp_path) -> None:
    source = _package(tmp_path, "root.source")
    (source / "service.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        MoveModuleTransformation(
            "root.source.service", "root.created.service", create_target_package=True
        ),
    )

    assert result.success
    assert (tmp_path / "root" / "created" / "__init__.py").is_file()
    assert (tmp_path / "root" / "created" / "service.py").is_file()


def test_move_module_rejects_existing_namespace_ancestor(tmp_path) -> None:
    source = _package(tmp_path, "root.source")
    (source / "service.py").write_bytes(b"VALUE = 1\n")
    namespace = tmp_path / "namespace"
    namespace.mkdir()

    result = _execute(
        tmp_path,
        MoveModuleTransformation(
            "root.source.service", "namespace.created.service", create_target_package=True
        ),
    )

    assert not result.success
    assert result.executed_steps == ()
    assert not (namespace / "__init__.py").exists()
    assert (source / "service.py").read_bytes() == b"VALUE = 1\n"


def test_move_module_preserves_alias_and_qualified_binding(tmp_path) -> None:
    source = _package(tmp_path, "root.source")
    _package(tmp_path, "root.target")
    (source / "service.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    consumer = tmp_path / "root" / "consumer.py"
    consumer.write_text(
        "import root.source.service as service\nresult = service.value()\n",
        encoding="utf-8",
    )

    result = _execute(
        tmp_path,
        MoveModuleTransformation("root.source.service", "root.target.service"),
    )

    assert result.success
    assert consumer.read_text() == (
        "import root.target.service as service\nresult = service.value()\n"
    )


def test_move_module_splits_package_level_multi_module_import(tmp_path) -> None:
    source = _package(tmp_path, "root.source")
    _package(tmp_path, "root.target")
    (source / "service.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
    consumer = tmp_path / "root" / "consumer.py"
    consumer.write_text("from root.source import service, other\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        MoveModuleTransformation("root.source.service", "root.target.service"),
    )

    assert result.success
    assert consumer.read_text() == (
        "from root.target import service\nfrom root.source import other\n"
    )


def test_move_module_rejects_new_cycle_before_mutation(tmp_path) -> None:
    source = _package(tmp_path, "root.source")
    _package(tmp_path, "root.target")
    service = source / "service.py"
    dependency = source / "dependency.py"
    service.write_bytes(b"from root.source.dependency import VALUE\n")
    dependency.write_bytes(b"from root.target.service import value\nVALUE = 1\n")
    before = {path: path.read_bytes() for path in (service, dependency)}

    result = _execute(
        tmp_path,
        MoveModuleTransformation("root.source.service", "root.target.service"),
    )

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert {path: path.read_bytes() for path in before} == before


def test_split_module_creates_cross_group_imports_and_keeps_remaining_symbols(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "models.py"
    source.write_text(
        "KEEP = 1\n"
        "class User:\n    pass\n"
        "def build():\n    return User()\n"
        "def remaining():\n    return KEEP\n",
        encoding="utf-8",
    )
    consumer = package / "consumer.py"
    consumer.write_text("from package.models import User, build\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        SplitModuleTransformation(
            "package.models",
            (
                SplitModuleGroup("package.users", ("User",)),
                SplitModuleGroup("package.builders", ("build",)),
            ),
        ),
    )

    assert result.success
    assert "class User" in (package / "users.py").read_text()
    assert "from package.users import User" in (package / "builders.py").read_text()
    assert "KEEP = 1" in source.read_text()
    assert "def remaining" in source.read_text()
    assert "from package.users import User" in consumer.read_text()
    assert "from package.builders import build" in consumer.read_text()


def test_split_module_moves_safe_constant(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "settings.py").write_text(
        "LIMIT: int = 3\ndef value():\n    return LIMIT\n", encoding="utf-8"
    )

    result = _execute(
        tmp_path,
        SplitModuleTransformation(
            "package.settings",
            (SplitModuleGroup("package.constants", ("LIMIT",)),),
        ),
    )

    assert result.success
    assert "LIMIT: int = 3" in (package / "constants.py").read_text()
    assert "from package.constants import LIMIT" in (package / "settings.py").read_text()


def test_split_module_updates_reexport_and_literal_all(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "source.py"
    source.write_text(
        "__all__ = ['Moved', 'Remaining']\n"
        "class Moved:\n    pass\n"
        "class Remaining:\n    pass\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text(
        "from .source import Moved, Remaining\n"
        "__all__ = ['Moved', 'Remaining']\n",
        encoding="utf-8",
    )

    result = _execute(
        tmp_path,
        SplitModuleTransformation(
            "package.source", (SplitModuleGroup("package.moved", ("Moved",)),)
        ),
    )

    assert result.success
    assert "__all__ = ['Remaining']" in source.read_text()
    package_code = (package / "__init__.py").read_text()
    assert "from .moved import Moved" in package_code
    assert "from .source import Remaining" in package_code
    assert "__all__ = ['Moved', 'Remaining']" in package_code


def test_split_delete_empty_source_ignores_empty_all_and_unused_imports(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "source.py"
    source.write_text(
        "from typing import Any\n__all__ = ['item']\ndef item() -> Any:\n    return 1\n",
        encoding="utf-8",
    )

    result = _execute(
        tmp_path,
        SplitModuleTransformation(
            "package.source",
            (SplitModuleGroup("package.target", ("item",)),),
            delete_empty_source=True,
        ),
    )

    assert result.success
    assert not source.exists()
    assert "__all__ = ['item']" in (package / "target.py").read_text()


def test_split_rejects_top_level_side_effect_without_mutation(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "source.py"
    source.write_bytes(b"register()\ndef item():\n    return 1\n")
    before = source.read_bytes()

    result = _execute(
        tmp_path,
        SplitModuleTransformation(
            "package.source", (SplitModuleGroup("package.target", ("item",)),)
        ),
    )

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert source.read_bytes() == before
    assert not (package / "target.py").exists()


def test_split_rejects_symbol_selected_in_two_groups(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "source.py"
    source.write_bytes(b"def item():\n    return 1\n")

    result = _execute(
        tmp_path,
        SplitModuleTransformation(
            "package.source",
            (
                SplitModuleGroup("package.one", ("item",)),
                SplitModuleGroup("package.two", ("item",)),
            ),
        ),
    )

    assert not result.success
    assert result.executed_steps == ()
    assert source.read_bytes() == b"def item():\n    return 1\n"


def test_merge_modules_deduplicates_imports_and_updates_consumers(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "a.py").write_text("from typing import Any\nclass A:\n    pass\n", encoding="utf-8")
    (package / "b.py").write_text("from typing import Any\ndef build() -> Any:\n    return 1\n", encoding="utf-8")
    consumer = package / "consumer.py"
    consumer.write_text("from package.a import A\nfrom package.b import build\n", encoding="utf-8")

    result = _execute(
        tmp_path, MergeModulesTransformation(("package.a", "package.b"), "package.combined")
    )

    assert result.success
    combined = (package / "combined.py").read_text(encoding="utf-8")
    assert combined.count("from typing import Any") == 1
    assert "class A" in combined and "def build" in combined
    assert not (package / "a.py").exists() and not (package / "b.py").exists()
    assert consumer.read_text().count("from package.combined import") == 2


def test_merge_symbol_conflict_fails_before_mutation(tmp_path) -> None:
    package = _package(tmp_path, "package")
    first = package / "a.py"
    second = package / "b.py"
    first.write_bytes(b"VALUE = 1\n")
    second.write_bytes(b"VALUE = 2\n")
    before = {path: path.read_bytes() for path in (first, second)}

    result = _execute(
        tmp_path, MergeModulesTransformation(("package.a", "package.b"), "package.combined")
    )

    assert not result.success
    assert {path: path.read_bytes() for path in before} == before
    assert not (package / "combined.py").exists()


def test_merge_keep_sources_preserves_original_files(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "a.py").write_text("A = 1\n", encoding="utf-8")
    (package / "b.py").write_text("B = 2\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        MergeModulesTransformation(
            ("package.a", "package.b"), "package.combined", keep_sources=True
        ),
    )

    assert result.success
    assert (package / "a.py").is_file() and (package / "b.py").is_file()
    assert "A = 1" in (package / "combined.py").read_text()


def test_merge_keep_sources_preserves_internal_source_imports(tmp_path) -> None:
    package = _package(tmp_path, "package")
    first = package / "a.py"
    second = package / "b.py"
    first.write_text("class A:\n    pass\n", encoding="utf-8")
    second.write_text(
        "from package.a import A\ndef build():\n    return A()\n", encoding="utf-8"
    )
    before = {path: path.read_bytes() for path in (first, second)}

    result = _execute(
        tmp_path,
        MergeModulesTransformation(
            ("package.a", "package.b"),
            "package.combined",
            keep_sources=True,
        ),
    )

    assert result.success
    assert {path: path.read_bytes() for path in before} == before
    assert (package / "combined.py").is_file()


def test_merge_resolves_safe_dependency_between_sources(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "a.py").write_text("class A:\n    pass\n", encoding="utf-8")
    (package / "b.py").write_text(
        "from package.a import A\ndef build():\n    return A()\n", encoding="utf-8"
    )

    result = _execute(
        tmp_path, MergeModulesTransformation(("package.a", "package.b"), "package.combined")
    )

    assert result.success
    combined = (package / "combined.py").read_text()
    assert "from package.a import A" not in combined
    assert "class A" in combined and "return A()" in combined


def test_merge_orders_eager_class_dependencies_before_consumers(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "child.py").write_text(
        "from package.base import Base\nclass Child(Base):\n    pass\n",
        encoding="utf-8",
    )
    (package / "base.py").write_text("class Base:\n    pass\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        MergeModulesTransformation(
            ("package.child", "package.base"), "package.combined"
        ),
    )

    assert result.success
    code = (package / "combined.py").read_text(encoding="utf-8")
    assert "from package.base import Base" not in code
    assert code.index("class Base") < code.index("class Child")


def test_merge_relocates_relative_imports_and_combines_literal_all(tmp_path) -> None:
    source = _package(tmp_path, "package.source")
    (source / "dependency.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "a.py").write_text(
        "from .dependency import VALUE\n__all__ = ['a']\ndef a():\n    return VALUE\n",
        encoding="utf-8",
    )
    (source / "b.py").write_text(
        "__all__ = ('b',)\ndef b():\n    return 2\n", encoding="utf-8"
    )

    result = _execute(
        tmp_path,
        MergeModulesTransformation(
            ("package.source.a", "package.source.b"), "package.combined"
        ),
    )

    assert result.success
    code = (tmp_path / "package" / "combined.py").read_text(encoding="utf-8")
    assert "from .source.dependency import VALUE" in code
    assert "__all__ = ['a', 'b']" in code


def test_merge_into_existing_module_preserves_existing_symbols(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "a.py").write_text("A = 1\n", encoding="utf-8")
    (package / "b.py").write_text("B = 2\n", encoding="utf-8")
    target = package / "combined.py"
    target.write_text("EXISTING = 3\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        MergeModulesTransformation(
            ("package.a", "package.b"), "package.combined", create_target=False
        ),
    )

    assert result.success
    code = target.read_text()
    assert "EXISTING = 3" in code and "A = 1" in code and "B = 2" in code


def test_rename_top_level_package_updates_external_consumers(tmp_path) -> None:
    package = _package(tmp_path, "oldpkg")
    (package / "model.py").write_text("class Model:\n    pass\n", encoding="utf-8")
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        "import oldpkg.model\nvalue = oldpkg.model.Model()\n", encoding="utf-8"
    )

    result = _execute(
        tmp_path, RenamePackageTransformation("oldpkg", "newpkg")
    )

    assert result.success
    assert not package.exists()
    assert (tmp_path / "newpkg" / "model.py").is_file()
    assert consumer.read_text() == (
        "import newpkg.model\nvalue = newpkg.model.Model()\n"
    )


def test_rename_subpackage_preserves_internal_relative_imports(tmp_path) -> None:
    package = _package(tmp_path, "root.old")
    (package / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "service.py").write_text("from .helper import VALUE\n", encoding="utf-8")

    result = _execute(
        tmp_path, RenamePackageTransformation("root.old", "root.new")
    )

    assert result.success
    assert (tmp_path / "root" / "new" / "service.py").read_text() == (
        "from .helper import VALUE\n"
    )


def test_move_nested_package_rewrites_internal_and_external_relative_imports(tmp_path) -> None:
    source = _package(tmp_path, "root.a.sub")
    _package(tmp_path, "root.b")
    (tmp_path / "root" / "a" / "dependency.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "service.py").write_text(
        "from ..dependency import VALUE\n", encoding="utf-8"
    )
    consumer = tmp_path / "root" / "consumer.py"
    consumer.write_text("from .a.sub.service import VALUE\n", encoding="utf-8")

    result = _execute(
        tmp_path, MovePackageTransformation("root.a.sub", "root.b.sub")
    )

    assert result.success
    moved = tmp_path / "root" / "b" / "sub" / "service.py"
    assert moved.read_text() == "from ...a.dependency import VALUE\n"
    assert consumer.read_text() == "from .b.sub.service import VALUE\n"


def test_move_package_can_create_explicit_destination_parents(tmp_path) -> None:
    source = _package(tmp_path, "root.source")
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path,
        MovePackageTransformation(
            "root.source", "root.created.deep.source", create_target_parents=True
        ),
    )

    assert result.success
    target = tmp_path / "root" / "created" / "deep" / "source"
    assert (target / "module.py").is_file()
    assert (tmp_path / "root" / "created" / "__init__.py").is_file()
    assert (tmp_path / "root" / "created" / "deep" / "__init__.py").is_file()


def test_move_package_inside_itself_is_rejected_without_mutation(tmp_path) -> None:
    source = _package(tmp_path, "root.package")
    file = source / "module.py"
    file.write_bytes(b"VALUE = 1\n")

    result = _execute(
        tmp_path,
        MovePackageTransformation("root.package", "root.package.child"),
    )

    assert not result.success
    assert result.executed_steps == ()
    assert file.read_bytes() == b"VALUE = 1\n"


class CorruptingValidateProjectExecutor(PythonValidateProjectExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        context = request.metadata["execution_context"]
        context.module_path("package.new").write_text("def broken(:\n", encoding="utf-8")
        result = ExecutionResult(True, request.operation)
        return result


class CorruptingPackageValidateExecutor(PythonValidateProjectExecutor):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        context = request.metadata["execution_context"]
        target = context.project_root / "root" / "target" / "moved" / "module.py"
        target.write_text("def broken(:\n", encoding="utf-8")
        return ExecutionResult(True, request.operation)


class StaleQualifiedRenameExecutor(PythonRenameModuleExecutor):
    def _rewrite_project(self, context, module_moves, symbol_moves):
        updates = []
        for info in context.semantic_context.snapshot.modules:
            code = info.parsed_module.code
            if info.module_name == "package.consumer":
                code = code.replace("import package.old", "import package.new")
            updates.append((info.path.resolve(), info.module_name, code))
        return tuple(updates)


class CorruptingPublicApiRenameExecutor(PythonRenameModuleExecutor):
    def _rewrite_project(self, context, module_moves, symbol_moves):
        updates = list(super()._rewrite_project(context, module_moves, symbol_moves))
        return tuple(
            (
                path,
                module_name,
                code.replace("__all__ = ['Item']", "__all__ = []")
                if module_name == "package"
                else code,
            )
            for path, module_name, code in updates
        )


class UnexpectedPathRenameExecutor(PythonRenameModuleExecutor):
    def _move_module(self, context, operation):
        changed = super()._move_module(context, operation)
        (context.project_root / "unexpected.bin").write_bytes(b"unexpected")
        return changed


def test_validation_failure_rolls_back_module_rename_byte_for_byte(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "old.py"
    consumer = package / "consumer.py"
    source.write_bytes(b"def value():\n    return 1\n")
    consumer.write_bytes(b"from package.old import value\n")
    before = {path: path.read_bytes() for path in (source, consumer)}

    result = _execute(
        tmp_path,
        RenameModuleTransformation("package.old", "package.new"),
        registry=_registry(validate_executor=CorruptingValidateProjectExecutor()),
    )

    assert not result.success
    assert result.error.code == "final_validation_failed"
    assert result.rollback_attempted and result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before
    assert not (package / "new.py").exists()
    assert result.post_impact_validation.rollback_graph_matches


def test_post_impact_stale_qualified_reference_triggers_rollback(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "old.py"
    consumer = package / "consumer.py"
    source.write_bytes(b"VALUE = 1\n")
    consumer.write_bytes(b"import package.old\nresult = package.old.VALUE\n")
    before = {path: path.read_bytes() for path in (source, consumer)}

    result = _execute(
        tmp_path,
        RenameModuleTransformation("package.old", "package.new"),
        registry=_registry(rename_executor=StaleQualifiedRenameExecutor()),
    )

    assert not result.success
    assert result.error.code == "post_impact_validation_failed"
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before
    assert not (package / "new.py").exists()
    assert any(
        item.code.value == "stale_module_reference"
        for item in result.post_impact_validation.discrepancies
    )


def test_post_impact_public_api_mismatch_triggers_rollback(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "old.py"
    initializer = package / "__init__.py"
    source.write_bytes(b"class Item:\n    pass\n")
    initializer.write_bytes(b"from .old import Item\n__all__ = ['Item']\n")
    before = {path: path.read_bytes() for path in (source, initializer)}

    result = _execute(
        tmp_path,
        RenameModuleTransformation("package.old", "package.new"),
        registry=_registry(rename_executor=CorruptingPublicApiRenameExecutor()),
    )

    assert not result.success
    assert result.error.code == "post_impact_validation_failed"
    assert result.rollback_applied
    assert {path: path.read_bytes() for path in before} == before
    assert any(
        item.code.value == "public_api_mismatch"
        for item in result.post_impact_validation.discrepancies
    )


def test_unexpected_non_python_path_triggers_rollback_and_is_removed(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "old.py"
    source.write_bytes(b"VALUE = 1\n")

    result = _execute(
        tmp_path,
        RenameModuleTransformation("package.old", "package.new"),
        registry=_registry(rename_executor=UnexpectedPathRenameExecutor()),
    )

    assert not result.success
    assert result.error.code == "post_impact_validation_failed"
    assert result.rollback_applied
    assert source.read_bytes() == b"VALUE = 1\n"
    assert not (package / "new.py").exists()
    assert not (tmp_path / "unexpected.bin").exists()
    assert any(
        item.code.value == "filesystem_layout_mismatch"
        for item in result.post_impact_validation.discrepancies
    )


def test_rename_module_result_classifies_deleted_source(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "old.py"
    target = package / "new.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "package.new")
    )

    assert result.success
    assert target.resolve() in result.created_paths
    assert source.resolve() in result.deleted_paths
    assert source.resolve() not in result.modified_paths


def test_technical_memory_is_refreshed_after_package_rename(tmp_path) -> None:
    package = _package(tmp_path, "oldpkg")
    (package / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    memory = TechnicalMemory.for_project(tmp_path)

    result = _execute(
        tmp_path,
        RenamePackageTransformation("oldpkg", "newpkg"),
        memory=memory,
    )

    assert result.success
    assert result.impact_analysis.memory_used
    persisted = (tmp_path / ".cmm" / "memory.json").read_text(encoding="utf-8")
    assert "newpkg/module.py" in persisted
    assert "oldpkg/module.py" not in persisted


def test_package_move_validation_failure_restores_directory_files_and_memory(tmp_path) -> None:
    source = _package(tmp_path, "root.source.moved")
    _package(tmp_path, "root.target")
    module = source / "module.py"
    data = source / "data.txt"
    module.write_bytes(b"VALUE = 1\n")
    data.write_bytes(b"exact bytes\x00\xff")
    before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    memory = TechnicalMemory.for_project(tmp_path)

    result = _execute(
        tmp_path,
        MovePackageTransformation("root.source.moved", "root.target.moved"),
        registry=_registry(validate_executor=CorruptingPackageValidateExecutor()),
        memory=memory,
    )

    assert not result.success
    assert result.error.code == "final_validation_failed"
    assert result.rollback_attempted and result.rollback_applied
    assert not (tmp_path / "root" / "target" / "moved").exists()
    assert {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*") if path.is_file()
    } == before
    persisted = (tmp_path / ".cmm" / "memory.json").read_text(encoding="utf-8")
    assert "root/source/moved/module.py" in persisted
    assert "root/target/moved/module.py" not in persisted


def test_package_move_rollback_restores_empty_directories(tmp_path) -> None:
    source = _package(tmp_path, "root.source.moved")
    _package(tmp_path, "root.target")
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "empty" / "nested").mkdir(parents=True)

    result = _execute(
        tmp_path,
        MovePackageTransformation("root.source.moved", "root.target.moved"),
        registry=_registry(validate_executor=CorruptingPackageValidateExecutor()),
    )

    assert not result.success
    assert result.rollback_applied
    assert (source / "empty" / "nested").is_dir()
    assert not (tmp_path / "root" / "target" / "moved").exists()


def test_preexisting_cycle_is_preserved_without_being_treated_as_new(tmp_path) -> None:
    package = _package(tmp_path, "package")
    (package / "a.py").write_text("from package.b import B\nA = 1\n", encoding="utf-8")
    (package / "b.py").write_text("from package.a import A\nB = 2\n", encoding="utf-8")

    result = _execute(
        tmp_path, RenameModuleTransformation("package.a", "package.renamed")
    )

    assert result.success
    assert (package / "renamed.py").is_file()
    assert "from package.renamed import A" in (package / "b.py").read_text()


def test_module_symlink_escape_is_rejected_before_mutation(tmp_path) -> None:
    package = _package(tmp_path, "package")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_bytes(b"VALUE = 1\n")
    link = package / "linked.py"
    link.symlink_to(outside)
    try:
        result = _execute(
            tmp_path, RenameModuleTransformation("package.linked", "package.renamed")
        )
        assert not result.success
        assert result.executed_steps == ()
        assert outside.read_bytes() == b"VALUE = 1\n"
        assert link.is_symlink()
    finally:
        outside.unlink(missing_ok=True)


def test_module_path_traversal_is_structured_and_does_not_mutate(tmp_path) -> None:
    package = _package(tmp_path, "package")
    source = package / "old.py"
    source.write_bytes(b"VALUE = 1\n")
    outside = tmp_path.parent / "outside.py"
    outside.unlink(missing_ok=True)

    result = _execute(
        tmp_path, RenameModuleTransformation("package.old", "../outside")
    )

    assert not result.success
    assert result.error.code == "precondition_failed"
    assert source.read_bytes() == b"VALUE = 1\n"
    assert not outside.exists()
