from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmm.execution.python import (
    PythonModuleInfo,
    PythonModuleWriter,
    PythonProjectParser,
    PythonUpdateImportsExecutor,
    SemanticContextBuilder,
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
