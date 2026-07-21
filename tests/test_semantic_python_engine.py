from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kernel.runtime import Runtime
from kernel.semantic import SemanticOperation, SemanticRuntime
from kernel.semantic_executors import create_default_semantic_registry
from kernel.services.python_locator import PythonLocator


def _run(payload: dict) -> tuple[object, str]:
    result = Runtime().run(payload)
    path = Path(payload["actions"][0]["path"])
    return result, path.read_text(encoding="utf-8")


def _python_action(path: Path, action: str, **kwargs: object) -> dict:
    return {
        "version": 1,
        "actions": [
            {
                "tool": "python",
                "action": action,
                "path": str(path),
                **kwargs,
            }
        ],
    }


def _assert_valid(source: str) -> None:
    ast.parse(source)


def test_e2e_insert_method_with_decorator_docstring_and_staticmethod(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("class User:\n    pass\n", encoding="utf-8")

    result, source = _run(
        _python_action(
            path,
            "insert_method",
            class_name="User",
            position="end",
            code="@staticmethod\ndef build():\n    \"\"\"Build it.\"\"\"\n    return 1",
        )
    )

    assert result.success is True
    assert "@staticmethod" in source
    assert '"""Build it."""' in source
    _assert_valid(source)


def test_e2e_replace_method_async_classmethod(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text(
        "class User:\n    @classmethod\n    async def load(cls):\n        return 1\n",
        encoding="utf-8",
    )

    result, source = _run(
        _python_action(
            path,
            "replace_method",
            class_name="User",
            method_name="load",
            code="@classmethod\nasync def load(cls):\n    \"\"\"Load async.\"\"\"\n    return 2",
        )
    )

    assert result.success is True
    assert "async def load" in source
    assert "return 2" in source
    _assert_valid(source)


def test_e2e_delete_method_leaves_valid_empty_class(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("class User:\n    def old(self):\n        return 1\n", encoding="utf-8")

    result, source = _run(
        _python_action(path, "delete_method", class_name="User", method_name="old")
    )

    assert result.success is True
    assert "def old" not in source
    assert "pass" in source
    _assert_valid(source)


def test_e2e_rename_method_reports_references_not_updated(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text(
        "class User:\n    def old(self):\n        return 1\n    def call(self):\n        return self.old()\n",
        encoding="utf-8",
    )

    result, source = _run(
        _python_action(
            path,
            "rename_method",
            class_name="User",
            old_name="old",
            new_name="new",
        )
    )

    assert result.success is True
    assert "def new" in source
    assert "self.old()" in source
    assert result.results[0].data["warnings"] == ["References were not updated automatically."]
    _assert_valid(source)


def test_e2e_add_import_is_idempotent_and_supports_alias_and_relative(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("value = 1\n", encoding="utf-8")

    first, source = _run(
        _python_action(path, "add_import", module="pkg", name="Thing", alias="T", level=1)
    )
    second, second_source = _run(
        _python_action(path, "add_import", module="pkg", name="Thing", alias="T", level=1)
    )

    assert first.success is True
    assert first.results[0].data["changed"] is True
    assert second.success is True
    assert second.results[0].data["changed"] is False
    assert source.count("from .pkg import Thing as T") == 1
    assert second_source.count("from .pkg import Thing as T") == 1
    _assert_valid(second_source)


def test_e2e_remove_import_removes_one_alias_from_multiple_import(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("from pkg import A, B\nfrom .rel import C as D, E\n", encoding="utf-8")

    result, source = _run(
        _python_action(path, "remove_import", module="pkg", name="A")
    )
    relative_result, relative_source = _run(
        _python_action(path, "remove_import", module="rel", name="C", alias="D", level=1)
    )

    assert result.success is True
    assert relative_result.success is True
    assert "from pkg import B" in relative_source
    assert "from .rel import E" in relative_source
    assert "A" not in relative_source
    _assert_valid(source)
    _assert_valid(relative_source)


def test_e2e_create_class_top_level_and_nested_scope(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("class Outer:\n    pass\n", encoding="utf-8")

    result, source = _run(
        _python_action(
            path,
            "create_class",
            class_name="Inner",
            scope="Outer",
            base_classes=["Base"],
            methods=["def value(self):\n    return 1"],
        )
    )

    assert result.success is True
    assert "class Inner(Base)" in source
    assert PythonLocator().find_class(path, "Outer.Inner") is not None
    _assert_valid(source)


def test_e2e_rename_class_nested_with_docstring_and_decorator(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text(
        "class Outer:\n    @decorator\n    class Inner:\n        \"\"\"Nested.\"\"\"\n        pass\n",
        encoding="utf-8",
    )

    result, source = _run(
        _python_action(
            path,
            "rename_class",
            class_name="Inner",
            new_name="Renamed",
            scope="Outer",
        )
    )

    assert result.success is True
    assert "class Renamed" in source
    assert "@decorator" in source
    assert '"""Nested."""' in source
    assert result.results[0].data["warnings"] == ["References were not updated automatically."]
    _assert_valid(source)


def test_e2e_delete_class_nested(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("class Outer:\n    class Inner:\n        pass\n", encoding="utf-8")

    result, source = _run(
        _python_action(path, "delete_class", class_name="Inner", scope="Outer")
    )

    assert result.success is True
    assert "class Inner" not in source
    assert "class Outer" in source
    assert "pass" in source
    _assert_valid(source)


def test_unknown_operation_and_invalid_parameters_are_structured_errors(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("class User:\n    pass\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown python action"):
        Runtime().run(_python_action(path, "unknown"))

    result = SemanticRuntime(create_default_semantic_registry()).execute_operation(
        SemanticOperation("replace_method", "python", {"path": str(path), "class_name": "User"})
    )

    assert result.success is False
    assert "Missing required parameter: method_name" in result.message

    missing = Runtime().run(
        _python_action(
            path,
            "replace_method",
            class_name="User",
            method_name="missing",
            code="def missing(self):\n    pass",
        )
    )
    assert missing.success is False
    assert "Python symbol not found" in missing.errors[0]


def test_ambiguous_class_and_conflict_fail_without_modifying_file(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    original = (
        "class Duplicate:\n    pass\n"
        "class Outer:\n    class Duplicate:\n        pass\n    def old(self):\n        pass\n    def taken(self):\n        pass\n"
    )
    path.write_text(original, encoding="utf-8")

    ambiguous = Runtime().run(
        _python_action(
            path,
            "insert_method",
            class_name="Duplicate",
            position="end",
            code="def added(self):\n    pass",
        )
    )
    conflict = Runtime().run(
        _python_action(
            path,
            "rename_method",
            class_name="Outer",
            old_name="old",
            new_name="taken",
        )
    )

    assert ambiguous.success is False
    assert "Ambiguous class" in ambiguous.errors[0]
    assert conflict.success is False
    assert "Method already exists" in conflict.errors[0]
    assert path.read_text(encoding="utf-8") == original


def test_invalid_python_file_is_not_modified(tmp_path: Path) -> None:
    path = tmp_path / "bad.py"
    original = "class Broken(:\n    pass\n"
    path.write_text(original, encoding="utf-8")

    result = Runtime().run(
        _python_action(path, "create_class", class_name="NeverWritten")
    )

    assert result.success is False
    assert path.read_text(encoding="utf-8") == original
