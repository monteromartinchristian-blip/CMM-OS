from __future__ import annotations

from pathlib import Path

import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.testing.discovery import discover_tests
from cmm.validation.testing.selection import (
    TestSelection as _TestSelection,
    select_affected_tests,
)


def _context(project_root: Path, *changed_files: str) -> ValidationContext:
    return ValidationContext(
        project_root=project_root,
        changed_files=tuple(Path(item) for item in changed_files),
    )


def _write_test(
    path: Path, content: str = "def test_sample():\n    assert True\n"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_direct_test_change_is_selected_with_full_confidence(tmp_path: Path) -> None:
    project_root = tmp_path
    test_path = project_root / "tests" / "pkg" / "test_changed.py"
    _write_test(test_path)

    selection = select_affected_tests(
        _context(project_root, "tests/pkg/test_changed.py")
    )

    assert selection.selected_tests == (Path("tests/pkg/test_changed.py"),)
    assert selection.confidence == 1.0
    assert not selection.requires_full_suite
    assert "direct_test_change" in selection.reasons


def test_basename_match_selects_equivalent_test(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "test_widget.py")

    selection = select_affected_tests(_context(project_root, "cmm/widget.py"))

    assert selection.selected_tests == (Path("tests/test_widget.py"),)
    assert selection.confidence >= 0.9
    assert not selection.requires_full_suite


def test_package_equivalent_change_selects_scoped_tests(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "runtime" / "test_runtime.py")

    selection = select_affected_tests(_context(project_root, "cmm/runtime/__init__.py"))

    assert selection.selected_tests == (Path("tests/runtime/test_runtime.py"),)
    assert selection.confidence >= 0.75


def test_token_match_is_supported(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(
        project_root
        / "tests"
        / "validation"
        / "test_validation_pipeline_executor_registry.py"
    )

    selection = select_affected_tests(
        _context(project_root, "cmm/feature/pipeline_executor_registry.py")
    )

    assert selection.selected_tests == (
        Path("tests/validation/test_validation_pipeline_executor_registry.py"),
    )
    assert selection.confidence == 0.75


def test_init_change_marks_related_package(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "planner" / "test_planner.py")
    _write_test(project_root / "tests" / "planner" / "test_executor.py")

    selection = select_affected_tests(_context(project_root, "cmm/planner/__init__.py"))

    assert selection.selected_tests == (
        Path("tests/planner/test_executor.py"),
        Path("tests/planner/test_planner.py"),
    )
    assert not selection.requires_full_suite
    assert "package_init" in selection.reasons


def test_config_change_requires_full_suite(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "test_config.py")

    selection = select_affected_tests(_context(project_root, "pyproject.toml"))

    assert selection.requires_full_suite
    assert "pytest_or_packaging_config_change" in selection.reasons
    assert selection.selected_tests == ()


def test_cross_cutting_validation_change_requires_full_suite(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "test_pipeline.py")

    selection = select_affected_tests(
        _context(project_root, "cmm/validation/executor.py")
    )

    assert selection.requires_full_suite
    assert "cross_cutting_validation_change" in selection.reasons


def test_kernel_change_requires_full_suite(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "core" / "test_kernel.py")

    selection = select_affected_tests(_context(project_root, "kernel/runtime.py"))

    assert selection.requires_full_suite
    assert "kernel_change" in selection.reasons


def test_python_change_without_selection_falls_back_to_full_suite(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "test_other.py")

    selection = select_affected_tests(_context(project_root, "cmm/unmatched.py"))

    assert selection.requires_full_suite
    assert "empty_selection_python_changes" in selection.reasons


def test_non_python_changes_do_not_force_full_suite(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "test_readme.py")

    selection = select_affected_tests(_context(project_root, "README.md"))

    assert not selection.requires_full_suite
    assert selection.selected_tests == ()


def test_multiple_packages_require_full_suite(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "core" / "test_core.py")
    _write_test(project_root / "tests" / "planner" / "test_planner.py")

    selection = select_affected_tests(
        _context(project_root, "cmm/core/module.py", "cmm/planner/module.py")
    )

    assert selection.requires_full_suite
    assert "multiple_packages" in selection.reasons


def test_selection_serialization_preserves_metadata(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_test(project_root / "tests" / "test_sample.py")
    selection = _TestSelection(
        selected_tests=(Path("tests/test_sample.py"),),
        related_changes={"cmm/sample.py": ("tests/test_sample.py",)},
        confidence=0.9,
        reasons=("direct_path_match",),
        metadata={"package_scopes": ("sample",)},
    )

    assert selection.serialize()["metadata"] == {"package_scopes": ("sample",)}
