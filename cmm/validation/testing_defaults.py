from __future__ import annotations

from cmm.validation.catalog import change_impact_step, default_static_analysis_steps, default_structural_steps
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep
from .testing_catalog import default_testing_steps


def default_validation_steps(context: ValidationContext) -> tuple[ValidationStep, ...]:
    steps: list[ValidationStep] = []
    if not context.changed_files:
        steps.extend(default_structural_steps(context))
    impact_step = change_impact_step(context)
    steps.append(impact_step)
    steps.extend(default_static_analysis_steps(context, change_impact_step=impact_step))
    steps.extend(default_testing_steps(context))
    deduped: list[ValidationStep] = []
    seen: set[str] = set()
    for step in steps:
        if step.name in seen:
            continue
        seen.add(step.name)
        deduped.append(step)
    return tuple(deduped)
