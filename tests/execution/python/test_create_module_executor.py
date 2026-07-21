from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from cmm.execution.python import PythonCreateModuleExecutor
from cmm.transformations import CreateModuleOperation, ExecutionRequest


def _request(module_name: str, project_root: Path) -> ExecutionRequest:
    return ExecutionRequest(
        operation=CreateModuleOperation(
            module_name=module_name,
            project_root=str(project_root),
        )
    )


def test_creates_simple_module() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)

        result = PythonCreateModuleExecutor().execute(_request("users", project_root))

        module_path = project_root / "users.py"
        assert result.success
        assert module_path.is_file()
        assert result.created_paths == (module_path,)


def test_creates_nested_package_module_and_init_files() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)

        result = PythonCreateModuleExecutor().execute(
            _request("package.subpackage.users", project_root)
        )

        package_path = project_root / "package"
        subpackage_path = package_path / "subpackage"
        module_path = subpackage_path / "users.py"
        assert result.success
        assert package_path.is_dir()
        assert (package_path / "__init__.py").is_file()
        assert subpackage_path.is_dir()
        assert (subpackage_path / "__init__.py").is_file()
        assert module_path.is_file()
        assert result.created_paths == (
            package_path,
            package_path / "__init__.py",
            subpackage_path,
            subpackage_path / "__init__.py",
            module_path,
        )


def test_does_not_overwrite_existing_module() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        module_path = project_root / "users.py"
        module_path.write_text("existing content", encoding="utf-8")

        result = PythonCreateModuleExecutor().execute(_request("users", project_root))

        assert not result.success
        assert result.diagnostics == ("Module already exists",)
        assert result.created_paths == ()
        assert module_path.read_text(encoding="utf-8") == "existing content"


def test_create_module_is_idempotent() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)
        executor = PythonCreateModuleExecutor()
        request = _request("package.users", project_root)

        first_result = executor.execute(request)
        second_result = executor.execute(request)

        assert first_result.success
        assert not second_result.success
        assert second_result.diagnostics == ("Module already exists",)
        assert second_result.created_paths == ()


def test_module_paths_are_composed_with_pathlib() -> None:
    with TemporaryDirectory() as directory:
        project_root = Path(directory)

        PythonCreateModuleExecutor().execute(
            _request("package.subpackage.users", project_root)
        )

        assert (project_root / "package" / "subpackage" / "users.py").is_file()
