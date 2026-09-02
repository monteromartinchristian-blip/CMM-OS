"""Tests for Phase 10.40 Domain resource adaptation into Phase 8."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    AdaptationContext,
    AdaptationStatus,
    CandidateKind,
    ExistingResourceAdapter,
    ExtractionContext,
    ExtractionStatus,
    KnowledgeExtractionResult,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    PlainTextKnowledgeExtractor,
    Resource,
    ResourceAdaptationResult,
    ResourceAdapterRegistry,
    ResourceInput,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    ResourceTransformation,
    SensitivityLevel,
)
from cmm.cognitive.contracts import Confidence
from cmm.domains.cognitive_integration_contracts import DomainCognitiveResourceInput
from cmm.domains.enums import DomainResourceResolutionStatus
from cmm.domains.errors import DomainCognitiveIntegrationBlockedError
from cmm.domains.identifiers import DomainId
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
CONTENT_CREATED_AT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
VALID_UNTIL = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc)
LAST_VERIFIED_AT = datetime(2026, 9, 2, 9, 30, tzinfo=timezone.utc)


class _ExactExistingResourceAdapter(ExistingResourceAdapter):
    name = "domain.existing_resource"

    def __init__(self) -> None:
        self.seen_context: AdaptationContext | None = None

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ):
        self.seen_context = context
        return super().adapt(source, context=context)


class _ResolutionDecoyAdapter(ExistingResourceAdapter):
    name = "resolution.decoy"

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ):
        raise AssertionError("registry auto-resolution must not select this adapter")


class _ExactPlainTextKnowledgeExtractor(PlainTextKnowledgeExtractor):
    name = "domain.plain_text"

    def __init__(self) -> None:
        self.seen_context: ExtractionContext | None = None
        self.result: KnowledgeExtractionResult | None = None

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
    ) -> KnowledgeExtractionResult:
        self.seen_context = context
        self.result = super().extract(resource, context=context)
        return self.result


class _ExtractionDecoy(PlainTextKnowledgeExtractor):
    name = "extraction.decoy"

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
    ) -> KnowledgeExtractionResult:
        raise AssertionError("extractor auto-resolution must not select this extractor")


class _FailedExistingResourceAdapter(ExistingResourceAdapter):
    name = "domain.existing_resource"

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult:
        return ResourceAdaptationResult(
            adapter_name=self.name,
            adapter_version=self.version,
            input_id=source.id,
            status=AdaptationStatus.FAILED,
            errors=("adapter failure",),
            created_at=NOW,
        )


class _MissingResourceAdapter(ExistingResourceAdapter):
    name = "domain.existing_resource"

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult:
        return ResourceAdaptationResult(
            adapter_name=self.name,
            adapter_version=self.version,
            input_id=source.id,
            status=AdaptationStatus.COMPLETED,
            resource=None,
            created_at=NOW,
        )


class _MandatoryStatusExtractor(PlainTextKnowledgeExtractor):
    name = "mandatory"

    def __init__(self, status: ExtractionStatus) -> None:
        self.status = status

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
    ) -> KnowledgeExtractionResult:
        return KnowledgeExtractionResult(
            resource_id=resource.id,
            extractor_name=self.name,
            extractor_version=self.version,
            status=self.status,
            errors=(f"mandatory extraction {self.status.value}",),
            created_at=NOW,
        )


def _canonical_resource(content: str = "The plan is stable.") -> Resource:
    return Resource(
        id="resource-1",
        domain="adapter-domain",
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.USER_INPUT,
        content=content,
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="adapter-source-1",
            author="adapter-author",
            retrieved_at=NOW,
            original_location="memory://resource-1",
            checksum="adapter-checksum",
            transformation_history=(
                ResourceTransformation(
                    operation="adapter_normalisation",
                    actor_id="adapter-actor",
                    created_at=NOW,
                ),
            ),
            metadata={"adapter_metadata": "retained"},
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


def _resource_input(
    resource: Resource | None = None,
    *,
    extractor_name: str | None = "plain_text",
) -> DomainCognitiveResourceInput:
    payload = resource or _canonical_resource()
    binding = DomainResourceBinding(
        id="binding-1",
        resource_id="resource-1",
        definition_id="definition-1",
        domain_id=DomainId("health"),
        adapter="domain.existing_resource",
        provenance=("domain-source-1", "domain-source-2"),
        sensitivity=SensitivityLevel.SENSITIVE,
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
            payload=payload,
            sensitivity=binding.sensitivity,
        ),
        extractor_name=extractor_name,
    )


def _registries(
    adapter: _ExactExistingResourceAdapter,
) -> tuple[ResourceAdapterRegistry, KnowledgeExtractorRegistry]:
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(adapter)
    adapter_registry.register(_ResolutionDecoyAdapter(), priority=100)
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())
    return adapter_registry, extractor_registry


def test_resource_uses_binding_adapter_and_exact_adaptation_context() -> None:
    from cmm.domains.cognitive_integration import _adapt_domain_resource

    resource_input = _resource_input()
    selected_adapter = _ExactExistingResourceAdapter()
    adapter_registry, extractor_registry = _registries(selected_adapter)

    resource, _ = _adapt_domain_resource(
        resource_input,
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        actor_id="actor-1",
        session_id="session-1",
        effective_permissions=("resource:read", "resource:infer"),
    )

    assert resource.id == "resource-1"
    assert selected_adapter.seen_context == AdaptationContext(
        actor_id="actor-1",
        target_domain="domain:health",
        permissions=("resource:read", "resource:infer"),
        trace_id="binding-1",
        session_id="session-1",
        timestamp=NOW,
        metadata={"domain_resolution_id": "resolution-1"},
    )


def test_resource_preserves_domain_metadata_in_canonical_phase_8_shapes() -> None:
    from cmm.domains.cognitive_integration import _adapt_domain_resource

    selected_adapter = _ExactExistingResourceAdapter()
    adapter_registry, extractor_registry = _registries(selected_adapter)

    resource, _ = _adapt_domain_resource(
        _resource_input(),
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        actor_id="actor-1",
        session_id="session-1",
        effective_permissions=("resource:read", "resource:infer"),
    )

    assert type(resource) is Resource
    assert resource.sensitivity is SensitivityLevel.SENSITIVE
    assert type(resource.reliability) is Confidence
    assert resource.reliability == Confidence(
        value=0.73,
        source="domain_resource_binding",
        reasons=("binding-1",),
    )
    assert type(resource.temporal_scope) is ResourceTemporalScope
    assert resource.temporal_scope.valid_from == VALID_FROM
    assert resource.temporal_scope.valid_until == VALID_UNTIL
    assert resource.temporal_scope.observed_at == OBSERVED_AT
    assert resource.temporal_scope.last_verified_at == LAST_VERIFIED_AT
    assert resource.temporal_scope.content_created_at == CONTENT_CREATED_AT
    assert resource.temporal_scope.ingested_at == NOW

    assert resource.provenance.source_type is ResourceSourceKind.USER_INPUT
    assert resource.provenance.source_id == "adapter-source-1"
    assert resource.provenance.author == "adapter-author"
    assert resource.provenance.retrieved_at == NOW
    assert resource.provenance.original_location == "memory://resource-1"
    assert resource.provenance.checksum == "adapter-checksum"
    assert resource.provenance.transformation_history[0].operation == (
        "adapter_normalisation"
    )
    assert resource.provenance.metadata == {
        "adapter_metadata": "retained",
        "domain_binding_id": "binding-1",
        "domain_definition_id": "definition-1",
        "domain_provenance": ("domain-source-1", "domain-source-2"),
        "domain_source_priority": 17,
    }


@pytest.mark.parametrize(
    "adapter",
    (_FailedExistingResourceAdapter(), _MissingResourceAdapter()),
    ids=("failed", "missing-resource"),
)
def test_resource_adaptation_fails_closed_without_successful_canonical_resource(
    adapter: ExistingResourceAdapter,
) -> None:
    from cmm.domains.cognitive_integration import _adapt_domain_resource

    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(adapter)
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())

    with pytest.raises(DomainCognitiveIntegrationBlockedError) as error:
        _adapt_domain_resource(
            _resource_input(),
            adapter_registry=adapter_registry,
            extractor_registry=extractor_registry,
            actor_id="actor-1",
            session_id="session-1",
            effective_permissions=("resource:read", "resource:infer"),
        )

    assert error.value.details["binding_id"] == "binding-1"
    assert error.value.details["adapter"] == "domain.existing_resource"


def test_materialisation_uses_requested_extractor_and_canonical_context() -> None:
    from cmm.domains.cognitive_integration import _adapt_domain_resource

    adapter = _ExactExistingResourceAdapter()
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(adapter)
    extractor = _ExactPlainTextKnowledgeExtractor()
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(extractor)
    extractor_registry.register(_ExtractionDecoy(), priority=100)

    resource, bundle = _adapt_domain_resource(
        _resource_input(extractor_name="domain.plain_text"),
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        actor_id="actor-1",
        session_id="session-1",
        effective_permissions=("resource:read", "resource:infer"),
    )

    assert extractor.seen_context is not None
    assert extractor.seen_context.actor_id == "actor-1"
    assert extractor.seen_context.domain == "domain:health"
    assert extractor.seen_context.trace_id == "binding-1"
    assert extractor.seen_context.session_id == "session-1"
    assert bundle.actor_id == "actor-1"
    assert bundle.items
    assert all(type(item) is KnowledgeItem for item in bundle.items)
    assert all(item.status is KnowledgeStatus.UNVERIFIED for item in bundle.items)
    assert all(item.kind is not KnowledgeKind.FACT for item in bundle.items)
    assert all(item.resource_id == resource.id for item in bundle.items)
    assert all(
        item.evidence[0].resource_provenance_id == "adapter-source-1"
        for item in bundle.items
    )


@pytest.mark.parametrize(
    "status",
    (ExtractionStatus.FAILED, ExtractionStatus.UNSUPPORTED),
)
def test_material_extraction_fails_closed_for_mandatory_failure(
    status: ExtractionStatus,
) -> None:
    from cmm.domains.cognitive_integration import _adapt_domain_resource

    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(_ExactExistingResourceAdapter())
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(_MandatoryStatusExtractor(status))

    with pytest.raises(DomainCognitiveIntegrationBlockedError) as error:
        _adapt_domain_resource(
            _resource_input(extractor_name="mandatory"),
            adapter_registry=adapter_registry,
            extractor_registry=extractor_registry,
            actor_id="actor-1",
            session_id="session-1",
            effective_permissions=("resource:read", "resource:infer"),
        )

    assert error.value.details == {
        "binding_id": "binding-1",
        "extractor": "mandatory",
        "status": status.value,
    }


def test_question_candidate_follows_canonical_materialisation_path() -> None:
    from cmm.domains.cognitive_integration import _adapt_domain_resource

    question = "What should happen next?"
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(_ExactExistingResourceAdapter())
    extractor = _ExactPlainTextKnowledgeExtractor()
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(extractor)

    _, bundle = _adapt_domain_resource(
        _resource_input(
            _canonical_resource(question),
            extractor_name="domain.plain_text",
        ),
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        actor_id="actor-1",
        session_id="session-1",
        effective_permissions=("resource:read", "resource:infer"),
    )

    assert extractor.result is not None
    question_candidates = [
        candidate
        for candidate in extractor.result.candidates
        if candidate.kind is CandidateKind.QUESTION
    ]
    assert [candidate.value for candidate in question_candidates] == [question]
    question_items = [
        item for item in bundle.items if item.kind is KnowledgeKind.QUESTION
    ]
    assert [item.statement for item in question_items] == [question]
    assert bundle.open_questions == (question,)
