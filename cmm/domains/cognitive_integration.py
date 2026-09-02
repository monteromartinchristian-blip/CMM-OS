"""Canonical Cognitive Layer integration for resolved Domain resources."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Protocol, runtime_checkable

from cmm.cognitive import (
    AdaptationContext,
    Confidence,
    ExtractionContext,
    ExtractionStatus,
    KnowledgeBundle,
    KnowledgeExtractorRegistry,
    KnowledgePackage,
    KnowledgePackageBuilder,
    KnowledgePackageRequest,
    KnowledgeStoreProtocol,
    ReasoningRuleContext,
    Resource,
    ResourceAdapterRegistry,
    SensitivityLevel,
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


def _build_knowledge_package(
    *,
    store: KnowledgeStoreProtocol,
    request: DomainCognitiveIntegrationRequest,
    adapted_resources: tuple[Resource, ...],
) -> KnowledgePackage:
    return KnowledgePackageBuilder(
        store,
        resources=adapted_resources,
    ).build(
        KnowledgePackageRequest(
            objective=request.objective,
            profile=request.profile.id,
            domain=str(request.profile.primary_domain),
            session_id=request.session_id,
            permission_context={
                "actor_id": request.actor_id,
                "effective_permissions": request.effective_permissions,
            },
            temporal_scope={
                "require_current_information": (
                    request.profile.temporal_policy.require_current_information
                ),
                "maximum_age_seconds": (
                    request.profile.temporal_policy.maximum_age_seconds
                ),
            },
            metadata={
                "domain_composition_id": request.composition.id,
            },
        )
    )


_SENSITIVITY_RANK = {
    SensitivityLevel.PUBLIC: 0,
    SensitivityLevel.INTERNAL: 1,
    SensitivityLevel.PERSONAL: 2,
    SensitivityLevel.SENSITIVE: 3,
    SensitivityLevel.HIGHLY_SENSITIVE: 4,
    SensitivityLevel.RESTRICTED: 5,
}


def _effective_sensitivity(resources: tuple[Resource, ...]) -> str | None:
    if not resources:
        return None
    return max(
        (resource.sensitivity for resource in resources),
        key=_SENSITIVITY_RANK.__getitem__,
    ).value


def _build_reasoning_context(
    *,
    request: DomainCognitiveIntegrationRequest,
    package: KnowledgePackage,
    extracted_bundles: tuple[KnowledgeBundle, ...],
    adapted_resources: tuple[Resource, ...],
    timestamp: datetime,
) -> ReasoningRuleContext:
    ordered_items = (
        *package.facts,
        *package.observations,
        *package.inferences,
        *package.hypotheses,
        *package.other_knowledge,
        *(item for bundle in extracted_bundles for item in bundle.items),
    )
    seen_item_ids: set[str] = set()
    unique_items = []
    for item in ordered_items:
        if item.id in seen_item_ids:
            continue
        seen_item_ids.add(item.id)
        unique_items.append(item)
    knowledge_items = tuple(unique_items)
    return ReasoningRuleContext(
        reasoning_id=f"domain-cognitive:{request.request_id}",
        timestamp=timestamp,
        session_id=request.session_id,
        knowledge_items=knowledge_items,
        contradictions=package.contradictions,
        active_domains=(
            str(request.profile.primary_domain),
            *(str(domain) for domain in request.profile.supporting_domains),
        ),
        primary_domain=str(request.profile.primary_domain),
        supporting_domains=tuple(
            str(domain) for domain in request.profile.supporting_domains
        ),
        effective_permissions=request.effective_permissions,
        effective_sensitivity=_effective_sensitivity(adapted_resources),
        metadata={
            "domain_composition_id": request.composition.id,
            "domain_profile_id": request.profile.id,
            "minimum_confidence": request.profile.minimum_confidence,
            "reasoning_depth": request.profile.reasoning_depth.value,
            "maximum_questions": request.profile.maximum_questions,
        },
    )


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
