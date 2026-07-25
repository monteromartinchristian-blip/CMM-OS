from __future__ import annotations

from cmm.validation.catalog import (
    change_impact_step,
    default_security_steps,
    default_static_analysis_steps,
    default_structural_steps,
)
from cmm.validation.context import ValidationContext
from cmm.validation.errors import ValidationContractError
from cmm.validation.policy import (
    ValidationPolicy,
    expand_validation_step_labels,
    resolve_validation_policy,
)
from cmm.validation.security import bandit_step, pip_audit_step
from cmm.validation.steps import ValidationStep
from .testing_catalog import default_testing_steps


def _build_broad_validation_steps(
    context: ValidationContext,
    *,
    require_full_suite: bool = False,
    include_structural_steps: bool | None = None,
) -> tuple[ValidationStep, ...]:
    steps: list[ValidationStep] = []
    if include_structural_steps is None:
        include_structural_steps = not context.changed_files
    if include_structural_steps:
        steps.extend(default_structural_steps(context))
    impact_step = change_impact_step(context)
    steps.append(impact_step)
    steps.extend(default_static_analysis_steps(context, change_impact_step=impact_step))
    testing_steps = default_testing_steps(
        context, require_full_suite=require_full_suite
    )
    steps.extend(
        default_security_steps(
            context,
            change_impact_step=impact_step,
            planned_steps=tuple(steps + list(testing_steps)),
        )
    )
    bandit = bandit_step(context, change_impact_step=impact_step)
    if bandit is not None:
        steps.append(bandit)
    pip_audit = pip_audit_step(context, change_impact_step=impact_step)
    if pip_audit is not None:
        steps.append(pip_audit)
    steps.extend(testing_steps)
    deduped: list[ValidationStep] = []
    seen: set[str] = set()
    for step in steps:
        if step.name in seen:
            continue
        seen.add(step.name)
        deduped.append(step)
    return tuple(deduped)


def _select_policy_steps(
    steps: tuple[ValidationStep, ...],
    policy: ValidationPolicy,
) -> tuple[ValidationStep, ...]:
    by_name = {step.name: step for step in steps}
    selected: list[ValidationStep] = []
    selected_names: set[str] = set()

    def add_step(name: str) -> None:
        if name in selected_names:
            return
        step = by_name.get(name)
        if step is None:
            return
        for dependency in step.dependencies:
            add_step(dependency)
        if name not in selected_names:
            selected.append(step)
            selected_names.add(name)

    _DYNAMIC_TEST_SCOPES = {"affected_tests", "unit_tests", "integration_tests"}
    for req_name in expand_validation_step_labels(policy.required_steps):
        if req_name not in by_name:
            if req_name in _DYNAMIC_TEST_SCOPES or req_name.startswith("custom."):
                continue
            raise ValidationContractError(
                f"Required validation step '{req_name}' for policy '{policy.name}' is missing."
            )
        add_step(req_name)

    for opt_name in expand_validation_step_labels(policy.optional_steps):
        if opt_name in by_name:
            add_step(opt_name)

    return tuple(selected)


def default_validation_steps(context: ValidationContext) -> tuple[ValidationStep, ...]:
    policy = resolve_validation_policy(context)
    if policy is None:
        return _build_broad_validation_steps(context)
    broad_steps = _build_broad_validation_steps(
        context,
        require_full_suite=policy.require_full_suite,
        include_structural_steps=True,
    )
    return _select_policy_steps(broad_steps, policy)
