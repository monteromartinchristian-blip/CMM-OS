from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from cmm.validation.errors import ValidationContractError

from .contracts import (
    ChangeType,
    ImportChange,
    ImportChangeKind,
    PublicAPIChange,
    PublicAPIChangeKind,
    SymbolChange,
    SymbolChangeKind,
)


@dataclass(frozen=True, slots=True)
class PythonSymbolSnapshot:
    name: str
    kind: str
    signature: str
    decorators: tuple[str, ...]
    bases: tuple[str, ...]
    public: bool


@dataclass(frozen=True, slots=True)
class PythonModuleDiff:
    module_name: str
    change_type: ChangeType
    symbol_changes: tuple[SymbolChange, ...]
    import_changes: tuple[ImportChange, ...]
    public_api_changes: tuple[PublicAPIChange, ...]
    signature_changed: bool
    decorator_changed: bool
    public_api_changed: bool
    confidence: float
    uncertainty: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationContractError("PythonModuleDiff.confidence must be between 0 and 1")
        object.__setattr__(self, "symbol_changes", tuple(self.symbol_changes or ()))
        object.__setattr__(self, "import_changes", tuple(self.import_changes or ()))
        object.__setattr__(self, "public_api_changes", tuple(self.public_api_changes or ()))
        object.__setattr__(self, "uncertainty", tuple(str(item) for item in self.uncertainty or ()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "change_type": self.change_type.value,
            "symbol_changes": [item.serialize() for item in self.symbol_changes],
            "import_changes": [item.serialize() for item in self.import_changes],
            "public_api_changes": [item.serialize() for item in self.public_api_changes],
            "signature_changed": self.signature_changed,
            "decorator_changed": self.decorator_changed,
            "public_api_changed": self.public_api_changed,
            "confidence": self.confidence,
            "uncertainty": list(self.uncertainty),
            "metadata": dict(self.metadata or {}),
        }


def diff_python_sources(
    *,
    module_name: str,
    before_source: str | None,
    after_source: str | None,
    before_path: Path | None = None,
    after_path: Path | None = None,
) -> PythonModuleDiff:
    before = _module_snapshot(module_name, before_source, before_path)
    after = _module_snapshot(module_name, after_source, after_path)

    before_symbols = {item.name: item for item in before["symbols"]}
    after_symbols = {item.name: item for item in after["symbols"]}
    before_imports = set(before["imports"])
    after_imports = set(after["imports"])
    before_public = set(before["public_api"])
    after_public = set(after["public_api"])

    symbol_changes: list[SymbolChange] = []
    signature_changed = False
    decorator_changed = False
    public_api_changed = before_public != after_public

    for name in sorted(before_symbols.keys() | after_symbols.keys()):
        before_item = before_symbols.get(name)
        after_item = after_symbols.get(name)
        if before_item is None and after_item is not None:
            symbol_changes.append(
                SymbolChange(
                    module=module_name,
                    symbol=name,
                    kind=SymbolChangeKind.ADDED,
                    confidence=0.95,
                    after_signature=after_item.signature,
                    after_decorators=after_item.decorators,
                    after_bases=after_item.bases,
                    public_before=False,
                    public_after=after_item.public,
                )
            )
            public_api_changed = public_api_changed or after_item.public
            continue
        if before_item is not None and after_item is None:
            symbol_changes.append(
                SymbolChange(
                    module=module_name,
                    symbol=name,
                    kind=SymbolChangeKind.DELETED,
                    confidence=0.95,
                    before_signature=before_item.signature,
                    before_decorators=before_item.decorators,
                    before_bases=before_item.bases,
                    public_before=before_item.public,
                    public_after=False,
                )
            )
            public_api_changed = public_api_changed or before_item.public
            continue
        assert before_item is not None and after_item is not None
        changed_signature = before_item.signature != after_item.signature or before_item.bases != after_item.bases
        changed_decorators = before_item.decorators != after_item.decorators
        if changed_signature or changed_decorators:
            symbol_changes.append(
                SymbolChange(
                    module=module_name,
                    symbol=name,
                    kind=SymbolChangeKind.MODIFIED,
                    confidence=0.9,
                    before_signature=before_item.signature,
                    after_signature=after_item.signature,
                    before_decorators=before_item.decorators,
                    after_decorators=after_item.decorators,
                    before_bases=before_item.bases,
                    after_bases=after_item.bases,
                    public_before=before_item.public,
                    public_after=after_item.public,
                    reasons=tuple(
                        reason
                        for reason, enabled in (
                            ("signature_changed", changed_signature),
                            ("decorator_changed", changed_decorators),
                        )
                        if enabled
                    ),
                )
            )
            signature_changed = signature_changed or changed_signature
            decorator_changed = decorator_changed or changed_decorators
    import_changes: list[ImportChange] = []
    for import_name in sorted(before_imports - after_imports):
        imported_module, imported_symbol, alias = _split_import(import_name)
        import_changes.append(
            ImportChange(
                module=module_name,
                imported_module=imported_module,
                imported_symbol=imported_symbol,
                alias=alias,
                kind=ImportChangeKind.REMOVED,
                confidence=0.95,
                before=import_name,
                reasons=("import_removed",),
            )
        )
    for import_name in sorted(after_imports - before_imports):
        imported_module, imported_symbol, alias = _split_import(import_name)
        import_changes.append(
            ImportChange(
                module=module_name,
                imported_module=imported_module,
                imported_symbol=imported_symbol,
                alias=alias,
                kind=ImportChangeKind.ADDED,
                confidence=0.95,
                after=import_name,
                reasons=("import_added",),
            )
        )

    public_api_changes: list[PublicAPIChange] = []
    if public_api_changed:
        added = tuple(sorted(after_public - before_public))
        removed = tuple(sorted(before_public - after_public))
        changed = tuple(sorted(
            name
            for name in before_symbols.keys() & after_symbols.keys()
            if before_symbols[name].public and after_symbols[name].public and before_symbols[name].signature != after_symbols[name].signature
        ))
        public_api_changes.append(
            PublicAPIChange(
                module=module_name,
                added=added,
                removed=removed,
                changed=changed,
                confidence=0.85 if (added or removed or changed) else 0.7,
                reasons=("public_api_diff",),
            )
        )

    has_symbol_changes = bool(symbol_changes)
    has_import_changes = bool(import_changes)
    if public_api_changed:
        change_type = ChangeType.PUBLIC_API_CHANGE
    elif has_symbol_changes:
        change_type = ChangeType.STRUCTURAL_CHANGE
    elif has_import_changes:
        change_type = ChangeType.IMPORT_CHANGE
    else:
        change_type = ChangeType.UNKNOWN

    uncertainty: list[str] = []
    if before_source is None:
        uncertainty.append("missing_before_source")
    if after_source is None:
        uncertainty.append("missing_after_source")
    if not before["parsed"] or not after["parsed"]:
        uncertainty.append("parse_recovery")

    confidence = 1.0
    if has_symbol_changes:
        confidence -= 0.1
    if has_import_changes:
        confidence -= 0.05
    if public_api_changed:
        confidence -= 0.15
    if uncertainty:
        confidence -= 0.1 * len(uncertainty)
    confidence = max(0.0, min(1.0, confidence))

    return PythonModuleDiff(
        module_name=module_name,
        change_type=change_type,
        symbol_changes=tuple(symbol_changes),
        import_changes=tuple(import_changes),
        public_api_changes=tuple(public_api_changes),
        signature_changed=signature_changed,
        decorator_changed=decorator_changed,
        public_api_changed=public_api_changed,
        confidence=confidence,
        uncertainty=tuple(uncertainty),
        metadata={
            "before_path": None if before_path is None else str(before_path),
            "after_path": None if after_path is None else str(after_path),
        },
    )


def _module_snapshot(module_name: str, source: str | None, path: Path | None) -> dict[str, Any]:
    if source is None:
        return {"symbols": tuple(), "imports": tuple(), "public_api": tuple(), "parsed": False}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"symbols": tuple(), "imports": tuple(), "public_api": tuple(), "parsed": False}

    imports = tuple(sorted(_collect_imports(tree)))
    symbols = tuple(sorted(_collect_symbols(tree), key=lambda item: item.name))
    public_api = _collect_public_api(tree, symbols)
    return {"symbols": symbols, "imports": imports, "public_api": public_api, "parsed": True}


def _collect_imports(tree: ast.Module) -> set[str]:
    imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(_format_import_alias(alias))
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    imports.add(f"from {module} import *")
                else:
                    imports.add(
                        f"from {module} import {alias.name}"
                        + (f" as {alias.asname}" if alias.asname else "")
                    )
    return imports


def _collect_symbols(tree: ast.Module) -> set[PythonSymbolSnapshot]:
    symbols: set[PythonSymbolSnapshot] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(
                PythonSymbolSnapshot(
                    name=node.name,
                    kind="function",
                    signature=_function_signature(node),
                    decorators=tuple(_format_decorator(item) for item in node.decorator_list),
                    bases=(),
                    public=not node.name.startswith("_"),
                )
            )
        elif isinstance(node, ast.ClassDef):
            symbols.add(
                PythonSymbolSnapshot(
                    name=node.name,
                    kind="class",
                    signature=_class_signature(node),
                    decorators=tuple(_format_decorator(item) for item in node.decorator_list),
                    bases=tuple(_format_expr(item) for item in node.bases),
                    public=not node.name.startswith("_"),
                )
            )
    return symbols


def _collect_public_api(tree: ast.Module, symbols: tuple[PythonSymbolSnapshot, ...]) -> tuple[str, ...]:
    exports: list[str] = [item.name for item in symbols if item.public]
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    values = _extract_string_sequence(node.value)
                    if values:
                        return tuple(sorted(values))
    return tuple(sorted(dict.fromkeys(exports)))


def _extract_string_sequence(node: ast.AST) -> tuple[str, ...]:
    items: list[str] = []
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for item in node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                items.append(item.value)
    return tuple(items)


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []
    positional = list(node.args.posonlyargs) + list(node.args.args)
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults, strict=False):
        parts.append(_format_arg(arg, default))
    if node.args.posonlyargs:
        parts.insert(len(node.args.posonlyargs), "/")
    if node.args.vararg is not None:
        parts.append("*" + _format_arg(node.args.vararg))
    elif node.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=False):
        parts.append(_format_arg(arg, default))
    if node.args.kwarg is not None:
        parts.append("**" + _format_arg(node.args.kwarg))
    signature = ", ".join(item for item in parts if item)
    return_annotation = f" -> {_format_expr(node.returns)}" if node.returns is not None else ""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({signature}){return_annotation}"


def _class_signature(node: ast.ClassDef) -> str:
    bases = ", ".join(_format_expr(base) for base in node.bases)
    keywords = ", ".join(
        f"{kw.arg}={_format_expr(kw.value)}" if kw.arg else f"**{_format_expr(kw.value)}"
        for kw in node.keywords
    )
    signature_items = [item for item in (bases, keywords) if item]
    suffix = f"({', '.join(signature_items)})" if signature_items else ""
    return f"class {node.name}{suffix}"


def _format_arg(arg: ast.arg, default: ast.AST | None = None) -> str:
    value = arg.arg
    if arg.annotation is not None:
        value += f": {_format_expr(arg.annotation)}"
    if default is not None:
        value += f"={_format_expr(default)}"
    return value


def _format_decorator(node: ast.AST) -> str:
    return _format_expr(node)


def _format_import_alias(alias: ast.alias) -> str:
    return alias.name + (f" as {alias.asname}" if alias.asname else "")


def _format_expr(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = _format_expr(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        if isinstance(node, ast.Constant):
            return repr(node.value)
        return node.__class__.__name__


def _split_import(value: str) -> tuple[str, str | None, str | None]:
    if value.startswith("from "):
        prefix, _, remainder = value.partition(" import ")
        module = prefix[len("from ") :]
        imported_symbol = None
        alias = None
        if " as " in remainder:
            imported_symbol, alias = remainder.split(" as ", maxsplit=1)
        else:
            imported_symbol = remainder
        return module, imported_symbol, alias
    if " as " in value:
        module, alias = value.split(" as ", maxsplit=1)
        return module.replace("import ", "").strip(), None, alias.strip()
    return value.replace("import ", "").strip(), None, None
