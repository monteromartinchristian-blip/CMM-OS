from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmm.execution.python import (
    PythonModuleInfo,
    PythonModuleWriter,
    PythonProjectParser,
    PythonUpdateImportsExecutor,
    SemanticContextBuilder,
    RelativeImportResolver,
)
from cmm.transformations import ExecutionRequest, UpdateImportsOperation


class RecordingWriter(PythonModuleWriter):
    def __init__(self) -> None:
        self.written_paths: list[Path] = []

    def write(self, module_info: PythonModuleInfo) -> bool:
        self.written_paths.append(module_info.path)
        return super().write(module_info)


def _request(project_root: Path) -> ExecutionRequest:
    context = SemanticContextBuilder().build(PythonProjectParser().parse(project_root))
    return ExecutionRequest(
        operation=UpdateImportsOperation(module="project"),
        metadata={
            "semantic_context": context,
            "old_module": "old_module",
            "new_module": "new_module",
            "symbol_name": "symbol",
        },
    )


def _advanced_request(
    project_root: Path,
    old_module: str,
    new_module: str,
    symbol: str,
    new_symbol: str | None = None,
) -> ExecutionRequest:
    context = SemanticContextBuilder().build(PythonProjectParser().parse(project_root))
    return ExecutionRequest(
        operation=UpdateImportsOperation(module=new_module),
        metadata={
            "semantic_context": context,
            "old_module": old_module,
            "new_module": new_module,
            "symbol_name": symbol,
            "new_symbol_name": new_symbol or symbol,
        },
    )


def test_updates_simple_from_import() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        module_path.write_text("from old_module import symbol\n", encoding="utf-8")

        result = PythonUpdateImportsExecutor().execute(_request(project_root))

        assert result.success
        assert module_path.read_text(encoding="utf-8") == (
            "from new_module import symbol\n"
        )


def test_updates_import_and_preserves_alias() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        module_path.write_text(
            "from old_module import symbol as local_symbol\n",
            encoding="utf-8",
        )

        result = PythonUpdateImportsExecutor().execute(_request(project_root))

        assert result.success
        assert module_path.read_text(encoding="utf-8") == (
            "from new_module import symbol as local_symbol\n"
        )


def test_updates_all_matching_modules() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        first_path = project_root / "first.py"
        second_path = project_root / "second.py"
        first_path.write_text("from old_module import symbol\n", encoding="utf-8")
        second_path.write_text("from old_module import symbol\n", encoding="utf-8")

        result = PythonUpdateImportsExecutor().execute(_request(project_root))

        assert result.created_paths == (first_path, second_path)
        assert "from new_module import symbol" in first_path.read_text(encoding="utf-8")
        assert "from new_module import symbol" in second_path.read_text(encoding="utf-8")


def test_does_not_write_modules_without_matching_import() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        changed_path = project_root / "changed.py"
        unchanged_path = project_root / "unchanged.py"
        changed_path.write_text("from old_module import symbol\n", encoding="utf-8")
        unchanged_code = "from other_module import value\n"
        unchanged_path.write_text(unchanged_code, encoding="utf-8")
        writer = RecordingWriter()

        result = PythonUpdateImportsExecutor(writer=writer).execute(
            _request(project_root)
        )

        assert result.success
        assert writer.written_paths == [changed_path]
        assert unchanged_path.read_text(encoding="utf-8") == unchanged_code


def test_returns_success_without_writes_when_import_is_missing() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        module_path.write_text("from other_module import symbol\n", encoding="utf-8")

        result = PythonUpdateImportsExecutor().execute(_request(project_root))

        assert result.success
        assert result.created_paths == ()
        assert module_path.read_text(encoding="utf-8") == (
            "from other_module import symbol\n"
        )


def test_preserves_import_comments_and_formatting() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        module_path.write_text(
            "# Import used by the service\n"
            "from old_module import symbol  # keep this comment\n",
            encoding="utf-8",
        )

        result = PythonUpdateImportsExecutor().execute(_request(project_root))

        assert result.success
        assert module_path.read_text(encoding="utf-8") == (
            "# Import used by the service\n"
            "from new_module import symbol  # keep this comment\n"
        )


def test_splits_multi_symbol_import_and_preserves_alias() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "consumer.py"
        path.write_text(
            "from package.source import (\n    A as AliasA,\n    B,\n)\nAliasA()\n",
            encoding="utf-8",
        )
        result = PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "package.source", "package.target", "A")
        )
        code = path.read_text(encoding="utf-8")
        assert result.success
        assert "from package.source import (\n    B,\n)" in code
        assert "from package.target import (\n    A as AliasA,\n)" in code


def test_rewrites_relative_import_levels_one_and_two() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        first = root / "top" / "consumer.py"
        second = root / "top" / "sub" / "consumer.py"
        first.parent.mkdir(parents=True)
        second.parent.mkdir(parents=True)
        (root / "top" / "__init__.py").write_text("", encoding="utf-8")
        (root / "top" / "sub" / "__init__.py").write_text("", encoding="utf-8")
        first.write_text("from .source import Symbol\n", encoding="utf-8")
        second.write_text("from ..pkg.source import Symbol as Alias\n", encoding="utf-8")
        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "top.source", "top.target", "Symbol")
        )
        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "top.pkg.source", "top.pkg.target", "Symbol")
        )
        assert "from .target import Symbol" in first.read_text(encoding="utf-8")
        assert "from ..pkg.target import Symbol as Alias" in second.read_text(encoding="utf-8")


def test_rewrites_qualified_module_alias_and_symbol_rename() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "consumer.py"
        path.write_text(
            "import package.source as source\nvalue = source.Symbol()\n",
            encoding="utf-8",
        )
        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "package.source", "package.target", "Symbol", "Renamed")
        )
        code = path.read_text(encoding="utf-8")
        assert "import package.target as source" in code
        assert "source.Renamed()" in code


def test_relative_resolver_rejects_package_escape() -> None:
    resolver = RelativeImportResolver()
    assert resolver.resolve("package.consumer", 3, "source") is None


def test_multi_symbol_split_preserves_two_aliases_and_has_no_empty_import() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "consumer.py"
        path.write_text(
            "from package.source import A as AliasA, B as AliasB\n",
            encoding="utf-8",
        )

        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "package.source", "package.target", "A")
        )
        code = path.read_text(encoding="utf-8")

        assert "from package.source import B as AliasB" in code
        assert "from package.target import A as AliasA" in code
        assert "import\n" not in code


def test_sequential_moves_split_one_import_to_different_destinations() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "consumer.py"
        path.write_text("from package.source import A, B\n", encoding="utf-8")

        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "package.source", "package.first", "A")
        )
        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "package.source", "package.second", "B")
        )
        code = path.read_text(encoding="utf-8")

        assert "from package.first import A" in code
        assert "from package.second import B" in code
        assert "from package.source" not in code


def test_relative_resolver_handles_init_and_repeated_package_names() -> None:
    resolver = RelativeImportResolver()
    from_init = resolver.resolve(
        "root.package", 1, "source", consumer_is_package=True
    )
    repeated = resolver.render_relative(
        "root.package.root.consumer", "root.package.root.target"
    )

    assert from_init is not None and from_init.absolute_module == "root.package.source"
    assert repeated is not None
    assert (repeated.level, repeated.module) == (1, "target")


def test_parenthesized_split_preserves_per_symbol_comments_and_trailing_commas() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "consumer.py"
        path.write_text(
            "from package.source import (\n"
            "    A as AliasA,  # moved\n"
            "    B,  # stays\n"
            ")\n",
            encoding="utf-8",
        )

        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "package.source", "package.target", "A")
        )
        code = path.read_text(encoding="utf-8")

        assert "A as AliasA,  # moved" in code
        assert "B,  # stays" in code
        compile(code, str(path), "exec")


def test_repeated_source_import_is_not_duplicated_at_destination() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "consumer.py"
        path.write_text(
            "from package.source import A\nfrom package.source import A\n",
            encoding="utf-8",
        )

        PythonUpdateImportsExecutor().execute(
            _advanced_request(root, "package.source", "package.target", "A")
        )
        code = path.read_text(encoding="utf-8")

        assert code.count("from package.target import A") == 1
        assert "from package.source import A" not in code
