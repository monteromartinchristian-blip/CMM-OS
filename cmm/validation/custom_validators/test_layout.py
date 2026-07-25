"""TestLayoutValidator implementation for CMM OS custom validators catalog."""

from __future__ import annotations

import ast
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.custom import CustomValidator
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import ValidationStepResult
from ._utils import (
    aggregate_status,
    format_syntax_error_info,
    is_ignored_path,
    read_file_safe,
    serialize_path,
)


def _count_tests_in_ast(tree: ast.AST) -> Tuple[int, int, bool]:
    """Count test functions, Test classes, and check for pytest/parametrize references in AST.

    Returns:
        (test_function_count, test_class_count, has_pytest_references)
    """

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.fn_count = 0
            self.class_count = 0
            self.has_pytest = False

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name.startswith("test_"):
                self.fn_count += 1
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node.name.startswith("test_"):
                self.fn_count += 1
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name.startswith("Test"):
                self.class_count += 1
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if node.attr in ("parametrize", "fixture", "mark", "raises"):
                self.has_pytest = True
            self.generic_visit(node)

        def visit_Name(self, node: ast.Name) -> None:
            if node.id == "pytest":
                self.has_pytest = True
            self.generic_visit(node)

    v = Visitor()
    v.visit(tree)
    return v.fn_count, v.class_count, v.has_pytest


class TestLayoutValidator(CustomValidator):
    """Validates structural layout, naming conventions, and syntax of project tests."""

    __test__ = False
    name = "test_layout"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        source_name = f"validation.custom.{self.name}"

        findings: List[ValidationFinding] = []
        tests_dir = context.project_root / "tests"
        cmm_dir = context.project_root / "cmm"

        empty_files: List[str] = []
        files_without_tests: List[str] = []
        syntax_errors: List[str] = []
        source_tree_tests: List[str] = []
        naming_issues: List[str] = []

        total_fn_count = 0
        total_class_count = 0

        # 1. Check tests/ directory
        if not tests_dir.is_dir():
            findings.append(
                ValidationFinding(
                    code="TEST_LAYOUT_DIRECTORY_MISSING",
                    message="Directory 'tests' was not found in project root",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path="tests",
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                test_file_count=0,
                test_fn_count=0,
                test_class_count=0,
                empty_files=empty_files,
                files_without_tests=files_without_tests,
                syntax_errors=syntax_errors,
                source_tree_tests=source_tree_tests,
                naming_issues=naming_issues,
            )

        # 2. Check test files misplaced in source tree cmm/
        if cmm_dir.is_dir():
            for p in sorted(cmm_dir.rglob("*.py")):
                if is_ignored_path(p):
                    continue
                name = p.name
                if name.startswith("test_") or (
                    name.endswith("_test.py") and name != "conftest.py"
                ):
                    rel_source_test = serialize_path(p, context.project_root)
                    read_res = read_file_safe(p)
                    if read_res.content is None or not read_res.content.strip():
                        # Cannot confirm file actually contains tests; skip emission.
                        continue
                    try:
                        tree = ast.parse(read_res.content, filename=str(p))
                    except SyntaxError:
                        # Cannot confirm file actually contains tests; skip emission.
                        continue
                    fn_count, class_count, has_pytest_ref = _count_tests_in_ast(tree)
                    if fn_count == 0 and class_count == 0 and not has_pytest_ref:
                        continue
                    source_tree_tests.append(rel_source_test)
                    findings.append(
                        ValidationFinding(
                            code="TEST_LAYOUT_TEST_IN_SOURCE",
                            message=f"Test file '{rel_source_test}' misplaced inside source directory 'cmm/'",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_source_test,
                            blocking=True,
                        )
                    )

        # 3. Discover python files under tests/
        all_py_files: List[Path] = []
        for p in sorted(tests_dir.rglob("*.py")):
            if not is_ignored_path(p):
                all_py_files.append(p)

        canonical_test_files: List[Path] = []
        auxiliary_files: List[Path] = []

        for p in all_py_files:
            fname = p.name
            rel_p = serialize_path(p, context.project_root)

            # Non-standard names
            if fname == "tests.py" or (
                fname.endswith("_tests.py") and not fname.startswith("test_")
            ):
                naming_issues.append(rel_p)
                findings.append(
                    ValidationFinding(
                        code="TEST_LAYOUT_NONSTANDARD_NAME",
                        message=f"Test file '{rel_p}' uses non-standard test naming pattern",
                        severity=ValidationSeverity.WARNING,
                        source=source_name,
                        file_path=rel_p,
                        blocking=False,
                    )
                )

            if fname.startswith("test_"):
                canonical_test_files.append(p)
            else:
                auxiliary_files.append(p)

        if not canonical_test_files:
            findings.append(
                ValidationFinding(
                    code="TEST_LAYOUT_NO_TESTS",
                    message="No canonical test files ('test_*.py') were found under 'tests/' directory",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path="tests",
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                test_file_count=0,
                test_fn_count=0,
                test_class_count=0,
                empty_files=empty_files,
                files_without_tests=files_without_tests,
                syntax_errors=syntax_errors,
                source_tree_tests=source_tree_tests,
                naming_issues=naming_issues,
            )

        # 4. Check case-insensitive Python module path collisions among canonical test files
        seen_module_casefold: Dict[str, str] = {}
        for p in canonical_test_files:
            rel_p = serialize_path(p, context.project_root)
            try:
                mod_parts = p.relative_to(tests_dir).with_suffix("").parts
                importable_mod = ".".join(mod_parts)
            except ValueError:
                importable_mod = p.stem

            key = importable_mod.casefold()
            if key in seen_module_casefold:
                prev_path = seen_module_casefold[key]
                findings.append(
                    ValidationFinding(
                        code="TEST_LAYOUT_MODULE_COLLISION",
                        message=f"Case-insensitive module collision between '{rel_p}' and '{prev_path}' as '{importable_mod}'",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_p,
                        blocking=True,
                        metadata={
                            "module": importable_mod,
                            "colliding_file": prev_path,
                        },
                    )
                )
            else:
                seen_module_casefold[key] = rel_p

        # 5. AST syntax and test case analysis for canonical test files
        for p in canonical_test_files:
            rel_p = serialize_path(p, context.project_root)
            fname = p.name

            read_res = read_file_safe(p)
            if read_res.content is None or not read_res.content.strip():
                empty_files.append(rel_p)
                findings.append(
                    ValidationFinding(
                        code="TEST_LAYOUT_EMPTY_TEST_FILE",
                        message=f"Test file '{rel_p}' is empty or contains no code",
                        severity=ValidationSeverity.WARNING,
                        source=source_name,
                        file_path=rel_p,
                        blocking=False,
                    )
                )
                continue

            try:
                tree = ast.parse(read_res.content, filename=str(p))
            except SyntaxError as exc:
                syntax_errors.append(rel_p)
                msg, meta = format_syntax_error_info(rel_p, exc)
                findings.append(
                    ValidationFinding(
                        code="TEST_LAYOUT_SYNTAX_ERROR",
                        message=msg,
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_p,
                        blocking=True,
                        metadata=meta,
                    )
                )
                continue

            fn_count, class_count, has_pytest_ref = _count_tests_in_ast(tree)
            total_fn_count += fn_count
            total_class_count += class_count

            if fn_count == 0 and class_count == 0 and not has_pytest_ref:
                files_without_tests.append(rel_p)
                findings.append(
                    ValidationFinding(
                        code="TEST_LAYOUT_NO_TEST_CASES",
                        message=f"Test file '{rel_p}' contains no test_* functions or Test* classes",
                        severity=ValidationSeverity.WARNING,
                        source=source_name,
                        file_path=rel_p,
                        blocking=False,
                    )
                )

        # 6. Syntax check for auxiliary files (without affecting test_file_count or test case warnings)
        for p in auxiliary_files:
            rel_p = serialize_path(p, context.project_root)
            read_res = read_file_safe(p)
            if read_res.content is not None and read_res.content.strip():
                try:
                    ast.parse(read_res.content, filename=str(p))
                except SyntaxError as exc:
                    syntax_errors.append(rel_p)
                    msg, meta = format_syntax_error_info(rel_p, exc)
                    findings.append(
                        ValidationFinding(
                            code="TEST_LAYOUT_SYNTAX_ERROR",
                            message=msg,
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_p,
                            blocking=True,
                            metadata=meta,
                        )
                    )

        duration_ms = int((time.monotonic() - t0) * 1000)
        return self._build_result(
            findings=findings,
            started_at=started_at,
            duration_ms=duration_ms,
            test_file_count=len(canonical_test_files),
            test_fn_count=total_fn_count,
            test_class_count=total_class_count,
            empty_files=empty_files,
            files_without_tests=files_without_tests,
            syntax_errors=syntax_errors,
            source_tree_tests=source_tree_tests,
            naming_issues=naming_issues,
        )

    def _build_result(
        self,
        findings: List[ValidationFinding],
        started_at: datetime,
        duration_ms: int,
        test_file_count: int,
        test_fn_count: int,
        test_class_count: int,
        empty_files: List[str],
        files_without_tests: List[str],
        syntax_errors: List[str],
        source_tree_tests: List[str],
        naming_issues: List[str],
    ) -> ValidationStepResult:
        status = aggregate_status(findings)
        completed_at = datetime.now(timezone.utc)

        artifact = ValidationArtifact(
            id="test-layout-report",
            kind="test_layout_report",
            source=f"validation.custom.{self.name}",
            content={
                "test_root": "tests",
                "test_file_count": test_file_count,
                "test_function_count": test_fn_count,
                "test_class_count": test_class_count,
                "empty_files": empty_files,
                "files_without_tests": files_without_tests,
                "syntax_errors": syntax_errors,
                "source_tree_tests": source_tree_tests,
                "naming_issues": naming_issues,
                "valid": status == ValidationStatus.PASSED,
            },
            findings=tuple(findings),
        )

        return ValidationStepResult(
            name=f"custom.{self.name}",
            status=status,
            duration_ms=duration_ms,
            findings=tuple(findings),
            artifacts=(artifact,),
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "custom_validator": True,
                "validator_name": self.name,
                "validator_category": "test_integrity",
            },
        )
