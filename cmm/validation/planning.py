"""Validation plan construction, policy resolution, and custom step binding for CMM OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cmm.validation.context import ValidationContext
from cmm.validation.custom import (
    CustomValidatorRegistry,
    build_custom_validation_step,
)
from cmm.validation.custom_validators.defaults import build_default_custom_validator_registry
from cmm.validation.errors import ValidationContractError
from cmm.validation.policy import (
    _STEP_ALIASES,
    ValidationPolicy,
    expand_validation_step_labels,
    resolve_validation_policy,
)
from cmm.validation.registry import ValidationRegistry
from cmm.validation.steps import ValidationStep
from cmm.validation.testing_defaults import _build_broad_validation_steps

_DYNAMIC_TEST_SCOPES: Set[str] = {
    "affected_tests",
    "unit_tests",
    "integration_tests",
    "full_suite",
    "type_check",
    "dead_code",
    "bandit",
    "pip_audit",
    "file_validation",
    "link_check",
    "documentation_validation",
    "kernel_specific_validations",
    "minimum_coverage",
    "version_validation",
    "migration_validation",
}


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    """Immutable representation of a resolved validation execution plan."""

    steps: Tuple[ValidationStep, ...]
    registry: ValidationRegistry = field(compare=False, repr=False)
    policy: Optional[ValidationPolicy] = None
    selected_custom_validators: Tuple[str, ...] = ()
    missing_optional_custom_validators: Tuple[str, ...] = ()
    excluded_steps: Tuple[str, ...] = ()

    def serialize(self) -> Dict[str, Any]:
        """Serialize plan metadata excluding runtime objects."""
        return {
            "policy": self.policy.serialize() if self.policy is not None else None,
            "step_names": [step.name for step in self.steps],
            "custom_step_names": [step.name for step in self.steps if step.name.startswith("custom.")],
            "required_step_names": list(self.policy.required_steps) if self.policy is not None else [],
            "optional_step_names": list(self.policy.optional_steps) if self.policy is not None else [],
            "excluded_step_names": list(self.excluded_steps),
            "selected_custom_validators": list(self.selected_custom_validators),
            "missing_optional_custom_validators": list(self.missing_optional_custom_validators),
        }


def _build_effective_aliases(custom_reg: CustomValidatorRegistry) -> Dict[str, Tuple[str, ...]]:
    """Build step aliases mapping including registered custom validators."""
    aliases = dict(_STEP_ALIASES)
    for name in custom_reg.names():
        c_name = f"custom.{name}"
        aliases[c_name] = (c_name,)
    return aliases


def _sort_steps_deterministically(steps: Sequence[ValidationStep]) -> Tuple[ValidationStep, ...]:
    """Sort validation steps into a stable, execution-optimal order."""
    order_groups: Dict[str, int] = {
        "syntax": 10,
        "formatter_check": 20,
        "lint_check": 30,
        "ast": 40,
        "change_impact": 50,
        "type_check": 60,
        "dead_code": 70,
        "security": 80,
        "bandit": 81,
        "pip_audit": 82,
        # Custom validators group (90 - 99)
        "custom.project_manifest": 90,
        "custom.validation_contract": 91,
        "custom.public_api": 92,
        "custom.test_layout": 93,
        # Testing group (100+)
        "affected_tests": 100,
        "unit_tests": 110,
        "integration_tests": 120,
        "full_suite": 130,
    }

    def get_order(step: ValidationStep) -> Tuple[int, str]:
        if step.name in order_groups:
            return (order_groups[step.name], step.name)
        if step.name.startswith("custom."):
            return (95, step.name)
        return (200, step.name)

    return tuple(sorted(steps, key=get_order))


def validate_custom_policy(
    policy: ValidationPolicy,
    *,
    custom_registry: Optional[CustomValidatorRegistry] = None,
) -> ValidationPolicy:
    """Validate that a ValidationPolicy only references valid labels and registered custom validators."""
    custom_reg = custom_registry if custom_registry is not None else build_default_custom_validator_registry()
    effective_aliases = _build_effective_aliases(custom_reg)

    req_expanded = expand_validation_step_labels(policy.required_steps, aliases=effective_aliases)
    expand_validation_step_labels(policy.optional_steps, aliases=effective_aliases)

    for step_name in req_expanded:
        if step_name.startswith("custom."):
            val_name = step_name[7:]
            if val_name not in custom_reg:
                raise ValidationContractError(
                    f"Required custom validator '{val_name}' for policy '{policy.name}' is not registered."
                )

    return policy


def build_validation_plan(
    context: ValidationContext,
    policy: Optional[ValidationPolicy] = None,
    *,
    registry: Optional[ValidationRegistry] = None,
    custom_registry: Optional[CustomValidatorRegistry] = None,
) -> ValidationPlan:
    """Build a complete, explicit ValidationPlan linking steps and registry handlers."""
    resolved_policy = policy if policy is not None else resolve_validation_policy(context)

    val_registry = registry if registry is not None else ValidationRegistry()
    custom_reg = custom_registry if custom_registry is not None else build_default_custom_validator_registry()
    effective_aliases = _build_effective_aliases(custom_reg)

    if resolved_policy is not None:
        validate_custom_policy(resolved_policy, custom_registry=custom_reg)

    # 1. Build built-in steps
    require_full = resolved_policy.require_full_suite if resolved_policy is not None else False
    built_in_steps = _build_broad_validation_steps(
        context,
        require_full_suite=require_full,
        include_structural_steps=True,
    )

    # 2. Build custom steps from custom_registry and register their handlers in val_registry
    custom_steps_dict: Dict[str, ValidationStep] = {}
    for name in custom_reg.names():
        validator = custom_reg.require(name)
        step = build_custom_validation_step(validator, validation_registry=val_registry)
        custom_steps_dict[step.name] = step

    all_available_steps_dict: Dict[str, ValidationStep] = {s.name: s for s in built_in_steps}
    all_available_steps_dict.update(custom_steps_dict)

    # 3. Handle explicit step exclusion (context.excluded_steps)
    excluded_canonical_names: Set[str] = set()
    if context.excluded_steps:
        try:
            expanded_excluded = expand_validation_step_labels(context.excluded_steps, aliases=effective_aliases)
        except ValidationContractError as exc:
            raise ValidationContractError(f"Invalid excluded step label: {exc}") from exc
        excluded_canonical_names = set(expanded_excluded)

    # 4. Handle requested steps vs policy selection
    selected_steps_list: List[ValidationStep] = []
    selected_step_names: Set[str] = set()
    missing_optional_custom: List[str] = []

    from dataclasses import replace

    def add_step_with_deps(name: str, *, is_required: bool = True) -> None:
        if name in selected_step_names or name in excluded_canonical_names:
            return
        step = all_available_steps_dict.get(name)
        if step is None:
            return
        for dep in step.dependencies:
            add_step_with_deps(dep, is_required=is_required)
        if name not in selected_step_names and name not in excluded_canonical_names:
            final_step = replace(step, required=is_required) if step.required != is_required else step
            selected_steps_list.append(final_step)
            selected_step_names.add(name)

    if context.requested_steps is not None:
        # Explicit step selection via context.requested_steps
        for raw_req in context.requested_steps:
            if not isinstance(raw_req, str) or not raw_req.strip():
                raise ValidationContractError("Requested step label must be a non-empty string.")

            # Reject un-prefixed names that refer to custom validators (e.g., 'project_manifest' instead of 'custom.project_manifest')
            if raw_req in custom_reg.names():
                raise ValidationContractError(
                    f"Invalid custom step name '{raw_req}'. Custom steps must use the canonical prefix 'custom.{raw_req}'."
                )

            expanded = expand_validation_step_labels(raw_req, aliases=effective_aliases)
            for canonical_name in expanded:
                if canonical_name not in all_available_steps_dict and canonical_name not in _DYNAMIC_TEST_SCOPES:
                    raise ValidationContractError(f"Requested validation step '{canonical_name}' is unknown or unavailable.")
                add_step_with_deps(canonical_name, is_required=True)
    elif resolved_policy is not None:
        # Selection via policy
        req_expanded = expand_validation_step_labels(resolved_policy.required_steps, aliases=effective_aliases)
        for req_name in req_expanded:
            if req_name in excluded_canonical_names:
                raise ValidationContractError(
                    f"Cannot exclude required step '{req_name}' for policy '{resolved_policy.name}'."
                )
            if req_name not in all_available_steps_dict:
                if req_name in _DYNAMIC_TEST_SCOPES:
                    continue
                raise ValidationContractError(
                    f"Required validation step '{req_name}' for policy '{resolved_policy.name}' is missing."
                )
            add_step_with_deps(req_name, is_required=True)

        opt_expanded = expand_validation_step_labels(resolved_policy.optional_steps, aliases=effective_aliases)
        for opt_name in opt_expanded:
            if opt_name in excluded_canonical_names:
                continue
            if opt_name in all_available_steps_dict:
                add_step_with_deps(opt_name, is_required=False)
            elif opt_name.startswith("custom."):
                missing_optional_custom.append(opt_name)
    else:
        # Default: all broad steps
        for step in _sort_steps_deterministically(tuple(all_available_steps_dict.values())):
            if step.name not in excluded_canonical_names:
                add_step_with_deps(step.name, is_required=step.required)

    sorted_selected_steps = _sort_steps_deterministically(selected_steps_list)

    selected_custom = tuple(
        s.metadata["custom_validator_name"]
        for s in sorted_selected_steps
        if s.name.startswith("custom.") and "custom_validator_name" in s.metadata
    )

    return ValidationPlan(
        steps=sorted_selected_steps,
        registry=val_registry,
        policy=resolved_policy,
        selected_custom_validators=selected_custom,
        missing_optional_custom_validators=tuple(missing_optional_custom),
        excluded_steps=tuple(sorted(excluded_canonical_names)),
    )


def build_default_validation_plan(
    context: ValidationContext,
    *,
    registry: Optional[ValidationRegistry] = None,
    custom_registry: Optional[CustomValidatorRegistry] = None,
) -> ValidationPlan:
    """Build a default ValidationPlan using default policies and default custom validators."""
    policy = resolve_validation_policy(context)
    return build_validation_plan(
        context,
        policy=policy,
        registry=registry,
        custom_registry=custom_registry,
    )
