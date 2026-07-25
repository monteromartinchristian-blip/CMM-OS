"""ValidationContractValidator implementation for CMM OS custom validators catalog."""

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
    read_file_safe,
    serialize_path,
)

REQUIRED_VALIDATION_MODULES = (
    "__init__.py",
    "custom.py",
    "pipeline.py",
    "registry.py",
    "steps.py",
    "results.py",
    "context.py",
    "enums.py",
    "findings.py",
    "artifacts.py",
)

REQUIRED_EXPORTS = (
    "ValidationContext",
    "ValidationStep",
    "ValidationStepResult",
    "ValidationPipeline",
    "ValidationRegistry",
    "ValidationExecutor",
    "ValidationFinding",
    "ValidationArtifact",
    "ValidationStatus",
    "ValidationSeverity",
    "CustomValidator",
    "CustomValidatorRegistry",
    "build_custom_validation_step",
)


def _extract_module_symbols(
    tree: ast.AST,
) -> Tuple[Set[str], Dict[str, Tuple[str | None, int, str]]]:
    """Extract top-level defined/imported symbols and relative imports from AST.

    Returns:
        (defined_or_imported_symbols, relative_imports)
        where relative_imports is {local_alias: (module_name, level, imported_symbol_name)}
    """
    symbols: Set[str] = set()
    rel_imports: Dict[str, Tuple[str | None, int, str]] = {}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                symbols.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                symbols.add(local_name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local_name = alias.asname or alias.name
                symbols.add(local_name)
                if node.level and node.level > 0:
                    rel_imports[local_name] = (node.module, node.level, alias.name)

    return symbols, rel_imports


def _resolve_relative_import_target(
    validation_dir: Path,
    module: str | None,
    level: int,
    imported_sym: str,
) -> Tuple[bool, str, str]:
    """Resolve a relative import to its target file and verify symbol presence.

    Returns:
        (resolved: bool, target_path_str: str, reason: str)
    """
    if level == 1:
        base_dir = validation_dir
    elif level == 2:
        base_dir = validation_dir.parent
    else:
        return False, "", "path_traversal_out_of_bounds"

    if module:
        mod_parts = module.split(".")
        cand_file = base_dir.joinpath(*mod_parts).with_suffix(".py")
        cand_pkg = base_dir.joinpath(*mod_parts, "__init__.py")
    else:
        cand_file = base_dir / "__init__.py"
        cand_pkg = base_dir / "__init__.py"

    target_file: Path | None = None
    if cand_file.is_file():
        target_file = cand_file
    elif cand_pkg.is_file():
        target_file = cand_pkg

    if target_file is None:
        target_name = f"{module}.py" if module else "__init__.py"
        return False, target_name, "file_not_found"

    read_res = read_file_safe(target_file)
    if read_res.content is None or read_res.is_unreadable:
        return False, target_file.name, "unreadable"

    try:
        tree = ast.parse(read_res.content, filename=str(target_file))
        defined_syms, _ = _extract_module_symbols(tree)
    except SyntaxError:
        return False, target_file.name, "syntax_error"

    if imported_sym == "*" or imported_sym in defined_syms:
        return True, target_file.name, "ok"

    return False, target_file.name, "symbol_not_found"


class ValidationContractValidator(CustomValidator):
    """Validates structural integrity, essential files, and public contract of cmm.validation."""

    name = "validation_contract"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()
        source_name = f"validation.custom.{self.name}"

        validation_dir = context.project_root / "cmm" / "validation"
        rel_validation_dir = serialize_path(validation_dir, context.project_root)

        findings: List[ValidationFinding] = []
        missing_modules: List[str] = []
        resolved_exports: List[str] = []
        missing_exports: List[str] = []
        duplicate_exports: List[str] = []
        unresolved_exports: List[str] = []

        # 1. Check required modules
        for mod_name in REQUIRED_VALIDATION_MODULES:
            mod_file = validation_dir / mod_name
            if not mod_file.is_file():
                missing_modules.append(mod_name)
                findings.append(
                    ValidationFinding(
                        code="VALIDATION_MODULE_MISSING",
                        message=f"Required validation module '{mod_name}' is missing under cmm/validation/",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=f"{rel_validation_dir}/{mod_name}",
                        blocking=True,
                        metadata={"module": mod_name},
                    )
                )

        init_file = validation_dir / "__init__.py"
        rel_init_file = serialize_path(init_file, context.project_root)

        if not init_file.is_file():
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                missing_modules=missing_modules,
                resolved_exports=resolved_exports,
                missing_exports=list(REQUIRED_EXPORTS),
                duplicate_exports=duplicate_exports,
                unresolved_exports=unresolved_exports,
            )

        # 2. Read and parse __init__.py AST
        read_res = read_file_safe(init_file)
        if read_res.is_unreadable or read_res.content is None:
            findings.append(
                ValidationFinding(
                    code="VALIDATION_INIT_READ_ERROR",
                    message=f"cmm/validation/__init__.py could not be read ({read_res.error_type or 'read_error'})",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_init_file,
                    blocking=True,
                    metadata={"error_type": read_res.error_type or "read_error"},
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                missing_modules=missing_modules,
                resolved_exports=resolved_exports,
                missing_exports=list(REQUIRED_EXPORTS),
                duplicate_exports=duplicate_exports,
                unresolved_exports=unresolved_exports,
            )

        try:
            tree = ast.parse(read_res.content, filename=str(init_file))
        except SyntaxError as exc:
            msg, meta = format_syntax_error_info(rel_init_file, exc)
            findings.append(
                ValidationFinding(
                    code="VALIDATION_INIT_SYNTAX_ERROR",
                    message=msg,
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_init_file,
                    blocking=True,
                    metadata=meta,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                missing_modules=missing_modules,
                resolved_exports=resolved_exports,
                missing_exports=list(REQUIRED_EXPORTS),
                duplicate_exports=duplicate_exports,
                unresolved_exports=unresolved_exports,
            )

        # 3. Extract __all__ and validate strictly
        all_assigns: List[ast.AST] = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        all_assigns.append(stmt.value)
            elif isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name) and stmt.target.id == "__all__":
                    if stmt.value is not None:
                        all_assigns.append(stmt.value)

        if not all_assigns:
            findings.append(
                ValidationFinding(
                    code="VALIDATION_ALL_MISSING",
                    message="__all__ is not defined in cmm/validation/__init__.py",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_init_file,
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                missing_modules=missing_modules,
                resolved_exports=resolved_exports,
                missing_exports=list(REQUIRED_EXPORTS),
                duplicate_exports=duplicate_exports,
                unresolved_exports=unresolved_exports,
            )

        if len(all_assigns) > 1:
            findings.append(
                ValidationFinding(
                    code="VALIDATION_ALL_MULTIPLE_ASSIGNMENTS",
                    message="Multiple assignments to __all__ found in cmm/validation/__init__.py",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_init_file,
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                missing_modules=missing_modules,
                resolved_exports=resolved_exports,
                missing_exports=list(REQUIRED_EXPORTS),
                duplicate_exports=duplicate_exports,
                unresolved_exports=unresolved_exports,
            )

        all_value_node = all_assigns[0]
        is_literal_seq = False
        has_invalid_item = False
        all_exports: List[str] = []

        if isinstance(all_value_node, (ast.List, ast.Tuple)):
            is_literal_seq = True
            for elt in all_value_node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    all_exports.append(elt.value)
                else:
                    has_invalid_item = True
                    is_literal_seq = False

        if has_invalid_item:
            findings.append(
                ValidationFinding(
                    code="VALIDATION_ALL_INVALID_ITEM",
                    message="__all__ in cmm/validation/__init__.py contains non-string items",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_init_file,
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                missing_modules=missing_modules,
                resolved_exports=resolved_exports,
                missing_exports=list(REQUIRED_EXPORTS),
                duplicate_exports=duplicate_exports,
                unresolved_exports=unresolved_exports,
            )

        if not is_literal_seq:
            findings.append(
                ValidationFinding(
                    code="VALIDATION_ALL_NOT_LITERAL",
                    message="__all__ in cmm/validation/__init__.py is not a literal list or tuple of string constants",
                    severity=ValidationSeverity.ERROR,
                    source=source_name,
                    file_path=rel_init_file,
                    blocking=True,
                )
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            return self._build_result(
                findings=findings,
                started_at=started_at,
                duration_ms=duration_ms,
                missing_modules=missing_modules,
                resolved_exports=resolved_exports,
                missing_exports=list(REQUIRED_EXPORTS),
                duplicate_exports=duplicate_exports,
                unresolved_exports=unresolved_exports,
            )

        # Check duplicates in __all__
        seen_all: Set[str] = set()
        for sym in all_exports:
            if sym in seen_all:
                duplicate_exports.append(sym)
                findings.append(
                    ValidationFinding(
                        code="VALIDATION_ALL_DUPLICATE",
                        message=f"Duplicate export '{sym}' found in __all__ of cmm/validation/__init__.py",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_init_file,
                        blocking=True,
                        metadata={"symbol": sym},
                    )
                )
            seen_all.add(sym)

        # Check required public exports
        all_exports_set = set(all_exports)
        for req_sym in REQUIRED_EXPORTS:
            if req_sym not in all_exports_set:
                missing_exports.append(req_sym)
                findings.append(
                    ValidationFinding(
                        code="VALIDATION_PUBLIC_SYMBOL_MISSING",
                        message=f"Required export '{req_sym}' is missing from __all__ in cmm/validation/__init__.py",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_init_file,
                        blocking=True,
                        metadata={"symbol": req_sym},
                    )
                )

        # 4. AST symbol resolution
        init_symbols, relative_imports = _extract_module_symbols(tree)

        for sym in all_exports:
            if sym not in init_symbols:
                unresolved_exports.append(sym)
                findings.append(
                    ValidationFinding(
                        code="VALIDATION_PUBLIC_SYMBOL_UNRESOLVED",
                        message=f"Export '{sym}' in __all__ is not defined or imported in cmm/validation/__init__.py",
                        severity=ValidationSeverity.ERROR,
                        source=source_name,
                        file_path=rel_init_file,
                        blocking=True,
                        metadata={"symbol": sym},
                    )
                )
            else:
                resolved_exports.append(sym)

        # Check relative imports via static resolver
        for local_sym, (mod_name, level, orig_sym) in relative_imports.items():
            if local_sym in all_exports_set or local_sym in REQUIRED_EXPORTS:
                resolved, target_str, reason = _resolve_relative_import_target(
                    validation_dir, mod_name, level, orig_sym
                )
                if not resolved:
                    findings.append(
                        ValidationFinding(
                            code="VALIDATION_RELATIVE_IMPORT_UNRESOLVED",
                            message=f"Relative import '{orig_sym}' as '{local_sym}' in '{target_str}' failed: {reason}",
                            severity=ValidationSeverity.ERROR,
                            source=source_name,
                            file_path=rel_init_file,
                            blocking=True,
                            metadata={
                                "symbol": local_sym,
                                "imported_symbol": orig_sym,
                                "target": target_str,
                                "reason": reason,
                            },
                        )
                    )

        duration_ms = int((time.monotonic() - t0) * 1000)
        return self._build_result(
            findings=findings,
            started_at=started_at,
            duration_ms=duration_ms,
            missing_modules=missing_modules,
            resolved_exports=resolved_exports,
            missing_exports=missing_exports,
            duplicate_exports=duplicate_exports,
            unresolved_exports=unresolved_exports,
        )

    def _build_result(
        self,
        findings: List[ValidationFinding],
        started_at: datetime,
        duration_ms: int,
        missing_modules: List[str],
        resolved_exports: List[str],
        missing_exports: List[str],
        duplicate_exports: List[str],
        unresolved_exports: List[str],
    ) -> ValidationStepResult:
        status = aggregate_status(findings)
        completed_at = datetime.now(timezone.utc)

        artifact = ValidationArtifact(
            id="validation-contract-report",
            kind="validation_contract_report",
            source=f"validation.custom.{self.name}",
            content={
                "required_modules": list(REQUIRED_VALIDATION_MODULES),
                "missing_modules": missing_modules,
                "required_exports": list(REQUIRED_EXPORTS),
                "resolved_exports": resolved_exports,
                "missing_exports": missing_exports,
                "duplicate_exports": duplicate_exports,
                "unresolved_exports": unresolved_exports,
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
                "validator_category": "code_integrity",
            },
        )
