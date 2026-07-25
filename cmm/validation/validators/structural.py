"""Basic structural validators for phase 7.3."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Any

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.protocols import InternalValidator
from cmm.validation.steps import ValidationStep, ValidationStepResult
class PythonStructuralValidator(InternalValidator):
    name = "structural"

    def validate(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:
        from cmm.validation.catalog import select_python_files

        files = select_python_files(context)
        findings: list[ValidationFinding] = []
        classes_found: list[str] = []
        functions_found: list[str] = []
        methods_found: list[str] = []
        imports_found: list[str] = []
        duplicates: list[dict[str, Any]] = []

        for rel_path in files:
            abs_path = context.project_root / rel_path
            try:
                source = abs_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            try:
                tree = ast.parse(source, filename=str(abs_path))
            except SyntaxError:
                continue
            top_level_classes = Counter(node.name for node in tree.body if isinstance(node, ast.ClassDef))
            top_level_functions = Counter(node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
            for name, count in top_level_classes.items():
                if count > 1:
                    findings.append(
                        ValidationFinding(
                            code="DUPLICATE_TOP_LEVEL_CLASS",
                            message=f"Top-level class '{name}' is defined {count} times.",
                            severity=ValidationSeverity.ERROR,
                            source="cmm.validation.structural",
                            file_path=rel_path,
                            blocking=True,
                            metadata={"symbol": name},
                        )
                    )
                    duplicates.append({"kind": "class", "name": name, "path": str(rel_path)})
                    classes_found.append(name)
            for name, count in top_level_functions.items():
                if count > 1:
                    findings.append(
                        ValidationFinding(
                            code="DUPLICATE_TOP_LEVEL_FUNCTION",
                            message=f"Top-level function '{name}' is defined {count} times.",
                            severity=ValidationSeverity.ERROR,
                            source="cmm.validation.structural",
                            file_path=rel_path,
                            blocking=True,
                            metadata={"symbol": name},
                        )
                    )
                    duplicates.append({"kind": "function", "name": name, "path": str(rel_path)})
                    functions_found.append(name)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports_found.extend(alias.name for alias in node.names)
                    for alias in node.names:
                        if alias.name in {a.name for a in node.names if a is not alias}:
                            pass
                elif isinstance(node, ast.ImportFrom):
                    imports_found.extend(alias.name for alias in node.names)
            import_counter: Counter[str] = Counter()
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_counter[alias.name] += 1
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        import_counter[f"{node.module}.{alias.name}"] += 1
            for name, count in import_counter.items():
                if count > 1:
                    findings.append(
                        ValidationFinding(
                            code="DUPLICATE_IMPORT",
                            message=f"Import '{name}' is repeated {count} times.",
                            severity=ValidationSeverity.ERROR,
                            source="cmm.validation.structural",
                            file_path=rel_path,
                            blocking=True,
                            metadata={"import": name},
                        )
                    )
                    duplicates.append({"kind": "import", "name": name, "path": str(rel_path)})

            def collect_class_methods(class_node: ast.ClassDef) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
                methods: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
                for child in class_node.body:
                    if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                        methods.append((child.name, child))
                return methods

            for class_node in [node for node in tree.body if isinstance(node, ast.ClassDef)]:
                method_counter: Counter[str] = Counter()
                for name, _ in collect_class_methods(class_node):
                    method_counter[name] += 1
                for name, count in method_counter.items():
                    if count > 1:
                        findings.append(
                            ValidationFinding(
                                code="DUPLICATE_CLASS_METHOD",
                                message=f"Method '{name}' is defined {count} times inside class '{class_node.name}'.",
                                severity=ValidationSeverity.ERROR,
                                source="cmm.validation.structural",
                                file_path=rel_path,
                                blocking=True,
                                metadata={"class": class_node.name, "method": name},
                            )
                        )
                        duplicates.append({"kind": "method", "name": name, "path": str(rel_path), "class": class_node.name})
                        methods_found.append(name)

        artifact = ValidationArtifact(
            id="structural-report",
            kind="structural_report",
            source="cmm.validation.structural",
            content={
                "checked_files": [str(p) for p in files],
                "classes_found": classes_found,
                "functions_found": functions_found,
                "methods_found": methods_found,
                "imports_found": imports_found,
                "duplicates_detected": duplicates,
            },
            findings=tuple(findings),
            metrics={
                "files_checked": len(files),
                "classes_found": len(classes_found),
                "functions_found": len(functions_found),
                "methods_found": len(methods_found),
                "imports_found": len(imports_found),
                "duplicates_detected": len(duplicates),
            },
        )
        status = ValidationStatus.FAILED if findings else ValidationStatus.PASSED
        return ValidationStepResult(
            name=step.name,
            status=status,
            findings=tuple(findings),
            artifacts=(artifact,),
            metadata={"files": [str(p) for p in files]},
        )
