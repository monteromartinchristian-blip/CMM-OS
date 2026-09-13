"""Phase 10.53 — Neurodivergence Knowledge Package schema tests.

The schema narrows the canonical Phase 8 ``KnowledgePackage`` through the real
``KnowledgePackageBuilder`` path, keeps the approved Neurodivergence context
reachable (objective, developmental timeline, source/period evidence, confirmed
information, in-evaluation information, working hypotheses, contradictory or
insufficient evidence, functional observations, authorized supporting-domain
projections, privacy/permission evidence), and never introduces a second
builder or a knowledge store.

Uncertainty, contradictions, provenance and the SENSITIVE floor are preserved.
"""

from __future__ import annotations

from cmm.cognitive import (
    Confidence,
    InMemoryKnowledgeStore,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackageRequest,
)
from cmm.cognitive.knowledge_packages import KnowledgePackageBuilder
from cmm.domains.knowledge_package_contracts import DomainKnowledgePackageSchema
from cmm.domains.knowledge_package_validation import validate_domain_knowledge_package
from cmm.domains.neurodivergence.knowledge_package import (
    build_neurodivergence_knowledge_package_schema,
)


def test_schema_identity_and_minimum_sensitivity():
    schema = build_neurodivergence_knowledge_package_schema()

    assert isinstance(schema, DomainKnowledgePackageSchema)
    assert schema.id == "knowledge-package-schema:neurodivergence"
    assert str(schema.domain_id) == "domain:neurodivergence"
    assert schema.version == "1"
    assert schema.required_sections == ("objective",)
    assert schema.minimum_sensitivity.name == "SENSITIVE"


def test_schema_keeps_the_approved_reasoning_context_reachable():
    schema = build_neurodivergence_knowledge_package_schema()
    by_field = {policy.field_name: policy for policy in schema.field_policies}

    # Confirmed information and observations stay provenance-bound: each item
    # must retain canonical evidence.
    for field in ("facts", "observations"):
        assert by_field[field].require_provenance is True, field

    # Working hypotheses and model interpretation keep explicit uncertainty and
    # are never narrowed to a fact kind.
    for field in ("hypotheses", "inferences", "other_knowledge"):
        assert by_field[field].preserve_uncertainty is True, field

    # Competing evidence stays visible.
    assert by_field["contradictions"].preserve_contradictions is True

    # The remaining approved context is made reachable through canonical
    # package sections (declared in optional_sections and mapped in metadata):
    # the developmental timeline, evidence by source and period, confirmed
    # information, in-evaluation information, contradictory or insufficient
    # evidence, functional observations, authorized supporting-domain
    # projections and privacy/permission evidence.
    assert "timeline" in schema.optional_sections
    assert "resources" in schema.optional_sections
    assert "privacy" in schema.optional_sections


def test_no_unbuildable_hard_requirement_is_declared():
    """Evidence requirements only bind knowledge-item category fields."""
    from cmm.domains.knowledge_package_contracts import (
        KNOWLEDGE_ITEM_CATEGORY_FIELDS,
    )

    schema = build_neurodivergence_knowledge_package_schema()

    for policy in schema.field_policies:
        if policy.require_provenance or policy.require_temporal_scope:
            assert policy.field_name in KNOWLEDGE_ITEM_CATEGORY_FIELDS, (
                policy.field_name
            )
        if policy.allowed_knowledge_kinds:
            assert policy.field_name in KNOWLEDGE_ITEM_CATEGORY_FIELDS, (
                policy.field_name
            )


def test_declared_fields_name_only_canonical_package_fields():
    from cmm.domains.knowledge_package_contracts import (
        CANONICAL_KNOWLEDGE_PACKAGE_FIELDS,
    )

    schema = build_neurodivergence_knowledge_package_schema()

    for policy in schema.field_policies:
        assert policy.field_name in CANONICAL_KNOWLEDGE_PACKAGE_FIELDS, (
            policy.field_name
        )


def test_domain_specific_sections_are_encoded_as_section_semantics():
    """Domain sections map onto canonical package sections, not new fields."""
    from cmm.domains.knowledge_package_contracts import (
        CANONICAL_KNOWLEDGE_PACKAGE_FIELDS,
    )
    from cmm.domains.neurodivergence.knowledge_package import (
        NEURODIVERGENCE_KNOWLEDGE_PACKAGE_SECTIONS,
    )

    schema = build_neurodivergence_knowledge_package_schema()
    mapping = NEURODIVERGENCE_KNOWLEDGE_PACKAGE_SECTIONS

    for section in (
        "active_exploratory_objective",
        "developmental_timeline",
        "evidence_by_source_and_period",
        "confirmed_information",
        "in_evaluation_information",
        "working_hypotheses",
        "contradictory_or_insufficient_evidence",
        "functional_observations",
        "supporting_domain_projections",
        "privacy_and_permission_evidence",
    ):
        assert section in mapping, section

    reachable = set(schema.required_sections) | set(schema.optional_sections)
    for section, canonical_field in mapping.items():
        assert canonical_field in CANONICAL_KNOWLEDGE_PACKAGE_FIELDS, section
        assert canonical_field in reachable, section

    # Every declared section is a canonical package section.
    for section in reachable:
        assert section in CANONICAL_KNOWLEDGE_PACKAGE_FIELDS, section
    assert schema.required_sections == ("objective",)
    # A canonical first-party schema stays declarative and metadata-free.
    assert schema.validator_refs == ()
    assert schema.metadata == {}


def test_schema_declares_no_unbuildable_hard_requirement():
    schema = build_neurodivergence_knowledge_package_schema()

    for policy in schema.field_policies:
        assert policy.required_non_empty is not True
        assert policy.minimum_items is None


def test_fact_fields_never_accept_an_inferential_kind():
    schema = build_neurodivergence_knowledge_package_schema()
    by_field = {policy.field_name: policy for policy in schema.field_policies}

    assert by_field["facts"].allowed_knowledge_kinds == (KnowledgeKind.FACT,)
    assert by_field["observations"].allowed_knowledge_kinds == (
        KnowledgeKind.OBSERVATION,
    )
    # A hypothesis field may never be narrowed to a fact kind.
    assert KnowledgeKind.FACT not in by_field["hypotheses"].allowed_knowledge_kinds


def test_no_second_global_knowledge_kind_is_introduced():
    from cmm.cognitive.enums import KnowledgeKind

    schema = build_neurodivergence_knowledge_package_schema()

    for policy in schema.field_policies:
        for kind in policy.allowed_knowledge_kinds:
            assert isinstance(kind, KnowledgeKind), kind


def test_real_builder_path_produces_a_valid_package():
    store = InMemoryKnowledgeStore()
    InMemoryKnowledgeStore.save_item(
        store,
        KnowledgeItem(
            id="nd-item-1",
            statement="The user reported lifelong sensory sensitivity.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.6, source="user-report"),
        ),
    )
    builder = KnowledgePackageBuilder(store)
    request = KnowledgePackageRequest(
        objective="organize developmental evidence for an assessment",
        profile="NeurodivergenceProfile",
        domain="domain:neurodivergence",
        session_id="session-nd-1",
        permission_context={"actor_id": "user-1", "effective_permissions": ()},
    )
    package = builder.build(request)
    assert package is not None
    assert package.objective == "organize developmental evidence for an assessment"

    schema = build_neurodivergence_knowledge_package_schema()
    # The canonical validator accepts the real package against the schema.
    validate_domain_knowledge_package(package, schema)


def test_no_second_builder_or_store_is_introduced():
    import cmm.domains.neurodivergence.knowledge_package as module

    with open(module.__file__, encoding="utf-8") as handle:
        text = handle.read()

    assert "KnowledgePackageBuilder(" not in text
    assert "class KnowledgePackageBuilder" not in text
    assert "Store(" not in text
