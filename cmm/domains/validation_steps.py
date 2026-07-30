"""Phase 10.5 – Domain Validation Steps.

Deterministic builder with DFS transitive dependency resolution.
"""

from __future__ import annotations

from cmm.domains.validation_contracts import DomainValidationRequest
from cmm.validation.steps import ValidationStep, ValidationStepType

STEP_MANIFEST = "domain.manifest"
STEP_CONTRACTS = "domain.contracts"
STEP_PERMISSIONS = "domain.permissions"
STEP_DEPENDENCIES = "domain.dependencies"
STEP_COMPATIBILITY = "domain.compatibility"
STEP_SECURITY = "domain.security"
STEP_FRAGMENTATION = "domain.fragmentation"
STEP_TESTS = "domain.tests"

ALL_DOMAIN_STEPS = (
    STEP_MANIFEST,
    STEP_CONTRACTS,
    STEP_PERMISSIONS,
    STEP_DEPENDENCIES,
    STEP_COMPATIBILITY,
    STEP_SECURITY,
    STEP_FRAGMENTATION,
    STEP_TESTS,
)

_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    STEP_MANIFEST: (),
    STEP_CONTRACTS: (STEP_MANIFEST,),
    STEP_PERMISSIONS: (STEP_MANIFEST,),
    STEP_DEPENDENCIES: (STEP_MANIFEST,),
    STEP_COMPATIBILITY: (STEP_MANIFEST,),
    STEP_SECURITY: (STEP_CONTRACTS, STEP_PERMISSIONS),
    STEP_FRAGMENTATION: (STEP_CONTRACTS,),
    STEP_TESTS: (STEP_CONTRACTS, STEP_SECURITY),
}

_STRICT_MANDATORY = frozenset(
    {
        STEP_MANIFEST,
        STEP_CONTRACTS,
        STEP_PERMISSIONS,
        STEP_DEPENDENCIES,
        STEP_COMPATIBILITY,
        STEP_SECURITY,
        STEP_FRAGMENTATION,
    }
)

_STEP_ORDER: dict[str, int] = {name: i for i, name in enumerate(ALL_DOMAIN_STEPS)}


def build_domain_validation_steps(
    request: DomainValidationRequest,
) -> tuple[ValidationStep, ...]:
    from cmm.domains.errors import DomainValidationRequestInvalid

    # Validate names
    if request.requested_steps is not None:
        unknown = set(request.requested_steps) - set(ALL_DOMAIN_STEPS)
        if unknown:
            raise DomainValidationRequestInvalid(
                f"Unknown requested steps: {sorted(unknown)}",
                details={"unknown": sorted(unknown)},
            )
        if len(set(request.requested_steps)) != len(request.requested_steps):
            raise DomainValidationRequestInvalid(
                "Duplicate requested steps",
                details={"duplicates": _find_dups(request.requested_steps)},
            )

    unknown_exc = set(request.excluded_steps) - set(ALL_DOMAIN_STEPS)
    if unknown_exc:
        raise DomainValidationRequestInvalid(
            f"Unknown excluded steps: {sorted(unknown_exc)}",
            details={"unknown": sorted(unknown_exc)},
        )

    if request.requested_steps is not None:
        intersection = set(request.requested_steps) & set(request.excluded_steps)
        if intersection:
            raise DomainValidationRequestInvalid(
                f"Steps both requested and excluded: {sorted(intersection)}",
                details={"conflict": sorted(intersection)},
            )

    if request.strict:
        for step_name in request.excluded_steps:
            if step_name in _STRICT_MANDATORY:
                raise DomainValidationRequestInvalid(
                    f"Cannot exclude mandatory step in strict mode: {step_name}",
                    details={"step": step_name},
                )
        if STEP_TESTS in request.excluded_steps and request.run_tests:
            raise DomainValidationRequestInvalid(
                "Cannot exclude domain.tests in strict mode when run_tests=True",
                details={"step": STEP_TESTS},
            )

    # Determine selected steps via DFS
    if request.requested_steps is not None:
        selected = _resolve_transitive_deps(
            request.requested_steps, request.excluded_steps
        )
    else:
        selected = set(ALL_DOMAIN_STEPS) - set(request.excluded_steps)

    # Build steps in original order
    result: list[ValidationStep] = []
    for name in ALL_DOMAIN_STEPS:
        if name not in selected:
            continue
        required = _is_required(request, name)
        result.append(
            ValidationStep(
                name=name,
                step_type=ValidationStepType.INTERNAL,
                required=required,
                dependencies=_DEPENDENCIES[name],
                tags=("domain",),
                metadata={"domain_step": name.split(".")[-1]},
            )
        )

    return tuple(result)


def _resolve_transitive_deps(
    requested: tuple[str, ...],
    excluded: tuple[str, ...],
) -> set[str]:
    from cmm.domains.errors import DomainValidationStepMissing

    excluded_set = set(excluded)
    resolved: set[str] = set(requested)
    stack = list(requested)

    while stack:
        current = stack.pop()
        for dep in _DEPENDENCIES.get(current, ()):
            if dep in excluded_set:
                raise DomainValidationStepMissing(
                    f"Transitive dependency '{dep}' of '{current}' is excluded",
                    details={"step": dep, "required_by": current},
                )
            if dep not in resolved:
                resolved.add(dep)
                stack.append(dep)

    return resolved


def _is_required(request: DomainValidationRequest, step_name: str) -> bool:
    if request.requested_steps is not None:
        return step_name in request.requested_steps
    if step_name in request.excluded_steps:
        return False
    return not (
        not request.strict and step_name == STEP_TESTS and not request.run_tests
    )


def _find_dups(items: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    dups: list[str] = []
    for item in items:
        if item in seen:
            dups.append(item)
        seen.add(item)
    return dups


__all__ = [
    "ALL_DOMAIN_STEPS",
    "STEP_COMPATIBILITY",
    "STEP_CONTRACTS",
    "STEP_DEPENDENCIES",
    "STEP_FRAGMENTATION",
    "STEP_MANIFEST",
    "STEP_PERMISSIONS",
    "STEP_SECURITY",
    "STEP_TESTS",
    "build_domain_validation_steps",
]
