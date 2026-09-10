"""Phase 10.49 – deterministic multi-domain knowledge package schema composition."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.errors import DomainKnowledgePackageCompositionError
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
    EffectiveDomainKnowledgePackageSchema,
)

__all__ = ["compose_domain_knowledge_package_schemas"]

# Explicit canonical sensitivity ordering. Composition must never rely on enum
# declaration order, which is not a security boundary.
SENSITIVITY_RANK: Mapping[SensitivityLevel, int] = {
    SensitivityLevel.PUBLIC: 0,
    SensitivityLevel.INTERNAL: 1,
    SensitivityLevel.PERSONAL: 2,
    SensitivityLevel.SENSITIVE: 3,
    SensitivityLevel.HIGHLY_SENSITIVE: 4,
    SensitivityLevel.RESTRICTED: 5,
}


def _normalize_schemas(
    schemas: Iterable[DomainKnowledgePackageSchema],
) -> tuple[DomainKnowledgePackageSchema, ...]:
    if isinstance(schemas, (str, bytes, bytearray)) or not isinstance(
        schemas, Iterable
    ):
        raise DomainKnowledgePackageCompositionError(
            "schemas must be an iterable of DomainKnowledgePackageSchema",
            field="schemas",
        )
    materialized = list(schemas)
    if not materialized:
        raise DomainKnowledgePackageCompositionError(
            "at least one schema is required for composition", field="schemas"
        )
    for index, schema in enumerate(materialized):
        if not isinstance(schema, DomainKnowledgePackageSchema):
            raise DomainKnowledgePackageCompositionError(
                f"schemas[{index}] must be a DomainKnowledgePackageSchema, "
                f"got {type(schema).__name__}",
                field="schemas",
            )
    return tuple(
        sorted(
            materialized, key=lambda item: (str(item.domain_id), item.version, item.id)
        )
    )


def _compose_policies(
    field_name: str, group: tuple[DomainKnowledgePackageFieldPolicy, ...]
) -> DomainKnowledgePackageFieldPolicy:
    configured_kinds = [
        set(policy.allowed_knowledge_kinds)
        for policy in group
        if policy.allowed_knowledge_kinds
    ]
    if configured_kinds:
        intersection = set.intersection(*configured_kinds)
        if not intersection:
            raise DomainKnowledgePackageCompositionError(
                f"allowed_knowledge_kinds for {field_name!r} have an empty "
                "intersection",
                field="field_policies",
                details={"field_name": field_name},
            )
        kinds = tuple(sorted(intersection, key=lambda kind: kind.value))
    else:
        kinds = ()

    minimums = [
        policy.minimum_items for policy in group if policy.minimum_items is not None
    ]

    return DomainKnowledgePackageFieldPolicy(
        field_name=field_name,
        required_non_empty=any(policy.required_non_empty for policy in group),
        minimum_items=max(minimums) if minimums else None,
        allowed_knowledge_kinds=kinds,
        require_provenance=any(policy.require_provenance for policy in group),
        require_temporal_scope=any(policy.require_temporal_scope for policy in group),
        preserve_uncertainty=any(policy.preserve_uncertainty for policy in group),
        preserve_contradictions=any(policy.preserve_contradictions for policy in group),
    )


def compose_domain_knowledge_package_schemas(
    schemas: Iterable[DomainKnowledgePackageSchema],
) -> EffectiveDomainKnowledgePackageSchema:
    """Compose Domain schemas into one immutable, order-independent effective schema.

    Composition is deterministic and monotonic: it only ever narrows. It never
    invents a synthetic Domain identity and never grants authority.
    """
    ordered = _normalize_schemas(schemas)

    required: set[str] = set()
    optional: set[str] = set()
    prohibited: set[str] = set()
    policy_groups: dict[str, list[DomainKnowledgePackageFieldPolicy]] = {}
    validator_refs: set[str] = set()
    strongest = SensitivityLevel.PUBLIC

    for schema in ordered:
        required.update(schema.required_sections)
        optional.update(schema.optional_sections)
        prohibited.update(schema.prohibited_sections)
        for policy in schema.field_policies:
            policy_groups.setdefault(policy.field_name, []).append(policy)
        validator_refs.update(schema.validator_refs)
        if SENSITIVITY_RANK[schema.minimum_sensitivity] > SENSITIVITY_RANK[strongest]:
            strongest = schema.minimum_sensitivity

    conflict = sorted(required & prohibited)
    if conflict:
        raise DomainKnowledgePackageCompositionError(
            f"required and prohibited sections are irreconcilable: {conflict}",
            field="required_sections",
            details={"conflict": conflict},
        )

    optional -= required
    optional -= prohibited

    composed_policies = tuple(
        _compose_policies(name, tuple(policy_groups[name]))
        for name in sorted(policy_groups)
    )

    prohibited_policy_conflict = sorted(
        policy.field_name
        for policy in composed_policies
        if policy.field_name in prohibited
        and (policy.required_non_empty or policy.minimum_items is not None)
    )
    if prohibited_policy_conflict:
        raise DomainKnowledgePackageCompositionError(
            f"prohibited sections cannot require content: {prohibited_policy_conflict}",
            field="field_policies",
            details={"conflict": prohibited_policy_conflict},
        )

    return EffectiveDomainKnowledgePackageSchema(
        source_schema_ids=tuple(schema.id for schema in ordered),
        domain_ids=tuple(schema.domain_id for schema in ordered),
        required_sections=tuple(sorted(required)),
        optional_sections=tuple(sorted(optional)),
        prohibited_sections=tuple(sorted(prohibited)),
        field_policies=composed_policies,
        minimum_sensitivity=strongest,
        validator_refs=tuple(sorted(validator_refs)),
    )
