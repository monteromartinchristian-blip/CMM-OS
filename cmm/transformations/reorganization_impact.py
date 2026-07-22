"""Impact contracts and validation for module/package reorganization."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from cmm.transformations.impact_analysis import (
    DependencyEdge,
    ExpectedImpactPlan,
    ImpactAnalysisRequest,
    ImpactAnalysisResult,
    ImpactAnalyzer,
    ImpactDiscrepancy,
    ImpactDiscrepancyCode,
    ImpactIssue,
    ImpactIssueCode,
    ImpactSeverity,
    ImpactedModule,
    ImpactedSymbol,
    PostImpactValidationResult,
    ProjectReferenceGraph,
)
from cmm.transformations.operations import (
    MergeModulesOperation,
    MoveModuleOperation,
    MovePackageOperation,
    RenameModuleOperation,
    RenamePackageOperation,
    ReorganizationOperation,
    SplitModuleOperation,
)


@dataclass(frozen=True)
class ReorganizationImpactRequest:
    """Immutable description of layout and symbol moves expected by an operation."""

    transformation_id: str
    module_moves: tuple[tuple[str, str], ...] = ()
    symbol_moves: tuple[tuple[str, str, str], ...] = ()
    package_moves: tuple[tuple[str, str], ...] = ()
    deleted_modules: tuple[str, ...] = ()

    @property
    def source_module(self) -> str:
        if self.module_moves:
            return self.module_moves[0][0]
        if self.symbol_moves:
            return self.symbol_moves[0][0]
        return self.package_moves[0][0]

    @property
    def target_module(self) -> str:
        if self.module_moves:
            return self.module_moves[0][1]
        if self.symbol_moves:
            return self.symbol_moves[0][2]
        return self.package_moves[0][1]

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(item[1] for item in self.symbol_moves) or ("project-layout",)

    @property
    def renamed_symbols(self) -> tuple[str, ...]:
        return ()

    @classmethod
    def from_operation(
        cls, operation: ReorganizationOperation, transformation_id: str
    ) -> "ReorganizationImpactRequest":
        if isinstance(operation, RenameModuleOperation | MoveModuleOperation):
            return cls(
                transformation_id,
                ((operation.source_module, operation.target_module),),
                deleted_modules=(operation.source_module,),
            )
        if isinstance(operation, SplitModuleOperation):
            moves = tuple(
                (operation.source_module, symbol, group.target_module)
                for group in operation.groups
                for symbol in group.symbols
            )
            deleted = (operation.source_module,) if operation.delete_empty_source else ()
            return cls(transformation_id, symbol_moves=moves, deleted_modules=deleted)
        if isinstance(operation, MergeModulesOperation):
            deleted = () if operation.keep_sources else operation.source_modules
            return cls(
                transformation_id,
                module_moves=tuple((source, operation.target_module) for source in operation.source_modules),
                deleted_modules=deleted,
            )
        if isinstance(operation, RenamePackageOperation | MovePackageOperation):
            return cls(
                transformation_id,
                package_moves=((operation.source_package, operation.target_package),),
            )
        raise TypeError(f"Unsupported reorganization operation: {type(operation).__name__}.")


class ReorganizationImpactAnalyzer:
    """Adapt the existing project graph to filesystem-level transformations."""

    def __init__(self, technical_memory: Any | None = None) -> None:
        self._technical_memory = technical_memory

    def analyze(
        self, context: Any, request: ReorganizationImpactRequest
    ) -> ImpactAnalysisResult:
        graph_result = ImpactAnalyzer(self._technical_memory).analyze(
            context,
            ImpactAnalysisRequest(
                source_module=request.source_module,
                target_module=request.target_module,
                symbols=(),
                transformation_id=request.transformation_id,
                graph_only=True,
            ),
        )
        graph = graph_result.graph
        helper = ImpactAnalyzer()
        module_moves = self._expanded_module_moves(graph, request)
        symbol_destinations = {
            (source, symbol): target for source, symbol, target in request.symbol_moves
        }
        affected_imports = tuple(sorted(
            (
                item for item in graph.imports
                if self._mapped_module(item.source_module, module_moves) != item.source_module
                or (
                    item.imported_symbol is not None
                    and self._mapped_module(
                        f"{item.source_module}.{item.imported_symbol}", module_moves
                    )
                    != f"{item.source_module}.{item.imported_symbol}"
                )
                or (item.source_module, item.imported_symbol) in symbol_destinations
            ),
            key=helper._import_key,
        ))
        affected_references = tuple(sorted(
            (
                item for item in graph.references
                if item.resolved_target is not None
                and (
                    self._mapped_module(item.resolved_target, module_moves)
                    != item.resolved_target
                    or (item.resolved_target, item.symbol) in symbol_destinations
                )
            ),
            key=helper._reference_key,
        ))
        consumers = tuple(sorted({item.consumer_module for item in affected_imports}))
        moved_symbols = self._moved_symbols(graph, request, module_moves)
        changed_modules = tuple(sorted({
            *consumers,
            *(item[0] for item in module_moves),
            *(item[1] for item in module_moves),
            *(item[0] for item in request.symbol_moves),
            *(item[2] for item in request.symbol_moves),
        }))
        expected_paths = self._expected_paths(context, request, graph_result.affected_paths)
        deleted_module_names = set(request.deleted_modules)
        for source, _ in request.package_moves:
            deleted_module_names.update(
                module for module in graph.modules
                if module == source or module.startswith(source + ".")
            )
        proposed_modules = tuple(sorted(
            (set(graph.modules) - deleted_module_names)
            | {self._mapped_module(module, module_moves) for module in graph.modules}
            | {target for _, target in module_moves}
            | {target for _, _, target in request.symbol_moves}
        ))
        proposed_dependencies = tuple(sorted({
            (
                self._mapped_module(item.consumer_module, module_moves),
                self._mapped_module(item.source_module, module_moves),
                "import",
            )
            for item in graph.imports
            if self._mapped_module(item.source_module, module_moves) in proposed_modules
            and self._mapped_module(item.consumer_module, module_moves)
                != self._mapped_module(item.source_module, module_moves)
        }))
        proposed_dependencies = tuple(DependencyEdge(*edge) for edge in proposed_dependencies)
        proposed_cycles = helper._cycles(proposed_modules, proposed_dependencies)
        mapped_existing_cycles = {
            tuple(sorted(self._mapped_module(module, module_moves) for module in cycle))
            for cycle in graph.cycles
        }
        new_cycles = tuple(sorted(set(proposed_cycles) - mapped_existing_cycles))
        errors = [
            issue for issue in graph_result.errors
            if issue.code != ImpactIssueCode.ARCHITECTURAL_CYCLE
        ]
        for cycle in new_cycles:
            errors.append(ImpactIssue(
                ImpactIssueCode.ARCHITECTURAL_CYCLE,
                ImpactSeverity.BLOCKING,
                f"Reorganization would introduce an import cycle: {' -> '.join(cycle)}.",
                related_modules=cycle,
            ))
        rewritten_imports = tuple(
            rewritten
            for item in affected_imports
            for rewritten in (
                self._rewrite_import(item, module_moves, symbol_destinations),
            )
            if rewritten.consumer_module != rewritten.source_module
        )
        rewritten_references = tuple(
            replace(
                item,
                module=self._mapped_module(item.module, module_moves),
                resolved_target=symbol_destinations.get(
                    (item.resolved_target, item.symbol),
                    self._mapped_module(item.resolved_target or "", module_moves),
                ),
            )
            for item in affected_references
        )
        package_moves = request.package_moves
        deleted_modules = tuple(sorted(deleted_module_names))
        new_modules = tuple(sorted({new for old, new in module_moves if old != new}))
        expected_packages = self._expected_packages(
            context, request, module_moves, deleted_modules
        )
        proposed_modules = tuple(sorted(set(proposed_modules) | set(expected_packages)))
        expected_public_api = self._expected_public_api(
            context, request, module_moves, deleted_modules
        )
        plan = ExpectedImpactPlan(
            changed_modules=changed_modules,
            rewritten_imports=rewritten_imports,
            rewritten_references=rewritten_references,
            moved_symbols=moved_symbols,
            new_modules=new_modules,
            deleted_modules=deleted_modules,
            expected_cycles=proposed_cycles,
            expected_reexports=tuple(item for item in rewritten_imports if item.reexport),
            public_bindings=tuple(sorted({
                item.alias or item.imported_symbol or ""
                for item in rewritten_imports if item.reexport
            } - {""})),
            expected_paths=expected_paths,
            moved_modules=module_moves,
            moved_packages=package_moves,
            new_packages=tuple(new for _, new in package_moves),
            deleted_packages=tuple(old for old, _ in package_moves),
            expected_modules=proposed_modules,
            expected_packages=expected_packages,
            expected_public_api=expected_public_api,
        )
        return ImpactAnalysisResult(
            success=not errors,
            request=request,  # type: ignore[arg-type]
            graph=graph,
            impacted_modules=changed_modules,
            impacted_symbols=tuple(
                f"{item.module}.{item.symbol}" for item in moved_symbols
            ),
            affected_imports=affected_imports,
            affected_references=affected_references,
            direct_dependencies=graph_result.direct_dependencies,
            transitive_dependencies=graph_result.transitive_dependencies,
            consumer_modules=consumers,
            affected_paths=expected_paths,
            cycles=graph.cycles,
            warnings=graph_result.warnings,
            errors=tuple(errors),
            plan=plan,
            impacted_module_records=tuple(
                ImpactedModule(name, self._module_path(context, name), "reorganization")
                for name in changed_modules
            ),
            memory_refreshed=graph_result.memory_refreshed,
            memory_used=graph_result.memory_used,
            memory_stale=graph_result.memory_stale,
            memory_errors=graph_result.memory_errors,
        )

    def validate_post(
        self,
        context: Any,
        expected: ImpactAnalysisResult,
        changed_paths: tuple[Path, ...],
    ) -> PostImpactValidationResult:
        request = expected.request
        assert isinstance(request, ReorganizationImpactRequest)
        context.refresh_semantic_context()
        actual = self.analyze_graph(context, request)
        discrepancies: list[ImpactDiscrepancy] = []
        plan = expected.plan
        assert plan is not None
        actual_modules = set(actual.modules)
        expected_modules = set(plan.expected_modules)
        for module in sorted(actual_modules - expected_modules):
            discrepancies.append(self._discrepancy(
                ImpactDiscrepancyCode.UNEXPECTED_MODULE,
                f"Unexpected module exists after reorganization: {module}.",
                module,
                actual=module,
            ))
        for source, target in plan.moved_modules:
            if target not in actual_modules:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.MISSING_TARGET_MODULE,
                    f"Target module is missing: {target}.", target, expected=target,
                ))
            if source in plan.deleted_modules and source in actual_modules:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.SOURCE_MODULE_STILL_PRESENT,
                    f"Source module still exists: {source}.", source, actual=source,
                ))
        for moved in plan.moved_symbols:
            target_symbol = f"{moved.target_module}.{moved.target_symbol}"
            source_symbol = f"{moved.module}.{moved.symbol}"
            if target_symbol not in actual.symbols:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.SYMBOL_IN_WRONG_MODULE,
                    f"Symbol {moved.symbol} is not present in {moved.target_module}.",
                    moved.target_module,
                    expected=target_symbol,
                ))
            if moved.module in plan.deleted_modules and source_symbol in actual.symbols:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.SOURCE_SYMBOL_STILL_PRESENT,
                    f"Source symbol still exists: {source_symbol}.",
                    moved.module,
                    actual=source_symbol,
                ))
        for source, symbol, target in request.symbol_moves:
            if f"{target}.{symbol}" not in actual.symbols:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.SYMBOL_IN_WRONG_MODULE,
                    f"Symbol {symbol} is not present in {target}.", target,
                    expected=f"{target}.{symbol}",
                ))
            if f"{source}.{symbol}" in actual.symbols:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.SOURCE_SYMBOL_STILL_PRESENT,
                    f"Source symbol still exists: {source}.{symbol}.", source,
                    actual=f"{source}.{symbol}",
                ))
        for source, target in plan.moved_packages:
            source_path = context.resolve_project_path(Path(*source.split(".")))
            target_path = context.resolve_project_path(Path(*target.split(".")))
            if not target_path.is_dir():
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.MISSING_TARGET_PACKAGE,
                    f"Target package is missing: {target}.", target, path=target_path,
                ))
            if source_path.exists():
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.SOURCE_PACKAGE_STILL_PRESENT,
                    f"Source package still exists: {source}.", source, path=source_path,
                ))
        actual_packages = {
            item.module_name
            for item in context.semantic_context.snapshot.modules
            if item.path.name == "__init__.py"
        }
        expected_packages = set(plan.expected_packages)
        for package in sorted(actual_packages - expected_packages):
            discrepancies.append(self._discrepancy(
                ImpactDiscrepancyCode.UNEXPECTED_PACKAGE,
                f"Unexpected package exists after reorganization: {package}.",
                package,
                actual=package,
            ))
        for module, expected_names in plan.expected_public_api:
            info = next((
                item for item in context.semantic_context.snapshot.modules
                if item.module_name == module
            ), None)
            actual_names = (
                self._literal_all(ast.parse(info.parsed_module.code))
                if info is not None and info.parsed_module is not None
                else None
            )
            if actual_names != expected_names:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.PUBLIC_API_MISMATCH,
                    f"Public API mismatch in {module}.",
                    module,
                    path=info.path if info is not None else None,
                    expected=expected_names,
                    actual=actual_names,
                ))
        old_names = tuple(sorted({
            *plan.deleted_modules,
            *(source for source, _ in plan.moved_packages),
        }))
        for item in actual.imports:
            imported_target = (
                f"{item.source_module}.{item.imported_symbol}"
                if item.imported_symbol is not None
                else item.source_module
            )
            if any(
                imported_target == old or imported_target.startswith(old + ".")
                for old in old_names
            ):
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.STALE_PACKAGE_IMPORT,
                    f"Stale import remains in {item.consumer_module}: {item.source_module}.",
                    item.consumer_module,
                    path=item.location.path,
                    actual=item.source_module,
                ))
            target = next((
                target for source, symbol, target in request.symbol_moves
                if item.source_module == source and item.imported_symbol == symbol
            ), None)
            if target is not None:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.STALE_IMPORT,
                    f"Stale symbol import remains in {item.consumer_module}: "
                    f"{item.source_module}.{item.imported_symbol}.",
                    item.consumer_module,
                    path=item.location.path,
                    expected=target,
                    actual=item.source_module,
                ))
        for item in actual.references:
            if item.resolved_target is not None and any(
                item.resolved_target == old or item.resolved_target.startswith(old + ".")
                for old in old_names
            ):
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.STALE_MODULE_REFERENCE,
                    f"Stale module reference remains in {item.module}: {item.resolved_target}.",
                    item.module,
                    path=item.location.path,
                    actual=item.resolved_target,
                ))
        for expected_import in plan.rewritten_imports:
            if not any(self._same_import(expected_import, item) for item in actual.imports):
                code = (
                    ImpactDiscrepancyCode.MISSING_REEXPORT
                    if expected_import.reexport
                    else ImpactDiscrepancyCode.STALE_IMPORT
                )
                discrepancies.append(self._discrepancy(
                    code,
                    f"Expected rewritten import is missing in {expected_import.consumer_module}.",
                    expected_import.consumer_module,
                    path=expected_import.location.path,
                    expected=(
                        expected_import.source_module,
                        expected_import.imported_symbol,
                        expected_import.alias,
                    ),
                ))
        for expected_reference in plan.rewritten_references:
            if not any(self._same_reference(expected_reference, item) for item in actual.references):
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.STALE_MODULE_REFERENCE,
                    f"Expected rewritten reference is missing in {expected_reference.module}.",
                    expected_reference.module,
                    path=expected_reference.location.path,
                    expected=(expected_reference.resolved_target, expected_reference.symbol),
                ))
        unexpected_cycles = tuple(sorted(set(actual.cycles) - set(plan.expected_cycles)))
        for cycle in unexpected_cycles:
            discrepancies.append(self._discrepancy(
                ImpactDiscrepancyCode.PACKAGE_CYCLE,
                f"Unexpected cycle after reorganization: {' -> '.join(cycle)}.",
                expected=(), actual=cycle,
            ))
        expected_paths = set(plan.expected_paths)
        actual_paths = self._project_inventory(context.project_root)
        for path in sorted(actual_paths - expected_paths):
            discrepancies.append(self._discrepancy(
                ImpactDiscrepancyCode.FILESYSTEM_LAYOUT_MISMATCH,
                f"Unexpected filesystem path after reorganization: {path}.",
                path=path,
                actual=path,
            ))
        for path in changed_paths:
            if path not in expected_paths:
                discrepancies.append(self._discrepancy(
                    ImpactDiscrepancyCode.FILESYSTEM_LAYOUT_MISMATCH,
                    f"Unexpected changed path: {path}.", path=path, actual=path,
                ))
        return PostImpactValidationResult(
            success=not discrepancies,
            discrepancies=tuple(discrepancies),
            actual_graph=actual,
            checked_paths=tuple(sorted(changed_paths)),
        )

    def validate_rollback(
        self, context: Any, expected: ImpactAnalysisResult
    ) -> PostImpactValidationResult:
        request = expected.request
        assert isinstance(request, ReorganizationImpactRequest)
        actual = self.analyze_graph(context, request)
        matches = self._graph_signature(actual) == self._graph_signature(expected.graph)
        discrepancies = () if matches else (
            self._discrepancy(
                ImpactDiscrepancyCode.ROLLBACK_GRAPH_MISMATCH,
                "Restored project graph differs from its pre-execution state.",
            ),
        )
        return PostImpactValidationResult(
            success=matches,
            actual_graph=actual,
            rollback_graph_matches=matches,
            rollback_discrepancies=discrepancies,
        )

    def analyze_graph(
        self, context: Any, request: ReorganizationImpactRequest
    ) -> ProjectReferenceGraph:
        return ImpactAnalyzer().analyze(
            context,
            ImpactAnalysisRequest(
                request.source_module,
                (
                    request.target_module
                    if request.target_module != request.source_module
                    else request.source_module + ".__impact_target__"
                ),
                (),
                transformation_id=request.transformation_id,
                graph_only=True,
            ),
        ).graph

    def _expanded_module_moves(
        self, graph: ProjectReferenceGraph, request: ReorganizationImpactRequest
    ) -> tuple[tuple[str, str], ...]:
        moves = list(request.module_moves)
        for source, target in request.package_moves:
            moves.extend(
                (module, target + module[len(source):])
                for module in graph.modules
                if module == source or module.startswith(source + ".")
            )
        return tuple(sorted(set(moves)))

    def _moved_symbols(
        self,
        graph: ProjectReferenceGraph,
        request: ReorganizationImpactRequest,
        module_moves: tuple[tuple[str, str], ...],
    ) -> tuple[ImpactedSymbol, ...]:
        result = [
            ImpactedSymbol(source, symbol, target, symbol)
            for source, symbol, target in request.symbol_moves
        ]
        for qualified in graph.symbols:
            module, _, symbol = qualified.rpartition(".")
            target = self._mapped_module(module, module_moves)
            if target != module:
                result.append(ImpactedSymbol(module, symbol, target, symbol))
        return tuple(sorted(set(result), key=lambda item: (
            item.module, item.symbol, item.target_module, item.target_symbol
        )))

    def _expected_paths(
        self, context: Any, request: ReorganizationImpactRequest, base: tuple[Path, ...]
    ) -> tuple[Path, ...]:
        paths = self._project_inventory(context.project_root)
        for source, target in request.module_moves:
            paths.add(self._module_path(context, source))
            target_path = context.module_path(target)
            paths.add(target_path)
            parent = target_path.parent
            while parent != context.project_root and parent.is_relative_to(context.project_root):
                paths.add(parent)
                parent = parent.parent
        for _, _, target in request.symbol_moves:
            paths.add(context.module_path(target))
        for source, target in request.package_moves:
            try:
                source_path = context.resolve_project_path(Path(*source.split(".")))
                target_path = context.resolve_project_path(Path(*target.split(".")))
            except ValueError:
                continue
            paths.add(source_path)
            paths.add(target_path)
            parent = target_path.parent
            while parent != context.project_root and parent.is_relative_to(context.project_root):
                paths.add(parent)
                parent = parent.parent
            for module in context.semantic_context.snapshot.modules:
                module_path = module.path.resolve()
                if module_path.is_relative_to(source_path):
                    paths.add(target_path / module_path.relative_to(source_path))
            if source_path.is_dir():
                paths.update(
                    target_path / item.relative_to(source_path)
                    for item in source_path.rglob("*")
                )
        target_packages = {
            target.rpartition(".")[0] for _, target in request.module_moves
        } | {
            target.rpartition(".")[0] for _, _, target in request.symbol_moves
        } | {
            target for _, target in request.package_moves
        }
        for package in target_packages - {""}:
            parts = package.split(".")
            for index in range(1, len(parts) + 1):
                directory = context.project_root.joinpath(*parts[:index])
                paths.add(directory)
                paths.add(directory / "__init__.py")
        paths.update(base)
        return tuple(sorted(paths))

    def _module_path(self, context: Any, module: str) -> Path:
        info = next(
            (item for item in context.semantic_context.snapshot.modules if item.module_name == module),
            None,
        )
        return info.path.resolve() if info is not None else context.module_path(module)

    def _mapped_module(
        self, module: str, moves: tuple[tuple[str, str], ...]
    ) -> str:
        for source, target in sorted(moves, key=lambda item: len(item[0]), reverse=True):
            if module == source:
                return target
            if module.startswith(source + "."):
                return target + module[len(source):]
        return module

    def _rewrite_import(
        self,
        item: Any,
        moves: tuple[tuple[str, str], ...],
        symbol_destinations: dict[tuple[str, str | None], str],
    ) -> Any:
        consumer = self._mapped_module(item.consumer_module, moves)
        explicit = symbol_destinations.get((item.source_module, item.imported_symbol))
        if explicit is not None:
            return replace(
                item,
                consumer_module=consumer,
                source_module=explicit,
                resolved_target=explicit,
            )
        source = self._mapped_module(item.source_module, moves)
        symbol = item.imported_symbol
        alias = item.alias
        if symbol is not None:
            candidate = f"{item.source_module}.{symbol}"
            mapped_candidate = self._mapped_module(candidate, moves)
            if mapped_candidate != candidate:
                source, _, new_symbol = mapped_candidate.rpartition(".")
                if alias is None and new_symbol != symbol:
                    alias = symbol
                symbol = new_symbol
        return replace(
            item,
            consumer_module=consumer,
            source_module=source,
            imported_symbol=symbol,
            alias=alias,
            resolved_target=source,
        )

    def _same_import(self, expected: Any, actual: Any) -> bool:
        return (
            expected.consumer_module,
            expected.source_module,
            expected.imported_symbol,
            expected.alias,
        ) == (
            actual.consumer_module,
            actual.source_module,
            actual.imported_symbol,
            actual.alias,
        )

    def _same_reference(self, expected: Any, actual: Any) -> bool:
        return (
            expected.module,
            expected.symbol,
            expected.resolved_target,
        ) == (
            actual.module,
            actual.symbol,
            actual.resolved_target,
        )

    def _graph_signature(self, graph: ProjectReferenceGraph) -> tuple[object, ...]:
        return (
            graph.modules,
            graph.symbols,
            tuple(
                (item.consumer_module, item.source_module, item.imported_symbol, item.alias)
                for item in graph.imports
            ),
            tuple((item.source, item.target, item.kind) for item in graph.dependencies),
            graph.cycles,
        )

    def _expected_packages(
        self,
        context: Any,
        request: ReorganizationImpactRequest,
        moves: tuple[tuple[str, str], ...],
        deleted_modules: tuple[str, ...],
    ) -> tuple[str, ...]:
        deleted = set(deleted_modules)
        packages = {
            item.module_name
            for item in context.semantic_context.snapshot.modules
            if item.path.name == "__init__.py" and item.module_name not in deleted
        }
        packages.update(
            self._mapped_module(item.module_name, moves)
            for item in context.semantic_context.snapshot.modules
            if item.path.name == "__init__.py"
        )
        target_modules = {
            target for _, target in request.module_moves
        } | {
            target for _, _, target in request.symbol_moves
        }
        for module in target_modules:
            parts = module.split(".")[:-1]
            packages.update(".".join(parts[:index]) for index in range(1, len(parts) + 1))
        for _, package in request.package_moves:
            parts = package.split(".")
            packages.update(".".join(parts[:index]) for index in range(1, len(parts) + 1))
        return tuple(sorted(packages))

    def _expected_public_api(
        self,
        context: Any,
        request: ReorganizationImpactRequest,
        moves: tuple[tuple[str, str], ...],
        deleted_modules: tuple[str, ...],
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        public: dict[str, tuple[str, ...]] = {}
        for item in context.semantic_context.snapshot.modules:
            if item.parsed_module is None:
                continue
            names = self._literal_all(ast.parse(item.parsed_module.code))
            if names is not None:
                public.setdefault(self._mapped_module(item.module_name, moves), names)
                if item.module_name not in deleted_modules:
                    public.setdefault(item.module_name, names)
        if request.symbol_moves:
            by_source: dict[str, set[str]] = {}
            by_target: dict[str, list[str]] = {}
            for source, symbol, target in request.symbol_moves:
                by_source.setdefault(source, set()).add(symbol)
                if symbol in public.get(source, ()):
                    by_target.setdefault(target, []).append(symbol)
            for source, selected in by_source.items():
                if source in public:
                    public[source] = tuple(name for name in public[source] if name not in selected)
            for target, names in by_target.items():
                public[target] = tuple(dict.fromkeys((*public.get(target, ()), *names)))
        merge_targets = {
            target for _, target in request.module_moves
            if sum(1 for _, candidate in request.module_moves if candidate == target) > 1
        }
        for target in merge_targets:
            names: list[str] = list(public.get(target, ()))
            for source, candidate in request.module_moves:
                if candidate != target:
                    continue
                original = next((
                    item for item in context.semantic_context.snapshot.modules
                    if item.module_name == source and item.parsed_module is not None
                ), None)
                if original is None:
                    continue
                source_names = self._literal_all(ast.parse(original.parsed_module.code)) or ()
                names.extend(name for name in source_names if name not in names)
            if names:
                public[target] = tuple(names)
        for module in deleted_modules:
            public.pop(module, None)
        return tuple(sorted(public.items()))

    def _literal_all(self, tree: ast.Module) -> tuple[str, ...] | None:
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
                return tuple(item.value for item in node.value.elts)
            return None
        return None

    def _project_inventory(self, root: Path) -> set[Path]:
        excluded = {
            ".git", ".venv", ".cmm", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".ruff_cache",
        }
        result: set[Path] = set()
        pending = [root]
        while pending:
            directory = pending.pop()
            try:
                entries = tuple(directory.iterdir())
            except OSError:
                continue
            for path in entries:
                if path.name in excluded:
                    continue
                result.add(path)
                if path.is_dir() and not path.is_symlink():
                    pending.append(path)
        return result

    def _discrepancy(
        self,
        code: ImpactDiscrepancyCode,
        message: str,
        module: str | None = None,
        *,
        path: Path | None = None,
        expected: object | None = None,
        actual: object | None = None,
    ) -> ImpactDiscrepancy:
        return ImpactDiscrepancy(code, message, ImpactSeverity.BLOCKING, module, path, expected, actual)
