"""Phase 10.49 – pure validation of a canonical Phase 8 ``KnowledgePackage``."""

from __future__ import annotations

from typing import Any

import pytest

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    ContradictionStatus,
    KnowledgeKind,
    SensitivityLevel,
    TemporalScopeKind,
)
from cmm.cognitive.knowledge import (
    Contradiction,
    Evidence,
    KnowledgeItem,
    TemporalScope,
)
from cmm.cognitive.knowledge_packages import KnowledgePackage
from cmm.domains.errors import DomainKnowledgePackageValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_composition import (
    compose_domain_knowledge_package_schemas,
)
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
)
from cmm.domains.knowledge_package_validation import (
    validate_domain_knowledge_package,
)


def _evidence(evidence_id: str = "evidence:1") -> Evidence:
    return Evidence(
        id=evidence_id,
        resource_id="resource:1",
        fragment="source fragment",
        confidence=Confidence(0.9),
    )


def _item(
    kind: KnowledgeKind,
    *,
    item_id: str = "item:1",
    statement: str = "A statement",
    sensitivity: SensitivityLevel | None = None,
    evidence: tuple[Evidence, ...] = (),
    temporal_scope: TemporalScope | None = None,
    confidence: float = 0.9,
) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=kind,
        confidence=Confidence(confidence),
        sensitivity=sensitivity,
        evidence=evidence,
        temporal_scope=temporal_scope
        if temporal_scope is not None
        else TemporalScope(),
    )


def _fact(**overrides: Any) -> KnowledgeItem:
    return _item(KnowledgeKind.FACT, **overrides)


def _package(**overrides: Any) -> KnowledgePackage:
    data: dict[str, Any] = {
        "id": "knowledge-package:test",
        "objective": "Assess academic progress",
    }
    data.update(overrides)
    return KnowledgePackage(**data)


def _schema(
    *,
    required: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    prohibited: tuple[str, ...] = (),
    policies: tuple[DomainKnowledgePackageFieldPolicy, ...] = (),
    sensitivity: SensitivityLevel = SensitivityLevel.PUBLIC,
    validators: tuple[str, ...] = (),
    domain_slug: str = "university",
) -> DomainKnowledgePackageSchema:
    return DomainKnowledgePackageSchema(
        id=f"knowledge-package-schema:{domain_slug}",
        domain_id=DomainId(domain_slug),
        version="1",
        required_sections=required,
        optional_sections=optional,
        prohibited_sections=prohibited,
        field_policies=policies,
        minimum_sensitivity=sensitivity,
        validator_refs=validators,
    )


# ── Identity, purity and no mutation ──────────────────────────────────────────


def test_validation_accepts_valid_package_and_returns_same_object() -> None:
    package = _package(facts=(_fact(),))
    schema = _schema(required=("objective", "facts"))

    assert validate_domain_knowledge_package(package, schema) is package


def test_validation_does_not_mutate_package() -> None:
    package = _package(facts=(_fact(),))
    schema = _schema(required=("facts",))
    before = package.serialize()

    validate_domain_knowledge_package(package, schema)

    assert package.serialize() == before


def test_validation_is_deterministic() -> None:
    package = _package(facts=(_fact(),))
    schema = _schema(required=("facts",))

    for _ in range(3):
        assert validate_domain_knowledge_package(package, schema) is package


def test_validation_accepts_composed_effective_schema() -> None:
    package = _package(facts=(_fact(),))
    effective = compose_domain_knowledge_package_schemas(
        (_schema(required=("objective",), domain_slug="a"),)
    )

    assert validate_domain_knowledge_package(package, effective) is package


@pytest.mark.parametrize("package", ({"id": "x"}, None, "knowledge-package:test", 42))
def test_validation_rejects_non_canonical_package(package: object) -> None:
    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, _schema())  # type: ignore[arg-type]


@pytest.mark.parametrize("schema", (None, {"id": "x"}, "schema", 42))
def test_validation_rejects_invalid_schema_type(schema: object) -> None:
    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(_package(), schema)  # type: ignore[arg-type]


# ── Structural failures ───────────────────────────────────────────────────────


def test_validation_rejects_prohibited_non_empty_section() -> None:
    package = _package(hypotheses=(_item(KnowledgeKind.HYPOTHESIS),))
    schema = _schema(prohibited=("hypotheses",))

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_allows_empty_prohibited_section() -> None:
    package = _package()
    schema = _schema(prohibited=("hypotheses",))

    assert validate_domain_knowledge_package(package, schema) is package


def test_validation_rejects_missing_required_section() -> None:
    package = _package()
    schema = _schema(required=("facts",))

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_rejects_required_non_empty_field() -> None:
    package = _package()
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts", required_non_empty=True
            ),
        )
    )

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_rejects_minimum_items_underflow() -> None:
    package = _package(facts=(_fact(),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(field_name="facts", minimum_items=2),
        )
    )

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_accepts_minimum_items_satisfied() -> None:
    package = _package(
        facts=(_fact(item_id="item:1"), _fact(item_id="item:2", statement="Second"))
    )
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(field_name="facts", minimum_items=2),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


def test_validation_rejects_disallowed_knowledge_kind() -> None:
    package = _package(facts=(_fact(),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.OBSERVATION,),
            ),
        )
    )

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_accepts_allowed_knowledge_kind() -> None:
    package = _package(facts=(_fact(),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts",
                allowed_knowledge_kinds=(KnowledgeKind.FACT,),
            ),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


# ── Provenance and temporal evidence ──────────────────────────────────────────


def test_validation_rejects_missing_required_provenance() -> None:
    package = _package(facts=(_fact(evidence=()),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts", require_provenance=True
            ),
        )
    )

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_accepts_present_provenance() -> None:
    package = _package(facts=(_fact(evidence=(_evidence(),)),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts", require_provenance=True
            ),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


def test_validation_rejects_missing_required_temporal_evidence() -> None:
    package = _package(facts=(_fact(temporal_scope=TemporalScope()),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts", require_temporal_scope=True
            ),
        )
    )

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_accepts_present_temporal_evidence() -> None:
    package = _package(
        facts=(_fact(temporal_scope=TemporalScope(kind=TemporalScopeKind.CURRENT)),)
    )
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="facts", require_temporal_scope=True
            ),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


# ── Minimum sensitivity matrix ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("floor", "effective", "accepted"),
    [
        (SensitivityLevel.SENSITIVE, SensitivityLevel.INTERNAL, False),
        (SensitivityLevel.SENSITIVE, SensitivityLevel.PERSONAL, False),
        (SensitivityLevel.SENSITIVE, SensitivityLevel.SENSITIVE, True),
        (SensitivityLevel.SENSITIVE, SensitivityLevel.HIGHLY_SENSITIVE, True),
        (SensitivityLevel.SENSITIVE, SensitivityLevel.RESTRICTED, True),
        (SensitivityLevel.PUBLIC, SensitivityLevel.PUBLIC, True),
    ],
)
def test_validation_minimum_sensitivity_matrix(
    floor: SensitivityLevel,
    effective: SensitivityLevel,
    accepted: bool,
) -> None:
    package = _package(facts=(_fact(sensitivity=effective),))
    schema = _schema(sensitivity=floor)

    if accepted:
        assert validate_domain_knowledge_package(package, schema) is package
    else:
        with pytest.raises(DomainKnowledgePackageValidationError):
            validate_domain_knowledge_package(package, schema)


def test_validation_empty_package_is_maximally_sensitive() -> None:
    package = _package()
    schema = _schema(sensitivity=SensitivityLevel.RESTRICTED)

    assert validate_domain_knowledge_package(package, schema) is package


# ── Uncertainty and contradiction preservation ────────────────────────────────


def test_validation_preserves_contradictions_when_required() -> None:
    contradiction = Contradiction(item_a_id="item:a", item_b_id="item:b")
    package = _package(contradictions=(contradiction,))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="contradictions", preserve_contradictions=True
            ),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


def test_validation_does_not_infer_contradiction_erasure_from_absence() -> None:
    package = _package()
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="contradictions", preserve_contradictions=True
            ),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


def test_validation_rejects_resolved_contradiction_when_preserved() -> None:
    contradiction = Contradiction(
        item_a_id="item:a",
        item_b_id="item:b",
        status=ContradictionStatus.RESOLVED,
        preferred_id="item:a",
        preference_reason="Stronger evidence",
    )
    package = _package(contradictions=(contradiction,))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="contradictions", preserve_contradictions=True
            ),
        )
    )

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_does_not_infer_uncertainty_erasure_from_absence() -> None:
    package = _package()
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="unknowns", preserve_uncertainty=True
            ),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


def test_validation_rejects_certainty_collapse_when_uncertainty_preserved() -> None:
    package = _package(inferences=(_item(KnowledgeKind.INFERENCE, confidence=1.0),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="inferences", preserve_uncertainty=True
            ),
        )
    )

    with pytest.raises(DomainKnowledgePackageValidationError):
        validate_domain_knowledge_package(package, schema)


def test_validation_accepts_retained_uncertainty() -> None:
    package = _package(inferences=(_item(KnowledgeKind.INFERENCE, confidence=0.6),))
    schema = _schema(
        policies=(
            DomainKnowledgePackageFieldPolicy(
                field_name="inferences", preserve_uncertainty=True
            ),
        )
    )

    assert validate_domain_knowledge_package(package, schema) is package


# ── Opaque validator references ───────────────────────────────────────────────


def test_validation_never_resolves_opaque_validator_refs() -> None:
    package = _package(facts=(_fact(),))
    schema = _schema(
        required=("facts",),
        validators=("validator:opaque-unregistered", "validator:another"),
    )

    # A schema whose validator refs cannot be resolved anywhere must still
    # validate structurally: Phase 10.49 never looks them up or executes them.
    assert validate_domain_knowledge_package(package, schema) is package
