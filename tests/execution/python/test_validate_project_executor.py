from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmm.execution import ExecutionResult
from cmm.execution.python import PythonProjectSnapshot, PythonValidateProjectExecutor
from cmm.transformations import ExecutionRequest, ValidateProjectOperation


def _request(project_root: Path) -> ExecutionRequest:
    return ExecutionRequest(
        operation=ValidateProjectOperation(scope="project"),
        metadata={"project_root": str(project_root)},
    )


def _snapshot_from(result: ExecutionResult) -> PythonProjectSnapshot:
    snapshot = result.metadata["snapshot"]
    assert isinstance(snapshot, PythonProjectSnapshot)
    return snapshot


def test_valid_project_produces_successful_snapshot() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "main.py").write_text("value = 1\n", encoding="utf-8")

        result = PythonValidateProjectExecutor().execute(_request(project_root))
        snapshot = _snapshot_from(result)

        assert result.success
        assert result.diagnostics == ()
        assert snapshot.errors == ()
        assert [module.module_name for module in snapshot.modules] == ["main"]
        assert snapshot.modules[0].parsed_module is not None


def test_syntax_error_is_reported_in_diagnostics() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "broken.py").write_text("def broken(:\n", encoding="utf-8")

        result = PythonValidateProjectExecutor().execute(_request(project_root))
        snapshot = _snapshot_from(result)

        assert not result.success
        assert result.diagnostics == snapshot.errors
        assert "broken.py" in result.diagnostics[0]
        assert snapshot.modules[0].parsed_module is None


def test_nested_packages_are_included_in_snapshot() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        package_path = project_root / "package" / "nested"
        package_path.mkdir(parents=True)
        (project_root / "package" / "__init__.py").touch()
        (package_path / "__init__.py").touch()
        (package_path / "models.py").write_text("class Model: pass\n", encoding="utf-8")

        result = PythonValidateProjectExecutor().execute(_request(project_root))
        snapshot = _snapshot_from(result)

        assert result.success
        assert [module.module_name for module in snapshot.modules] == [
            "package",
            "package.nested",
            "package.nested.models",
        ]


def test_excludes_virtualenv_and_pycache_directories() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "valid.py").write_text("value = 1\n", encoding="utf-8")
        venv_path = project_root / ".venv"
        cache_path = project_root / "__pycache__"
        venv_path.mkdir()
        cache_path.mkdir()
        (venv_path / "ignored.py").write_text("def invalid(:\n", encoding="utf-8")
        (cache_path / "ignored.py").write_text("def invalid(:\n", encoding="utf-8")

        result = PythonValidateProjectExecutor().execute(_request(project_root))
        snapshot = _snapshot_from(result)

        assert result.success
        assert [module.module_name for module in snapshot.modules] == ["valid"]


def test_snapshot_contains_all_project_modules() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        (project_root / "first.py").write_text("first = 1\n", encoding="utf-8")
        subdirectory = project_root / "package"
        subdirectory.mkdir()
        (subdirectory / "second.py").write_text("second = 2\n", encoding="utf-8")

        result = PythonValidateProjectExecutor().execute(_request(project_root))
        snapshot = _snapshot_from(result)

        assert result.success
        assert {module.path for module in snapshot.modules} == {
            project_root / "first.py",
            subdirectory / "second.py",
        }
