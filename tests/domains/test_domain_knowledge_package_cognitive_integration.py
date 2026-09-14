"""Phase 10.49 – optional schema validation inside the canonical cognitive integrator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    CognitiveValidator,
    Confidence,
    ExistingResourceAdapter,
    InMemoryKnowledgeStore,
    InMemoryReasoningRuleRegistry,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    PlainTextKnowledgeExtractor,
    Resource,
    ResourceAdapterRegistry,
    ResourceInput,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    SensitivityLevel,
)
from cmm.domains import cognitive_integration as cognitive_integration_module
from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
    DomainCognitiveResourceInput,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainReasoningDepth,
    DomainResourceResolutionStatus,
)
from cmm.domains.errors import (
    DomainCognitiveIntegrationContractError,
    DomainKnowledgePackageValidationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_composition import (
    compose_domain_knowledge_package_schemas,
)
from cmm.domains.knowledge_package_contracts import (
    DomainKnowledgePackageFieldPolicy,
    DomainKnowledgePackageSchema,
)
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
    ResolvedDomainProfile,
)
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)
from cmm.domains.rule_execution import DefaultDomainRuleExecutor
from cmm.domains.rule_selection import DefaultDomainRuleSelector

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
CONTENT_CREATED_AT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
VALID_UNTIL = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc)
LAST_VERIFIED_AT = datetime(2026, 9, 2, 9, 30, tzinfo=timezone.utc)


# ── Canonical fixtures ────────────────────────────────────────────────────────


def _canonical_resource(content: str = "The plan is stable.") -> Resource:
    return Resource(
        id="resource-1",
        domain="domain:health",
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.USER_INPUT,
        content=content,
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="source-1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(0.99, source="adapter"),
        temporal_scope=ResourceTemporalScope(
            content_created_at=CONTENT_CREATED_AT,
            observed_at=CONTENT_CREATED_AT,
            ingested_at=NOW,
        ),
        sensitivity=SensitivityLevel.INTERNAL,
        permissions=(
            ResourcePermission(
                allowed_operations=(
                    ResourcePermissionOperation.READ,
                    ResourcePermissionOperation.INFER,
                )
            ),
        ),
        created_at=NOW,
        updated_at=NOW,
    )


def _resource_input() -> DomainCognitiveResourceInput:
    binding = DomainResourceBinding(
        id="binding-1",
        resource_id="resource-1",
        definition_id="definition-1",
        domain_id=DomainId("health"),
        adapter="existing_resource",
        provenance=("domain-source-1",),
        sensitivity=SensitivityLevel.INTERNAL,
        temporal_scope={
            "valid_from": VALID_FROM,
            "valid_until": VALID_UNTIL,
            "observed_at": OBSERVED_AT,
            "last_verified_at": LAST_VERIFIED_AT,
        },
        source_priority=17,
        reliability=0.73,
    )
    resolution = DomainResourceResolution(
        id="resolution-1",
        resource_id=binding.resource_id,
        status=DomainResourceResolutionStatus.RESOLVED,
        trace_id="resolution-trace-1",
        resolved_at=NOW,
        bindings=(binding,),
    )
    return DomainCognitiveResourceInput(
        resolution=resolution,
        binding=binding,
        source=ResourceInput(
            id=binding.resource_id,
            source_kind=ResourceSourceKind.USER_INPUT,
            payload=_canonical_resource(),
            sensitivity=binding.sensitivity,
        ),
        extractor_name="plain_text",
    )


def _store() -> InMemoryKnowledgeStore:
    store = InMemoryKnowledgeStore()
    InMemoryKnowledgeStore.save_item(
        store,
        KnowledgeItem(
            id="integration-provenance-item",
            statement="Review canonical health information.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.91, source="existing-evidence"),
            resource_id="resource-1",
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    return store


class _SpyRuleSelector(DefaultDomainRuleSelector):
    def __init__(self) -> None:
        super().__init__(clock=lambda: NOW)
        self.calls = 0

    def select(self, *args: object, **kwargs: object):
        self.calls += 1
        return super().select(*args, **kwargs)  # type: ignore[arg-type]


def _integrator(
    store: InMemoryKnowledgeStore,
    selector: _SpyRuleSelector,
) -> DefaultDomainCognitiveIntegrator:
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(ExistingResourceAdapter())
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())
    return DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=store,
        rule_registry=InMemoryReasoningRuleRegistry(),
        cognitive_validator=CognitiveValidator(),
        rule_selector=selector,
        rule_executor=DefaultDomainRuleExecutor(clock=lambda: NOW),
        clock=lambda: NOW,
    )


def _request(**overrides: object) -> DomainCognitiveIntegrationRequest:
    composition = DomainComposition(
        id="composition-1",
        resolution_id="resolution-result-1",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        composed_at=NOW,
    )
    profile = ResolvedDomainProfile(
        id="profile-1",
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        profile_names=("HealthProfile",),
        required_rules=(),
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=None,
        priority_resource_kinds=(),
        prohibited_resource_kinds=(),
        minimum_confidence=0.8,
        reasoning_depth=DomainReasoningDepth.DEEP,
        allowed_inferences=None,
        prohibited_inferences=(),
        maximum_questions=3,
        escalation_rules=(),
        prohibited_actions=(),
        question_policy=DomainQuestionPolicy(),
        presentation_policy=DomainPresentationPolicy(),
        memory_policy=DomainMemoryPolicy(),
        temporal_policy=DomainTemporalPolicy(),
        production_policy=DomainProductionPolicy(),
        permissions=None,
        modifications=(),
        trace_id="profile-trace-1",
        resolved_at=NOW,
    )
    data: dict[str, object] = {
        "request_id": "request-1",
        "resolution_context_id": "resolution-context-1",
        "resolution_result_id": "resolution-result-1",
        "objective": "Review health information",
        "composition": composition,
        "profile": profile,
        "resources": (_resource_input(),),
        "actor_id": "actor-1",
        "session_id": "session-1",
        "effective_permissions": ("resource:read", "resource:infer"),
    }
    data.update(overrides)
    return DomainCognitiveIntegrationRequest(**data)  # type: ignore[arg-type]


def _store_state(store: InMemoryKnowledgeStore) -> dict[str, object]:
    return {
        "items": [item.serialize() for item in store.list_items()],
        "evidence": [evidence.serialize() for evidence in store.list_evidence()],
        "relations": [relation.serialize() for relation in store.list_relations()],
        "contradictions": [
            contradiction.serialize() for contradiction in store.list_contradictions()
        ],
        "bundles": [bundle.serialize() for bundle in store.list_bundles()],
    }


def _schema(
    *,
    required: tuple[str, ...] = (),
    prohibited: tuple[str, ...] = (),
    policies: tuple[DomainKnowledgePackageFieldPolicy, ...] = (),
    domain_slug: str = "health",
) -> DomainKnowledgePackageSchema:
    return DomainKnowledgePackageSchema(
        id=f"knowledge-package-schema:{domain_slug}",
        domain_id=DomainId(domain_slug),
        version="1",
        required_sections=required,
        prohibited_sections=prohibited,
        field_policies=policies,
    )


# ── Request contract ──────────────────────────────────────────────────────────


def test_request_defaults_knowledge_package_schema_to_none() -> None:
    assert _request().knowledge_package_schema is None


def test_request_accepts_domain_schema() -> None:
    schema = _schema(required=("objective",))

    assert _request(knowledge_package_schema=schema).knowledge_package_schema is schema


def test_request_accepts_effective_schema() -> None:
    effective = compose_domain_knowledge_package_schemas((_schema(),))

    assert (
        _request(knowledge_package_schema=effective).knowledge_package_schema
        is effective
    )


@pytest.mark.parametrize("value", ("schema", {"id": "x"}, 42, ["schema"]))
def test_request_rejects_invalid_schema_type(value: object) -> None:
    with pytest.raises(DomainCognitiveIntegrationContractError):
        _request(knowledge_package_schema=value)


# ── Integrator seam ───────────────────────────────────────────────────────────


def test_integrator_validates_after_canonical_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}
    original = cognitive_integration_module.validate_domain_knowledge_package

    def _spy(package: object, schema: object) -> object:
        seen["package"] = package
        seen["schema"] = schema
        return original(package, schema)  # type: ignore[arg-type]

    monkeypatch.setattr(
        cognitive_integration_module, "validate_domain_knowledge_package", _spy
    )

    store = _store()
    selector = _SpyRuleSelector()
    schema = _schema(required=("objective",))
    result = _integrator(store, selector).integrate(
        _request(knowledge_package_schema=schema)
    )

    assert type(result.knowledge_package) is KnowledgePackage
    assert seen["package"] is result.knowledge_package
    assert seen["schema"] is schema
    assert selector.calls == 1


def test_integrator_without_schema_still_uses_canonical_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    original = cognitive_integration_module.validate_domain_knowledge_package

    def _spy(package: object, schema: object) -> object:
        calls["count"] += 1
        return original(package, schema)  # type: ignore[arg-type]

    monkeypatch.setattr(
        cognitive_integration_module, "validate_domain_knowledge_package", _spy
    )

    store = _store()
    result = _integrator(store, _SpyRuleSelector()).integrate(_request())

    assert type(result.knowledge_package) is KnowledgePackage
    assert calls["count"] == 0


def test_integrator_fails_closed_and_leaves_store_unchanged() -> None:
    store = _store()
    before = _store_state(store)
    selector = _SpyRuleSelector()
    schema = _schema(required=("hypotheses",))

    with pytest.raises(DomainKnowledgePackageValidationError):
        _integrator(store, selector).integrate(
            _request(knowledge_package_schema=schema)
        )

    assert _store_state(store) == before
    assert selector.calls == 0


def test_integrator_returns_canonical_trace_references_with_schema() -> None:
    store = _store()
    schema = _schema(required=("objective",))
    result = _integrator(store, _SpyRuleSelector()).integrate(
        _request(knowledge_package_schema=schema)
    )

    assert result.trace_references.knowledge_package_ids == (
        result.knowledge_package.id,
    )
    assert result.request_id == "request-1"
