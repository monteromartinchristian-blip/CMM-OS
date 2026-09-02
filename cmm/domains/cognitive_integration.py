"""Canonical Cognitive Layer integration for resolved Domain resources."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol, runtime_checkable

from cmm.cognitive import (
    AdaptationContext,
    Confidence,
    ExtractionContext,
    ExtractionStatus,
    KnowledgeBundle,
    KnowledgeExtractorRegistry,
    Resource,
    ResourceAdapterRegistry,
    materialise_result,
)
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
    DomainCognitiveIntegrationResult,
    DomainCognitiveResourceInput,
)
from cmm.domains.errors import DomainCognitiveIntegrationBlockedError


@runtime_checkable
class DomainCognitiveIntegrator(Protocol):
    """Protocol for the Domain-to-Cognitive orchestration boundary."""

    def integrate(
        self,
        request: DomainCognitiveIntegrationRequest,
    ) -> DomainCognitiveIntegrationResult: ...


def _adapt_domain_resource(
    resource_input: DomainCognitiveResourceInput,
    *,
    adapter_registry: ResourceAdapterRegistry,
    extractor_registry: KnowledgeExtractorRegistry,
    actor_id: str | None,
    session_id: str | None,
    effective_permissions: tuple[str, ...],
) -> tuple[Resource, KnowledgeBundle]:
    binding = resource_input.binding
    resolution = resource_input.resolution
    adapter = adapter_registry.get(binding.adapter)
    adaptation = adapter.adapt(
        resource_input.source,
        context=AdaptationContext(
            actor_id=actor_id,
            target_domain=str(binding.domain_id),
            permissions=effective_permissions,
            trace_id=binding.id,
            session_id=session_id,
            timestamp=resolution.resolved_at,
            metadata={"domain_resolution_id": resolution.id},
        ),
    )
    if not adaptation.successful or adaptation.resource is None:
        raise DomainCognitiveIntegrationBlockedError(
            "Domain resource adaptation did not produce a canonical Resource",
            details={
                "binding_id": binding.id,
                "adapter": binding.adapter,
                "status": adaptation.status.value,
            },
        )

    resource = adaptation.resource
    resource = replace(
        resource,
        sensitivity=binding.sensitivity,
        reliability=Confidence(
            value=binding.reliability,
            source="domain_resource_binding",
            reasons=(binding.id,),
        ),
        temporal_scope=replace(
            resource.temporal_scope,
            **dict(binding.temporal_scope),
        ),
        provenance=replace(
            resource.provenance,
            metadata={
                **resource.provenance.metadata,
                "domain_binding_id": binding.id,
                "domain_definition_id": binding.definition_id,
                "domain_provenance": binding.provenance,
                "domain_source_priority": binding.source_priority,
            },
        ),
    )
    extraction = extractor_registry.extract(
        resource,
        context=ExtractionContext(
            actor_id=actor_id,
            domain=str(binding.domain_id),
            trace_id=binding.id,
            session_id=session_id,
        ),
        extractor_name=resource_input.extractor_name,
    )
    if extraction.status in {ExtractionStatus.FAILED, ExtractionStatus.UNSUPPORTED}:
        raise DomainCognitiveIntegrationBlockedError(
            "Mandatory Domain resource extraction did not succeed",
            details={
                "binding_id": binding.id,
                "extractor": extraction.extractor_name,
                "status": extraction.status.value,
            },
        )

    bundle = materialise_result(
        extraction,
        actor_id=actor_id,
        resource_provenance_id=resource.provenance.source_id,
    )
    return resource, bundle
