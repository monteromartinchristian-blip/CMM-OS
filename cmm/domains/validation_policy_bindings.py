"""Phase 10.43 — Canonical Domain validation policy bindings.

Thin Domain-owned bindings over canonical Phase 7 ``ValidationPolicy``
semantics. No registry, executor, pipeline, store, history, event bus,
commit gate, runtime, or result model is introduced here.
"""

from __future__ import annotations

from collections.abc import Iterable

from cmm.validation import DEFAULT_VALIDATION_POLICIES, ValidationPolicy

DOMAIN_PACK_INSTALLATION_POLICY_NAME = "DomainPackInstallationPolicy"
DOMAIN_PACK_UPDATE_POLICY_NAME = "DomainPackUpdatePolicy"
DOMAIN_OPERATION_POLICY_NAME = "DomainOperationPolicy"
DOMAIN_WORKFLOW_POLICY_NAME = "DomainWorkflowPolicy"
CROSS_DOMAIN_EXECUTION_POLICY_NAME = "CrossDomainExecutionPolicy"
PROJECT_DOMAIN_CHANGE_POLICY_NAME = "ProjectDomainChangePolicy"

DOMAIN_PACK_BASE_VALIDATION_IDS: tuple[str, ...] = (
    "domain.compatibility",
    "domain.contracts",
    "domain.dependencies",
    "domain.fragmentation",
    "domain.manifest",
    "domain.permissions",
    "domain.security",
    "domain.tests",
)

_PROJECT_IMPACT_TO_CANONICAL_POLICY = {
    "small": "small_change",
    "structural": "structural_change",
    "public": "structural_change",
    "broad": "full",
    "high": "full",
}


def compose_required_validation_ids(
    *groups: Iterable[str],
) -> tuple[str, ...]:
    """Deterministic monotonic union of required validation IDs.

    Deduplicates equal IDs, sorts lexically, and fails closed on empty or
    non-string members. Adding groups can only add obligations, never remove
    them.
    """
    values: set[str] = set()
    for group in groups:
        if group is None:  # type: ignore[unreachable]
            raise ValueError("validation id groups must not be None")
        for item in group:
            if not isinstance(item, str) or not item:
                raise ValueError("validation ids must be non-empty strings")
            values.add(item)
    return tuple(sorted(values))


def _clean_extra_ids(extra: Iterable[str] | None, field: str) -> tuple[str, ...]:
    if extra is None:
        return ()
    if isinstance(extra, (str, bytes)):
        raise TypeError(f"{field} must be an iterable of non-empty strings")
    try:
        items = tuple(extra)
    except TypeError as exc:
        raise TypeError(f"{field} must be iterable") from exc
    for item in items:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{field} must contain only non-empty strings")
    return tuple(items)


def build_domain_pack_installation_policy(
    *,
    extra_required_steps: Iterable[str] = (),
    optional_steps: Iterable[str] = (),
    allow_commit: bool = False,
) -> ValidationPolicy:
    required = compose_required_validation_ids(
        DOMAIN_PACK_BASE_VALIDATION_IDS,
        _clean_extra_ids(extra_required_steps, "extra_required_steps"),
    )
    return ValidationPolicy(
        name=DOMAIN_PACK_INSTALLATION_POLICY_NAME,
        required_steps=required,
        optional_steps=_clean_extra_ids(optional_steps, "optional_steps"),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=bool(allow_commit),
        metadata={
            "domain_policy_family": DOMAIN_PACK_INSTALLATION_POLICY_NAME,
            "domain_use_case": "pack_installation",
        },
    )


def build_domain_pack_update_policy(
    *,
    extra_required_steps: Iterable[str] = (),
    optional_steps: Iterable[str] = (),
    allow_commit: bool = False,
) -> ValidationPolicy:
    required = compose_required_validation_ids(
        DOMAIN_PACK_BASE_VALIDATION_IDS,
        _clean_extra_ids(extra_required_steps, "extra_required_steps"),
    )
    return ValidationPolicy(
        name=DOMAIN_PACK_UPDATE_POLICY_NAME,
        required_steps=required,
        optional_steps=_clean_extra_ids(optional_steps, "optional_steps"),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=bool(allow_commit),
        metadata={
            "domain_policy_family": DOMAIN_PACK_UPDATE_POLICY_NAME,
            "domain_use_case": "pack_update",
        },
    )


def build_domain_operation_policy(
    *,
    required_validation_ids: Iterable[str] = (),
    optional_steps: Iterable[str] = (),
    allow_commit: bool = False,
) -> ValidationPolicy:
    required = compose_required_validation_ids(
        _clean_extra_ids(required_validation_ids, "required_validation_ids"),
    )
    return ValidationPolicy(
        name=DOMAIN_OPERATION_POLICY_NAME,
        required_steps=required,
        optional_steps=_clean_extra_ids(optional_steps, "optional_steps"),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=bool(allow_commit),
        metadata={
            "domain_policy_family": DOMAIN_OPERATION_POLICY_NAME,
            "domain_use_case": "domain_operation",
        },
    )


def build_domain_workflow_policy(
    *,
    required_validation_ids: Iterable[str] = (),
    optional_steps: Iterable[str] = (),
    allow_commit: bool = False,
) -> ValidationPolicy:
    required = compose_required_validation_ids(
        _clean_extra_ids(required_validation_ids, "required_validation_ids"),
    )
    return ValidationPolicy(
        name=DOMAIN_WORKFLOW_POLICY_NAME,
        required_steps=required,
        optional_steps=_clean_extra_ids(optional_steps, "optional_steps"),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=bool(allow_commit),
        metadata={
            "domain_policy_family": DOMAIN_WORKFLOW_POLICY_NAME,
            "domain_use_case": "domain_workflow",
        },
    )


def build_cross_domain_execution_policy(
    *,
    global_required: Iterable[str] = (),
    primary_required: Iterable[str] = (),
    supporting_required: Iterable[str] = (),
    operation_required: Iterable[str] = (),
    workflow_required: Iterable[str] = (),
    dependency_required: Iterable[str] = (),
    project_required: Iterable[str] = (),
    optional_steps: Iterable[str] = (),
    allow_commit: bool = False,
) -> ValidationPolicy:
    required = compose_required_validation_ids(
        _clean_extra_ids(global_required, "global_required"),
        _clean_extra_ids(primary_required, "primary_required"),
        _clean_extra_ids(supporting_required, "supporting_required"),
        _clean_extra_ids(operation_required, "operation_required"),
        _clean_extra_ids(workflow_required, "workflow_required"),
        _clean_extra_ids(dependency_required, "dependency_required"),
        _clean_extra_ids(project_required, "project_required"),
    )
    return ValidationPolicy(
        name=CROSS_DOMAIN_EXECUTION_POLICY_NAME,
        required_steps=required,
        optional_steps=_clean_extra_ids(optional_steps, "optional_steps"),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=bool(allow_commit),
        metadata={
            "domain_policy_family": CROSS_DOMAIN_EXECUTION_POLICY_NAME,
            "domain_use_case": "cross_domain_execution",
        },
    )


def build_project_domain_change_policy(
    *,
    required_validation_ids: Iterable[str] = (),
    impact: str = "small",
    optional_steps: Iterable[str] = (),
    allow_commit: bool = False,
) -> ValidationPolicy:
    if not isinstance(impact, str) or not impact.strip():
        raise ValueError("impact must be a non-empty string")
    canonical_key = impact.strip().lower()
    canonical_policy_name = _PROJECT_IMPACT_TO_CANONICAL_POLICY.get(
        canonical_key, "small_change"
    )
    canonical = DEFAULT_VALIDATION_POLICIES.get(canonical_policy_name)
    canonical_steps: tuple[str, ...] = (
        tuple(canonical.required_steps) if canonical is not None else ()
    )
    required = compose_required_validation_ids(
        canonical_steps,
        _clean_extra_ids(required_validation_ids, "required_validation_ids"),
    )
    require_full = (
        bool(canonical.require_full_suite) if canonical is not None else False
    )
    # Broad/high-impact changes escalate to full-suite semantics even if the
    # canonical catalog entry ever changes.
    if canonical_key in ("broad", "high", "full"):
        require_full = True
    return ValidationPolicy(
        name=PROJECT_DOMAIN_CHANGE_POLICY_NAME,
        required_steps=required,
        optional_steps=_clean_extra_ids(optional_steps, "optional_steps"),
        stop_on_blocking_failure=True,
        require_full_suite=require_full,
        allow_commit=bool(allow_commit),
        metadata={
            "domain_policy_family": PROJECT_DOMAIN_CHANGE_POLICY_NAME,
            "domain_use_case": "project_domain_change",
            "project_impact": canonical_key,
            "canonical_phase7_policy": canonical_policy_name,
        },
    )


__all__ = [
    "CROSS_DOMAIN_EXECUTION_POLICY_NAME",
    "DOMAIN_OPERATION_POLICY_NAME",
    "DOMAIN_PACK_BASE_VALIDATION_IDS",
    "DOMAIN_PACK_INSTALLATION_POLICY_NAME",
    "DOMAIN_PACK_UPDATE_POLICY_NAME",
    "DOMAIN_WORKFLOW_POLICY_NAME",
    "PROJECT_DOMAIN_CHANGE_POLICY_NAME",
    "build_cross_domain_execution_policy",
    "build_domain_operation_policy",
    "build_domain_pack_installation_policy",
    "build_domain_pack_update_policy",
    "build_domain_workflow_policy",
    "build_project_domain_change_policy",
    "compose_required_validation_ids",
]
