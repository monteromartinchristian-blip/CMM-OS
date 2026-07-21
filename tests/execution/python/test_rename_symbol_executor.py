from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmm.execution.python import (
    PythonModuleInfo,
    PythonModuleWriter,
    PythonProjectParser,
    PythonRenameSymbolExecutor,
    SemanticContextBuilder,
)
from cmm.transformations import ExecutionRequest, RenameSymbolOperation


class RecordingWriter(PythonModuleWriter):
    def __init__(self) -> None:
        self.written_paths: list[Path] = []

    def write(self, module_info: PythonModuleInfo) -> bool:
        self.written_paths.append(module_info.path)
        return super().write(module_info)


def _request(
    project_root: Path,
    old_name: str = "greet",
    new_name: str = "welcome",
    module_name: str = "module",
) -> ExecutionRequest:
    snapshot = PythonProjectParser().parse(project_root)
    context = SemanticContextBuilder().build(
        snapshot,
        build_reference_index=True,
    )
    return ExecutionRequest(
        operation=RenameSymbolOperation(symbol=old_name, new_name=new_name),
        metadata={
            "module": module_name,
            "semantic_context": context,
        },
    )


def test_renames_top_level_function_and_simple_call() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        module_path.write_text(
            "def greet():\n    return 'hello'\n\ngreet()\n",
            encoding="utf-8",
        )

        result = PythonRenameSymbolExecutor().execute(_request(project_root))
        code = module_path.read_text(encoding="utf-8")

        assert result.success
        assert "def welcome():" in code
        assert "welcome()" in code
        assert "greet" not in code


def test_renames_multiple_calls_and_preserves_docstrings_and_comments() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        module_path.write_text(
            "# Greeting helper\n"
            "def greet(name: str) -> str:\n"
            '    """Return a greeting."""\n'
            "    return name\n\n"
            "greet('one')\n"
            "greet('two')\n",
            encoding="utf-8",
        )

        result = PythonRenameSymbolExecutor().execute(_request(project_root))
        code = module_path.read_text(encoding="utf-8")

        assert result.success
        assert code.count("welcome(") == 3
        assert "# Greeting helper" in code
        assert '"""Return a greeting."""' in code
        assert result.metadata["renamed_references"] == 2


def test_returns_failure_when_source_function_is_missing() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "module.py").write_text("value = 1\n", encoding="utf-8")

        result = PythonRenameSymbolExecutor().execute(_request(project_root))

        assert not result.success
        assert result.diagnostics == ("Function not found",)


def test_returns_failure_when_new_name_already_exists() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        module_path.write_text(
            "def greet():\n    return 'hello'\n\n"
            "def welcome():\n    return 'welcome'\n",
            encoding="utf-8",
        )

        result = PythonRenameSymbolExecutor().execute(_request(project_root))

        assert not result.success
        assert result.diagnostics == ("Function already exists",)
        assert "def greet():" in module_path.read_text(encoding="utf-8")


def test_returns_failure_for_invalid_new_name() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "module.py").write_text(
            "def greet():\n    return 'hello'\n",
            encoding="utf-8",
        )

        result = PythonRenameSymbolExecutor().execute(
            _request(project_root, new_name="not-valid")
        )

        assert not result.success
        assert result.diagnostics == ("Invalid new name",)


def test_writes_only_the_module_that_changes() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "module.py"
        other_path = project_root / "other.py"
        module_path.write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
        other_code = "greet()\n"
        other_path.write_text(other_code, encoding="utf-8")
        writer = RecordingWriter()

        result = PythonRenameSymbolExecutor(writer=writer).execute(
            _request(project_root)
        )

        assert result.success
        assert writer.written_paths == [module_path]
        assert other_path.read_text(encoding="utf-8") == other_code
