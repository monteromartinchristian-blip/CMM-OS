"""Phase 10.52 — Mental Health Knowledge Package schema tests.

The schema narrows the canonical Phase 8 ``KnowledgePackage`` through the real
``KnowledgePackageBuilder`` path and keeps the approved Mental Health context
reachable, without introducing a second builder or a knowledge store.
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
from cmm.domains.mental_health.knowledge_package import (
    build_mental_health_knowledge_package_schema,
)


def test_schema_identity_and_minimum_sensitivity():
    schema = build_mental_health_knowledge_package_schema()
    assert isinstance(schema, DomainKnowledgePackageSchema)
    assert schema.id == "knowledge-package-schema:mental-health"
    assert str(schema.domain_id) == "domain:mental-health"
    assert schema.version == "1"
    assert schema.required_sections == ("objective",)
    assert schema.minimum_sensitivity.name == "SENSITIVE"


def test_schema_keeps_approved_context_reachable():
    schema = build_mental_health_knowledge_package_schema()
    by_field = {policy.field_name: policy for policy in schema.field_policies}
    # Facts and observations stay provenance-bound.
    assert by_field["facts"].allowed_knowledge_kinds == (KnowledgeKind.FACT,)
    assert by_field["facts"].require_provenance is True
    assert by_field["observations"].allowed_knowledge_kinds == (
        KnowledgeKind.OBSERVATION,
    )
    # Interpretations, hypotheses and contradictions are never collapsed.
    assert by_field["inferences"].preserve_uncertainty is True
    assert by_field["hypotheses"].preserve_uncertainty is True
    assert by_field["contradictions"].preserve_contradictions is True


def test_schema_declares_no_unbuildable_hard_requirement():
    schema = build_mental_health_knowledge_package_schema()
    for policy in schema.field_policies:
        assert policy.required_non_empty is not True
        assert policy.minimum_items is None


def test_real_builder_path_produces_a_valid_package():
    store = InMemoryKnowledgeStore()
    InMemoryKnowledgeStore.save_item(
        store,
        KnowledgeItem(
            id="mh-item-1",
            statement="The user reported feeling lonely this week.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.6, source="user-report"),
        ),
    )
    builder = KnowledgePackageBuilder(store)
    request = KnowledgePackageRequest(
        objective="review ordinary emotional context",
        profile="MentalHealthProfile",
        domain="domain:mental-health",
        session_id="session-mh-1",
        permission_context={"actor_id": "user-1", "effective_permissions": ()},
    )
    package = builder.build(request)
    assert package is not None
    assert package.objective == "review ordinary emotional context"

    schema = build_mental_health_knowledge_package_schema()
    # The canonical validator accepts the real package against the schema.
    validate_domain_knowledge_package(package, schema)


def test_no_second_builder_or_store_is_introduced():
    import cmm.domains.mental_health.knowledge_package as module

    source = module.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    assert "KnowledgePackageBuilder(" not in text
    assert "class KnowledgePackageBuilder" not in text
    assert "Store(" not in text
