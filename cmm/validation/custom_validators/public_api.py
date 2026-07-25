"""PublicApiValidator implementation for CMM OS custom validators catalog."""

from __future__ import annotations

import ast
import re
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
    read_file_safe,
    serialize_path,
)

VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _defines_top_level_all(tree: ast.AST) -> bool:
    """Check if AST contains a top-level assignment to __all__."""
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return True
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == "__all__":
                return True
    return False


def _find_target_init_files(project_root: Path) -> List[Path]:
    """Identify controlled target __init__.py files for public API inspection."""
    mandatory: List[Path] = []
    for cand in (
        project_root / "cmm" / "__init__.py",
        project_root / "cmm" / "validation" / "__init__.py",
    ):
        if cand.is_file():
            mandatory.append(cand)

    optional_targets: List[Path] = []
    cmm_dir = project_root / "cmm"
    if cmm_dir.is_dir():
        for item in sorted(cmm_dir.iterdir()):
            if item.is_dir():
                init_file = item / "__init__.py"
                if init_file.is_file() and init_file not in mandatory:
                    read_res = read_file_safe(init_file)
                    if read_res.content is not None:
                        try:
                            tree = ast.parse(read_res.content, filename=str(init_file))
                            if _defines_top_level_all(tree):
                                optional_targets.append(init_file)
                        except SyntaxError:
                            pass

    seen: Set[Path] = set()
    result: List[Path] = []
    for t in mandatory + sorted(optional_targets):
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _extract_top_level_names(tree: ast.AST) -> Tuple[Set[str], List[str]]:
    """Extract top-level defined or imported symbol names and duplicate import names."""
    names: Set[str] = set()
    duplicates: List[str] = []

    def _add(name: str) -> None:
        if name in names:
            duplicates.append(name)
        names.add(name)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    _add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                _add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                _add(local_name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local_name = alias.asname or alias.name
                _add(local_name)

    return names, duplicates


class PublicApiValidator(CustomValidator):
    """Validates structural consistency and export contracts of public package APIs."""

    name = "public_api"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        source_name = f"validation.custom.{self.name}"

        init_files = _find_target_init_files(context.project_root)

        findings: List[ValidationFinding] = []
        scanned_modules: List[str] = []
        exports_by_module: Dict[str, List[str]] = {}
        unresolved_exports: List[str] = []
        duplicate_exports: List[str] = []
        private_exports: List[str] = []
        parse_errors: List[str] = []

        for init_file in init_files:
            rel_path = serialize_path(init_file, context.project_root)
            scanned_modules.append(rel_path)

            read_res = read_file_safe(init_file)
            if read_res.is_unreadable or read_res.content is None:
                parse_errors.append(rel_path)
                findings.append(
                    ValidationFinding(
                        code="PUBLIC_API_SCAN_INCOMPLETE",
                        message=f"Could not read module file '{rel_path}' ({read_res.error_type or 'read_error'})",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_path,
                        blocking=True,
                        metadata={"error_type": read_res.error_type or "read_error"},
                    )
                )
                continue

            try:
                tree = ast.parse(read_res.content, filename=str(init_file))
            except SyntaxError as exc:
                parse_errors.append(rel_path)
                msg, meta = format_syntax_error_info(rel_path, exc)
                findings.append(
                    ValidationFinding(
                        code="PUBLIC_API_SYNTAX_ERROR",
                        message=msg,
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_path,
                        blocking=True,
                        metadata=meta,
                    )
                )
                continue

            # Check __all__ assignments
            all_assigns: List[ast.AST] = []
            for stmt in tree.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            all_assigns.append(stmt.value)
                elif isinstance(stmt, ast.AnnAssign):
                    if (
                        isinstance(stmt.target, ast.Name)
                        and stmt.target.id == "__all__"
                    ):
                        if stmt.value is not None:
                            all_assigns.append(stmt.value)

            if len(all_assigns) > 1:
                findings.append(
                    ValidationFinding(
                        code="PUBLIC_API_ALL_MULTIPLE_ASSIGNMENTS",
                        message=f"Multiple assignments to __all__ found in '{rel_path}'",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_path,
                        blocking=True,
                    )
                )
                continue

            if not all_assigns:
                # Lack of __all__ is valid; skip __all__ specific checks for this module
                exports_by_module[rel_path] = []
                continue

            all_node = all_assigns[0]
            is_literal_seq = False
            raw_exports: List[str] = []

            if isinstance(all_node, (ast.List, ast.Tuple)):
                is_literal_seq = True
                for elt in all_node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        raw_exports.append(elt.value)
                    else:
                        is_literal_seq = False

            if not is_literal_seq:
                findings.append(
                    ValidationFinding(
                        code="PUBLIC_API_ALL_NOT_LITERAL",
                        message=f"__all__ in '{rel_path}' is not a literal list or tuple of string constants",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_path,
                        blocking=True,
                    )
                )
                continue

            exports_by_module[rel_path] = raw_exports

            # Check __all__ items
            seen_exports: Set[str] = set()
            defined_names, duplicate_imports = _extract_top_level_names(tree)

            for dup_imp in set(duplicate_imports):
                if dup_imp in raw_exports and not dup_imp.startswith("_"):
                    findings.append(
                        ValidationFinding(
                            code="PUBLIC_API_DUPLICATE_IMPORT",
                            message=f"Symbol '{dup_imp}' imported or defined multiple times in '{rel_path}'",
                            severity=ValidationSeverity.WARNING,
                            source=source_name,
                            file_path=rel_path,
                            blocking=False,
                            metadata={"symbol": dup_imp},
                        )
                    )

            for exp in raw_exports:
                # Check invalid format / empty
                if not exp or not VALID_IDENTIFIER.match(exp):
                    findings.append(
                        ValidationFinding(
                            code="PUBLIC_API_INVALID_EXPORT_NAME",
                            message=f"Export name '{exp}' in '{rel_path}' is empty or invalid identifier",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_path,
                            blocking=True,
                            metadata={"export": exp},
                        )
                    )
                    continue

                # Check private export (exclude standard dunders like __version__)
                if exp.startswith("_") and not (
                    exp.startswith("__") and exp.endswith("__")
                ):
                    private_exports.append(f"{rel_path}:{exp}")
                    findings.append(
                        ValidationFinding(
                            code="PUBLIC_API_PRIVATE_EXPORT",
                            message=f"Private symbol '{exp}' is exported in __all__ of '{rel_path}'",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_path,
                            blocking=True,
                            metadata={"export": exp},
                        )
                    )

                # Check duplicate export
                if exp in seen_exports:
                    duplicate_exports.append(f"{rel_path}:{exp}")
                    findings.append(
                        ValidationFinding(
                            code="PUBLIC_API_DUPLICATE_EXPORT",
                            message=f"Duplicate export '{exp}' found in __all__ of '{rel_path}'",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_path,
                            blocking=True,
                            metadata={"export": exp},
                        )
                    )
                seen_exports.add(exp)

                # Check unresolved export
                if exp not in defined_names:
                    unresolved_exports.append(f"{rel_path}:{exp}")
                    findings.append(
                        ValidationFinding(
                            code="PUBLIC_API_UNRESOLVED_EXPORT",
                            message=f"Export '{exp}' in __all__ cannot be resolved to any definition or import in '{rel_path}'",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_path,
                            blocking=True,
                            metadata={"export": exp},
                        )
                    )

        duration_ms = int((time.monotonic() - t0) * 1000)
        status = aggregate_status(findings)
        completed_at = datetime.now(timezone.utc)

        artifact = ValidationArtifact(
            id="public-api-report",
            kind="public_api_report",
            source=f"validation.custom.{self.name}",
            content={
                "scanned_modules": scanned_modules,
                "exports_by_module": exports_by_module,
                "unresolved_exports": unresolved_exports,
                "duplicate_exports": duplicate_exports,
                "private_exports": private_exports,
                "parse_errors": parse_errors,
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
                "validator_category": "api_integrity",
            },
        )
