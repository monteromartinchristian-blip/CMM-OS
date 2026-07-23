from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity
from cmm.validation.findings import ValidationFinding

from .contracts import (
    ChangeImpactResult,
    ChangeSet,
    ChangeType,
    DependencyGraph,
    FileChangeKind,
    ImportChangeKind,
    PublicAPIChange,
    PublicAPIChangeKind,
    SymbolChange,
    SymbolChangeKind,
)
from .diff import PythonModuleDiff, diff_python_sources
from .graph import affected_dependents, build_dependency_graph, module_name_from_path


TestSelector = Callable[[ValidationContext], Any]


@dataclass(frozen=True, slots=True)
class ChangeImpactAnalyzer:
    project_index: Any | None = None
    test_selector: TestSelector | None = None

    def analyze(self, change_set: ChangeSet) -> ChangeImpactResult:
        dependency_graph = change_set.dependency_graph
        if dependency_graph is None:
            dependency_graph = build_dependency_graph(
                change_set.after_root or change_set.project_root,
                project_index=self.project_index,
            )

        module_diffs: list[PythonModuleDiff] = []
        affected_modules: set[str] = set()
        affected_symbols: set[str] = set()
        public_api_changed = False
        uncertainty = list(change_set.uncertainty)

        for file_change in change_set.file_changes:
            module_name = self._module_name_for_change(change_set.project_root, file_change)
            if module_name is None:
                continue

            affected_modules.add(module_name)
            before_source = file_change.before.content if file_change.before is not None else None
            after_source = file_change.after.content if file_change.after is not None else None
            if before_source is None and after_source is None:
                uncertainty.append(f"missing_content:{module_name}")
                continue

            if module_name and (before_source is not None or after_source is not None):
                module_diff = diff_python_sources(
                    module_name=module_name,
                    before_source=before_source,
                    after_source=after_source,
                    before_path=None if file_change.before is None else file_change.before.path,
                    after_path=None if file_change.after is None else file_change.after.path,
                )
                module_diffs.append(module_diff)
                affected_symbols.update(
                    f"{module_name}:{item.symbol}"
                    for item in module_diff.symbol_changes
                )
                public_api_changed = public_api_changed or module_diff.public_api_changed

        public_api_changed = public_api_changed or bool(change_set.public_api_changes)

        if module_diffs:
            for module_diff in module_diffs:
                affected_modules.add(module_diff.module_name)

        graph_modules = affected_dependents(
            dependency_graph,
            set(affected_modules),
        )
        affected_modules.update(graph_modules)
        self._augment_with_project_index(affected_modules, set(affected_modules))

        selected_tests = self._select_tests(change_set)
        requires_full_suite = bool(change_set.requires_full_suite or public_api_changed or any(diff.public_api_changed for diff in module_diffs))
        if not module_diffs and change_set.has_python_changes:
            requires_full_suite = True
            uncertainty.append("python_change_without_diff")

        confidence = self._confidence(change_set, module_diffs, len(affected_modules), len(selected_tests), len(uncertainty))
        if confidence < 0.7:
            requires_full_suite = True
            uncertainty.append("low_confidence")

        change_type = self._result_change_type(change_set, module_diffs, public_api_changed)
        findings = self._findings(change_set, public_api_changed, requires_full_suite, confidence, uncertainty)
        artifacts = (
            ValidationArtifact(
                id="change-impact-result",
                kind="change_impact",
                source="validation.impact",
                content={
                    "change_set": change_set.serialize(),
                    "module_diffs": [diff.serialize() for diff in module_diffs],
                    "dependency_graph": dependency_graph.serialize(),
                    "affected_modules": sorted(affected_modules),
                    "affected_symbols": sorted(affected_symbols),
                    "affected_tests": sorted(selected_tests),
                },
                metrics={
                    "confidence": confidence,
                    "requires_full_suite": requires_full_suite,
                },
                metadata={
                    "change_type": change_type.value,
                    "public_api_changed": public_api_changed,
                },
            ),
        )

        return ChangeImpactResult(
            change_type=change_type,
            affected_modules=tuple(sorted(affected_modules)),
            affected_symbols=tuple(sorted(affected_symbols)),
            affected_tests=tuple(sorted(selected_tests)),
            public_api_changed=public_api_changed,
            confidence=confidence,
            requires_full_suite=requires_full_suite,
            findings=findings,
            artifacts=artifacts,
            uncertainty=tuple(sorted(dict.fromkeys(uncertainty))),
            metadata={
                "change_set": change_set.serialize(),
                "dependency_graph": dependency_graph.serialize(),
                "module_diffs": [diff.serialize() for diff in module_diffs],
            },
        )

    def _module_name_for_change(self, project_root: Path, file_change: Any) -> str | None:
        candidate = file_change.after_path or file_change.before_path
        if candidate is None:
            return None
        if not str(candidate).endswith(".py"):
            return None
        return module_name_from_path(project_root, candidate)

    def _select_tests(self, change_set: ChangeSet) -> tuple[str, ...]:
        context = ValidationContext(
            project_root=change_set.project_root,
            changed_files=tuple(change_set.changed_files),
            change_type="impact",
            requested_steps=None,
            metadata={"change_type": change_set.change_type.value},
        )
        selector = self.test_selector
        if selector is None:
            from cmm.validation.testing.selection import select_affected_tests as default_selector

            selector = default_selector
        try:
            selection = selector(context)
        except Exception:
            return ()
        return tuple(str(path) for path in getattr(selection, "selected_tests", ()) or ())

    def _augment_with_project_index(self, impacted_modules: set[str], original_modules: set[str]) -> None:
        if self.project_index is None:
            return
        if not hasattr(self.project_index, "find_module") or not hasattr(self.project_index, "find_imported_by"):
            return
        for module_name in tuple(original_modules):
            try:
                node = self.project_index.find_module(module_name)
            except Exception:
                node = None
            if node is None:
                continue
            try:
                dependents = self.project_index.find_imported_by(node)
            except Exception:
                continue
            for dependent in dependents or ():
                name = getattr(dependent, "title", None) or getattr(dependent, "identifier", None)
                if name:
                    impacted_modules.add(str(name))

    def _result_change_type(self, change_set: ChangeSet, module_diffs: list[PythonModuleDiff], public_api_changed: bool) -> ChangeType:
        if public_api_changed:
            return ChangeType.PUBLIC_API_CHANGE
        if any(item.kind == FileChangeKind.RENAMED for item in change_set.file_changes):
            return ChangeType.RENAMED_FILE
        if any(diff.symbol_changes for diff in module_diffs):
            return ChangeType.STRUCTURAL_CHANGE
        if any(diff.import_changes for diff in module_diffs):
            return ChangeType.IMPORT_CHANGE
        return change_set.change_type

    def _confidence(
        self,
        change_set: ChangeSet,
        module_diffs: list[PythonModuleDiff],
        impacted_count: int,
        test_count: int,
        uncertainty_count: int,
    ) -> float:
        confidence = change_set.confidence
        if module_diffs:
            confidence = min(confidence, min(diff.confidence for diff in module_diffs))
        confidence -= 0.02 * max(0, impacted_count - 1)
        confidence -= 0.03 * max(0, test_count - 1)
        confidence -= 0.08 * uncertainty_count
        return max(0.0, min(1.0, confidence))

    def _findings(
        self,
        change_set: ChangeSet,
        public_api_changed: bool,
        requires_full_suite: bool,
        confidence: float,
        uncertainty: list[str],
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        findings.append(
            ValidationFinding(
                code="CHANGE_IMPACT_ANALYZED",
                message="Change impact analysis completed.",
                severity=ValidationSeverity.INFO,
                source="validation.impact",
                blocking=False,
                metadata={"change_type": change_set.change_type.value},
            )
        )
        if public_api_changed:
            findings.append(
                ValidationFinding(
                    code="CHANGE_IMPACT_PUBLIC_API",
                    message="Public API changes were detected conservatively.",
                    severity=ValidationSeverity.INFO,
                    source="validation.impact",
                    blocking=False,
                    metadata={"public_api_changed": True},
                )
            )
        if requires_full_suite:
            findings.append(
                ValidationFinding(
                    code="CHANGE_IMPACT_FULL_SUITE",
                    message="The detected uncertainty requires the full suite.",
                    severity=ValidationSeverity.INFO,
                    source="validation.impact",
                    blocking=False,
                    metadata={"confidence": confidence, "uncertainty": tuple(sorted(dict.fromkeys(uncertainty)))},
                )
            )
        return tuple(findings)
