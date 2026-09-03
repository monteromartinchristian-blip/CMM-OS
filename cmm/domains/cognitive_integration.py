"""Canonical Cognitive Layer integration for resolved Domain resources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from cmm.cognitive import (
    AdaptationContext,
    CognitiveValidationContext,
    CognitiveValidationDecision,
    CognitiveValidationResult,
    CognitiveValidator,
    Confidence,
    ExtractionContext,
    ExtractionStatus,
    KnowledgeBundle,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    KnowledgePackageBuilder,
    KnowledgePackageRequest,
    KnowledgeStoreProtocol,
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRecommendation,
    ReasoningRuleContext,
    ReasoningRuleRegistry,
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
from cmm.domains.errors import (
    DomainCognitiveIntegrationBlockedError,
    DomainCognitiveIntegrationContractError,
)
from cmm.domains.presentation_contracts import (
    DomainPresentationEpistemicKind,
    DomainPresentationItemRef,
    DomainPresentationItemType,
)
from cmm.domains.rule_contracts import DomainRuleExecutionResult
from cmm.domains.rule_execution import DefaultDomainRuleExecutor, DomainRuleExecutor
from cmm.domains.rule_selection import DefaultDomainRuleSelector, DomainRuleSelector
from cmm.domains.trace_contracts import DomainTraceReferences

_BLOCKING_COGNITIVE_VALIDATION_DECISIONS = {
    CognitiveValidationDecision.BLOCK,
    CognitiveValidationDecision.INVALIDATE,
    CognitiveValidationDecision.REPAIR,
    CognitiveValidationDecision.REBUILD,
    CognitiveValidationDecision.REQUEST_APPROVAL,
}


@runtime_checkable
class DomainCognitiveIntegrator(Protocol):
    """Protocol for the Domain-to-Cognitive orchestration boundary."""

    def integrate(
        self,
        request: DomainCognitiveIntegrationRequest,
    ) -> DomainCognitiveIntegrationResult: ...


class DefaultDomainCognitiveIntegrator:
    """Thin orchestration boundary over canonical Cognitive and Domain owners."""

    def __init__(
        self,
        *,
        adapter_registry: ResourceAdapterRegistry,
        extractor_registry: KnowledgeExtractorRegistry,
        knowledge_store: KnowledgeStoreProtocol,
        rule_registry: ReasoningRuleRegistry,
        cognitive_validator: CognitiveValidator | None = None,
        rule_selector: DomainRuleSelector | None = None,
        rule_executor: DomainRuleExecutor | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(adapter_registry, ResourceAdapterRegistry):
            raise DomainCognitiveIntegrationContractError(
                "adapter_registry must be a ResourceAdapterRegistry",
                field="adapter_registry",
            )
        if not isinstance(extractor_registry, KnowledgeExtractorRegistry):
            raise DomainCognitiveIntegrationContractError(
                "extractor_registry must be a KnowledgeExtractorRegistry",
                field="extractor_registry",
            )
        if not isinstance(knowledge_store, KnowledgeStoreProtocol):
            raise DomainCognitiveIntegrationContractError(
                "knowledge_store must satisfy KnowledgeStoreProtocol",
                field="knowledge_store",
            )
        if not isinstance(rule_registry, ReasoningRuleRegistry):
            raise DomainCognitiveIntegrationContractError(
                "rule_registry must satisfy ReasoningRuleRegistry",
                field="rule_registry",
            )
        if cognitive_validator is not None and not isinstance(
            cognitive_validator, CognitiveValidator
        ):
            raise DomainCognitiveIntegrationContractError(
                "cognitive_validator must be a CognitiveValidator",
                field="cognitive_validator",
            )
        if rule_selector is not None and not isinstance(
            rule_selector, DomainRuleSelector
        ):
            raise DomainCognitiveIntegrationContractError(
                "rule_selector must satisfy DomainRuleSelector",
                field="rule_selector",
            )
        if rule_executor is not None and not isinstance(
            rule_executor, DomainRuleExecutor
        ):
            raise DomainCognitiveIntegrationContractError(
                "rule_executor must satisfy DomainRuleExecutor",
                field="rule_executor",
            )
        if clock is not None and not callable(clock):
            raise DomainCognitiveIntegrationContractError(
                "clock must be callable",
                field="clock",
            )

        self._adapter_registry = adapter_registry
        self._extractor_registry = extractor_registry
        self._knowledge_store = knowledge_store
        self._rule_registry = rule_registry
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._cognitive_validator = (
            cognitive_validator
            if cognitive_validator is not None
            else CognitiveValidator()
        )
        self._rule_selector = (
            rule_selector
            if rule_selector is not None
            else DefaultDomainRuleSelector(clock=self._clock)
        )
        self._rule_executor = (
            rule_executor
            if rule_executor is not None
            else DefaultDomainRuleExecutor(clock=self._clock)
        )

    def _now(self) -> datetime:
        value = self._clock()
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise DomainCognitiveIntegrationContractError(
                "clock must return a timezone-aware datetime",
                field="clock",
            )
        return value

    def integrate(
        self,
        request: DomainCognitiveIntegrationRequest,
    ) -> DomainCognitiveIntegrationResult:
        if type(request) is not DomainCognitiveIntegrationRequest:
            raise DomainCognitiveIntegrationContractError(
                "request must be a DomainCognitiveIntegrationRequest",
                field="request",
            )

        for resource_input in request.resources:
            missing = tuple(
                permission
                for permission in resource_input.binding.permissions
                if permission not in request.effective_permissions
            )
            if missing:
                raise DomainCognitiveIntegrationBlockedError(
                    f"Domain resource binding '{resource_input.binding.id}' required permissions "
                    f"not satisfied: absent from effective_permissions",
                    details={
                        "request_id": request.request_id,
                        "binding_id": resource_input.binding.id,
                        "missing_permissions": missing,
                    },
                )

        timestamp = self._now()
        adapted = tuple(
            _adapt_domain_resource(
                resource_input,
                adapter_registry=self._adapter_registry,
                extractor_registry=self._extractor_registry,
                actor_id=request.actor_id,
                session_id=request.session_id,
                effective_permissions=request.effective_permissions,
            )
            for resource_input in request.resources
        )
        adapted_resources = tuple(resource for resource, _ in adapted)
        extracted_bundles = tuple(bundle for _, bundle in adapted)
        package = _build_knowledge_package(
            store=self._knowledge_store,
            request=request,
            adapted_resources=adapted_resources,
        )
        reasoning_context = _build_reasoning_context(
            request=request,
            package=package,
            extracted_bundles=extracted_bundles,
            adapted_resources=adapted_resources,
            timestamp=timestamp,
        )
        validation_results = _validate_cognitive_inputs(
            validator=self._cognitive_validator,
            request=request,
            package=package,
            resources=adapted_resources,
            bundles=extracted_bundles,
            now=timestamp,
        )
        plan = self._rule_selector.select(
            registry=self._rule_registry,
            profile=request.profile,
            composition=request.composition,
            global_mandatory_rules=request.global_mandatory_rules,
            security_rules=request.security_rules,
            effective_permissions=request.effective_permissions,
            requested_rule_ids=request.requested_rule_ids,
        )
        rule_result = self._rule_executor.execute(
            plan=plan,
            context=reasoning_context,
            registry=self._rule_registry,
        )
        presentation_items = _presentation_items(
            request=request,
            bundles=extracted_bundles,
            rule_result=rule_result,
        )
        trace_references = _build_trace_references(request=request, package=package)
        return DomainCognitiveIntegrationResult(
            request_id=request.request_id,
            knowledge_package=package,
            validation_results=validation_results,
            reasoning_context=reasoning_context,
            rule_plan=plan,
            rule_result=rule_result,
            adapted_resources=adapted_resources,
            extracted_bundles=extracted_bundles,
            presentation_items=presentation_items,
            trace_references=trace_references,
        )


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


def _build_trace_references(
    *,
    request: DomainCognitiveIntegrationRequest,
    package: KnowledgePackage,
) -> DomainTraceReferences:
    return DomainTraceReferences(
        resolution_context_id=request.resolution_context_id,
        resolution_result_id=request.resolution_result_id,
        composition_id=request.composition.id,
        knowledge_package_ids=(package.id,),
    )


def _presentation_items(
    *,
    request: DomainCognitiveIntegrationRequest,
    bundles: tuple[KnowledgeBundle, ...],
    rule_result: DomainRuleExecutionResult,
) -> tuple[DomainPresentationItemRef, ...]:
    items: list[DomainPresentationItemRef] = []
    seen_question_ids: set[str] = set()

    def add_message(
        *,
        ref_id: str,
        item_type: DomainPresentationItemType,
        message: (
            ReasoningFinding
            | ReasoningGap
            | ReasoningRecommendation
            | ReasoningEscalation
        ),
        epistemic_kind: DomainPresentationEpistemicKind | None = None,
    ) -> None:
        metadata = message.metadata
        domain_id = message.domain_id
        items.append(
            DomainPresentationItemRef(
                ref_id=ref_id,
                item_type=item_type,
                source_order=len(items),
                domain_ids=(domain_id,) if domain_id is not None else (),
                epistemic_kind=epistemic_kind,
                requires_provenance=metadata.get("requires_provenance") is True,
                pending=metadata.get("pending") is True,
                requires_user_interaction=(
                    metadata.get("requires_user_interaction") is True
                ),
                requires_approval=metadata.get("requires_approval") is True,
                requires_confirmation=(metadata.get("requires_confirmation") is True),
                explicitly_visible=metadata.get("explicitly_visible") is True,
            )
        )

    def add_question(
        knowledge_item: KnowledgeItem,
        *,
        domain_ids: tuple[str, ...] = (),
    ) -> None:
        if (
            knowledge_item.kind is not KnowledgeKind.QUESTION
            or knowledge_item.id in seen_question_ids
        ):
            return
        seen_question_ids.add(knowledge_item.id)
        items.append(
            DomainPresentationItemRef(
                ref_id=knowledge_item.id,
                item_type=DomainPresentationItemType.QUESTION,
                source_order=len(items),
                domain_ids=domain_ids,
                confidence=knowledge_item.confidence.value,
                requires_provenance=True,
                pending=True,
                requires_user_interaction=True,
            )
        )

    for index, finding in enumerate(rule_result.findings):
        add_message(
            ref_id=f"{rule_result.id}:finding:{index}",
            item_type=DomainPresentationItemType.FINDING,
            message=finding,
        )
    for index, gap in enumerate(rule_result.gaps):
        add_message(
            ref_id=f"{rule_result.id}:gap:{index}",
            item_type=DomainPresentationItemType.GAP,
            message=gap,
        )
    for contradiction in rule_result.contradictions:
        items.append(
            DomainPresentationItemRef(
                ref_id=contradiction.id,
                item_type=DomainPresentationItemType.CONTRADICTION,
                source_order=len(items),
                requires_provenance=True,
            )
        )
    for index, recommendation in enumerate(rule_result.recommendations):
        add_message(
            ref_id=f"{rule_result.id}:recommendation:{index}",
            item_type=DomainPresentationItemType.RECOMMENDATION,
            message=recommendation,
            epistemic_kind=DomainPresentationEpistemicKind.RECOMMENDATION,
        )
    for index, escalation in enumerate(rule_result.escalations):
        add_message(
            ref_id=f"{rule_result.id}:escalation:{index}",
            item_type=DomainPresentationItemType.ESCALATION,
            message=escalation,
        )
    for bundle_index, bundle in enumerate(bundles):
        domain_ids = (
            (str(request.resources[bundle_index].binding.domain_id),)
            if bundle_index < len(request.resources)
            else ()
        )
        for knowledge_item in bundle.items:
            add_question(knowledge_item, domain_ids=domain_ids)
    for knowledge_item in rule_result.produced_knowledge:
        add_question(knowledge_item)

    return tuple(items)


def _validate_cognitive_inputs(
    *,
    validator: CognitiveValidator,
    request: DomainCognitiveIntegrationRequest,
    package: KnowledgePackage,
    resources: tuple[Resource, ...],
    bundles: tuple[KnowledgeBundle, ...],
    now: datetime,
) -> tuple[CognitiveValidationResult, ...]:
    context = CognitiveValidationContext(
        actor_id=request.actor_id,
        domain=str(request.profile.primary_domain),
        permission_context={
            "effective_permissions": request.effective_permissions,
        },
        require_current_information=bool(
            request.profile.temporal_policy.require_current_information
        ),
        now=now,
        metadata={
            "domain_profile_id": request.profile.id,
            "domain_composition_id": request.composition.id,
        },
    )
    targets = (
        package,
        *resources,
        *(item for bundle in bundles for item in bundle.items),
    )
    results = tuple(validator.validate(target, context) for target in targets)

    blocked = next(
        (
            result
            for result in results
            if result.decision in _BLOCKING_COGNITIVE_VALIDATION_DECISIONS
        ),
        None,
    )
    if blocked is not None:
        raise DomainCognitiveIntegrationBlockedError(
            "Cognitive validation blocked Domain rule execution",
            details={
                "request_id": request.request_id,
                "validation_result_id": blocked.id,
                "target_id": blocked.target_id,
                "decision": blocked.decision.value,
                "blocking_finding_codes": tuple(
                    finding.code for finding in blocked.blocking_findings
                ),
            },
        )

    return results


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
