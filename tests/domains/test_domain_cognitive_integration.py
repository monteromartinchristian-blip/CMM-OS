"""Tests for Phase 10.40 Domain resource adaptation into Phase 8."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    AdaptationContext,
    AdaptationStatus,
    CandidateKind,
    CognitiveValidationContext,
    CognitiveValidationDecision,
    CognitiveValidationResult,
    CognitiveValidator,
    Contradiction,
    ExistingResourceAdapter,
    ExtractionContext,
    ExtractionStatus,
    InMemoryKnowledgeStore,
    InMemoryReasoningRuleRegistry,
    KnowledgeBundle,
    KnowledgeExtractionResult,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    KnowledgeStatus,
    PlainTextKnowledgeExtractor,
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRecommendation,
    ReasoningRiskLevel,
    ReasoningRule,
    ReasoningRuleCategory,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
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
    TemporalScope,
    TemporalScopeKind,
)
from cmm.cognitive.contracts import Confidence
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
    DomainCognitiveResourceInput,
)
from cmm.domains.composition_contracts import DomainComposition, PresentationComposition
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainReasoningDepth,
    DomainResourceResolutionStatus,
    DomainRuleExecutionStatus,
    DomainRuleSelectionStatus,
)
from cmm.domains.errors import (
    DomainCognitiveIntegrationBlockedError,
    DomainCognitiveIntegrationContractError,
)
from cmm.domains.identifiers import DomainId
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
from cmm.domains.rule_contracts import DomainRuleExecutionResult
from cmm.validation.enums import ValidationSeverity
from cmm.validation.findings import ValidationFinding

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


class _RecordingValidationRule:
    name = "test.record_context"

    def __init__(self) -> None:
        self.calls: list[tuple[object, CognitiveValidationContext]] = []

    def applies(self, target: object) -> bool:
        return True

    def evaluate(
        self,
        target: object,
        context: CognitiveValidationContext,
    ) -> tuple[ValidationFinding, ...]:
        self.calls.append((target, context))
        return ()


class _RequestInformationValidationRule:
    name = "test.request_information"

    def applies(self, target: object) -> bool:
        return isinstance(target, KnowledgePackage)

    def evaluate(
        self,
        target: object,
        context: CognitiveValidationContext,
    ) -> tuple[ValidationFinding, ...]:
        return (
            ValidationFinding(
                code="COG_EVIDENCE_INSUFFICIENT",
                message="Canonical evidence is incomplete",
                severity=ValidationSeverity.WARNING,
                source="test.cognitive_validation",
                blocking=True,
                metadata={"target_id": getattr(target, "id", "unknown")},
            ),
        )


class _CountingReasoningRule:
    def __init__(
        self,
        rule_id: str = "test.cognitive_validation_count",
        *,
        scope: ReasoningRuleScope = ReasoningRuleScope.DOMAIN,
        domain_id: str | None = "domain:health",
        priority: int = 1,
    ) -> None:
        self.evaluations = 0
        self._definition = ReasoningRuleDefinition(
            id=rule_id,
            name="Cognitive validation count",
            version="1.0.0",
            scope=scope,
            category=ReasoningRuleCategory.VALIDATION,
            status=ReasoningRuleStatus.ENABLED,
            priority=priority,
            risk_level=ReasoningRiskLevel.LOW,
            domain_id=domain_id,
        )

    @property
    def definition(self) -> ReasoningRuleDefinition:
        return self._definition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        self.evaluations += 1
        return ReasoningRuleResult(
            rule_id=self.definition.id,
            rule_name=self.definition.name,
            rule_version=self.definition.version,
            status=ReasoningRuleResultStatus.APPLIED,
            started_at=context.timestamp,
            completed_at=context.timestamp,
            domain_id=self.definition.domain_id,
        )


class _PresentationEvidenceReasoningRule:
    def __init__(self) -> None:
        self._definition = ReasoningRuleDefinition(
            id="health.presentation",
            name="Canonical presentation evidence",
            version="1.0.0",
            scope=ReasoningRuleScope.DOMAIN,
            category=ReasoningRuleCategory.VALIDATION,
            status=ReasoningRuleStatus.ENABLED,
            priority=1,
            risk_level=ReasoningRiskLevel.LOW,
            domain_id="domain:health",
        )

    @property
    def definition(self) -> ReasoningRuleDefinition:
        return self._definition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        question = next(
            item
            for item in context.knowledge_items
            if item.kind is KnowledgeKind.QUESTION
        )
        return ReasoningRuleResult(
            rule_id=self.definition.id,
            rule_name=self.definition.name,
            rule_version=self.definition.version,
            status=ReasoningRuleResultStatus.APPLIED,
            domain_id=self.definition.domain_id,
            findings=(
                ReasoningFinding(
                    code="CANONICAL_WARNING",
                    message="Canonical warning evidence remains represented.",
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                ),
            ),
            contradictions=(
                Contradiction(
                    id="canonical-contradiction-1",
                    item_a_id="integration-provenance-item",
                    item_b_id=question.id,
                    created_at=context.timestamp,
                ),
            ),
            gaps=(
                ReasoningGap(
                    code="CANONICAL_GAP",
                    message="Canonical gap evidence remains represented.",
                    severity=ReasoningSeverity.WARNING,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                ),
            ),
            recommendations=(
                ReasoningRecommendation(
                    code="CANONICAL_RECOMMENDATION",
                    message="Review canonical evidence.",
                    severity=ReasoningSeverity.INFO,
                    rule_id=self.definition.id,
                    domain_id=self.definition.domain_id,
                ),
            ),
            escalation=ReasoningEscalation(
                code="CANONICAL_ESCALATION",
                message="Seek qualified review.",
                severity=ReasoningSeverity.CRITICAL,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            ),
            started_at=context.timestamp,
            completed_at=context.timestamp,
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


def _integration_request(
    *,
    minimum_confidence: float = 0.8,
    temporal_policy: DomainTemporalPolicy | None = None,
) -> DomainCognitiveIntegrationRequest:
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
        minimum_confidence=minimum_confidence,
        reasoning_depth=DomainReasoningDepth.DEEP,
        allowed_inferences=None,
        prohibited_inferences=(),
        maximum_questions=3,
        escalation_rules=(),
        prohibited_actions=(),
        question_policy=DomainQuestionPolicy(),
        presentation_policy=DomainPresentationPolicy(),
        memory_policy=DomainMemoryPolicy(),
        temporal_policy=temporal_policy or DomainTemporalPolicy(),
        production_policy=DomainProductionPolicy(),
        permissions=None,
        modifications=(),
        trace_id="profile-trace-1",
        resolved_at=NOW,
    )
    return DomainCognitiveIntegrationRequest(
        request_id="request-1",
        resolution_context_id="resolution-context-1",
        resolution_result_id="resolution-result-1",
        objective="Review health information",
        composition=composition,
        profile=profile,
        actor_id="actor-1",
        session_id="session-1",
        effective_permissions=("resource:read", "resource:infer"),
    )


def _serialized_store_state(store: InMemoryKnowledgeStore) -> dict[str, object]:
    return {
        "items": [item.serialize() for item in store.list_items()],
        "evidence": [evidence.serialize() for evidence in store.list_evidence()],
        "relations": [relation.serialize() for relation in store.list_relations()],
        "contradictions": [
            contradiction.serialize() for contradiction in store.list_contradictions()
        ],
        "bundles": [bundle.serialize() for bundle in store.list_bundles()],
    }


def _presentation_rule_result(
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    produced_knowledge: tuple[KnowledgeItem, ...] = (),
    contradictions: tuple[Contradiction, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    recommendations: tuple[ReasoningRecommendation, ...] = (),
    escalations: tuple[ReasoningEscalation, ...] = (),
) -> DomainRuleExecutionResult:
    return DomainRuleExecutionResult(
        id="rule-result-1",
        plan_id="rule-plan-1",
        status=DomainRuleExecutionStatus.COMPLETED,
        findings=findings,
        produced_knowledge=produced_knowledge,
        contradictions=contradictions,
        gaps=gaps,
        recommendations=recommendations,
        escalations=escalations,
        started_at=NOW,
        completed_at=NOW,
    )


def test_presentation_items_map_only_canonical_evidence_with_stable_ids() -> None:
    """Would fail if mappings changed type, hashed content, or invented confidence."""
    from cmm.domains.cognitive_integration import _presentation_items
    from cmm.domains.presentation_contracts import DomainPresentationItemType

    question = KnowledgeItem(
        id="canonical-question-1",
        statement="Which canonical evidence is missing?",
        kind=KnowledgeKind.QUESTION,
        confidence=Confidence(0.42, source="canonical-extraction"),
        created_at=NOW,
        updated_at=NOW,
    )
    non_question = replace(
        question,
        id="canonical-observation-1",
        statement="This is not a presentation question.",
        kind=KnowledgeKind.OBSERVATION,
    )
    finding = ReasoningFinding(
        code="CANONICAL_WARNING",
        message="Content must never be embedded in the reference ID.",
        severity=ReasoningSeverity.WARNING,
        rule_id="health.presentation",
        domain_id="domain:health",
    )
    second_finding = replace(finding, code="SECOND_FINDING")
    gap = ReasoningGap(
        code="CANONICAL_GAP",
        message="More evidence is needed.",
        severity=ReasoningSeverity.WARNING,
        rule_id="health.presentation",
        domain_id="domain:health",
    )
    contradiction = Contradiction(
        id="canonical-contradiction-1",
        item_a_id=question.id,
        item_b_id=non_question.id,
        created_at=NOW,
    )
    recommendation = ReasoningRecommendation(
        code="CANONICAL_RECOMMENDATION",
        message="Review the canonical evidence.",
        severity=ReasoningSeverity.INFO,
        rule_id="health.presentation",
        domain_id="domain:health",
    )
    escalation = ReasoningEscalation(
        code="CANONICAL_ESCALATION",
        message="Seek qualified review.",
        severity=ReasoningSeverity.CRITICAL,
        rule_id="health.presentation",
        domain_id="domain:health",
    )

    items = _presentation_items(
        request=_integration_request(minimum_confidence=0.99),
        bundles=(
            KnowledgeBundle(
                id="canonical-bundle-1",
                items=(question, non_question),
                created_at=NOW,
            ),
        ),
        rule_result=_presentation_rule_result(
            findings=(finding, second_finding),
            gaps=(gap,),
            contradictions=(contradiction,),
            recommendations=(recommendation,),
            escalations=(escalation,),
        ),
    )

    assert tuple(item.item_type for item in items) == (
        DomainPresentationItemType.FINDING,
        DomainPresentationItemType.FINDING,
        DomainPresentationItemType.GAP,
        DomainPresentationItemType.CONTRADICTION,
        DomainPresentationItemType.RECOMMENDATION,
        DomainPresentationItemType.ESCALATION,
        DomainPresentationItemType.QUESTION,
    )
    assert tuple(item.ref_id for item in items) == (
        "rule-result-1:finding:0",
        "rule-result-1:finding:1",
        "rule-result-1:gap:0",
        "canonical-contradiction-1",
        "rule-result-1:recommendation:0",
        "rule-result-1:escalation:0",
        "canonical-question-1",
    )
    assert tuple(item.source_order for item in items) == tuple(range(7))
    assert tuple(item.confidence for item in items) == (
        None,
        None,
        None,
        None,
        None,
        None,
        0.42,
    )
    assert items[3].requires_provenance is True
    assert items[6].requires_provenance is True
    assert items[6].requires_user_interaction is True
    assert items[6].pending is True
    assert all("Content" not in item.ref_id for item in items)


def test_presentation_gap_interaction_uses_only_explicit_canonical_flags() -> None:
    """Would fail if wording/profile thresholds synthesized interaction state."""
    from cmm.domains.cognitive_integration import _presentation_items

    implicit = ReasoningGap(
        code="CLARIFICATION_REQUIRED",
        message="User clarification is required before proceeding.",
        severity=ReasoningSeverity.WARNING,
        rule_id="health.presentation",
        references=("canonical-question-1",),
    )
    explicit = replace(
        implicit,
        code="EXPLICIT_USER_RESOLUTION",
        metadata={
            "pending": True,
            "requires_user_interaction": True,
            "requires_approval": True,
            "requires_confirmation": True,
        },
    )

    items = _presentation_items(
        request=_integration_request(minimum_confidence=1.0),
        bundles=(),
        rule_result=_presentation_rule_result(gaps=(implicit, explicit)),
    )

    assert items[0].confidence is None
    assert items[0].requires_provenance is False
    assert items[0].pending is False
    assert items[0].requires_user_interaction is False
    assert items[0].requires_approval is False
    assert items[0].requires_confirmation is False
    assert items[1].pending is True
    assert items[1].requires_user_interaction is True
    assert items[1].requires_approval is True
    assert items[1].requires_confirmation is True


def test_presentation_items_include_rule_questions_with_first_seen_deduplication() -> (
    None
):
    """Would fail if rule-produced questions were omitted or duplicated by ID."""
    from cmm.domains.cognitive_integration import _presentation_items
    from cmm.domains.presentation_contracts import DomainPresentationItemType

    bundle_question = KnowledgeItem(
        id="shared-question-1",
        statement="Which bundle evidence is missing?",
        kind=KnowledgeKind.QUESTION,
        confidence=Confidence(0.31, source="bundle-extraction"),
        created_at=NOW,
        updated_at=NOW,
    )
    repeated_rule_question = replace(
        bundle_question,
        statement="A later copy must not replace the first canonical question.",
        confidence=Confidence(0.88, source="rule-copy"),
    )
    rule_question = KnowledgeItem(
        id="rule-question-1",
        statement="Which rule evidence is missing?",
        kind=KnowledgeKind.QUESTION,
        confidence=Confidence(0.67, source="rule-output"),
        created_at=NOW,
        updated_at=NOW,
    )
    rule_observation = replace(
        rule_question,
        id="rule-observation-1",
        statement="Rule observations do not become presentation questions.",
        kind=KnowledgeKind.OBSERVATION,
    )

    items = _presentation_items(
        request=_integration_request(),
        bundles=(
            KnowledgeBundle(
                id="bundle-with-shared-question",
                items=(bundle_question,),
                created_at=NOW,
            ),
        ),
        rule_result=_presentation_rule_result(
            produced_knowledge=(
                repeated_rule_question,
                rule_question,
                rule_observation,
            ),
        ),
    )

    assert tuple(item.ref_id for item in items) == (
        "shared-question-1",
        "rule-question-1",
    )
    assert all(item.item_type is DomainPresentationItemType.QUESTION for item in items)
    assert tuple(item.source_order for item in items) == (0, 1)
    assert tuple(item.confidence for item in items) == (0.31, 0.67)
    assert all(item.requires_provenance for item in items)
    assert all(item.pending for item in items)
    assert all(item.requires_user_interaction for item in items)


def test_package_and_context_builders_read_store_without_mutating_it() -> None:
    from cmm.domains.cognitive_integration import (
        _build_knowledge_package,
        _build_reasoning_context,
    )

    temporal_scope = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=VALID_FROM,
        valid_until=VALID_UNTIL,
        last_verified_at=LAST_VERIFIED_AT,
    )
    first = KnowledgeItem(
        id="prior-health-fact",
        statement="Health information is current.",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.61, source="evidence"),
        resource_id="resource-1",
        temporal_scope=temporal_scope,
        created_at=NOW,
        updated_at=NOW,
    )
    second = KnowledgeItem(
        id="prior-health-observation",
        statement="Health information may be outdated.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=Confidence(0.55, source="evidence"),
        created_at=NOW,
        updated_at=NOW,
    )
    contradiction = Contradiction(
        id="health-contradiction",
        item_a_id=first.id,
        item_b_id=second.id,
        explanation="The source dates disagree.",
        created_at=NOW,
    )
    store = InMemoryKnowledgeStore()
    store.save_item(first)
    store.save_item(second)
    store.save_contradiction(contradiction)
    before = _serialized_store_state(store)
    request = _integration_request(
        temporal_policy=DomainTemporalPolicy(
            require_current_information=True,
            maximum_age_seconds=7_200,
        )
    )

    package = _build_knowledge_package(
        store=store,
        request=request,
        adapted_resources=(_canonical_resource(),),
    )
    context = _build_reasoning_context(
        request=request,
        package=package,
        extracted_bundles=(),
        adapted_resources=(_canonical_resource(),),
        timestamp=NOW,
    )

    assert package.profile == "profile-1"
    assert package.domain == "domain:health"
    assert package.session_id == "session-1"
    assert package.facts == (first,)
    assert package.observations == (second,)
    assert package.contradictions == (contradiction,)
    assert package.resources == (_canonical_resource(),)
    assert dict(package.temporal_scope) == {
        "require_current_information": True,
        "maximum_age_seconds": 7_200,
    }
    assert dict(package.metadata) == {"domain_composition_id": "composition-1"}
    assert context.knowledge_items == (first, second)
    assert context.contradictions == (contradiction,)
    assert _serialized_store_state(store) == before


def test_reasoning_context_builds_stable_first_seen_canonical_knowledge_union() -> None:
    from cmm.domains.cognitive_integration import _build_reasoning_context

    temporal_scope = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=VALID_FROM,
        valid_until=VALID_UNTIL,
        last_verified_at=LAST_VERIFIED_AT,
    )
    fact = KnowledgeItem(
        id="fact-1",
        statement="Health fact.",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.61, source="evidence"),
        temporal_scope=temporal_scope,
        created_at=NOW,
        updated_at=NOW,
    )
    observation = KnowledgeItem(
        id="observation-1",
        statement="Health observation.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=Confidence(0.62, source="evidence"),
        created_at=NOW,
        updated_at=NOW,
    )
    inference = KnowledgeItem(
        id="inference-1",
        statement="Health inference.",
        kind=KnowledgeKind.INFERENCE,
        confidence=Confidence(0.63, source="evidence"),
        created_at=NOW,
        updated_at=NOW,
    )
    hypothesis = KnowledgeItem(
        id="hypothesis-1",
        statement="Health hypothesis.",
        kind=KnowledgeKind.HYPOTHESIS,
        confidence=Confidence(0.64, source="evidence"),
        created_at=NOW,
        updated_at=NOW,
    )
    question = KnowledgeItem(
        id="question-1",
        statement="What health evidence is missing?",
        kind=KnowledgeKind.QUESTION,
        confidence=Confidence(0.65, source="evidence"),
        created_at=NOW,
        updated_at=NOW,
    )
    extracted_first = KnowledgeItem(
        id="extracted-1",
        statement="First extracted item.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=Confidence(0.66, source="extraction"),
        created_at=NOW,
        updated_at=NOW,
    )
    extracted_second = KnowledgeItem(
        id="extracted-2",
        statement="Second extracted item.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=Confidence(0.67, source="extraction"),
        created_at=NOW,
        updated_at=NOW,
    )
    contradiction = Contradiction(
        id="contradiction-1",
        item_a_id=fact.id,
        item_b_id=observation.id,
        explanation="Canonical contradiction.",
        created_at=NOW,
    )
    package = KnowledgePackage(
        id="package-1",
        objective="Review health information",
        facts=(fact,),
        observations=(observation,),
        inferences=(inference,),
        hypotheses=(hypothesis,),
        other_knowledge=(question,),
        contradictions=(contradiction,),
        created_at=NOW,
    )
    bundles = (
        KnowledgeBundle(id="bundle-1", items=(extracted_first, fact), created_at=NOW),
        KnowledgeBundle(
            id="bundle-2",
            items=(extracted_second, extracted_first),
            created_at=NOW,
        ),
    )
    resources = (
        replace(
            _canonical_resource(),
            id="public-resource",
            sensitivity=SensitivityLevel.PUBLIC,
        ),
        replace(
            _canonical_resource(),
            id="restricted-resource",
            sensitivity=SensitivityLevel.RESTRICTED,
        ),
    )

    context = _build_reasoning_context(
        request=_integration_request(minimum_confidence=0.9),
        package=package,
        extracted_bundles=bundles,
        adapted_resources=resources,
        timestamp=NOW,
    )

    assert context.reasoning_id == "domain-cognitive:request-1"
    assert [item.id for item in context.knowledge_items] == [
        "fact-1",
        "observation-1",
        "inference-1",
        "hypothesis-1",
        "question-1",
        "extracted-1",
        "extracted-2",
    ]
    assert context.knowledge_items[0] is fact
    assert context.knowledge_items[0].confidence.value == 0.61
    assert context.knowledge_items[0].temporal_scope is temporal_scope
    assert context.contradictions == (contradiction,)
    assert context.contradictions[0] is contradiction
    assert context.active_domains == ("domain:health", "domain:university")
    assert context.primary_domain == "domain:health"
    assert context.supporting_domains == ("domain:university",)
    assert context.effective_permissions == ("resource:read", "resource:infer")
    assert context.effective_sensitivity == "restricted"
    assert dict(context.metadata) == {
        "domain_composition_id": "composition-1",
        "domain_profile_id": "profile-1",
        "minimum_confidence": 0.9,
        "reasoning_depth": "deep",
        "maximum_questions": 3,
    }


@pytest.mark.parametrize(
    ("sensitivities", "expected"),
    (
        ((), None),
        ((SensitivityLevel.PUBLIC,), "public"),
        (
            (SensitivityLevel.PUBLIC, SensitivityLevel.INTERNAL),
            "internal",
        ),
        (
            (SensitivityLevel.INTERNAL, SensitivityLevel.PERSONAL),
            "personal",
        ),
        (
            (SensitivityLevel.PERSONAL, SensitivityLevel.SENSITIVE),
            "sensitive",
        ),
        (
            (SensitivityLevel.SENSITIVE, SensitivityLevel.HIGHLY_SENSITIVE),
            "highly_sensitive",
        ),
        (
            (SensitivityLevel.HIGHLY_SENSITIVE, SensitivityLevel.RESTRICTED),
            "restricted",
        ),
    ),
)
def test_effective_sensitivity_uses_canonical_phase_8_rank(
    sensitivities: tuple[SensitivityLevel, ...], expected: str | None
) -> None:
    from cmm.domains.cognitive_integration import _effective_sensitivity

    resources = tuple(
        replace(
            _canonical_resource(),
            id=f"resource-{index}",
            sensitivity=sensitivity,
        )
        for index, sensitivity in enumerate(sensitivities)
    )

    assert _effective_sensitivity(resources) == expected


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


def test_cognitive_validation_covers_package_every_resource_and_materialized_item() -> (
    None
):
    from cmm.domains.cognitive_integration import _validate_cognitive_inputs

    resources = (
        replace(_canonical_resource(), id="resource-1"),
        replace(_canonical_resource(), id="resource-2"),
    )
    extracted_items = (
        KnowledgeItem(
            id="extracted-item-1",
            statement="First extracted observation.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.72, source="extraction"),
            created_at=NOW,
            updated_at=NOW,
        ),
        KnowledgeItem(
            id="extracted-item-2",
            statement="Second extracted observation.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.73, source="extraction"),
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    bundles = (
        KnowledgeBundle(
            id="bundle-1",
            items=(extracted_items[0],),
            created_at=NOW,
        ),
        KnowledgeBundle(
            id="bundle-2",
            items=(extracted_items[1],),
            created_at=NOW,
        ),
    )
    package = KnowledgePackage(
        id="package-1",
        objective="Review health information",
        resources=resources,
        provenance=("resource-1", "resource-2"),
        created_at=NOW,
    )
    recording_rule = _RecordingValidationRule()
    validator = CognitiveValidator((*CognitiveValidator().rules, recording_rule))
    request = _integration_request()

    results = _validate_cognitive_inputs(
        validator=validator,
        request=request,
        package=package,
        resources=resources,
        bundles=bundles,
        now=NOW,
    )

    expected_targets = (package, *resources, *extracted_items)
    expected_context = CognitiveValidationContext(
        actor_id="actor-1",
        domain="domain:health",
        permission_context={
            "effective_permissions": ("resource:read", "resource:infer"),
        },
        require_current_information=False,
        now=NOW,
        metadata={
            "domain_profile_id": "profile-1",
            "domain_composition_id": "composition-1",
        },
    )
    assert tuple(target for target, _ in recording_rule.calls) == expected_targets
    assert all(context == expected_context for _, context in recording_rule.calls)
    assert [result.target_id for result in results] == [
        "package-1",
        "resource-1",
        "resource-2",
        "extracted-item-1",
        "extracted-item-2",
    ]
    assert [result.target_kind for result in results] == [
        "knowledge_package",
        "Resource",
        "Resource",
        "knowledge_item",
        "knowledge_item",
    ]


def test_blocking_privacy_validation_prevents_rule_evaluation_and_hides_content() -> (
    None
):
    from cmm.domains.cognitive_integration import _validate_cognitive_inputs

    untrusted_content = "PRIVATE-CONTENT-MUST-NOT-LEAK"
    resource = replace(
        _canonical_resource(untrusted_content),
        permissions=(
            ResourcePermission(
                allowed_operations=(ResourcePermissionOperation.READ,),
            ),
        ),
    )
    package = KnowledgePackage(
        id="privacy-blocked-package",
        objective="Review health information",
        resources=(resource,),
        provenance=(resource.id,),
        created_at=NOW,
    )
    counting_rule = _CountingReasoningRule()
    assert isinstance(counting_rule, ReasoningRule)

    with pytest.raises(DomainCognitiveIntegrationBlockedError) as error:
        _validate_cognitive_inputs(
            validator=CognitiveValidator(),
            request=_integration_request(),
            package=package,
            resources=(resource,),
            bundles=(),
            now=NOW,
        )
        counting_rule.evaluate(
            ReasoningRuleContext(reasoning_id="privacy-blocked", timestamp=NOW)
        )

    assert counting_rule.evaluations == 0
    assert error.value.details["target_id"] == "privacy-blocked-package"
    assert error.value.details["decision"] == "block"
    assert error.value.details["blocking_finding_codes"] == ("COG_PRIVACY_DENIED",)
    assert untrusted_content not in str(error.value)
    assert untrusted_content not in repr(dict(error.value.details))


def test_missing_mandatory_provenance_blocks_before_rule_evaluation() -> None:
    from cmm.domains.cognitive_integration import _validate_cognitive_inputs

    package = KnowledgePackage(
        id="missing-provenance-package",
        objective="Review health information",
        provenance=(),
        created_at=NOW,
    )
    counting_rule = _CountingReasoningRule()

    with pytest.raises(DomainCognitiveIntegrationBlockedError) as error:
        _validate_cognitive_inputs(
            validator=CognitiveValidator(),
            request=_integration_request(),
            package=package,
            resources=(),
            bundles=(),
            now=NOW,
        )
        counting_rule.evaluate(
            ReasoningRuleContext(reasoning_id="provenance-blocked", timestamp=NOW)
        )

    assert counting_rule.evaluations == 0
    assert error.value.details["target_id"] == "missing-provenance-package"
    assert error.value.details["decision"] == "block"
    assert error.value.details["blocking_finding_codes"] == ("COG_PROVENANCE_MISSING",)


def test_expired_required_current_validation_blocks_before_rule_evaluation() -> None:
    from cmm.domains.cognitive_integration import _validate_cognitive_inputs

    expired_item = KnowledgeItem(
        id="expired-item",
        statement="This observation is no longer current.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=Confidence(0.8, source="extraction"),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.INTERVAL,
            valid_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            valid_until=datetime(2025, 1, 2, tzinfo=timezone.utc),
        ),
        created_at=NOW,
        updated_at=NOW,
    )
    bundle = KnowledgeBundle(
        id="expired-bundle",
        items=(expired_item,),
        created_at=NOW,
    )
    package = KnowledgePackage(
        id="current-information-package",
        objective="Review current health information",
        provenance=("source-1",),
        created_at=NOW,
    )
    counting_rule = _CountingReasoningRule()

    with pytest.raises(DomainCognitiveIntegrationBlockedError) as error:
        _validate_cognitive_inputs(
            validator=CognitiveValidator(),
            request=_integration_request(
                temporal_policy=DomainTemporalPolicy(
                    require_current_information=True,
                )
            ),
            package=package,
            resources=(),
            bundles=(bundle,),
            now=NOW,
        )
        counting_rule.evaluate(
            ReasoningRuleContext(reasoning_id="expired-blocked", timestamp=NOW)
        )

    assert counting_rule.evaluations == 0
    assert error.value.details["target_id"] == "expired-item"
    assert error.value.details["decision"] == "invalidate"
    assert error.value.details["blocking_finding_codes"] == ("COG_TEMPORAL_EXPIRED",)


def test_request_information_validation_remains_evidence_and_rules_may_proceed() -> (
    None
):
    from cmm.domains.cognitive_integration import _validate_cognitive_inputs

    package = KnowledgePackage(
        id="information-gap-package",
        objective="Review health information",
        missing_information=("current blood pressure reading",),
        provenance=("source-1",),
        created_at=NOW,
    )
    validator = CognitiveValidator(
        (*CognitiveValidator().rules, _RequestInformationValidationRule())
    )
    counting_rule = _CountingReasoningRule()

    results = _validate_cognitive_inputs(
        validator=validator,
        request=_integration_request(),
        package=package,
        resources=(),
        bundles=(),
        now=NOW,
    )
    rule_result = counting_rule.evaluate(
        ReasoningRuleContext(reasoning_id="information-gap", timestamp=NOW)
    )

    assert results[0].decision is CognitiveValidationDecision.REQUEST_INFORMATION
    assert "COG_EVIDENCE_INSUFFICIENT" in {
        finding.code for finding in results[0].findings
    }
    assert package.other_knowledge == ()
    assert package.missing_information == ("current blood pressure reading",)
    assert counting_rule.evaluations == 1
    assert rule_result.status is ReasoningRuleResultStatus.APPLIED


def test_escalate_validation_remains_evidence_and_rules_may_proceed() -> None:
    from cmm.domains.cognitive_integration import _validate_cognitive_inputs

    package = KnowledgePackage(
        id="escalated-package",
        objective="Review contradictory health information",
        contradictions=(
            Contradiction(
                id="unresolved-contradiction",
                item_a_id="claim-a",
                item_b_id="claim-b",
                explanation="The health claims disagree.",
                created_at=NOW,
            ),
        ),
        provenance=("source-1",),
        created_at=NOW,
    )
    counting_rule = _CountingReasoningRule()

    results = _validate_cognitive_inputs(
        validator=CognitiveValidator(),
        request=_integration_request(),
        package=package,
        resources=(),
        bundles=(),
        now=NOW,
    )
    counting_rule.evaluate(
        ReasoningRuleContext(reasoning_id="escalated", timestamp=NOW)
    )

    assert results[0].decision is CognitiveValidationDecision.ESCALATE
    assert counting_rule.evaluations == 1


class _MutationSentinelKnowledgeStore(InMemoryKnowledgeStore):
    def _mutation_forbidden(self, *args: object, **kwargs: object) -> object:
        raise AssertionError(
            "the Domain cognitive integrator must not mutate the store"
        )

    save_item = _mutation_forbidden
    delete_item = _mutation_forbidden
    save_evidence = _mutation_forbidden
    delete_evidence = _mutation_forbidden
    save_relation = _mutation_forbidden
    delete_relation = _mutation_forbidden
    save_contradiction = _mutation_forbidden
    delete_contradiction = _mutation_forbidden
    save_bundle = _mutation_forbidden
    delete_bundle = _mutation_forbidden


def _integrator_dependencies() -> dict[str, object]:
    adapter_registry, extractor_registry = _registries(_ExactExistingResourceAdapter())
    return {
        "adapter_registry": adapter_registry,
        "extractor_registry": extractor_registry,
        "knowledge_store": InMemoryKnowledgeStore(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
    }


def _store_with_matching_provenance(
    store: InMemoryKnowledgeStore | None = None,
) -> InMemoryKnowledgeStore:
    value = store or InMemoryKnowledgeStore()
    InMemoryKnowledgeStore.save_item(
        value,
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
    return value


@pytest.mark.parametrize(
    "field",
    (
        "adapter_registry",
        "extractor_registry",
        "knowledge_store",
        "rule_registry",
        "cognitive_validator",
        "rule_selector",
        "rule_executor",
        "clock",
    ),
)
def test_integrator_rejects_invalid_dependencies_with_narrow_error(field: str) -> None:
    """Would fail if constructor wiring admitted a non-canonical dependency."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator

    dependencies = _integrator_dependencies()
    dependencies[field] = object()

    with pytest.raises(DomainCognitiveIntegrationContractError) as error:
        DefaultDomainCognitiveIntegrator(**dependencies)  # type: ignore[arg-type]

    assert error.value.field == field


def test_integrator_keeps_injected_stateful_owners_and_defaults_stateless_helpers() -> (
    None
):
    """Would fail if the integrator hid a store/registry or omitted allowed defaults."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
    from cmm.domains.rule_execution import DefaultDomainRuleExecutor
    from cmm.domains.rule_selection import DefaultDomainRuleSelector

    dependencies = _integrator_dependencies()
    clock = lambda: NOW
    integrator = DefaultDomainCognitiveIntegrator(
        **dependencies,  # type: ignore[arg-type]
        clock=clock,
    )

    assert integrator._adapter_registry is dependencies["adapter_registry"]
    assert integrator._extractor_registry is dependencies["extractor_registry"]
    assert integrator._knowledge_store is dependencies["knowledge_store"]
    assert integrator._rule_registry is dependencies["rule_registry"]
    assert type(integrator._cognitive_validator) is CognitiveValidator
    assert type(integrator._rule_selector) is DefaultDomainRuleSelector
    assert type(integrator._rule_executor) is DefaultDomainRuleExecutor
    assert integrator._clock is clock


def test_global_before_domain_rules_use_canonical_selection_and_execution() -> None:
    """Would fail if Domain specialization could precede a mandatory global rule."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator

    global_rule = _CountingReasoningRule(
        "global.mandatory",
        scope=ReasoningRuleScope.GLOBAL,
        domain_id=None,
        priority=1,
    )
    domain_rule = _CountingReasoningRule(
        "health.required",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:health",
        priority=100,
    )
    rule_registry = InMemoryReasoningRuleRegistry()
    rule_registry.register(domain_rule)
    rule_registry.register(global_rule)
    request = _integration_request()
    request = replace(
        request,
        resources=(_resource_input(),),
        global_mandatory_rules=(global_rule.definition.id,),
        profile=replace(
            request.profile,
            required_rules=(domain_rule.definition.id,),
        ),
    )
    adapter_registry, extractor_registry = _registries(_ExactExistingResourceAdapter())

    result = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=_store_with_matching_provenance(),
        rule_registry=rule_registry,
        clock=lambda: NOW,
    ).integrate(request)

    assert tuple(
        selected.definition.id for selected in result.rule_plan.selected_rules
    ) == ("global.mandatory", "health.required")
    assert result.rule_result.applied_rule_ids == (
        "global.mandatory",
        "health.required",
    )
    assert all(
        type(item) is ReasoningRuleResult for item in result.rule_result.rule_results
    )
    assert all(
        type(item) is CognitiveValidationResult for item in result.validation_results
    )
    assert tuple(item.target_id for item in result.validation_results) == (
        result.knowledge_package.id,
        result.adapted_resources[0].id,
        *(item.id for item in result.extracted_bundles[0].items),
    )
    assert global_rule.evaluations == 1
    assert domain_rule.evaluations == 1
    assert result.presentation_items == ()
    assert result.trace_references.resolution_context_id == "resolution-context-1"
    assert result.trace_references.resolution_result_id == "resolution-result-1"
    assert result.trace_references.composition_id == "composition-1"


def test_integrator_builds_reference_only_domain_trace_links() -> None:
    """Would fail if canonical trace references omitted the knowledge package."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator

    adapter_registry, extractor_registry = _registries(_ExactExistingResourceAdapter())
    request = replace(_integration_request(), resources=(_resource_input(),))

    result = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=_store_with_matching_provenance(),
        rule_registry=InMemoryReasoningRuleRegistry(),
        clock=lambda: NOW,
    ).integrate(request)

    assert (
        result.trace_references.resolution_context_id == request.resolution_context_id
    )
    assert result.trace_references.resolution_result_id == request.resolution_result_id
    assert result.trace_references.composition_id == request.composition.id
    assert result.trace_references.knowledge_package_ids == (
        result.knowledge_package.id,
    )
    assert result.trace_references.cognitive_result_ids == ()
    assert result.trace_references.reasoning_trace_ids == ()


def test_integrator_preserves_blocked_rule_plan_without_evaluating_rules() -> None:
    """Would fail if the integrator bypassed canonical blocked-plan execution."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator

    global_rule = _CountingReasoningRule(
        "global.mandatory",
        scope=ReasoningRuleScope.GLOBAL,
        domain_id=None,
    )
    rule_registry = InMemoryReasoningRuleRegistry()
    rule_registry.register(global_rule)
    request = _integration_request()
    request = replace(
        request,
        resources=(_resource_input(),),
        global_mandatory_rules=(global_rule.definition.id,),
        profile=replace(request.profile, required_rules=("health.missing",)),
    )
    adapter_registry, extractor_registry = _registries(_ExactExistingResourceAdapter())

    result = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=_store_with_matching_provenance(),
        rule_registry=rule_registry,
        clock=lambda: NOW,
    ).integrate(request)

    assert result.rule_plan.status is DomainRuleSelectionStatus.BLOCKED
    assert result.rule_result.status is DomainRuleExecutionStatus.BLOCKED
    assert result.rule_result.blocked_rule_ids == ("health.missing",)
    assert result.rule_result.rule_results == ()
    assert global_rule.evaluations == 0


def test_integrator_leaves_seeded_official_knowledge_store_exactly_unchanged() -> None:
    """Would fail if integration persisted adapted or materialized knowledge."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator

    prior_item = KnowledgeItem(
        id="prior-health-item",
        statement="Existing canonical health knowledge.",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.91, source="existing-evidence"),
        resource_id="resource-1",
        created_at=NOW,
        updated_at=NOW,
    )
    store = InMemoryKnowledgeStore()
    store.save_item(prior_item)
    before = _serialized_store_state(store)
    adapter_registry, extractor_registry = _registries(_ExactExistingResourceAdapter())

    result = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=store,
        rule_registry=InMemoryReasoningRuleRegistry(),
        clock=lambda: NOW,
    ).integrate(replace(_integration_request(), resources=(_resource_input(),)))

    assert prior_item.id in {
        item.id
        for item in (
            *result.knowledge_package.facts,
            *result.knowledge_package.observations,
            *result.knowledge_package.inferences,
            *result.knowledge_package.hypotheses,
            *result.knowledge_package.other_knowledge,
        )
    }
    assert _serialized_store_state(store) == before


def test_integrator_never_calls_a_knowledge_store_mutator() -> None:
    """Would fail on any direct KnowledgeStoreProtocol mutation attempt."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator

    adapter_registry, extractor_registry = _registries(_ExactExistingResourceAdapter())

    result = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=_store_with_matching_provenance(
            _MutationSentinelKnowledgeStore()
        ),
        rule_registry=InMemoryReasoningRuleRegistry(),
        clock=lambda: NOW,
    ).integrate(replace(_integration_request(), resources=(_resource_input(),)))

    assert result.adapted_resources[0].id == "resource-1"
    assert result.extracted_bundles[0].items


def test_integrator_returns_references_consumed_by_real_presentation_planner() -> None:
    """Would fail if integration rendered output or dropped canonical evidence."""
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
    from cmm.domains.presentation_contracts import (
        DomainPresentationItemType,
        DomainPresentationRequest,
    )
    from cmm.domains.presentation_planner import DefaultDomainPresentationPlanner
    from cmm.domains.rule_execution import DefaultDomainRuleExecutor

    rule = _PresentationEvidenceReasoningRule()
    rule_registry = InMemoryReasoningRuleRegistry()
    rule_registry.register(rule)
    presentation = PresentationComposition(
        values={
            "preferred_section_order": (
                "findings",
                "gaps",
                "contradictions",
                "questions",
            )
        },
        provenance={"health": "profile-1"},
    )
    request = _integration_request()
    request = replace(
        request,
        resources=(
            _resource_input(
                _canonical_resource("Which health evidence is missing?"),
            ),
        ),
        composition=replace(request.composition, presentation=presentation),
        profile=replace(
            request.profile,
            required_rules=(rule.definition.id,),
            presentation_policy=DomainPresentationPolicy(
                include_provenance=True,
                preferred_section_order=(
                    "findings",
                    "gaps",
                    "contradictions",
                    "questions",
                ),
            ),
        ),
    )
    adapter_registry, extractor_registry = _registries(_ExactExistingResourceAdapter())

    result = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=_store_with_matching_provenance(),
        rule_registry=rule_registry,
        rule_executor=DefaultDomainRuleExecutor(
            clock=lambda: NOW,
            id_factory=lambda: "canonical-rule-result-1",
        ),
        clock=lambda: NOW,
    ).integrate(request)

    assert request.composition.presentation is not None
    plan = DefaultDomainPresentationPlanner().plan(
        DomainPresentationRequest(
            request_id="presentation-request-1",
            upstream_result_id=result.rule_result.id,
            composition_id=request.composition.id,
            policy_id=request.profile.id,
            presentation=request.composition.presentation,
            policy=request.profile.presentation_policy,
            items=result.presentation_items,
            primary_domain_id=str(request.composition.primary_domain),
            supporting_domain_ids=tuple(
                str(domain) for domain in request.composition.supporting_domains
            ),
        )
    )

    by_type = {item.item_type: item for item in result.presentation_items}
    question_item = next(
        item
        for bundle in result.extracted_bundles
        for item in bundle.items
        if item.kind is KnowledgeKind.QUESTION
    )
    sections = {section.section_id: section.item_refs for section in plan.sections}
    assert plan.item_refs == result.presentation_items
    assert plan.question_refs == (question_item.id,)
    assert question_item.id in sections["questions"]
    assert "canonical-rule-result-1:finding:0" in sections["findings"]
    assert "canonical-rule-result-1:gap:0" in sections["gaps"]
    assert "canonical-contradiction-1" in sections["contradictions"]
    assert by_type[DomainPresentationItemType.QUESTION].confidence == (
        question_item.confidence.value
    )
    assert (
        next(
            item
            for item in plan.item_refs
            if item.item_type is DomainPresentationItemType.QUESTION
        ).confidence
        == question_item.confidence.value
    )
