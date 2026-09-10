"""Phase 10.49 – deterministic multi-domain knowledge package schema composition."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.domains.errors import DomainKnowledgePackageCompositionError
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_composition import (
    compose_domain_knowledge_package_schemas,
)
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
)


def _schema(
    domain_slug: str,
    *,
    version: str = "1",
    required: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    prohibited: tuple[str, ...] = (),
    policies: tuple[DomainKnowledgePackageFieldPolicy, ...] = (),
    sensitivity: SensitivityLevel = SensitivityLevel.PUBLIC,
    validators: tuple[str, ...] = (),
) -> DomainKnowledgePackageSchema:
    return DomainKnowledgePackageSchema(
        id=f"knowledge-package-schema:{domain_slug}",
        domain_id=DomainId(domain_slug),
        version=version,
        required_sections=required,
        optional_sections=optional,
        prohibited_sections=prohibited,
        field_policies=policies,
        minimum_sensitivity=sensitivity,
        validator_refs=validators,
    )


def _health() -> DomainKnowledgePackageSchema:
    return _schema(
        "health",
        required=("objective", "facts"),
        optional=("timeline",),
        prohibited=("hypotheses",),
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                required_non_empty=True,
                allowed_knowledge_kinds=(
                    KnowledgeKind.FACT,
                    KnowledgeKind.INFERENCE,
                ),
                require_provenance=True,
            ),
        ),
        sensitivity=SensitivityLevel.SENSITIVE,
        validators=("validator:health-dates",),
    )


def _university() -> DomainKnowledgePackageSchema:
    return _schema(
        "university",
        required=("objective", "timeline"),
        optional=("facts", "unknowns"),
        prohibited=("other_knowledge",),
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                minimum_items=2,
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
                require_temporal_scope=True,
            ),
        ),
        sensitivity=SensitivityLevel.INTERNAL,
        validators=("validator:university-terms",),
    )


# ── Order independence and monotonicity ───────────────────────────────────────


def test_composition_is_order_independent() -> None:
    forward = compose_domain_knowledge_package_schemas((_health(), _university()))
    backward = compose_domain_knowledge_package_schemas((_university(), _health()))

    assert forward == backward
    assert forward.to_dict() == backward.to_dict()


def test_composition_unions_sections_and_uses_strongest_sensitivity() -> None:
    effective = compose_domain_knowledge_package_schemas((_health(), _university()))

    assert effective.required_sections == ("facts", "objective", "timeline")
    assert effective.optional_sections == ("unknowns",)
    assert effective.prohibited_sections == ("hypotheses", "other_knowledge")
    assert effective.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert effective.validator_refs == (
        "validator:health-dates",
        "validator:university-terms",
    )
    assert effective.source_schema_ids == (
        "knowledge-package-schema:health",
        "knowledge-package-schema:university",
    )
    assert effective.domain_ids == (DomainId("health"), DomainId("university"))


def test_composition_is_monotone_never_weakens_sensitivity() -> None:
    low = _schema("a", sensitivity=SensitivityLevel.PUBLIC)
    high = _schema("b", sensitivity=SensitivityLevel.RESTRICTED)

    assert (
        compose_domain_knowledge_package_schemas((low, high)).minimum_sensitivity
        is SensitivityLevel.RESTRICTED
    )


# ── Policy narrowing ──────────────────────────────────────────────────────────


def test_composition_narrows_field_policies_most_restrictively() -> None:
    first = _schema(
        "a",
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                required_non_empty=False,
                minimum_items=1,
                allowed_knowledge_kinds=(
                    KnowledgeKind.FACT,
                    KnowledgeKind.OBSERVATION,
                ),
            ),
        ),
    )
    second = _schema(
        "b",
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                required_non_empty=True,
                minimum_items=3,
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
                require_provenance=True,
                preserve_contradictions=True,
            ),
        ),
    )

    effective = compose_domain_knowledge_package_schemas((first, second))

    assert len(effective.field_policies) == 1
    policy = effective.field_policies[0]
    assert policy.field_name == "facts"
    assert policy.required_non_empty is True
    assert policy.minimum_items == 3
    assert policy.allowed_knowledge_kinds == (KnowledgeKind.FACT,)
    assert policy.require_provenance is True
    assert policy.preserve_contradictions is True


def test_composition_keeps_single_configured_allowlist() -> None:
    only = _schema(
        "a",
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="observations",
                allowed_knowledge_kinds=(KnowledgeKind.OBSERVATION,),
            ),
        ),
    )
    plain = _schema(
        "b", policies=(DomainKnowledgePackageFieldPolicy(field_name="observations"),)
    )

    effective = compose_domain_knowledge_package_schemas((only, plain))

    assert effective.field_policies[0].allowed_knowledge_kinds == (
        KnowledgeKind.OBSERVATION,
    )
    assert effective.field_policies[0].minimum_items is None
    assert effective.field_policies[0].required_non_empty is False


# ── Fail-closed conflicts ─────────────────────────────────────────────────────


def test_composition_rejects_empty_input() -> None:
    with pytest.raises(DomainKnowledgePackageCompositionError):
        compose_domain_knowledge_package_schemas(())


@pytest.mark.parametrize("order", ("forward", "reverse"))
def test_composition_rejects_required_prohibited_conflict(order: str) -> None:
    requires_facts = _schema("a", required=("facts",))
    prohibits_facts = _schema("b", prohibited=("facts",))
    pair = (
        (requires_facts, prohibits_facts)
        if order == "forward"
        else (prohibits_facts, requires_facts)
    )

    with pytest.raises(DomainKnowledgePackageCompositionError):
        compose_domain_knowledge_package_schemas(pair)


@pytest.mark.parametrize("order", ("forward", "reverse"))
def test_composition_rejects_empty_kind_intersection(order: str) -> None:
    facts_only = _schema(
        "a",
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="other_knowledge",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
            ),
        ),
    )
    opinions_only = _schema(
        "b",
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="other_knowledge",
                allowed_knowledge_kinds=(KnowledgeKind.OPINION,),
            ),
        ),
    )
    pair = (
        (facts_only, opinions_only)
        if order == "forward"
        else (opinions_only, facts_only)
    )

    with pytest.raises(DomainKnowledgePackageCompositionError):
        compose_domain_knowledge_package_schemas(pair)


def test_composition_rejects_content_requirement_on_prohibited_section() -> None:
    prohibits_facts = _schema("a", prohibited=("facts",))
    requires_facts = _schema(
        "b",
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts", required_non_empty=True
            ),
        ),
    )

    with pytest.raises(DomainKnowledgePackageCompositionError):
        compose_domain_knowledge_package_schemas((prohibits_facts, requires_facts))


def test_composition_rejects_non_schema_items() -> None:
    with pytest.raises(DomainKnowledgePackageCompositionError):
        compose_domain_knowledge_package_schemas((object(),))  # type: ignore[arg-type]


def test_composition_rejects_non_iterable_input() -> None:
    with pytest.raises(DomainKnowledgePackageCompositionError):
        compose_domain_knowledge_package_schemas("not-a-schema")  # type: ignore[arg-type]


# ── Effective schema boundary ─────────────────────────────────────────────────


def test_effective_schema_carries_no_knowledge_payload() -> None:
    effective = compose_domain_knowledge_package_schemas((_health(),))

    for field_name in ("facts", "objective", "contradictions", "resources"):
        assert not hasattr(effective, field_name)


def test_effective_schema_round_trips() -> None:
    effective = compose_domain_knowledge_package_schemas((_health(), _university()))

    assert type(effective).from_dict(effective.to_dict()) == effective


def test_composition_result_is_immutable() -> None:
    effective = compose_domain_knowledge_package_schemas((_health(),))

    with pytest.raises(FrozenInstanceError):
        effective.minimum_sensitivity = SensitivityLevel.PUBLIC  # type: ignore[misc]
