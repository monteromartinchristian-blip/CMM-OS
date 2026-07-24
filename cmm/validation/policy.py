from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .context import ValidationContext
from .errors import ValidationContractError


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def canonical_validation_policy_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return _POLICY_ALIASES.get(normalized, normalized)


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    name: str
    required_steps: tuple[str, ...]
    optional_steps: tuple[str, ...] = ()
    stop_on_blocking_failure: bool = True
    require_full_suite: bool = False
    allow_commit: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationContractError("ValidationPolicy.name must not be empty")
        object.__setattr__(self, "name", canonical_validation_policy_name(self.name) or self.name)
        object.__setattr__(self, "required_steps", _as_tuple(self.required_steps))
        object.__setattr__(self, "optional_steps", _as_tuple(self.optional_steps))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required_steps": list(self.required_steps),
            "optional_steps": list(self.optional_steps),
            "stop_on_blocking_failure": self.stop_on_blocking_failure,
            "require_full_suite": self.require_full_suite,
            "allow_commit": self.allow_commit,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ValidationPolicy":
        return cls(
            name=str(payload["name"]),
            required_steps=_as_tuple(payload.get("required_steps", ())),
            optional_steps=_as_tuple(payload.get("optional_steps", ())),
            stop_on_blocking_failure=bool(payload.get("stop_on_blocking_failure", True)),
            require_full_suite=bool(payload.get("require_full_suite", False)),
            allow_commit=bool(payload.get("allow_commit", False)),
            metadata=dict(payload.get("metadata", {})) if isinstance(payload.get("metadata"), Mapping) else {},
        )


_POLICY_ALIASES: dict[str, str] = {
    "docs_only": "documentation_only",
    "documentation": "documentation_only",
    "documentation_only": "documentation_only",
    "documentationonly": "documentation_only",
    "smallchange": "small_change",
    "small_change": "small_change",
    "structuralchange": "structural_change",
    "structural_change": "structural_change",
    "importschange": "imports_change",
    "imports_change": "imports_change",
    "publicapichange": "public_api_change",
    "public_api_change": "public_api_change",
    "kernelchange": "kernel_change",
    "kernel_change": "kernel_change",
    "release": "release",
    "autonomousexecution": "autonomous_execution",
    "autonomous_execution": "autonomous_execution",
    "full": "full",
}


_STEP_ALIASES: dict[str, tuple[str, ...]] = {
    "formatter_check": ("formatter_check",),
    "formatter": ("formatter_check",),
    "lint": ("lint_check",),
    "lint_check": ("lint_check",),
    "syntax": ("syntax",),
    "ast": ("ast",),
    "structural": ("structural",),
    "affected_tests": ("affected_tests",),
    "unit_tests": ("unit_tests",),
    "integration_tests": ("integration_tests",),
    "full_suite": ("full_suite",),
    "import_analysis": ("change_impact",),
    "change_impact": ("change_impact",),
    "cycle_checks": ("change_impact",),
    "contract_validation": ("ast",),
    "associated_documentation": ("formatter_check",),
    "static_analysis": ("change_impact", "type_check", "dead_code"),
    "type_check": ("type_check",),
    "dead_code": ("dead_code",),
    "security": ("security", "bandit", "pip_audit"),
    "bandit": ("bandit",),
    "pip_audit": ("pip_audit",),
    "e2e": ("integration_tests",),
    "kernel_specific_validations": ("ast",),
    "minimum_coverage": ("full_suite",),
    "version_validation": ("ast",),
    "documentation_validation": ("formatter_check",),
    "migration_validation": ("ast",),
    "restrictive_policy": ("syntax",),
    "allowed_commands_only": ("lint_check",),
    "all_required_checks": ("ast",),
    "complete_artifacts": ("change_impact",),
    "mandatory_traceability": ("security",),
    "file_validation": ("formatter_check",),
    "link_check": ("formatter_check",),
}


def expand_validation_step_labels(
    labels: tuple[str, ...] | list[str] | str,
    *,
    aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    if isinstance(labels, str):
        labels = (labels,)
    step_aliases = aliases if aliases is not None else _STEP_ALIASES
    expanded: list[str] = []
    seen: set[str] = set()

    def _expand(label_str: str, active_path: tuple[str, ...]) -> None:
        canonical = str(label_str).strip().lower().replace("-", "_").replace(" ", "_")
        if canonical in active_path:
            cycle_str = " -> ".join(active_path + (canonical,))
            raise ValidationContractError(f"Circular alias detected in validation step labels: {cycle_str}")
        if canonical not in step_aliases:
            raise ValidationContractError(f"Unknown validation step label '{label_str}'.")

        targets = step_aliases[canonical]
        if len(targets) == 1 and targets[0] == canonical:
            if canonical not in seen:
                seen.add(canonical)
                expanded.append(canonical)
            return

        new_path = active_path + (canonical,)
        for target in targets:
            _expand(target, new_path)

    for label in labels:
        _expand(label, ())

    return tuple(expanded)


def default_validation_policies() -> dict[str, ValidationPolicy]:
    return dict(DEFAULT_VALIDATION_POLICIES)


def resolve_validation_policy(
    context: ValidationContext,
    *,
    policies: Mapping[str, ValidationPolicy] | None = None,
) -> ValidationPolicy | None:
    available = policies or DEFAULT_VALIDATION_POLICIES

    requested = canonical_validation_policy_name(context.requested_policy)
    if requested is not None:
        try:
            return available[requested]
        except KeyError as exc:
            raise ValidationContractError(f"Unknown validation policy '{context.requested_policy}'.") from exc

    change_type = canonical_validation_policy_name(context.change_type)
    if change_type in available:
        return available[change_type]
    return None


DEFAULT_VALIDATION_POLICIES: dict[str, ValidationPolicy] = {
    "documentation_only": ValidationPolicy(
        name="documentation_only",
        required_steps=(),
        optional_steps=("formatter_check",),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=True,
        metadata={
            "objective": "file validation, formatting, link checking, and documentation-specific validations",
            "future_required_steps": ("file_validation", "link_check", "documentation_validation"),
        },
    ),
    "small_change": ValidationPolicy(
        name="small_change",
        required_steps=("formatter_check", "lint", "syntax", "ast", "affected_tests"),
        optional_steps=(),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=True,
        metadata={"objective": "small, low-risk change"},
    ),
    "structural_change": ValidationPolicy(
        name="structural_change",
        required_steps=("formatter_check", "lint", "syntax", "ast", "affected_tests", "unit_tests", "integration_tests", "static_analysis"),
        optional_steps=(),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=True,
        metadata={"objective": "structural change with static analysis"},
    ),
    "imports_change": ValidationPolicy(
        name="imports_change",
        required_steps=("lint", "syntax", "ast", "import_analysis", "affected_tests", "cycle_checks"),
        optional_steps=(),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=True,
        metadata={"objective": "import and cycle-sensitive change"},
    ),
    "public_api_change": ValidationPolicy(
        name="public_api_change",
        required_steps=("formatter_check", "lint", "syntax", "ast", "affected_tests", "unit_tests", "integration_tests", "full_suite", "contract_validation", "associated_documentation"),
        optional_steps=(),
        stop_on_blocking_failure=True,
        require_full_suite=True,
        allow_commit=True,
        metadata={"objective": "public API change"},
    ),
    "kernel_change": ValidationPolicy(
        name="kernel_change",
        required_steps=("formatter_check", "lint", "syntax", "ast", "full_suite", "static_analysis", "security", "e2e", "kernel_specific_validations"),
        optional_steps=("bandit", "pip_audit"),
        stop_on_blocking_failure=True,
        require_full_suite=True,
        allow_commit=True,
        metadata={"objective": "kernel or runtime change"},
    ),
    "release": ValidationPolicy(
        name="release",
        required_steps=("formatter_check", "lint", "ast", "full_suite", "static_analysis", "security", "e2e", "minimum_coverage", "version_validation", "documentation_validation", "migration_validation"),
        optional_steps=("bandit", "pip_audit"),
        stop_on_blocking_failure=True,
        require_full_suite=True,
        allow_commit=True,
        metadata={"objective": "release validation"},
    ),
    "autonomous_execution": ValidationPolicy(
        name="autonomous_execution",
        required_steps=("restrictive_policy", "allowed_commands_only", "all_required_checks", "complete_artifacts", "mandatory_traceability"),
        optional_steps=(),
        stop_on_blocking_failure=True,
        require_full_suite=True,
        allow_commit=False,
        metadata={"objective": "autonomous execution with strict controls"},
    ),
}


__all__ = [
    "DEFAULT_VALIDATION_POLICIES",
    "ValidationPolicy",
    "canonical_validation_policy_name",
    "default_validation_policies",
    "expand_validation_step_labels",
    "resolve_validation_policy",
]
