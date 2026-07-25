from __future__ import annotations

from typing import Any, Mapping
from pathlib import Path

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import (
    ValidationStep,
    ValidationStepResult,
    ValidationStepType,
)

from .analyzer import ChangeImpactAnalyzer
from .contracts import ChangeSet
from .snapshots import ChangeSetBuilder


class ChangeImpactValidator:
    def validate(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        change_set = self._load_change_set(context, step.metadata)
        analyzer = ChangeImpactAnalyzer(
            project_index=step.metadata.get("project_index"),
            test_selector=None,
        )
        result = analyzer.analyze(change_set)
        return ValidationStepResult(
            name=step.name,
            status=ValidationStatus.PASSED,
            duration_ms=0,
            stdout="",
            stderr="",
            findings=result.findings,
            artifacts=result.artifacts,
            metadata={
                "change_impact": result.serialize(),
                "affected_tests": list(result.affected_tests),
                "change_set": change_set.serialize(),
                "confidence": result.confidence,
                "requires_full_suite": result.requires_full_suite,
            },
        )

    def _load_change_set(
        self, context: ValidationContext, metadata: Mapping[str, Any]
    ) -> ChangeSet:
        payload = metadata.get("change_set")
        if isinstance(payload, Mapping):
            return ChangeSet.from_mapping(payload)
        builder = ChangeSetBuilder()
        before_root = metadata.get("before_root")
        after_root = metadata.get("after_root")
        git_ref = metadata.get("git_ref")
        changed_files = metadata.get("changed_files")
        return builder.build(
            project_root=context.project_root,
            before_root=Path(str(before_root)) if before_root is not None else None,
            after_root=Path(str(after_root)) if after_root is not None else None,
            changed_files=tuple(changed_files)
            if isinstance(changed_files, (list, tuple))
            else context.changed_files,
            git_ref=None if git_ref is None else str(git_ref),
        )


def change_impact_step(context: ValidationContext) -> ValidationStep:
    builder = ChangeSetBuilder()
    change_set = builder.build(
        project_root=context.project_root,
        changed_files=context.changed_files,
    )
    from cmm.validation.testing.selection import select_affected_tests

    selection = select_affected_tests(context)
    return ValidationStep(
        name="change_impact",
        step_type=ValidationStepType.INTERNAL,
        required=True,
        timeout_seconds=120,
        stop_on_failure=True,
        metadata={
            "project_root": str(context.project_root),
            "changed_files": [str(path) for path in context.changed_files],
            "change_set": change_set.serialize(),
            "change_type": change_set.change_type.value,
            "affected_tests": [str(path) for path in selection.selected_tests],
            "test_selection": selection.serialize(),
        },
    )
