"""Unit tests for TestLayoutValidator (Phase 7.9 - Block 2)."""

from __future__ import annotations

from pathlib import Path
import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.custom_validators.test_layout import TestLayoutValidator
from cmm.validation.enums import ValidationStatus


def test_test_layout_valid(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_example.py").write_text(
        "def test_foo():\n"
        "    assert True\n\n"
        "class TestBar:\n"
        "    def test_method(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    (tests_dir / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (tests_dir / "helpers.py").write_text(
        "def helper_fn(): return 42\n", encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()

    assert validator.name == "test_layout"
    result = validator.validate(context)

    assert result.status == ValidationStatus.PASSED
    assert len(result.findings) == 0
    assert len(result.artifacts) == 1
    art = result.artifacts[0]
    assert art.kind == "test_layout_report"
    assert art.content["valid"] is True
    # Only test_*.py counts towards test_file_count
    assert art.content["test_file_count"] == 1
    assert art.content["test_function_count"] == 2
    assert art.content["test_class_count"] == 1


def test_test_layout_only_auxiliary_files_produces_no_tests(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (tests_dir / "helpers.py").write_text(
        "def fixture_helper(): pass\n", encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "TEST_LAYOUT_NO_TESTS" for f in result.findings)
    assert result.artifacts[0].content["test_file_count"] == 0


def test_test_layout_misplaced_test_in_source(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_valid.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "test_bad.py").write_text("def test_bad(): pass\n", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    assert any(f.code == "TEST_LAYOUT_TEST_IN_SOURCE" for f in result.findings)


def test_test_layout_empty_canonical_test_file(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_empty.py").write_text("", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.WARNING
    assert any(f.code == "TEST_LAYOUT_EMPTY_TEST_FILE" for f in result.findings)


def test_test_layout_no_test_cases_in_canonical_test_file(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_dummy.py").write_text(
        "def helper_func():\n    return 42\n", encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.WARNING
    assert any(f.code == "TEST_LAYOUT_NO_TEST_CASES" for f in result.findings)


def test_test_layout_syntax_error_sanitized(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_broken.py").write_text("def test_broken(:\n", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    syntax_finding = next(
        f for f in result.findings if f.code == "TEST_LAYOUT_SYNTAX_ERROR"
    )
    assert "line" in syntax_finding.metadata
    assert "column" in syntax_finding.metadata
    assert "def test_broken(:" not in syntax_finding.message
    assert "def test_broken(:" not in str(syntax_finding.metadata)


def test_test_layout_nonstandard_name_warnings(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_ok.py").write_text(
        "def test_something(): pass\n", encoding="utf-8"
    )
    (tests_dir / "tests.py").write_text("x = 1\n", encoding="utf-8")
    (tests_dir / "example_tests.py").write_text("y = 2\n", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.WARNING
    warnings = [f for f in result.findings if f.code == "TEST_LAYOUT_NONSTANDARD_NAME"]
    assert len(warnings) == 2


def test_test_layout_distinct_basenames_in_different_dirs_do_not_collide(
    tmp_path: Path,
) -> None:
    tests_dir = tmp_path / "tests"
    unit_dir = tests_dir / "unit"
    integration_dir = tests_dir / "integration"
    unit_dir.mkdir(parents=True)
    integration_dir.mkdir(parents=True)

    (unit_dir / "test_foo.py").write_text("def test_u(): pass\n", encoding="utf-8")
    (integration_dir / "test_foo.py").write_text(
        "def test_i(): pass\n", encoding="utf-8"
    )

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.PASSED
    assert len(result.findings) == 0
    assert result.artifacts[0].content["test_file_count"] == 2


def test_test_layout_case_insensitive_module_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    f1 = tests_dir / "API" / "test_x.py"
    f2 = tests_dir / "api" / "test_x.py"
    real_f = tests_dir / "test_real.py"
    real_f.write_text("def test_ok(): pass\n", encoding="utf-8")

    def mock_rglob(self, pattern):
        return [real_f, f1, f2]

    monkeypatch.setattr(Path, "rglob", mock_rglob)

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    assert result.status == ValidationStatus.FAILED
    collision_finding = next(
        f for f in result.findings if f.code == "TEST_LAYOUT_MODULE_COLLISION"
    )
    assert "colliding_file" in collision_finding.metadata


def test_test_layout_serialization(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    serialized = result.serialize()
    assert serialized["name"] == "custom.test_layout"
    assert serialized["artifacts"][0]["kind"] == "test_layout_report"


def test_test_layout_module_named_test_layout_without_tests_is_not_finding(
    tmp_path: Path,
) -> None:
    """Regression: a cmm/ module whose name starts with test_ but contains no
    test_* functions, Test* classes, or pytest references must not produce a
    TEST_LAYOUT_TEST_IN_SOURCE finding.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_valid.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "test_layout.py").write_text(
        "def helper():\n    return 42\n\nCONST = 1\n",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    misplaced = [f for f in result.findings if f.code == "TEST_LAYOUT_TEST_IN_SOURCE"]
    assert misplaced == []
    assert "cmm/test_layout.py" not in result.artifacts[0].content["source_tree_tests"]


def test_test_layout_module_named_test_misplaced_with_test_function_is_finding(
    tmp_path: Path,
) -> None:
    """Regression: a cmm/ module whose name starts with test_ and that does
    contain a test_* function must produce a TEST_LAYOUT_TEST_IN_SOURCE finding.
    """
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_valid.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    cmm_dir = tmp_path / "cmm"
    cmm_dir.mkdir()
    (cmm_dir / "test_misplaced.py").write_text(
        "def test_example():\n    assert True\n",
        encoding="utf-8",
    )

    context = ValidationContext(project_root=tmp_path)
    validator = TestLayoutValidator()
    result = validator.validate(context)

    misplaced = [f for f in result.findings if f.code == "TEST_LAYOUT_TEST_IN_SOURCE"]
    assert len(misplaced) == 1
    assert misplaced[0].file_path == "cmm/test_misplaced.py"
    assert "cmm/test_misplaced.py" in result.artifacts[0].content["source_tree_tests"]
