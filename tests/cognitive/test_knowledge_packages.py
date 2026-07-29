from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from inspect import getsourcefile
from pathlib import Path

import pytest

from cmm.cognitive import (
    Confidence,
    Contradiction,
    ContradictionSeverity,
    InMemoryKnowledgeStore,
    InvalidKnowledgePackageError,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    KnowledgePackageBuilder,
    KnowledgePackageRequest,
    Resource,
    ResourceKind,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


def item(
    item_id: str, statement: str, kind: KnowledgeKind, resource_id: str | None = None
) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=kind,
        confidence=Confidence(value=0.8),
        created_at=NOW,
        updated_at=NOW,
        resource_id=resource_id,
    )


def resource(resource_id: str = "resource:health") -> Resource:
    return Resource(
        id=resource_id,
        domain="health",
        kind=ResourceKind.NOTE,
        source=ResourceSourceKind.USER_INPUT,
        content="patient notes",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="user:1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(value=0.9),
        temporal_scope=ResourceTemporalScope(ingested_at=NOW),
        created_at=NOW,
        updated_at=NOW,
    )


def test_minimal_package_is_immutable_and_serializable() -> None:
    package = KnowledgePackage(
        id="knowledge-package-123",
        objective="Assess health",
        created_at=NOW,
    )

    assert package.schema_version == 1
    assert package.facts == ()
    assert package.serialize() == package.to_dict()
    assert KnowledgePackage.from_mapping(package.serialize()) == package
    with pytest.raises(AttributeError):
        package.objective = "changed"  # type: ignore[misc]


def test_package_round_trip_is_deterministic_and_preserves_epistemology() -> None:
    facts = (item("fact:1", "Patient has fever", KnowledgeKind.FACT),)
    observations = (
        item("observation:1", "Temperature is 38C", KnowledgeKind.OBSERVATION),
    )
    inferences = (
        item("inference:1", "Infection is possible", KnowledgeKind.INFERENCE),
    )
    hypotheses = (item("hypothesis:1", "Viral infection", KnowledgeKind.HYPOTHESIS),)
    package = KnowledgePackage(
        id="knowledge-package-123",
        objective="Assess health",
        facts=facts,
        observations=observations,
        inferences=inferences,
        hypotheses=hypotheses,
        resources=(resource(),),
        provenance=("resource:health",),
        created_at=NOW,
        valid_until=NOW + timedelta(days=1),
    )

    first = package.serialize()
    second = KnowledgePackage.from_dict(first).serialize()
    assert first == second
    assert set(first["facts"][0]) >= {"id", "kind", "confidence"}
    assert first["observations"][0]["kind"] == "observation"
    assert first["inferences"][0]["kind"] == "inference"
    assert first["hypotheses"][0]["kind"] == "hypothesis"
    assert first["valid_until"] == (NOW + timedelta(days=1)).isoformat()


def test_package_accepts_existing_bundle_items_and_preserves_other_kinds() -> None:
    decision = item("decision:1", "Use treatment", KnowledgeKind.DECISION)
    bundle = KnowledgeBundle(items=(decision,), created_at=NOW)
    package = KnowledgePackage(
        id="p", objective="treatment", other_knowledge=bundle.items, created_at=NOW
    )
    assert package.other_knowledge == (decision,)
    assert KnowledgePackage.from_mapping(package.serialize()).other_knowledge == (
        decision,
    )


def test_package_rejects_invalid_dates_versions_and_duplicate_ids() -> None:
    with pytest.raises(InvalidKnowledgePackageError):
        KnowledgePackage(id="p", objective="x", schema_version=999)
    with pytest.raises(InvalidKnowledgePackageError):
        KnowledgePackage(
            id="p",
            objective="x",
            created_at=NOW,
            valid_until=NOW - timedelta(seconds=1),
        )
    duplicate = item("same", "one", KnowledgeKind.FACT)
    with pytest.raises(InvalidKnowledgePackageError):
        KnowledgePackage(id="p", objective="x", facts=(duplicate, duplicate))
    with pytest.raises(InvalidKnowledgePackageError):
        KnowledgePackage.from_mapping(
            {"id": "p", "objective": "x", "schema_version": 2}
        )


@pytest.mark.parametrize(
    ("field_name", "wrong_item"),
    [
        ("facts", item("wrong-fact", "hypothesis", KnowledgeKind.HYPOTHESIS)),
        ("observations", item("wrong-observation", "fact", KnowledgeKind.FACT)),
        ("inferences", item("wrong-inference", "fact", KnowledgeKind.FACT)),
        ("hypotheses", item("wrong-hypothesis", "fact", KnowledgeKind.FACT)),
        ("other_knowledge", item("wrong-other", "fact", KnowledgeKind.FACT)),
    ],
)
def test_package_rejects_incorrect_epistemic_classification(
    field_name: str, wrong_item: KnowledgeItem
) -> None:
    with pytest.raises(InvalidKnowledgePackageError):
        KnowledgePackage(id="p", objective="x", **{field_name: (wrong_item,)})


def test_builder_selects_relevant_items_categories_contradictions_and_limits() -> None:
    store = InMemoryKnowledgeStore()
    relevant_fact = item("fact:health", "health fever", KnowledgeKind.FACT)
    relevant_observation = item(
        "obs:health", "health temperature", KnowledgeKind.OBSERVATION
    )
    irrelevant = item("fact:other", "finance shares", KnowledgeKind.FACT)
    for value in (relevant_fact, relevant_observation, irrelevant):
        store.save_item(value)
    contradiction = Contradiction(
        id="contradiction:health",
        item_a_id=relevant_fact.id,
        item_b_id=relevant_observation.id,
        severity=ContradictionSeverity.HIGH,
        created_at=NOW,
    )
    store.save_contradiction(contradiction)

    package = KnowledgePackageBuilder(store).build(
        KnowledgePackageRequest(
            objective="health",
            max_items=1,
            include_contradictions=True,
            required_categories=(KnowledgeKind.FACT,),
        )
    )
    assert len(package.facts) == 1
    assert package.observations == ()
    assert package.contradictions == (contradiction,)
    assert irrelevant.id not in {entry.id for entry in package.facts}


def test_builder_provenance_and_serialization_are_deterministic() -> None:
    store = InMemoryKnowledgeStore()
    first = item("fact:a", "health a", KnowledgeKind.FACT)
    second = item("fact:b", "health b", KnowledgeKind.FACT)
    store.save_item(first)
    store.save_item(second)
    request = KnowledgePackageRequest(objective="health")
    builder = KnowledgePackageBuilder(store)
    package_a = builder.build(request)
    package_b = builder.build(request)
    assert package_a.provenance == package_b.provenance == ("fact:a", "fact:b")
    assert package_a.serialize() == package_b.serialize()


def test_builder_applies_resource_and_contradiction_limits() -> None:
    store = InMemoryKnowledgeStore()
    source = resource()
    value = item("fact:resource", "health", KnowledgeKind.FACT, resource_id=source.id)
    other = item("fact:other", "health other", KnowledgeKind.FACT)
    store.save_item(value)
    store.save_item(other)
    contradiction = Contradiction(
        item_a_id=value.id, item_b_id=other.id, created_at=NOW
    )
    store.save_contradiction(contradiction)
    builder = KnowledgePackageBuilder(store, resources=(source,))
    limited = builder.build(
        KnowledgePackageRequest(
            objective="health", max_resources=0, max_contradictions=0
        )
    )
    assert limited.resources == ()
    assert limited.contradictions == ()
    included = builder.build(
        KnowledgePackageRequest(objective="health", max_resources=1)
    )
    assert included.resources == (source,)


def test_request_explicit_context_fields_are_limited_and_metadata_is_not_semantic() -> (
    None
):
    store = InMemoryKnowledgeStore()
    store.save_item(item("fact:1", "health", KnowledgeKind.FACT))
    request = KnowledgePackageRequest(
        objective="health",
        missing_information=("lab result",),
        relevant_memory=("m1", "m2"),
        prior_reasoning=("r1", "r2"),
        max_memory=1,
        max_prior_reasoning=1,
        metadata={
            "missing_information": ("wrong",),
            "relevant_memory": ("wrong",),
            "prior_reasoning": ("wrong",),
        },
    )
    package = KnowledgePackageBuilder(store).build(request)
    assert package.missing_information == ("lab result",)
    assert package.relevant_memory == ("m1",)
    assert package.prior_reasoning == ("r1",)
    excluded = KnowledgePackageBuilder(store).build(
        KnowledgePackageRequest(
            objective="health", prior_reasoning=("r1",), include_prior_reasoning=False
        )
    )
    assert excluded.prior_reasoning == ()


def test_request_privacy_is_separate_from_permission_context() -> None:
    store = InMemoryKnowledgeStore()
    store.save_item(item("fact:1", "health", KnowledgeKind.FACT))
    request = KnowledgePackageRequest(
        objective="health",
        permission_context={"actor_id": "actor:1"},
        privacy={"classification": "internal"},
    )
    package = KnowledgePackageBuilder(store).build(request)
    assert dict(package.privacy) == {"classification": "internal"}
    assert dict(package.privacy) != dict(request.permission_context)


def test_builder_policy_requires_two_arguments() -> None:
    store = InMemoryKnowledgeStore()
    store.save_item(item("fact:1", "health", KnowledgeKind.FACT))
    with pytest.raises(TypeError):
        KnowledgePackageBuilder(store, inclusion_policy=lambda candidate: True).build(
            KnowledgePackageRequest(objective="health")
        )


def test_package_id_is_stable_safe_and_distinguishes_requests() -> None:
    store = InMemoryKnowledgeStore()
    store.save_item(item("fact:1", "health", KnowledgeKind.FACT))
    builder = KnowledgePackageBuilder(store)
    base = builder.build(
        KnowledgePackageRequest(objective="Health / status", profile="medical")
    )
    same = builder.build(
        KnowledgePackageRequest(objective=" health / status ", profile="medical")
    )
    different = builder.build(
        KnowledgePackageRequest(objective="Health / status", profile="legal")
    )
    assert base.id == same.id
    assert base.id != different.id
    assert " " not in base.id
    assert "/" not in base.id


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "p", "objective": "x", "facts": "not-a-list"},
        {"id": "p", "objective": "x", "facts": {"id": "not-a-list"}},
        {"id": "p", "objective": "x", "resources": "not-a-list"},
        {"id": "p", "objective": "x", "schema_version": 1, "hypotheses": "not-a-list"},
    ],
)
def test_package_rejects_non_sequence_payload_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(InvalidKnowledgePackageError):
        KnowledgePackage.from_mapping(payload)


def test_builder_excludes_unauthorized_content_and_can_return_empty_package() -> None:
    store = InMemoryKnowledgeStore()
    private = item("private", "health private", KnowledgeKind.FACT)
    store.save_item(private)
    denied = KnowledgePackageBuilder(
        store, inclusion_policy=lambda candidate, context: False
    ).build(KnowledgePackageRequest(objective="health"))
    assert denied.facts == ()
    assert denied.resources == ()

    empty = KnowledgePackageBuilder(store).build(
        KnowledgePackageRequest(objective="unrelated topic")
    )
    assert empty.facts == ()
    assert empty.contradictions == ()


def test_builder_supports_existing_bundle_and_query_without_provider_imports() -> None:
    store = InMemoryKnowledgeStore()
    value = item("fact:1", "objective", KnowledgeKind.FACT)
    store.save_item(value)
    package = KnowledgePackageBuilder(store).build(
        KnowledgePackageRequest(objective="objective", query={"limit": 1})
    )
    assert package.facts == (value,)


def test_package_module_has_no_provider_or_routing_imports() -> None:
    source_path = getsourcefile(KnowledgePackageBuilder)
    assert source_path is not None
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
    imported_modules = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        "provider" in module or "routing" in module for module in imported_modules
    )
