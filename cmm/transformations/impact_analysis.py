"""Deterministic, read-only project impact analysis for transformations."""

from __future__ import annotations

import ast
import builtins
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


class ReferenceKind(str, Enum):
    IMPORT = "import"
    SYMBOL = "symbol"
    QUALIFIED = "qualified"
    REEXPORT = "reexport"
    INHERITANCE = "inheritance"
    ANNOTATION = "annotation"
    DYNAMIC = "dynamic"


class ImpactSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ImpactIssueCode(str, Enum):
    INVALID_MODULE = "invalid_module"
    INVALID_PYTHON = "invalid_python"
    UNKNOWN_REFERENCE = "unknown_reference"
    AMBIGUOUS_REFERENCE = "ambiguous_reference"
    DYNAMIC_REFERENCE = "dynamic_reference"
    UNSUPPORTED_IMPORT = "unsupported_import"
    DYNAMIC_ALL = "dynamic_all"
    AMBIGUOUS_REEXPORT = "ambiguous_reexport"
    ARCHITECTURAL_CYCLE = "architectural_cycle"
    UNSELECTED_DEPENDENCY = "unselected_dependency"
    TECHNICAL_MEMORY_ERROR = "technical_memory_error"


class RewriteCapability(str, Enum):
    DETECTED = "detected"
    ANALYZABLE = "analyzable"
    REWRITABLE = "rewritable"
    BLOCKING = "blocking"


class ImpactDiscrepancyCode(str, Enum):
    MISSING_TARGET_SYMBOL = "missing_target_symbol"
    SOURCE_SYMBOL_STILL_PRESENT = "source_symbol_still_present"
    STALE_IMPORT = "stale_import"
    STALE_REFERENCE = "stale_reference"
    UNEXPECTED_CYCLE = "unexpected_cycle"
    UNEXPECTED_PATH_CHANGE = "unexpected_path_change"
    MISSING_REEXPORT = "missing_reexport"
    PUBLIC_API_MISMATCH = "public_api_mismatch"
    UNRESOLVED_REFERENCE_AFTER_REWRITE = "unresolved_reference_after_rewrite"
    ROLLBACK_GRAPH_MISMATCH = "rollback_graph_mismatch"


@dataclass(frozen=True)
class ReferenceLocation:
    path: Path
    line: int
    column: int


@dataclass(frozen=True)
class SymbolReference:
    module: str
    symbol: str
    location: ReferenceLocation
    kind: ReferenceKind
    binding: str | None = None
    resolved_target: str | None = None
    capability: RewriteCapability = RewriteCapability.REWRITABLE
    rewrite_supported: bool = True
    blocking_reason: str | None = None


@dataclass(frozen=True)
class ImportReference:
    consumer_module: str
    source_module: str
    imported_symbol: str | None
    alias: str | None
    relative: bool
    location: ReferenceLocation
    reexport: bool = False
    resolved_target: str | None = None
    capability: RewriteCapability = RewriteCapability.REWRITABLE
    rewrite_supported: bool = True
    blocking_reason: str | None = None


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class ImpactIssue:
    code: ImpactIssueCode
    severity: ImpactSeverity
    message: str
    module: str | None = None
    location: ReferenceLocation | None = None
    related_modules: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImpactedModule:
    module: str
    path: Path | None
    reason: str


@dataclass(frozen=True)
class ImpactedSymbol:
    module: str
    symbol: str
    target_module: str
    target_symbol: str


@dataclass(frozen=True)
class ExpectedImpactPlan:
    changed_modules: tuple[str, ...]
    rewritten_imports: tuple[ImportReference, ...]
    rewritten_references: tuple[SymbolReference, ...]
    moved_symbols: tuple[ImpactedSymbol, ...]
    new_modules: tuple[str, ...] = ()
    deleted_modules: tuple[str, ...] = ()
    expected_cycles: tuple[tuple[str, ...], ...] = ()
    public_bindings: tuple[str, ...] = ()
    expected_reexports: tuple[ImportReference, ...] = ()
    expected_paths: tuple[Path, ...] = ()

    def serialize(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible plan data."""
        return _serialize(asdict(self))


@dataclass(frozen=True)
class ImpactDiscrepancy:
    code: ImpactDiscrepancyCode
    message: str
    severity: ImpactSeverity = ImpactSeverity.BLOCKING
    module: str | None = None
    path: Path | None = None
    expected: object | None = None
    actual: object | None = None


@dataclass(frozen=True)
class PostImpactValidationResult:
    success: bool
    discrepancies: tuple[ImpactDiscrepancy, ...] = ()
    actual_graph: ProjectReferenceGraph | None = None
    checked_paths: tuple[Path, ...] = ()
    rollback_graph_matches: bool | None = None
    rollback_discrepancies: tuple[ImpactDiscrepancy, ...] = ()


@dataclass(frozen=True)
class ProjectReferenceGraph:
    modules: tuple[str, ...]
    symbols: tuple[str, ...]
    imports: tuple[ImportReference, ...]
    references: tuple[SymbolReference, ...]
    dependencies: tuple[DependencyEdge, ...]
    cycles: tuple[tuple[str, ...], ...] = ()
    issues: tuple[ImpactIssue, ...] = ()


@dataclass(frozen=True)
class ImpactAnalysisRequest:
    source_module: str
    target_module: str
    symbols: tuple[str, ...]
    renamed_symbols: tuple[str, ...] = ()
    transformation_id: str = "transformation"

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbols", tuple(self.symbols))
        object.__setattr__(self, "renamed_symbols", tuple(self.renamed_symbols))
        if not self.source_module or not self.target_module or not self.symbols:
            raise ValueError("Impact analysis requires source, target and symbols.")
        if self.source_module == self.target_module:
            raise ValueError("Impact analysis source and target modules must differ.")
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("Impact analysis symbols must be unique.")
        if len(self.renamed_symbols) not in {0, len(self.symbols)}:
            raise ValueError("renamed_symbols must be empty or parallel to symbols.")


@dataclass(frozen=True)
class ImpactAnalysisResult:
    success: bool
    request: ImpactAnalysisRequest
    graph: ProjectReferenceGraph
    impacted_modules: tuple[str, ...] = ()
    impacted_symbols: tuple[str, ...] = ()
    affected_imports: tuple[ImportReference, ...] = ()
    affected_references: tuple[SymbolReference, ...] = ()
    direct_dependencies: tuple[str, ...] = ()
    transitive_dependencies: tuple[str, ...] = ()
    consumer_modules: tuple[str, ...] = ()
    affected_paths: tuple[Path, ...] = ()
    cycles: tuple[tuple[str, ...], ...] = ()
    ambiguous_references: tuple[SymbolReference, ...] = ()
    dynamic_references: tuple[SymbolReference, ...] = ()
    unsupported_references: tuple[SymbolReference, ...] = ()
    warnings: tuple[ImpactIssue, ...] = ()
    errors: tuple[ImpactIssue, ...] = ()
    plan: ExpectedImpactPlan | None = None
    impacted_module_records: tuple[ImpactedModule, ...] = ()
    memory_refreshed: bool = False
    memory_used: bool = False
    memory_stale: bool = False
    memory_errors: tuple[str, ...] = ()

    @property
    def blocking_issues(self) -> tuple[ImpactIssue, ...]:
        return self.errors

    @property
    def summary(self) -> str:
        if self.success:
            return f"Impact analysis succeeded for {', '.join(self.request.symbols)}."
        return "; ".join(issue.message for issue in self.errors) or "Impact analysis failed."


class ImpactAnalyzer:
    """Build a project graph and analyze a proposed symbol move/extraction."""

    def __init__(self, technical_memory: Any | None = None) -> None:
        self._technical_memory = technical_memory

    def analyze(self, context: Any, request: ImpactAnalysisRequest) -> ImpactAnalysisResult:
        snapshot = context.semantic_context.snapshot
        issues: list[ImpactIssue] = []
        modules: dict[str, Any] = {}
        for item in snapshot.modules:
            if not item.path.resolve().is_relative_to(context.project_root):
                issues.append(ImpactIssue(
                    ImpactIssueCode.INVALID_MODULE,
                    ImpactSeverity.BLOCKING,
                    f"Module path escapes project_root: {item.path}.",
                    item.module_name,
                ))
                continue
            modules[item.module_name] = item
        imports: list[ImportReference] = []
        references: list[SymbolReference] = []
        dependencies: list[DependencyEdge] = []
        symbols: list[str] = []
        ast_modules: dict[str, ast.Module] = {}
        defs: dict[str, set[str]] = {}
        for module_name, module in sorted(modules.items()):
            if module.parsed_module is None:
                issues.append(ImpactIssue(
                    ImpactIssueCode.INVALID_PYTHON,
                    ImpactSeverity.BLOCKING,
                    f"Python module is not analyzable: {module_name}.",
                    module_name,
                ))
                continue
            try:
                tree = ast.parse(module.parsed_module.code, filename=str(module.path))
            except SyntaxError as error:
                issues.append(ImpactIssue(
                    ImpactIssueCode.INVALID_PYTHON,
                    ImpactSeverity.BLOCKING,
                    f"Invalid Python in {module_name}: {error}.",
                    module_name,
                ))
                continue
            ast_modules[module_name] = tree
            defs[module_name] = {
                node.name for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            }
            symbols.extend(f"{module_name}.{name}" for name in sorted(defs[module_name]))
            self._collect_imports(module_name, module.path, tree, request, imports, issues)
            self._collect_dynamic(module_name, tree, module.path, references, issues, request)
            self._collect_qualified_references(
                module_name, module.path, tree, request, references, issues
            )
            self._collect_all_issues(module_name, tree, issues)

        import_edges = [
            DependencyEdge(item.consumer_module, item.source_module, "import")
            for item in imports
            if item.source_module in modules
        ]
        dependencies.extend(import_edges)
        cycles = self._cycles(tuple(sorted(modules)), dependencies)
        for cycle in cycles:
            if request.source_module in cycle or request.target_module in cycle:
                issues.append(ImpactIssue(
                    ImpactIssueCode.ARCHITECTURAL_CYCLE,
                    ImpactSeverity.BLOCKING,
                    f"Import cycle affects transformation: {' -> '.join(cycle)}.",
                    related_modules=cycle,
                ))

        selected = set(request.symbols)
        target_defs = defs.get(request.target_module, set())
        qualified = tuple(
            reference for reference in references
            if reference.kind == ReferenceKind.QUALIFIED
            and reference.symbol in selected
        )
        qualified_consumers = {item.module for item in qualified}
        affected_imports = tuple(sorted(
            [
                item for item in imports
                if item.source_module == request.source_module
                and (
                    item.imported_symbol in selected
                    or (
                        item.imported_symbol is None
                        and item.consumer_module in qualified_consumers
                    )
                )
            ],
            key=self._import_key,
        ))
        from cmm.transformations.relative_import_resolver import RelativeImportResolver

        relative_resolver = RelativeImportResolver()
        checked_imports: list[ImportReference] = []
        blocked_imports: dict[tuple[Any, ...], ImportReference] = {}
        for item in affected_imports:
            checked = item
            module_info = modules.get(item.consumer_module)
            if item.relative and relative_resolver.render_relative(
                item.consumer_module,
                request.target_module,
                consumer_is_package=(
                    module_info is not None and module_info.path.name == "__init__.py"
                ),
            ) is None:
                reason = (
                    f"Relative import from {item.consumer_module} to "
                    f"{request.target_module} cannot be preserved."
                )
                checked = replace(
                    item,
                    capability=RewriteCapability.BLOCKING,
                    rewrite_supported=False,
                    blocking_reason=reason,
                )
                issues.append(ImpactIssue(
                    ImpactIssueCode.UNSUPPORTED_IMPORT,
                    ImpactSeverity.BLOCKING,
                    reason,
                    item.consumer_module,
                    item.location,
                ))
                blocked_imports[self._import_key(item)] = checked
            checked_imports.append(checked)
        affected_imports = tuple(checked_imports)
        if blocked_imports:
            imports = [
                blocked_imports.get(self._import_key(item), item)
                for item in imports
            ]
        reexport_modules = {
            item.consumer_module for item in affected_imports if item.reexport
        }
        issues = [
            issue for issue in issues
            if issue.code != ImpactIssueCode.DYNAMIC_ALL
            or issue.module in reexport_modules
        ]
        target_names = request.renamed_symbols or request.symbols
        for reexport in (item for item in affected_imports if item.reexport):
            if reexport.imported_symbol not in request.symbols or reexport.alias is not None:
                continue
            target_name = target_names[request.symbols.index(reexport.imported_symbol)]
            if target_name == reexport.imported_symbol:
                continue
            chained = [
                item for item in imports
                if item.source_module == reexport.consumer_module
                and item.imported_symbol == reexport.imported_symbol
            ]
            for item in chained:
                issues.append(ImpactIssue(
                    ImpactIssueCode.AMBIGUOUS_REEXPORT,
                    ImpactSeverity.BLOCKING,
                    (
                        f"Reexport chain through {reexport.consumer_module} exposes "
                        f"{reexport.imported_symbol} to {item.consumer_module}."
                    ),
                    item.consumer_module,
                    item.location,
                ))
        consumers = tuple(sorted({item.consumer_module for item in affected_imports}))
        consumers = tuple(sorted(set(consumers) | {item.module for item in qualified}))
        for item in affected_imports:
            kind = ReferenceKind.REEXPORT if item.reexport else ReferenceKind.IMPORT
            references.append(SymbolReference(
                item.consumer_module,
                item.imported_symbol or "",
                item.location,
                kind,
                item.alias,
            ))

        direct: set[str] = set()
        for symbol in request.symbols:
            node = self._find_definition(ast_modules.get(request.source_module), symbol)
            if node is None:
                issues.append(ImpactIssue(
                    ImpactIssueCode.UNKNOWN_REFERENCE,
                    ImpactSeverity.BLOCKING,
                    f"Target symbol is not defined top-level: {request.source_module}.{symbol}.",
                    request.source_module,
                ))
                continue
            loaded = self._loaded_names(node)
            local = self._bound_names(node)
            imported = self._import_bindings(ast_modules[request.source_module], request.source_module)
            for name in sorted(loaded - local - set(dir(builtins)) - {"self", "cls"}):
                if name in selected:
                    target = f"{request.source_module}.{name}"
                    direct.add(target)
                    dependencies.append(DependencyEdge(
                        f"{request.source_module}.{symbol}", target, "selected-symbol"
                    ))
                elif name in defs.get(request.source_module, set()) and name not in target_defs:
                    issue = ImpactIssue(
                        ImpactIssueCode.UNSELECTED_DEPENDENCY,
                        ImpactSeverity.BLOCKING,
                        f"Selected symbol {symbol} depends on unselected local symbol {name}.",
                        request.source_module,
                    )
                    issues.append(issue)
                elif name in imported:
                    imported_module, imported_name = imported[name]
                    target = f"{imported_module}.{imported_name}"
                    direct.add(target)
                    dependencies.append(DependencyEdge(
                        f"{request.source_module}.{symbol}", target, "external-import"
                    ))
                else:
                    issues.append(ImpactIssue(
                        ImpactIssueCode.UNKNOWN_REFERENCE,
                        ImpactSeverity.WARNING,
                        f"Reference {name} in {request.source_module}.{symbol} could not be resolved.",
                        request.source_module,
                    ))

        transitive = self._transitive_dependencies(tuple(direct), dependencies)
        affected_path_set = {
            modules[name].path for name in (set(consumers) | {request.source_module, request.target_module})
            if name in modules
        }
        affected_path_set.add(context.module_path(request.source_module))
        affected_path_set.add(context.module_path(request.target_module))
        affected_paths = tuple(sorted(affected_path_set))
        proposed_edges = [
            edge for edge in dependencies
            if not (
                edge.kind == "import"
                and any(
                    item.consumer_module == edge.source
                    and item.source_module == edge.target
                    for item in affected_imports
                )
            )
        ]
        proposed_edges.extend(
            DependencyEdge(item.consumer_module, request.target_module, "import")
            for item in affected_imports
        )
        proposed_cycles = self._cycles(tuple(sorted(modules)), proposed_edges)
        for cycle in sorted(set(proposed_cycles) - set(cycles)):
            issues.append(ImpactIssue(
                ImpactIssueCode.ARCHITECTURAL_CYCLE,
                ImpactSeverity.BLOCKING,
                f"Transformation would introduce an import cycle: {' -> '.join(cycle)}.",
                related_modules=cycle,
            ))
        memory_refreshed = False
        memory_used = self._technical_memory is not None
        memory_stale = False
        memory_errors: list[str] = []
        if self._technical_memory is not None:
            refresh = getattr(self._technical_memory, "refresh", None)
            if callable(refresh):
                try:
                    result = refresh()
                    if not bool(getattr(result, "success", True)):
                        errors = tuple(getattr(result, "errors", ()))
                        raise RuntimeError("; ".join(errors) or "Technical memory refresh failed.")
                    memory_refreshed = bool(getattr(result, "rebuilt", False))
                    change_set = getattr(result, "change_set", None)
                    memory_stale = bool(change_set is not None and not getattr(change_set, "empty", True))
                except (OSError, RuntimeError, ValueError) as error:
                    memory_errors.append(str(error))
                    issues.append(ImpactIssue(
                        ImpactIssueCode.TECHNICAL_MEMORY_ERROR,
                        ImpactSeverity.BLOCKING,
                        f"Technical memory refresh failed: {error}.",
                    ))
        graph = ProjectReferenceGraph(
            modules=tuple(sorted(modules)),
            symbols=tuple(sorted(symbols)),
            imports=tuple(sorted(imports, key=self._import_key)),
            references=tuple(sorted(references, key=self._reference_key)),
            dependencies=tuple(sorted(dependencies, key=lambda item: (item.source, item.target, item.kind))),
            cycles=cycles,
            issues=tuple(issues),
        )
        target_names = request.renamed_symbols or request.symbols
        moved_symbols = tuple(
            ImpactedSymbol(request.source_module, source, request.target_module, target)
            for source, target in zip(request.symbols, target_names, strict=True)
        )
        rewritten_imports = tuple(
            replace(
                item,
                source_module=request.target_module,
                imported_symbol=target_names[request.symbols.index(item.imported_symbol)]
                if item.imported_symbol in request.symbols else item.imported_symbol,
                resolved_target=request.target_module,
            )
            for item in affected_imports
        )
        expected_reexports = tuple(item for item in rewritten_imports if item.reexport)
        public_bindings = tuple(sorted({
            item.alias or item.imported_symbol or ""
            for item in expected_reexports
        } - {""}))
        impacted_module_names = tuple(sorted(set(consumers) | {request.source_module, request.target_module}))
        plan = ExpectedImpactPlan(
            changed_modules=impacted_module_names,
            rewritten_imports=rewritten_imports,
            rewritten_references=tuple(sorted((
                replace(
                    item,
                    symbol=target_names[request.symbols.index(item.symbol)],
                    resolved_target=request.target_module,
                )
                for item in qualified
            ), key=self._reference_key)),
            moved_symbols=moved_symbols,
            new_modules=((request.target_module,) if request.target_module not in modules else ()),
            expected_cycles=proposed_cycles,
            public_bindings=public_bindings,
            expected_reexports=expected_reexports,
            expected_paths=affected_paths,
        )
        errors = tuple(issue for issue in issues if issue.severity == ImpactSeverity.BLOCKING)
        warnings = tuple(issue for issue in issues if issue.severity != ImpactSeverity.BLOCKING)
        return ImpactAnalysisResult(
            success=not errors,
            request=request,
            graph=graph,
            impacted_modules=impacted_module_names,
            impacted_symbols=tuple(sorted(f"{request.source_module}.{name}" for name in request.symbols)),
            affected_imports=affected_imports,
            affected_references=tuple(sorted(references, key=self._reference_key)),
            direct_dependencies=tuple(sorted(direct)),
            transitive_dependencies=tuple(sorted(transitive - direct)),
            consumer_modules=consumers,
            affected_paths=affected_paths,
            cycles=cycles,
            ambiguous_references=tuple(
                reference for reference in references
                if reference.capability == RewriteCapability.BLOCKING
                and reference.kind != ReferenceKind.DYNAMIC
            ),
            dynamic_references=tuple(
                reference for reference in references if reference.kind == ReferenceKind.DYNAMIC
            ),
            unsupported_references=tuple(
                reference for reference in references
                if not reference.rewrite_supported
            ),
            warnings=warnings,
            errors=errors,
            plan=plan,
            impacted_module_records=tuple(
                ImpactedModule(name, modules[name].path if name in modules else None, "rewrite")
                for name in impacted_module_names
            ),
            memory_refreshed=memory_refreshed,
            memory_used=memory_used,
            memory_stale=memory_stale,
            memory_errors=tuple(memory_errors),
        )

    def validate_post(
        self,
        context: Any,
        expected: ImpactAnalysisResult,
        changed_paths: tuple[Path, ...] = (),
    ) -> PostImpactValidationResult:
        """Compare the transformed project with the immutable pre-impact plan."""
        request = expected.request
        actual = ImpactAnalyzer().analyze(context, request)
        discrepancies: list[ImpactDiscrepancy] = []
        target_names = request.renamed_symbols or request.symbols
        module_symbols = set(actual.graph.symbols)
        for source_name, target_name in zip(request.symbols, target_names, strict=True):
            if f"{request.target_module}.{target_name}" not in module_symbols:
                discrepancies.append(ImpactDiscrepancy(
                    ImpactDiscrepancyCode.MISSING_TARGET_SYMBOL,
                    f"Target symbol is missing: {request.target_module}.{target_name}.",
                    module=request.target_module,
                    expected=f"{request.target_module}.{target_name}",
                    actual=None,
                ))
            if f"{request.source_module}.{source_name}" in module_symbols:
                discrepancies.append(ImpactDiscrepancy(
                    ImpactDiscrepancyCode.SOURCE_SYMBOL_STILL_PRESENT,
                    f"Source symbol still exists: {request.source_module}.{source_name}.",
                    module=request.source_module,
                    expected=None,
                    actual=f"{request.source_module}.{source_name}",
                ))
        expected_direct_consumers = {
            item.consumer_module
            for item in (expected.plan.rewritten_imports if expected.plan is not None else ())
            if item.imported_symbol is None
        }
        for item in actual.graph.imports:
            if item.source_module == request.source_module and (
                item.imported_symbol in request.symbols
                or (
                    item.imported_symbol is None
                    and item.consumer_module in expected_direct_consumers
                )
            ):
                discrepancies.append(ImpactDiscrepancy(
                    ImpactDiscrepancyCode.STALE_IMPORT,
                    f"Stale import remains in {item.consumer_module}: {item.imported_symbol}.",
                    module=item.consumer_module,
                    path=item.location.path,
                    expected=request.target_module,
                    actual=request.source_module,
                ))
        stale_qualified = [
            item for item in actual.graph.references
            if item.kind == ReferenceKind.QUALIFIED and item.symbol in request.symbols
        ]
        for item in stale_qualified:
            discrepancies.append(ImpactDiscrepancy(
                ImpactDiscrepancyCode.STALE_REFERENCE,
                f"Stale qualified reference remains in {item.module}: {item.symbol}.",
                module=item.module,
                path=item.location.path,
                expected=request.target_module,
                actual=request.source_module,
            ))
        expected_cycles = set(
            expected.plan.expected_cycles
            if expected.plan is not None
            else expected.graph.cycles
        )
        for cycle in actual.graph.cycles:
            if cycle not in expected_cycles:
                discrepancies.append(ImpactDiscrepancy(
                    ImpactDiscrepancyCode.UNEXPECTED_CYCLE,
                    f"Unexpected cycle introduced: {' -> '.join(cycle)}.",
                    expected=tuple(sorted(expected_cycles)),
                    actual=cycle,
                ))
        expected_paths = set(expected.plan.expected_paths if expected.plan is not None else expected.affected_paths)
        for path in changed_paths:
            if path.suffix == ".py" and path not in expected_paths:
                discrepancies.append(ImpactDiscrepancy(
                    ImpactDiscrepancyCode.UNEXPECTED_PATH_CHANGE,
                    f"Unexpected path changed: {path}.",
                    path=path,
                    expected=tuple(sorted(str(item) for item in expected_paths)),
                    actual=str(path),
                ))
        for issue in actual.errors:
            if issue.code not in {
                ImpactIssueCode.AMBIGUOUS_REFERENCE,
                ImpactIssueCode.DYNAMIC_REFERENCE,
                ImpactIssueCode.DYNAMIC_ALL,
                ImpactIssueCode.UNSUPPORTED_IMPORT,
            }:
                continue
            discrepancies.append(ImpactDiscrepancy(
                ImpactDiscrepancyCode.UNRESOLVED_REFERENCE_AFTER_REWRITE,
                f"Post-transformation reference issue: {issue.message}",
                module=issue.module,
                path=issue.location.path if issue.location is not None else None,
                expected="rewritable static reference",
                actual=issue.code.value,
            ))
        if expected.plan is not None:
            for item in expected.plan.rewritten_imports:
                if not any(
                    actual_import.consumer_module == item.consumer_module
                    and actual_import.source_module == item.source_module
                    and actual_import.imported_symbol == item.imported_symbol
                    and actual_import.alias == item.alias
                    for actual_import in actual.graph.imports
                ):
                    discrepancies.append(ImpactDiscrepancy(
                        ImpactDiscrepancyCode.UNRESOLVED_REFERENCE_AFTER_REWRITE,
                        f"Expected rewritten import is missing in {item.consumer_module}.",
                        module=item.consumer_module,
                        path=item.location.path,
                        expected=(item.source_module, item.imported_symbol, item.alias),
                        actual=None,
                    ))
            for item in expected.plan.expected_reexports:
                if not any(
                    actual_import.consumer_module == item.consumer_module
                    and actual_import.source_module == request.target_module
                    and actual_import.imported_symbol == item.imported_symbol
                    for actual_import in actual.graph.imports
                ):
                    discrepancies.append(ImpactDiscrepancy(
                        ImpactDiscrepancyCode.MISSING_REEXPORT,
                        f"Expected reexport is missing in {item.consumer_module}.",
                        module=item.consumer_module,
                        expected=(request.target_module, item.imported_symbol),
                        actual=None,
                    ))
            for module_name in {item.consumer_module for item in expected.plan.expected_reexports}:
                module_info = next(
                    (item for item in context.semantic_context.snapshot.modules if item.module_name == module_name),
                    None,
                )
                if module_info is None or module_info.parsed_module is None:
                    continue
                tree = ast.parse(module_info.parsed_module.code)
                public_names = self._literal_all(tree)
                if public_names is None:
                    continue
                expected_names = {
                    item.alias or item.imported_symbol
                    for item in expected.plan.expected_reexports
                    if item.consumer_module == module_name
                }
                if not expected_names <= public_names:
                    discrepancies.append(ImpactDiscrepancy(
                        ImpactDiscrepancyCode.PUBLIC_API_MISMATCH,
                        f"Public API mismatch in {module_name}: expected {sorted(expected_names)}.",
                        module=module_name,
                        expected=tuple(sorted(expected_names)),
                        actual=tuple(sorted(public_names)),
                    ))
        return PostImpactValidationResult(
            success=not discrepancies,
            discrepancies=tuple(discrepancies),
            actual_graph=actual.graph,
            checked_paths=tuple(sorted(changed_paths)),
        )

    def validate_rollback(
        self,
        context: Any,
        expected: ImpactAnalysisResult,
    ) -> PostImpactValidationResult:
        """Verify that rollback restored the pre-execution project graph."""
        actual = ImpactAnalyzer().analyze(context, expected.request).graph
        comparable_actual = (
            actual.modules,
            actual.symbols,
            actual.imports,
            actual.references,
            actual.dependencies,
            actual.cycles,
        )
        comparable_expected = (
            expected.graph.modules,
            expected.graph.symbols,
            expected.graph.imports,
            expected.graph.references,
            expected.graph.dependencies,
            expected.graph.cycles,
        )
        discrepancies: tuple[ImpactDiscrepancy, ...] = ()
        if comparable_actual != comparable_expected:
            discrepancies = (ImpactDiscrepancy(
                ImpactDiscrepancyCode.ROLLBACK_GRAPH_MISMATCH,
                "Project reference graph differs from its pre-execution state after rollback.",
                expected=expected.graph,
                actual=actual,
            ),)
        return PostImpactValidationResult(
            success=not discrepancies,
            discrepancies=discrepancies,
            actual_graph=actual,
            rollback_graph_matches=not discrepancies,
            rollback_discrepancies=discrepancies,
        )

    def _literal_all(self, tree: ast.Module) -> set[str] | None:
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
            if isinstance(node.value, (ast.List, ast.Tuple)) and all(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                for item in node.value.elts
            ):
                return {item.value for item in node.value.elts}
            return None
        return None

    def _collect_imports(
        self,
        module: str,
        path: Path,
        tree: ast.Module,
        request: ImpactAnalysisRequest,
        output: list[ImportReference],
        issues: list[ImpactIssue],
    ) -> None:
        from cmm.transformations.relative_import_resolver import RelativeImportResolver

        resolver = RelativeImportResolver()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                resolution = resolver.resolve(
                    module,
                    node.level,
                    node.module or "",
                    consumer_is_package=path.name == "__init__.py",
                )
                if resolution is None:
                    if any(alias.name in request.symbols for alias in node.names):
                        issues.append(ImpactIssue(
                            ImpactIssueCode.UNSUPPORTED_IMPORT,
                            ImpactSeverity.BLOCKING,
                            f"Relative import escapes or is ambiguous in {module}.",
                            module,
                            self._location(module, node, path),
                        ))
                    continue
                source = resolution.absolute_module
                reexport = path.name == "__init__.py"
                if any(alias.name == "*" for alias in node.names):
                    if source != request.source_module:
                        continue
                    issues.append(ImpactIssue(ImpactIssueCode.UNSUPPORTED_IMPORT, ImpactSeverity.BLOCKING, f"Wildcard import in {module}.", module))
                    continue
                for alias in node.names:
                    output.append(ImportReference(module, source, alias.name, alias.asname, node.level > 0, self._location(module, node, path), reexport))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    output.append(ImportReference(module, alias.name, None, alias.asname, False, self._location(module, node, path), False))

    def _collect_qualified_references(
        self,
        module: str,
        path: Path,
        tree: ast.Module,
        request: ImpactAnalysisRequest,
        output: list[SymbolReference],
        issues: list[ImpactIssue],
    ) -> None:
        aliases: dict[str, tuple[str, bool]] = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name.split(".", 1)[0]] = (
                        alias.name,
                        alias.asname is not None,
                    )
        selected_references: list[SymbolReference] = []
        other_bindings: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            parts: list[str] = []
            current: ast.AST = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            parts.reverse()
            if len(parts) < 2:
                continue
            binding = aliases.get(parts[0])
            if binding is None or binding[0] != request.source_module:
                continue
            if binding[1]:
                symbol_index = 1
            else:
                module_parts = request.source_module.split(".")
                if parts[: len(module_parts)] != module_parts:
                    continue
                symbol_index = len(module_parts)
            if symbol_index >= len(parts):
                continue
            if parts[symbol_index] not in request.symbols:
                other_bindings.add(parts[0])
                continue
            shadowed = self._binding_shadowed(tree, parts[0])
            capability = RewriteCapability.BLOCKING if shadowed else RewriteCapability.REWRITABLE
            location = ReferenceLocation(path, node.lineno, node.col_offset)
            selected_references.append(SymbolReference(
                module,
                parts[symbol_index],
                location,
                ReferenceKind.QUALIFIED,
                parts[0],
                request.source_module,
                capability,
                not shadowed,
                f"Module binding {parts[0]} is shadowed." if shadowed else None,
            ))
            if shadowed:
                issues.append(ImpactIssue(
                    ImpactIssueCode.AMBIGUOUS_REFERENCE,
                    ImpactSeverity.BLOCKING,
                    f"Module binding {parts[0]} is shadowed in {module}.",
                    module,
                    location,
                ))
        output.extend(selected_references)
        mixed = sorted({item.binding for item in selected_references} & other_bindings)
        for binding in mixed:
            issues.append(ImpactIssue(
                ImpactIssueCode.AMBIGUOUS_REFERENCE,
                ImpactSeverity.BLOCKING,
                f"Module binding {binding} mixes moved and non-moved symbol references in {module}.",
                module,
            ))

    def _collect_dynamic(self, module: str, tree: ast.Module, path: Path, references: list[SymbolReference], issues: list[ImpactIssue], request: ImpactAnalysisRequest) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name) and node.func.id in {"getattr", "eval", "exec", "__import__"}
                or isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
            ):
                values = {
                    arg.value for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                }
                function_name = (
                    node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                )
                if function_name == "getattr":
                    relevant = bool(values & set(request.symbols))
                elif function_name in {"__import__", "import_module"}:
                    relevant = request.source_module in values
                else:
                    relevant = any(
                        request.source_module in value
                        or any(symbol in value for symbol in request.symbols)
                        for value in values
                    )
                if relevant:
                    location = ReferenceLocation(path, node.lineno, node.col_offset)
                    reference = SymbolReference(
                        module,
                        request.symbols[0] if request.symbols else "",
                        location,
                        ReferenceKind.DYNAMIC,
                        capability=RewriteCapability.BLOCKING,
                        rewrite_supported=False,
                        blocking_reason="Dynamic references cannot be resolved statically.",
                    )
                    references.append(reference)
                    issues.append(ImpactIssue(ImpactIssueCode.DYNAMIC_REFERENCE, ImpactSeverity.BLOCKING, f"Dynamic reference in {module} cannot be rewritten safely.", module, location))

    def _collect_all_issues(self, module: str, tree: ast.Module, issues: list[ImpactIssue]) -> None:
        for node in tree.body:
            dynamic = False
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                dynamic = not isinstance(node.value, (ast.List, ast.Tuple)) or not all(
                    isinstance(item, ast.Constant) and isinstance(item.value, str)
                    for item in node.value.elts
                )
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and isinstance(
                node.target, ast.Name
            ) and node.target.id == "__all__":
                dynamic = True
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                function = node.value.func
                dynamic = (
                    isinstance(function, ast.Attribute)
                    and isinstance(function.value, ast.Name)
                    and function.value.id == "__all__"
                )
            if dynamic:
                issues.append(ImpactIssue(
                    ImpactIssueCode.DYNAMIC_ALL,
                    ImpactSeverity.BLOCKING,
                    f"Dynamic __all__ in {module} cannot be updated safely.",
                    module,
                ))

    def _binding_shadowed(self, tree: ast.Module, binding: str) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.arg) and node.arg == binding:
                return True
            if isinstance(node, ast.Name) and node.id == binding and isinstance(node.ctx, ast.Store):
                return True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == binding:
                return True
        return False

    def _find_definition(self, tree: ast.Module | None, name: str) -> ast.AST | None:
        if tree is None:
            return None
        return next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name), None)

    def _loaded_names(self, node: ast.AST) -> set[str]:
        return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}

    def _bound_names(self, node: ast.AST) -> set[str]:
        bound = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.update(item.arg for item in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs))
            if node.args.vararg:
                bound.add(node.args.vararg.arg)
            if node.args.kwarg:
                bound.add(node.args.kwarg.arg)
        return bound

    def _import_bindings(self, tree: ast.Module, module: str = "") -> dict[str, tuple[str, str]]:
        result = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                source = self._resolve_relative(module, node.level, node.module or "")
                for alias in node.names:
                    if alias.name != "*":
                        result[alias.asname or alias.name] = (source, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result[alias.asname or alias.name.split(".", 1)[0]] = (alias.name, alias.name)
        return result

    def _resolve_relative(self, module: str, level: int, imported: str, package_module: bool = False) -> str:
        if level == 0:
            return imported
        parts = module.split(".") if module else []
        base = parts if package_module else parts[:-1]
        if level > 1:
            base = base[: max(0, len(base) - level + 1)]
        return ".".join((*base, *([imported] if imported else [])))

    def _cycles(self, modules: tuple[str, ...], edges: Iterable[DependencyEdge]) -> tuple[tuple[str, ...], ...]:
        adjacency: dict[str, set[str]] = {module: set() for module in modules}
        for edge in edges:
            if edge.target in adjacency:
                adjacency.setdefault(edge.source, set()).add(edge.target)

        visited: set[str] = set()
        finish_order: list[str] = []
        for start in sorted(adjacency):
            if start in visited:
                continue
            stack: list[tuple[str, bool]] = [(start, False)]
            while stack:
                current, expanded = stack.pop()
                if expanded:
                    finish_order.append(current)
                    continue
                if current in visited:
                    continue
                visited.add(current)
                stack.append((current, True))
                stack.extend(
                    (target, False)
                    for target in sorted(adjacency.get(current, ()), reverse=True)
                    if target not in visited
                )

        reverse: dict[str, set[str]] = {module: set() for module in adjacency}
        for source, targets in adjacency.items():
            for target in targets:
                reverse[target].add(source)
        assigned: set[str] = set()
        cycles: list[tuple[str, ...]] = []
        for start in reversed(finish_order):
            if start in assigned:
                continue
            component: set[str] = set()
            pending = [start]
            assigned.add(start)
            while pending:
                current = pending.pop()
                component.add(current)
                for source in sorted(reverse[current], reverse=True):
                    if source not in assigned:
                        assigned.add(source)
                        pending.append(source)
            if len(component) > 1 or start in adjacency[start]:
                cycles.append(tuple(sorted(component)))
        return tuple(sorted(cycles))

    def _transitive_dependencies(self, roots: tuple[str, ...], edges: Iterable[DependencyEdge]) -> set[str]:
        adjacency: dict[str, set[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
        seen: set[str] = set()
        pending = list(roots)
        while pending:
            current = pending.pop(0)
            if current in seen:
                continue
            seen.add(current)
            pending.extend(sorted(adjacency.get(current, ())))
        return seen

    def _location(self, module: str, node: ast.AST, path: Path | None = None) -> ReferenceLocation:
        return ReferenceLocation(path or Path(module), getattr(node, "lineno", 0), getattr(node, "col_offset", 0))

    def _import_key(self, item: ImportReference) -> tuple[Any, ...]:
        return (item.consumer_module, item.source_module, item.imported_symbol or "", item.alias or "", item.location.line)

    def _reference_key(self, item: SymbolReference) -> tuple[Any, ...]:
        return (item.module, item.symbol, item.location.line, item.location.column, item.kind.value)


def _serialize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value
