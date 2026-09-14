"""Phase 10.49 — Domain Knowledge Package contract tests.

Strict, immutable, serializable Domain-owned schema contracts that constrain the
canonical Phase 8 ``KnowledgePackage``. These tests fail closed on malformed
input and never grant authority.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.domains.errors import (
    DomainKnowledgePackageContractError,
    DomainKnowledgePackageSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_contracts import (
    CANONICAL_KNOWLEDGE_PACKAGE_FIELDS,
    KNOWLEDGE_ITEM_CATEGORY_FIELDS,
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
    EffectiveDomainKnowledgePackageSchema,
)

_DATACLASS_FIELDS = frozenset(
    field
    for field in KnowledgePackage.__dataclass_fields__
    if not field.startswith("_")
)


# ── Canonical field vocabulary ────────────────────────────────────────────────


def test_field_vocabulary_matches_canonical_knowledge_package() -> None:
    assert CANONICAL_KNOWLEDGE_PACKAGE_FIELDS == _DATACLASS_FIELDS
    assert "schema_version" in CANONICAL_KNOWLEDGE_PACKAGE_FIELDS
    assert "facts" in KNOWLEDGE_ITEM_CATEGORY_FIELDS
    assert "objective" not in KNOWLEDGE_ITEM_CATEGORY_FIELDS


# ── DomainKnowledgePackageFieldPolicy ─────────────────────────────────────────


def test_field_policy_is_frozen_and_round_trips() -> None:
    policy = DomainKnowledgePackageFieldPolicy(
        field_name="facts",
        required_non_empty=True,
        minimum_items=2,
        allowed_knowledge_kinds=(KnowledgeKind.FACT,),
        require_provenance=True,
        require_temporal_scope=True,
        preserve_uncertainty=True,
        preserve_contradictions=True,
    )

    assert DomainKnowledgePackageFieldPolicy.from_dict(policy.to_dict()) == policy
    assert policy.to_dict() == {
        "field_name": "facts",
        "required_non_empty": True,
        "minimum_items": 2,
        "allowed_knowledge_kinds": ["fact"],
        "require_provenance": True,
        "require_temporal_scope": True,
        "preserve_uncertainty": True,
        "preserve_contradictions": True,
    }

    with pytest.raises(FrozenInstanceError):
        policy.field_name = "observations"  # type: ignore[misc]


def test_field_policy_defaults_are_inert() -> None:
    policy = DomainKnowledgePackageFieldPolicy(field_name="objective")

    assert policy.required_non_empty is False
    assert policy.minimum_items is None
    assert policy.allowed_knowledge_kinds == ()
    assert policy.require_provenance is False
    assert policy.require_temporal_scope is False
    assert policy.preserve_uncertainty is False
    assert policy.preserve_contradictions is False


@pytest.mark.parametrize(
    "payload",
    [
        {"field_name": ""},
        {"field_name": "   "},
        {"field_name": "not_a_package_field"},
        {"field_name": "facts", "minimum_items": -1},
        {"field_name": "facts", "minimum_items": True},
        {"field_name": "facts", "minimum_items": "2"},
        {"field_name": "facts", "allowed_knowledge_kinds": ["fact", "fact"]},
        {"field_name": "facts", "allowed_knowledge_kinds": ["unknown-kind"]},
        {"field_name": "facts", "required_non_empty": "yes"},
        {"field_name": "facts", "unknown": "x"},
        {"field_name": 7},
        "not-a-mapping",
    ],
)
def test_field_policy_rejects_malformed_payloads(payload: object) -> None:
    with pytest.raises(DomainKnowledgePackageSerializationError):
        DomainKnowledgePackageFieldPolicy.from_dict(payload)  # type: ignore[arg-type]


def test_field_policy_requires_non_blank_field_name() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        DomainKnowledgePackageFieldPolicy(field_name="")

    with pytest.raises(DomainKnowledgePackageContractError):
        DomainKnowledgePackageFieldPolicy(field_name="missing-field")


def test_field_policy_allowed_kinds_only_for_item_categories() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        DomainKnowledgePackageFieldPolicy(
            field_name="objective",
            allowed_knowledge_kinds=(KnowledgeKind.FACT,),
        )

    with pytest.raises(DomainKnowledgePackageContractError):
        DomainKnowledgePackageFieldPolicy(
            field_name="facts",
            allowed_knowledge_kinds=(KnowledgeKind.FACT, KnowledgeKind.FACT),
        )


def test_field_policy_rejects_strict_bool_violations() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        DomainKnowledgePackageFieldPolicy(field_name="facts", required_non_empty=1)  # type: ignore[arg-type]

    with pytest.raises(DomainKnowledgePackageContractError):
        DomainKnowledgePackageFieldPolicy(
            field_name="facts",
            preserve_uncertainty="true",  # type: ignore[arg-type]
        )


# ── DomainKnowledgePackageSchema ──────────────────────────────────────────────


def _schema(**overrides: object) -> DomainKnowledgePackageSchema:
    base: dict[str, object] = {
        "id": "knowledge-package-schema:university",
        "domain_id": DomainId("university"),
        "version": "1",
    }
    base.update(overrides)
    return DomainKnowledgePackageSchema(**base)  # type: ignore[arg-type]


def test_schema_is_frozen_and_round_trips_deterministically() -> None:
    schema = _schema(
        required_sections=("objective", "facts"),
        optional_sections=("timeline",),
        prohibited_sections=("hypotheses",),
        field_policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                required_non_empty=True,
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
            ),
        ),
        minimum_sensitivity=SensitivityLevel.INTERNAL,
        validator_refs=("validator:university-dates",),
        metadata={"phase": "10.49"},
    )

    payload = schema.to_dict()
    assert DomainKnowledgePackageSchema.from_dict(payload) == schema
    assert DomainKnowledgePackageSchema.from_dict(schema.to_dict()).to_dict() == payload
    assert payload["base_schema"] == "KnowledgePackage"
    assert payload["minimum_sensitivity"] == "internal"
    assert isinstance(schema.metadata, MappingProxyType)

    with pytest.raises(FrozenInstanceError):
        schema.id = "other"  # type: ignore[misc]


def test_schema_defaults_are_restrictive_and_empty() -> None:
    schema = _schema()

    assert schema.base_schema == "KnowledgePackage"
    assert schema.required_sections == ()
    assert schema.optional_sections == ()
    assert schema.prohibited_sections == ()
    assert schema.field_policies == ()
    assert schema.minimum_sensitivity is SensitivityLevel.PUBLIC
    assert schema.validator_refs == ()
    assert schema.metadata == {}


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": ""},
        {"version": ""},
        {"domain_id": "not-a-domain"},
        {"base_schema": "DomainKnowledgePackage"},
        {"base_schema": ""},
    ],
)
def test_schema_rejects_invalid_identity(overrides: dict[str, object]) -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(**overrides)


def test_schema_rejects_unknown_sections() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(required_sections=("not_a_section",))


def test_schema_rejects_duplicate_sections() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(required_sections=("facts", "facts"))


@pytest.mark.parametrize(
    ("required", "optional", "prohibited"),
    [
        (("facts",), ("facts",), ()),
        (("facts",), (), ("facts",)),
        ((), ("facts",), ("facts",)),
    ],
)
def test_schema_rejects_section_overlap(
    required: tuple[str, ...],
    optional: tuple[str, ...],
    prohibited: tuple[str, ...],
) -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(
            required_sections=required,
            optional_sections=optional,
            prohibited_sections=prohibited,
        )


def test_schema_rejects_duplicate_field_policies() -> None:
    policy = DomainKnowledgePackageFieldPolicy(field_name="facts")

    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(field_policies=(policy, policy))


def test_schema_rejects_non_empty_policy_on_prohibited_section() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(
            prohibited_sections=("facts",),
            field_policies=(
                DomainKnowledgePackageFieldPolicy(
                    field_name="facts", required_non_empty=True
                ),
            ),
        )

    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(
            prohibited_sections=("facts",),
            field_policies=(
                DomainKnowledgePackageFieldPolicy(field_name="facts", minimum_items=1),
            ),
        )


def test_schema_rejects_invalid_sensitivity() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(minimum_sensitivity="ultra-secret")  # type: ignore[arg-type]

    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(minimum_sensitivity=None)  # type: ignore[arg-type]


def test_schema_rejects_duplicate_or_blank_validator_refs() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(validator_refs=("validator:a", "validator:a"))

    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(validator_refs=("   ",))


def test_schema_rejects_malformed_metadata() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(metadata=["not", "a", "mapping"])

    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(metadata={1: "non-string-key"})

    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(metadata={"bad": object()})


def test_schema_rejects_model_provider_authority_metadata() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(metadata={"preferred_model_id": "gpt-x"})

    with pytest.raises(DomainKnowledgePackageContractError):
        _schema(metadata={"provider": "acme"})


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": "x"},
        {"id": "x", "domain_id": "domain:x", "version": "1", "unknown": 1},
        {"id": "x", "domain_id": "domain:x", "version": "1", "base_schema": "Other"},
        {
            "id": "x",
            "domain_id": "domain:x",
            "version": "1",
            "required_sections": ["facts"],
            "prohibited_sections": ["facts"],
        },
        {
            "id": "x",
            "domain_id": "domain:x",
            "version": "1",
            "minimum_sensitivity": "nonsense",
        },
        {
            "id": "x",
            "domain_id": "domain:x",
            "version": "1",
            "field_policies": [{"field_name": "facts", "minimum_items": -3}],
        },
        "not-a-mapping",
    ],
)
def test_schema_from_dict_fails_closed(payload: object) -> None:
    with pytest.raises(DomainKnowledgePackageSerializationError):
        DomainKnowledgePackageSchema.from_dict(payload)  # type: ignore[arg-type]


# ── EffectiveDomainKnowledgePackageSchema ─────────────────────────────────────


def test_effective_schema_is_immutable_evidence() -> None:
    effective = EffectiveDomainKnowledgePackageSchema(
        source_schema_ids=("knowledge-package-schema:health",),
        domain_ids=(DomainId("health"),),
        required_sections=("objective",),
        optional_sections=(),
        prohibited_sections=(),
        field_policies=(),
        minimum_sensitivity=SensitivityLevel.SENSITIVE,
        validator_refs=(),
    )

    assert (
        EffectiveDomainKnowledgePackageSchema.from_dict(effective.to_dict())
        == effective
    )
    assert effective.to_dict()["minimum_sensitivity"] == "sensitive"
    assert not hasattr(effective, "facts")

    with pytest.raises(FrozenInstanceError):
        effective.minimum_sensitivity = SensitivityLevel.PUBLIC  # type: ignore[misc]


def test_effective_schema_requires_at_least_one_source() -> None:
    with pytest.raises(DomainKnowledgePackageContractError):
        EffectiveDomainKnowledgePackageSchema(
            source_schema_ids=(),
            domain_ids=(),
            required_sections=(),
            optional_sections=(),
            prohibited_sections=(),
            field_policies=(),
            minimum_sensitivity=SensitivityLevel.PUBLIC,
            validator_refs=(),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "source_schema_ids": [],
            "domain_ids": [],
            "required_sections": [],
            "optional_sections": [],
            "prohibited_sections": [],
            "field_policies": [],
            "minimum_sensitivity": "public",
            "validator_refs": [],
        },
        {
            "source_schema_ids": ["s"],
            "domain_ids": ["domain:a"],
            "required_sections": ["facts"],
            "optional_sections": [],
            "prohibited_sections": ["facts"],
            "field_policies": [],
            "minimum_sensitivity": "public",
            "validator_refs": [],
        },
        {
            "source_schema_ids": ["s"],
            "domain_ids": ["domain:a"],
            "required_sections": [],
            "optional_sections": [],
            "prohibited_sections": [],
            "field_policies": [],
            "minimum_sensitivity": "public",
            "validator_refs": [],
            "unknown": True,
        },
        "not-a-mapping",
    ],
)
def test_effective_schema_from_dict_fails_closed(payload: object) -> None:
    with pytest.raises(DomainKnowledgePackageSerializationError):
        EffectiveDomainKnowledgePackageSchema.from_dict(payload)  # type: ignore[arg-type]
