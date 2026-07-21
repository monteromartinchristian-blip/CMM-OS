from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmm.execution.python import (
    PythonCopySymbolExecutor,
    PythonProjectParser,
    SemanticContextBuilder,
)
from cmm.transformations import CopySymbolOperation, ExecutionRequest


def _request(project_root: Path, symbol: str = "greet") -> ExecutionRequest:
    snapshot = PythonProjectParser().parse(project_root)
    return ExecutionRequest(
        operation=CopySymbolOperation(
            symbol=symbol,
            source="source",
            destination="target",
        ),
        metadata={"semantic_context": SemanticContextBuilder().build(snapshot)},
    )


def test_copies_simple_top_level_function() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "source.py").write_text(
            "def greet():\n    return 'hello'\n",
            encoding="utf-8",
        )
        target_path = project_root / "target.py"
        target_path.write_text("", encoding="utf-8")

        result = PythonCopySymbolExecutor().execute(_request(project_root))

        assert result.success
        assert "def greet():" in target_path.read_text(encoding="utf-8")


def test_copied_function_preserves_docstring_annotations_and_comments() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        source_path = project_root / "source.py"
        source_path.write_text(
            "# Greets a user\n"
            "def greet(name: str) -> str:\n"
            '    """Return a greeting."""\n'
            "    return f'Hello {name}'\n",
            encoding="utf-8",
        )
        target_path = project_root / "target.py"
        target_path.write_text("", encoding="utf-8")

        result = PythonCopySymbolExecutor().execute(_request(project_root))
        target_code = target_path.read_text(encoding="utf-8")

        assert result.success
        assert "# Greets a user" in target_code
        assert "def greet(name: str) -> str:" in target_code
        assert '"""Return a greeting."""' in target_code


def test_returns_failure_when_target_module_is_missing() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "source.py").write_text(
            "def greet():\n    return 'hello'\n",
            encoding="utf-8",
        )

        result = PythonCopySymbolExecutor().execute(_request(project_root))

        assert not result.success
        assert result.diagnostics == ("Target module not found",)


def test_returns_failure_when_function_is_missing() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "source.py").write_text("value = 1\n", encoding="utf-8")
        (project_root / "target.py").write_text("", encoding="utf-8")

        result = PythonCopySymbolExecutor().execute(_request(project_root))

        assert not result.success
        assert result.diagnostics == ("Function not found",)


def test_returns_failure_for_duplicate_function_without_writing() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "source.py").write_text(
            "def greet():\n    return 'source'\n",
            encoding="utf-8",
        )
        target_path = project_root / "target.py"
        target_path.write_text(
            "def greet():\n    return 'target'\n",
            encoding="utf-8",
        )

        result = PythonCopySymbolExecutor().execute(_request(project_root))

        assert not result.success
        assert result.diagnostics == ("Function already exists",)
        assert target_path.read_text(encoding="utf-8") == (
            "def greet():\n    return 'target'\n"
        )


def test_source_module_remains_intact() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        source_path = project_root / "source.py"
        source_code = "def greet():\n    return 'hello'\n"
        source_path.write_text(source_code, encoding="utf-8")
        (project_root / "target.py").write_text("", encoding="utf-8")

        result = PythonCopySymbolExecutor().execute(_request(project_root))

        assert result.success
        assert source_path.read_text(encoding="utf-8") == source_code
