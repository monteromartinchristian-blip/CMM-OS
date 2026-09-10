"""Phase 10.49 – pure validation of a canonical Phase 8 ``KnowledgePackage``.

``validate_domain_knowledge_package`` checks an *already-produced* canonical
``KnowledgePackage`` against a Domain schema. It is deterministic, side-effect
free and fail-closed: on success it returns the exact same object, and it never
mutates, repairs, stores or rebuilds the package.

Preservation semantics are deliberately positive-evidence-only: a
``preserve_uncertainty`` / ``preserve_contradictions`` requirement is never
violated merely because a section is empty. It is violated only when the package
itself shows that uncertainty or a contradiction was collapsed — an
inference/hypothesis asserted at absolute certainty, or a contradiction marked
resolved.

Opaque validator references are never resolved or executed. This module never
grants permission, privacy, provider or execution authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Sized
from typing import Any, NoReturn

from cmm.cognitive.enums import (
    ContradictionStatus,
    KnowledgeKind,
    TemporalScopeKind,
)
from cmm.cognitive.knowledge import Contradiction, KnowledgeItem, TemporalScope
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.cognitive.privacy import privacy_from_knowledge_package
from cmm.domains.errors import (
    DomainError,
    DomainKnowledgePackageValidationError,
)
from cmm.domains.knowledge_package_composition import SENSITIVITY_RANK
from cmm.domains.knowledge_package_contracts import (
    KNOWLEDGE_ITEM_CATEGORY_FIELDS,
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
    EffectiveDomainKnowledgePackageSchema,
)

__all__ = ["validate_domain_knowledge_package"]

_UNCERTAIN_KINDS = (KnowledgeKind.INFERENCE, KnowledgeKind.HYPOTHESIS)


def _fail(
    message: str, *, field: str | None = None, details: dict[str, Any] | None = None
) -> NoReturn:
    raise DomainKnowledgePackageValidationError(message, field=field, details=details)


def _is_empty(value: Any) -> bool:
    """Return True when a canonical package section carries no content."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (Mapping, Sequence)):
        return len(value) == 0
    return False


def _require_schema(schema: Any) -> None:
    if not isinstance(
        schema, (DomainKnowledgePackageSchema, EffectiveDomainKnowledgePackageSchema)
    ):
        _fail(
            "schema must be a DomainKnowledgePackageSchema or "
            "EffectiveDomainKnowledgePackageSchema",
            field="schema",
        )


def _validate_prohibited_sections(
    package: KnowledgePackage,
    schema: DomainKnowledgePackageSchema | EffectiveDomainKnowledgePackageSchema,
) -> None:
    for section in schema.prohibited_sections:
        if not _is_empty(getattr(package, section)):
            _fail(
                f"prohibited section {section!r} must remain empty",
                field=section,
            )


def _validate_required_sections(
    package: KnowledgePackage,
    schema: DomainKnowledgePackageSchema | EffectiveDomainKnowledgePackageSchema,
) -> None:
    for section in schema.required_sections:
        if _is_empty(getattr(package, section)):
            _fail(
                f"required section {section!r} must not be empty",
                field=section,
            )


def _validate_kinds(policy: DomainKnowledgePackageFieldPolicy, value: Any) -> None:
    if policy.field_name not in KNOWLEDGE_ITEM_CATEGORY_FIELDS:
        _fail(
            f"allowed_knowledge_kinds is only valid for knowledge-item category "
            f"fields, not {policy.field_name!r}",
            field=policy.field_name,
        )
    for item in value:
        if not isinstance(item, KnowledgeItem):
            _fail(
                f"{policy.field_name} must contain KnowledgeItem values",
                field=policy.field_name,
            )
        if item.kind not in policy.allowed_knowledge_kinds:
            _fail(
                f"{policy.field_name} item {item.id!r} has disallowed kind "
                f"{item.kind.value!r}",
                field=policy.field_name,
                details={
                    "item_id": item.id,
                    "kind": item.kind.value,
                    "allowed": sorted(
                        kind.value for kind in policy.allowed_knowledge_kinds
                    ),
                },
            )


def _validate_provenance(policy: DomainKnowledgePackageFieldPolicy, value: Any) -> None:
    if policy.field_name in KNOWLEDGE_ITEM_CATEGORY_FIELDS:
        for item in value:
            if not isinstance(item, KnowledgeItem) or not item.evidence:
                item_id = getattr(item, "id", None)
                _fail(
                    f"{policy.field_name} item {item_id!r} must retain canonical "
                    "provenance evidence",
                    field=policy.field_name,
                    details={"item_id": item_id},
                )
        return
    if _is_empty(value):
        _fail(
            f"{policy.field_name} must retain canonical provenance",
            field=policy.field_name,
        )


def _validate_temporal(policy: DomainKnowledgePackageFieldPolicy, value: Any) -> None:
    if policy.field_name in KNOWLEDGE_ITEM_CATEGORY_FIELDS:
        for item in value:
            scope = getattr(item, "temporal_scope", None)
            if (
                not isinstance(scope, TemporalScope)
                or scope.kind is TemporalScopeKind.UNKNOWN
            ):
                item_id = getattr(item, "id", None)
                _fail(
                    f"{policy.field_name} item {item_id!r} must retain canonical "
                    "temporal evidence",
                    field=policy.field_name,
                    details={"item_id": item_id},
                )
        return
    if _is_empty(value):
        _fail(
            f"{policy.field_name} must retain canonical temporal evidence",
            field=policy.field_name,
        )


def _validate_uncertainty(
    policy: DomainKnowledgePackageFieldPolicy, value: Any
) -> None:
    # Absence is never treated as uncertainty erasure.
    if policy.field_name not in KNOWLEDGE_ITEM_CATEGORY_FIELDS:
        return
    for item in value:
        if not isinstance(item, KnowledgeItem):
            continue
        if item.kind in _UNCERTAIN_KINDS and item.confidence.value >= 1.0:
            _fail(
                f"{policy.field_name} item {item.id!r} collapses uncertainty into "
                "absolute certainty",
                field=policy.field_name,
                details={"item_id": item.id, "kind": item.kind.value},
            )


def _validate_contradictions(
    package: KnowledgePackage, policy: DomainKnowledgePackageFieldPolicy
) -> None:
    # Absence is never treated as contradiction erasure.
    for contradiction in package.contradictions:
        if not isinstance(contradiction, Contradiction):
            _fail(
                "contradictions must contain canonical Contradiction values",
                field="contradictions",
            )
        if contradiction.status is ContradictionStatus.RESOLVED:
            _fail(
                f"contradiction {contradiction.id!r} is resolved; preservation "
                "forbids erasing contradiction visibility",
                field="contradictions",
                details={"contradiction_id": contradiction.id},
            )


def _validate_field_policies(
    package: KnowledgePackage,
    schema: DomainKnowledgePackageSchema | EffectiveDomainKnowledgePackageSchema,
) -> None:
    for policy in sorted(schema.field_policies, key=lambda item: item.field_name):
        value = getattr(package, policy.field_name)
        if policy.required_non_empty and _is_empty(value):
            _fail(
                f"{policy.field_name} must not be empty",
                field=policy.field_name,
            )
        if policy.minimum_items is not None and (
            not isinstance(value, Sized) or len(value) < policy.minimum_items
        ):
            _fail(
                f"{policy.field_name} must contain at least "
                f"{policy.minimum_items} item(s)",
                field=policy.field_name,
                details={"minimum_items": policy.minimum_items},
            )
        if policy.allowed_knowledge_kinds:
            _validate_kinds(policy, value)
        if policy.require_provenance:
            _validate_provenance(policy, value)
        if policy.require_temporal_scope:
            _validate_temporal(policy, value)
        if policy.preserve_uncertainty:
            _validate_uncertainty(policy, value)
        if policy.preserve_contradictions:
            _validate_contradictions(package, policy)


def _validate_minimum_sensitivity(
    package: KnowledgePackage,
    schema: DomainKnowledgePackageSchema | EffectiveDomainKnowledgePackageSchema,
) -> None:
    floor = schema.minimum_sensitivity
    try:
        effective = privacy_from_knowledge_package(package).sensitivity
    except DomainError as exc:  # pragma: no cover - defensive canonical boundary
        _fail(
            f"could not derive canonical privacy: {exc.message}",
            field="minimum_sensitivity",
        )
    if SENSITIVITY_RANK[effective] < SENSITIVITY_RANK[floor]:
        _fail(
            f"effective sensitivity {effective.value!r} is below the schema floor "
            f"{floor.value!r}",
            field="minimum_sensitivity",
            details={"effective": effective.value, "floor": floor.value},
        )


def validate_domain_knowledge_package(
    package: KnowledgePackage,
    schema: DomainKnowledgePackageSchema | EffectiveDomainKnowledgePackageSchema,
) -> KnowledgePackage:
    """Validate a canonical package against a Domain schema.

    Returns the exact same object on success; raises
    :class:`DomainKnowledgePackageValidationError` on any violation. The package
    is never mutated, and opaque validator references are never resolved.
    """
    _require_schema(schema)
    if type(package) is not KnowledgePackage:
        _fail(
            "validate_domain_knowledge_package only accepts the canonical "
            f"KnowledgePackage, got {type(package).__name__}",
            field="package",
        )

    _validate_prohibited_sections(package, schema)
    _validate_required_sections(package, schema)
    _validate_field_policies(package, schema)
    _validate_minimum_sensitivity(package, schema)
    return package
