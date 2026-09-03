"""Phase 10.41 — DefaultDomainAgentRuntimeIntegrator behavior tests (Task 3)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
)
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.agent_runtime_integration import (
    DefaultDomainAgentRuntimeIntegrator,
)
from cmm.domains.agent_runtime_integration_contracts import (
    DomainAgentRuntimeDecisionCode,
    DomainAgentRuntimeIntegrationRequest,
)
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.errors import (
    DomainAgentRuntimeIntegrationBlockedError,
    DomainAgentRuntimeIntegrationContractError,
)
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_contracts import (
    DomainProfileDefinition,
    DomainProfileResolutionRequest,
)
from cmm.domains.profile_resolver import DefaultDomainProfileResolver
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.university.definition import build_university_domain_definition

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


def _execute_boundary(integrator: Any, request: Any) -> Any:
    """Invoke the integration boundary through its public entry point."""
    method = integrator.execute
    return method(request)


# ── Counting boundary adapters (real delegates, observation only) ─────────────


class _CountingResolver:
    """Pass-through counter around the real canonical resolver."""

    def __init__(self, delegate: DefaultDomainResolver) -> None:
        self._delegate = delegate
        self.resolve_calls = 0

    def resolve(self, context: DomainResolutionContext) -> Any:
        self.resolve_calls += 1
        return self._delegate.resolve(context)


class _CountingAgentRuntimeService:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.requests: list[IntegratedAgentExecutionRequest] = []

    def run(self, request: IntegratedAgentExecutionRequest) -> Any:
        self.execute_calls += 1
        self.requests.append(request)
        raise AssertionError("Agent Runtime must not be called in Task 3")

    execute = run


class _CountingCognitiveIntegrator:
    def __init__(self) -> None:
        self.integrate_calls = 0

    def integrate(self, request: DomainCognitiveIntegrationRequest) -> Any:
        self.integrate_calls += 1
        raise AssertionError("Cognitive integration must not run in Task 3")


# ── Fixture helpers ───────────────────────────────────────────────────────────


def _resolution_context(**overrides: object) -> DomainResolutionContext:
    values: dict[str, object] = {
        "id": "res-ctx-1041",
        "user_input": "University examination in Room 101",
        "available_domains": (DomainId("university"),),
        "authorized_domains": (DomainId("university"),),
        "explicit_domains": (DomainId("university"),),
        "active_domains": (),
        "created_at": NOW,
    }
    values.update(overrides)
    return DomainResolutionContext(**values)


def _agent_request() -> IntegratedAgentExecutionRequest:
    return IntegratedAgentExecutionRequest(
        execution_id="exec-1041",
        request_id="req-1041",
        goal_id="goal-1041",
        actor_id="actor-1041",
        owner_actor_id="actor-1041",
        max_autonomy_level=2,
        created_at=NOW,
    )


def _integration_request(
    context: DomainResolutionContext | None = None,
) -> DomainAgentRuntimeIntegrationRequest:
    return DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-1041",
        resolution_context=context if context is not None else _resolution_context(),
        agent_request=_agent_request(),
    )


def _definition_provider() -> Any:
    definitions = (
        build_university_domain_definition(),
        build_health_domain_definition(),
    )

    def provider(resolution: Any) -> tuple[Any, ...]:
        selected = {
            resolution.primary_domain,
            *resolution.supporting_domains,
        }
        return tuple(
            definition for definition in definitions if definition.id in selected
        )

    return provider


def _profile_input_provider() -> Any:
    def provider(
        composition: Any, request: DomainAgentRuntimeIntegrationRequest
    ) -> dict[str, Any]:
        return {
            "request": DomainProfileResolutionRequest(
                id="prof-req-1041",
                primary_domain=composition.primary_domain,
                supporting_domains=composition.supporting_domains,
            ),
            "global_profile": DomainProfileDefinition(
                id="general.profile",
                domain_id=DomainId("general"),
                profile_name="GeneralProfile",
            ),
            "primary_profile": DomainProfileDefinition(
                id="university.profile",
                domain_id=DomainId("university"),
                profile_name="UniversityProfile",
                required_rules=("university.deadline",),
                minimum_confidence=0.75,
                reasoning_depth=DomainReasoningDepth.STANDARD,
                maximum_questions=10,
            ),
            "supporting_profiles": tuple(
                DomainProfileDefinition(
                    id=f"{domain.slug}.profile",
                    domain_id=domain,
                    profile_name=f"{domain.slug.capitalize()}Profile",
                )
                for domain in composition.supporting_domains
            ),
            "overlays": (),
        }

    return provider


def _permission_stack() -> tuple[DomainPermissionResolver, DomainPermissionGate]:
    registry = DomainPermissionRegistry()
    registry.register(
        _university_policy(
            allowed_operations=("documents.read", "other.read", "x.op"),
        )
    )
    permission_resolver = DomainPermissionResolver(registry)
    permission_gate = DomainPermissionGate(permission_resolver, clock=lambda: NOW)
    return permission_resolver, permission_gate


def _build_integrator(
    *,
    resolver: Any | None = None,
    context: DomainResolutionContext | None = None,
    definition_provider: Any | None = None,
) -> tuple[DefaultDomainAgentRuntimeIntegrator, dict[str, Any]]:
    real_resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    counting_resolver = (
        resolver if resolver is not None else _CountingResolver(real_resolver)
    )
    agent_service = _CountingAgentRuntimeService()
    cognitive_integrator = _CountingCognitiveIntegrator()
    permission_resolver, permission_gate = _permission_stack()
    integrator = DefaultDomainAgentRuntimeIntegrator(
        resolver=counting_resolver,
        composer=DefaultDomainComposer(
            id_factory=lambda: "composition-1041", clock=lambda: NOW
        ),
        profile_resolver=DefaultDomainProfileResolver(
            clock=lambda: NOW,
            id_factory=lambda: "prof-res-1041",
            profile_id_factory=lambda: "resolved-profile-1041",
            trace_id_factory=lambda: "prof-trace-1041",
        ),
        permission_resolver=permission_resolver,
        permission_gate=permission_gate,
        cognitive_integrator=cognitive_integrator,
        agent_runtime_service=agent_service,
        domain_definition_provider=(
            definition_provider
            if definition_provider is not None
            else _definition_provider()
        ),
        profile_input_provider=_profile_input_provider(),
        clock=lambda: NOW,
    )
    return integrator, {
        "agent_service": agent_service,
        "cognitive_integrator": cognitive_integrator,
    }


# ── Constructor injection ─────────────────────────────────────────────────────


def test_constructor_rejects_missing_dependencies() -> None:
    with pytest.raises((TypeError, DomainAgentRuntimeIntegrationContractError)):
        DefaultDomainAgentRuntimeIntegrator()  # type: ignore[call-arg]


def test_constructor_rejects_wrong_dependency_types() -> None:
    permission_resolver, permission_gate = _permission_stack()
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        DefaultDomainAgentRuntimeIntegrator(
            resolver="not-a-resolver",
            composer=DefaultDomainComposer(clock=lambda: NOW),
            profile_resolver=DefaultDomainProfileResolver(clock=lambda: NOW),
            permission_resolver=permission_resolver,
            permission_gate=permission_gate,
            cognitive_integrator=None,
            agent_runtime_service=None,
            domain_definition_provider=lambda resolution: (),
            profile_input_provider=lambda composition, request: {},
            clock=lambda: NOW,
        )


# ── Initial resolution ────────────────────────────────────────────────────────


def test_initial_resolution_runs_before_any_phase9_call() -> None:
    integrator, monitors = _build_integrator()
    result = _execute_boundary(integrator, _integration_request())

    assert monitors["agent_service"].execute_calls == 0
    assert monitors["cognitive_integrator"].integrate_calls == 0
    codes = {decision.code for decision in result.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_RESOLVED in codes
    assert result.resolution.primary_domain == DomainId("university")
    assert result.blocked is True
    assert result.agent_result is None
    assert DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_BLOCKED in codes


def test_resolver_called_exactly_once_per_execution() -> None:
    real_resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    counting = _CountingResolver(real_resolver)
    integrator, _ = _build_integrator(resolver=counting)
    _execute_boundary(integrator, _integration_request())
    assert counting.resolve_calls == 1


# ── Blocked resolution fails closed ───────────────────────────────────────────


def test_blocked_resolution_emits_zero_side_effects() -> None:
    # No explicit/authorized evidence: resolver cannot resolve a primary Domain.
    context = _resolution_context(
        id="res-ctx-blocked",
        explicit_domains=(),
        available_domains=(),
        authorized_domains=(),
    )
    integrator, monitors = _build_integrator()
    with pytest.raises(DomainAgentRuntimeIntegrationBlockedError) as exc_info:
        _execute_boundary(integrator, _integration_request(context))

    assert monitors["agent_service"].execute_calls == 0
    assert monitors["cognitive_integrator"].integrate_calls == 0
    details = dict(exc_info.value.details)
    decisions = details.get("decisions", ())
    assert any(
        decision["code"] == DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_BLOCKED.value
        for decision in decisions
    )


# ── Composition ───────────────────────────────────────────────────────────────


def test_composition_uses_canonical_composer_and_selected_definitions() -> None:
    integrator, _ = _build_integrator()
    result = _execute_boundary(integrator, _integration_request())

    assert result.composition.primary_domain == DomainId("university")
    assert result.composition.supporting_domains == ()
    codes = {decision.code for decision in result.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_COMPOSED in codes
    assert result.composition.resolution_id == result.resolution.id


def test_missing_selected_definitions_fail_closed() -> None:
    integrator, monitors = _build_integrator(
        definition_provider=lambda resolution: (),
    )
    with pytest.raises(DomainAgentRuntimeIntegrationBlockedError):
        _execute_boundary(integrator, _integration_request())
    assert monitors["agent_service"].execute_calls == 0


# ── Profile resolution ────────────────────────────────────────────────────────


def test_profile_comes_from_existing_profile_resolver() -> None:
    integrator, _ = _build_integrator()
    result = _execute_boundary(integrator, _integration_request())

    assert result.profile.primary_domain == DomainId("university")
    assert result.profile.supporting_domains == ()
    assert result.profile.required_rules == ("university.deadline",)
    assert result.profile.minimum_confidence == 0.75
    codes = {decision.code for decision in result.decisions}
    assert DomainAgentRuntimeDecisionCode.PROFILE_RESOLVED in codes


def test_profile_matches_direct_resolver_call() -> None:
    integrator, _ = _build_integrator()
    result = _execute_boundary(integrator, _integration_request())

    direct_resolver = DefaultDomainProfileResolver(
        clock=lambda: NOW,
        id_factory=lambda: "prof-res-1041",
        profile_id_factory=lambda: "resolved-profile-1041",
        trace_id_factory=lambda: "prof-trace-1041",
    )
    direct = direct_resolver.resolve(
        request=DomainProfileResolutionRequest(
            id="prof-req-1041",
            primary_domain=DomainId("university"),
            supporting_domains=(),
        ),
        global_profile=DomainProfileDefinition(
            id="general.profile",
            domain_id=DomainId("general"),
            profile_name="GeneralProfile",
        ),
        primary_profile=DomainProfileDefinition(
            id="university.profile",
            domain_id=DomainId("university"),
            profile_name="UniversityProfile",
            required_rules=("university.deadline",),
            minimum_confidence=0.75,
            reasoning_depth=DomainReasoningDepth.STANDARD,
            maximum_questions=10,
        ),
        supporting_profiles=(),
        overlays=(),
    )
    assert result.profile == direct.profile


# ── Task 4: Phase 10.40 cognitive projection into the Phase 9 seam ────────────

PROJECTION_NAMESPACE = "domain_intelligence"

FORBIDDEN_PROJECTION_KEYS = (
    "chain_of_thought",
    "reasoning_text",
    "internal_reasoning",
    "scratchpad",
    "hidden_trace",
    "raw_provider_payload",
    "knowledge_store",
    "memory_store",
)

REQUIRED_PROJECTION_KEYS = (
    "domain_resolution_context_id",
    "domain_resolution_result_id",
    "domain_composition_id",
    "primary_domain",
    "supporting_domains",
    "resolved_profile_id",
    "knowledge_package_id",
    "adapted_resource_ids",
    "presentation_reference_ids",
    "domain_cognitive_request_id",
)


def _cognitive_fixture() -> tuple[Any, tuple[Any, ...]]:
    from cmm.cognitive import (
        CognitiveValidator,
        Confidence,
        ExistingResourceAdapter,
        InMemoryKnowledgeStore,
        KnowledgeExtractorRegistry,
        KnowledgeItem,
        KnowledgeKind,
        MappingResourceAdapter,
        PlainTextKnowledgeExtractor,
        PlainTextResourceAdapter,
        Resource,
        ResourceAdapterRegistry,
        ResourceInput,
        ResourceIntegrityStatus,
        ResourceKind,
        ResourcePermission,
        ResourcePermissionOperation,
        ResourceProvenance,
        ResourceSourceKind,
        ResourceTemporalScope,
        SensitivityLevel,
    )
    from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
    from cmm.domains.cognitive_integration_contracts import (
        DomainCognitiveResourceInput,
    )
    from cmm.domains.resource_contracts import (
        DomainResourceContext,
        DomainResourceDefinition,
    )
    from cmm.domains.resource_resolver import DefaultDomainResourceResolver
    from cmm.domains.rule_catalog import build_initial_reasoning_rule_catalog
    from cmm.domains.rule_execution import DefaultDomainRuleExecutor
    from cmm.domains.rule_selection import DefaultDomainRuleSelector

    valid_from = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    valid_until = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)
    observed_at = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
    last_verified_at = datetime(2026, 9, 2, 11, 0, tzinfo=timezone.utc)

    res_definition = DomainResourceDefinition(
        id="def-subject-guide-1041",
        kind="subject_guide",
        domain_id=DomainId("university"),
        adapter="existing_resource",
        default_permissions=("resource.read",),
        default_sensitivity="internal",
    )
    res_context_item = DomainResourceContext(
        resource_id="res-exam-guide-1041",
        kind="subject_guide",
        provenance=("academic-registry-01",),
        permissions=("resource.read",),
        temporal_scope={
            "valid_from": valid_from,
            "valid_until": valid_until,
            "observed_at": observed_at,
            "last_verified_at": last_verified_at,
        },
        sensitivity="internal",
    )
    resource_resolver = DefaultDomainResourceResolver(
        id_factory=lambda: "res-res-1041", clock=lambda: NOW
    )
    resource_resolution = resource_resolver.resolve(
        context=res_context_item,
        definitions=(res_definition,),
        requested_domains=(DomainId("university"),),
        request_permissions=("resource.read",),
    )
    binding = resource_resolution.bindings[0]

    canonical_resource = Resource(
        id=binding.resource_id,
        domain="domain:university",
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.LOCAL_FILE,
        content=("The university examination is scheduled for October 15 in Room 101."),
        provenance=ResourceProvenance(
            source_id=binding.resource_id,
            source_type=ResourceSourceKind.LOCAL_FILE,
            retrieved_at=NOW,
        ),
        reliability=Confidence(0.9),
        temporal_scope=ResourceTemporalScope(),
        sensitivity=SensitivityLevel.INTERNAL,
        permissions=(
            ResourcePermission(
                allowed_operations=(
                    ResourcePermissionOperation.READ,
                    ResourcePermissionOperation.INFER,
                )
            ),
        ),
        integrity=ResourceIntegrityStatus.VERIFIED,
    )
    resource_input = DomainCognitiveResourceInput(
        resolution=resource_resolution,
        binding=binding,
        source=ResourceInput(
            id=binding.resource_id,
            payload=canonical_resource,
            source_kind=ResourceSourceKind.LOCAL_FILE,
            sensitivity=SensitivityLevel.INTERNAL,
        ),
        extractor_name="plain_text",
    )

    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(PlainTextResourceAdapter())
    adapter_registry.register(MappingResourceAdapter())
    adapter_registry.register(ExistingResourceAdapter())
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())

    knowledge_store = InMemoryKnowledgeStore()
    knowledge_store.save_item(
        KnowledgeItem(
            id="prior-fact-1041",
            statement=(
                "All registered students must take examinations in designated rooms."
            ),
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.61, source="academic-handbook"),
            resource_id=binding.resource_id,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    cognitive_integrator = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=knowledge_store,
        rule_registry=build_initial_reasoning_rule_catalog(),
        cognitive_validator=CognitiveValidator(),
        rule_selector=DefaultDomainRuleSelector(
            clock=lambda: NOW, id_factory=lambda: "domain-rule-plan-1041"
        ),
        rule_executor=DefaultDomainRuleExecutor(
            clock=lambda: NOW, id_factory=lambda: "domain-rule-execution-1041"
        ),
        clock=lambda: NOW,
    )
    return cognitive_integrator, (resource_input,)


def _build_cognitive_integrator_case() -> tuple[Any, dict[str, Any], Any]:
    cognitive_integrator, cognitive_resources = _cognitive_fixture()
    real_resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    agent_service = _CountingAgentRuntimeService()
    permission_resolver, permission_gate = _permission_stack()
    integrator = DefaultDomainAgentRuntimeIntegrator(
        resolver=_CountingResolver(real_resolver),
        composer=DefaultDomainComposer(
            id_factory=lambda: "composition-1041", clock=lambda: NOW
        ),
        profile_resolver=DefaultDomainProfileResolver(
            clock=lambda: NOW,
            id_factory=lambda: "prof-res-1041",
            profile_id_factory=lambda: "resolved-profile-1041",
            trace_id_factory=lambda: "prof-trace-1041",
        ),
        permission_resolver=permission_resolver,
        permission_gate=permission_gate,
        cognitive_integrator=cognitive_integrator,
        agent_runtime_service=agent_service,
        domain_definition_provider=_definition_provider(),
        profile_input_provider=_profile_input_provider(),
        clock=lambda: NOW,
    )
    context = _resolution_context(permissions=("resource.read",))
    request = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-1041",
        resolution_context=context,
        agent_request=_agent_request(),
        cognitive_resources=cognitive_resources,
    )
    return integrator, {"agent_service": agent_service}, request


def test_cognitive_integration_runs_before_agent_runtime_service() -> None:
    integrator, monitors, request = _build_cognitive_integrator_case()
    result = _execute_boundary(integrator, request)

    assert monitors["agent_service"].execute_calls == 0
    assert result.cognitive_result is not None
    codes = {decision.code for decision in result.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_COGNITIVE_BOUND in codes
    assert result.cognitive_result.knowledge_package.id is not None


def test_cognitive_projection_is_deterministic() -> None:
    projections = []
    for _ in range(2):
        integrator, _, request = _build_cognitive_integrator_case()
        prepared = integrator._prepare(request)
        cognitive_result = integrator._cognitive_integrator.integrate(
            integrator._cognitive_request(request, prepared)
        )
        projections.append(
            dict(
                integrator._project_cognitive_context(
                    incoming_context={},
                    resolution_context=request.resolution_context,
                    prepared=prepared,
                    cognitive_result=cognitive_result,
                )[PROJECTION_NAMESPACE]
            )
        )
    assert projections[0] == projections[1]
    for key in REQUIRED_PROJECTION_KEYS:
        assert key in projections[0], key


def test_cognitive_projection_contains_no_forbidden_keys() -> None:
    integrator, _, request = _build_cognitive_integrator_case()
    prepared = integrator._prepare(request)
    cognitive_result = integrator._cognitive_integrator.integrate(
        integrator._cognitive_request(request, prepared)
    )
    projection = integrator._project_cognitive_context(
        incoming_context={},
        resolution_context=request.resolution_context,
        prepared=prepared,
        cognitive_result=cognitive_result,
    )
    flat = str(projection).lower()
    for token in FORBIDDEN_PROJECTION_KEYS:
        assert token not in flat, token


def test_cognitive_projection_preserves_caller_context_and_fails_closed_on_collision() -> (
    None
):
    integrator, _, request = _build_cognitive_integrator_case()
    prepared = integrator._prepare(request)
    cognitive_result = integrator._cognitive_integrator.integrate(
        integrator._cognitive_request(request, prepared)
    )

    merged = integrator._project_cognitive_context(
        incoming_context={"caller_note": {"surface": "api"}},
        resolution_context=request.resolution_context,
        prepared=prepared,
        cognitive_result=cognitive_result,
    )
    assert merged["caller_note"] == {"surface": "api"}
    assert PROJECTION_NAMESPACE in merged

    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        integrator._project_cognitive_context(
            incoming_context={PROJECTION_NAMESPACE: {"different": "caller-data"}},
            resolution_context=request.resolution_context,
            prepared=prepared,
            cognitive_result=cognitive_result,
        )

    identical = dict(merged[PROJECTION_NAMESPACE])
    preserved = integrator._project_cognitive_context(
        incoming_context={PROJECTION_NAMESPACE: identical},
        resolution_context=request.resolution_context,
        prepared=prepared,
        cognitive_result=cognitive_result,
    )
    assert preserved[PROJECTION_NAMESPACE] == identical


def test_specialized_agent_request_preserves_canonical_fields() -> None:
    integrator, _, request = _build_cognitive_integrator_case()
    prepared = integrator._prepare(request)
    cognitive_result = integrator._cognitive_integrator.integrate(
        integrator._cognitive_request(request, prepared)
    )
    projected = integrator._project_cognitive_context(
        incoming_context=request.agent_request.cognitive_context,
        resolution_context=request.resolution_context,
        prepared=prepared,
        cognitive_result=cognitive_result,
    )
    specialized = integrator._specialized_agent_request(
        request.agent_request, projected
    )

    assert specialized.execution_id == request.agent_request.execution_id
    assert specialized.request_id == request.agent_request.request_id
    assert specialized.goal_id == request.agent_request.goal_id
    assert specialized.actor_id == request.agent_request.actor_id
    assert specialized.owner_actor_id == request.agent_request.owner_actor_id
    assert specialized.max_autonomy_level == request.agent_request.max_autonomy_level
    assert specialized.operations == request.agent_request.operations
    assert (
        specialized.cognitive_context[PROJECTION_NAMESPACE]
        == projected[PROJECTION_NAMESPACE]
    )


# ── Task 5: permission narrowing and canonical approval semantics ─────────────


def _university_policy(**overrides: object) -> Any:
    from cmm.agent_runtime.agent_security_enums import SensitivityLevel
    from cmm.domains.permission_contracts import DomainPermissionPolicy

    values: dict[str, object] = {
        "policy_id": "perm-policy-uni-1041",
        "domain_id": "domain:university",
        "version": "1.0.0",
        "allowed_capabilities": (
            PermissionCapability.OPERATION_EXECUTE,
            PermissionCapability.KNOWLEDGE_READ,
        ),
        "allowed_sensitivity_levels": (
            SensitivityLevel.PUBLIC,
            SensitivityLevel.INTERNAL,
        ),
    }
    values.update(overrides)
    return DomainPermissionPolicy(**values)


def _agent_permission_context(**overrides: object) -> Any:
    from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
    from cmm.agent_runtime.agent_security_enums import SensitivityLevel

    values: dict[str, object] = {
        "id": "perm-ctx-1041",
        "agent_id": "agent-1041",
        "agent_run_id": "run-1041",
        "goal_id": "goal-1041",
        "actor_id": "actor-1041",
        "owner_actor_id": "actor-1041",
        "allowed_domains": ("documents",),
        "allowed_resources": ("doc-1",),
        "allowed_operations": ("other.read",),
        "allowed_sensitivity_levels": (SensitivityLevel.INTERNAL,),
        "maximum_autonomy_level": 2,
        "created_at": NOW,
    }
    values.update(overrides)
    return AgentPermissionContext(**values)


def _build_permission_integrator(
    policies: tuple[Any, ...],
    *,
    permission_context: Any | None = None,
    with_operation: bool = False,
    context: Any | None = None,
    scoring_policy: Any | None = None,
) -> tuple[Any, dict[str, Any], Any]:
    from dataclasses import replace as _replace

    from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
    from cmm.domains.resolver_contracts import DomainScoringPolicy as _ScoringPolicy

    scoring = scoring_policy
    if scoring is None:
        scoring = _ScoringPolicy(max_supporting_domains=1, supporting_margin=100.0)

    registry = DomainPermissionRegistry()
    for policy in policies:
        registry.register(policy)
    permission_resolver = DomainPermissionResolver(registry)
    permission_gate = DomainPermissionGate(permission_resolver, clock=lambda: NOW)

    real_resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        scoring_policy=scoring,
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    agent_service = _CountingAgentRuntimeService()
    integrator = DefaultDomainAgentRuntimeIntegrator(
        resolver=_CountingResolver(real_resolver),
        composer=DefaultDomainComposer(
            id_factory=lambda: "composition-1041", clock=lambda: NOW
        ),
        profile_resolver=DefaultDomainProfileResolver(
            clock=lambda: NOW,
            id_factory=lambda: "prof-res-1041",
            profile_id_factory=lambda: "resolved-profile-1041",
            trace_id_factory=lambda: "prof-trace-1041",
        ),
        permission_resolver=permission_resolver,
        permission_gate=permission_gate,
        cognitive_integrator=_CountingCognitiveIntegrator(),
        agent_runtime_service=agent_service,
        domain_definition_provider=_definition_provider(),
        profile_input_provider=_profile_input_provider(),
        clock=lambda: NOW,
    )
    agent_request = _agent_request()
    if permission_context is not None:
        agent_request = _replace(agent_request, permission_context=permission_context)
    if with_operation:
        agent_request = _replace(
            agent_request,
            operations=(
                AgentOperationRequest(
                    id="op-1041",
                    agent_run_id="run-1041",
                    workflow_id="workflow-1041",
                    task_id="task-1041",
                    operation_name="documents.read",
                    idempotency_key="idem-1041",
                    created_at="2026-09-03T12:00:00+00:00",
                ),
            ),
        )
    request = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-1041",
        resolution_context=(context if context is not None else _resolution_context()),
        agent_request=agent_request,
    )
    return integrator, {"agent_service": agent_service}, request


def test_domain_deny_blocks_execution_without_agent_runtime_call() -> None:
    integrator, monitors, request = _build_permission_integrator(
        (
            _university_policy(
                prohibited_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
            ),
        ),
        with_operation=True,
    )
    result = _execute_boundary(integrator, request)

    assert monitors["agent_service"].execute_calls == 0
    assert result.blocked is True
    assert result.agent_result is None
    denied = next(
        decision
        for decision in result.decisions
        if decision.code is DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_BLOCKED
    )
    assert "domain_permission_denied" in denied.reason_codes


def test_domain_approval_required_records_decision_without_manufacturing_evidence() -> (
    None
):
    integrator, monitors, request = _build_permission_integrator(
        (
            _university_policy(
                allowed_operations=("documents.read",),
                approval_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
            ),
        ),
        with_operation=True,
    )
    result = _execute_boundary(integrator, request)

    assert monitors["agent_service"].execute_calls == 0
    codes = {decision.code for decision in result.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_APPROVAL_REQUIRED in codes
    # Phase 10.41 never manufactures approval evidence.
    for decision in result.decisions:
        assert not any("approval_valid" in code for code in decision.reason_codes)


def test_domain_allow_cannot_widen_agent_permission_context() -> None:
    incoming = _agent_permission_context(allow_delegation=True)
    integrator, _, request = _build_permission_integrator(
        (
            # Domain ALLOWs documents.read, which the Agent context lacks.
            _university_policy(allowed_operations=("documents.read",)),
        ),
        permission_context=incoming,
    )
    _execute_boundary(integrator, request)

    prepared = integrator._prepare(request)
    resolution = integrator._resolve_domain_permissions(request, prepared)
    narrowed = integrator._narrow_permission_context(
        incoming,
        resolution.domain_policies,
        primary_domain_id=str(integrator._prepare(request).composition.primary_domain),
    )
    # Domain ALLOW never adds an operation absent from the Agent allowlist.
    assert "documents.read" not in narrowed.allowed_operations
    assert set(narrowed.allowed_operations) <= set(incoming.allowed_operations)
    assert narrowed.allow_delegation is True


def test_supporting_domain_prohibition_wins_over_primary_allow() -> None:
    incoming = _agent_permission_context(
        allowed_domains=("documents", "health"),
        allowed_operations=("documents.read", "x.op"),
    )
    primary_policy = _university_policy(
        allowed_operations=("documents.read", "x.op"),
    )
    health_policy = _university_policy(
        policy_id="perm-policy-health-1041",
        domain_id="domain:health",
        allowed_operations=("x.op", "health.read"),
        prohibited_operations=("x.op",),
    )
    from cmm.domains.resolution_contracts import DomainResolutionResource

    context = _resolution_context(
        id="res-ctx-support-1041",
        user_input="University examination with medical accommodation",
        available_domains=(DomainId("university"), DomainId("health")),
        authorized_domains=(DomainId("university"), DomainId("health")),
        explicit_domains=(DomainId("university"),),
        resources=(
            DomainResolutionResource(
                id="res-ref-support-1041",
                resource_type="document",
                source="user",
                domain_ids=(DomainId("health"),),
            ),
        ),
    )
    integrator, _, request = _build_permission_integrator(
        (primary_policy, health_policy),
        permission_context=incoming,
        context=context,
    )
    result = _execute_boundary(integrator, request)

    assert result.composition.supporting_domains == (DomainId("health"),)
    resolution = integrator._resolve_domain_permissions(
        request, integrator._prepare(request)
    )
    assert any(
        policy.domain_id == "domain:health" for policy in resolution.domain_policies
    )
    narrowed = integrator._narrow_permission_context(
        incoming,
        resolution.domain_policies,
        primary_domain_id=str(integrator._prepare(request).composition.primary_domain),
    )
    assert "x.op" not in narrowed.allowed_operations
    assert "documents.read" in narrowed.allowed_operations


def test_narrowed_permission_context_is_never_wider_than_incoming() -> None:
    from cmm.agent_runtime.agent_security_enums import SensitivityLevel

    incoming = _agent_permission_context(
        allowed_operations=("documents.read",),
        allowed_sensitivity_levels=(
            SensitivityLevel.INTERNAL,
            SensitivityLevel.CONFIDENTIAL,
        ),
        allow_memory_write=True,
    )
    integrator, _, request = _build_permission_integrator(
        (
            _university_policy(
                allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
                allow_memory_write=False,
            ),
        ),
        permission_context=incoming,
    )
    _execute_boundary(integrator, request)

    resolution = integrator._resolve_domain_permissions(
        request, integrator._prepare(request)
    )
    narrowed = integrator._narrow_permission_context(
        incoming,
        resolution.domain_policies,
        primary_domain_id=str(integrator._prepare(request).composition.primary_domain),
    )
    assert narrowed.allowed_sensitivity_levels == (SensitivityLevel.INTERNAL,)
    assert narrowed.allow_memory_write is False
    assert narrowed.allowed_operations == ("documents.read",)


def test_stale_approval_is_not_reused_as_authority() -> None:
    from dataclasses import replace as _replace

    integrator, monitors, request = _build_permission_integrator(
        (
            _university_policy(
                allowed_operations=("documents.read",),
                approval_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
            ),
        ),
        with_operation=True,
    )
    stale_request = _replace(
        request,
        agent_request=_replace(
            request.agent_request,
            available_approval_ids=("approval-stale-1041",),
            metadata={"requires_approval": True, "domain_approval_satisfied": True},
        ),
    )
    result = _execute_boundary(integrator, stale_request)

    assert monitors["agent_service"].execute_calls == 0
    codes = {decision.code for decision in result.decisions}
    # The stale caller metadata boolean is not authority: the canonical
    # approval-required decision stands.
    assert DomainAgentRuntimeDecisionCode.DOMAIN_APPROVAL_REQUIRED in codes
    assert "approval-stale-1041" not in str(result.decisions)


# ── Task 6: Domain autonomy ceiling without widening authority ────────────────


def _autonomy_policy(maximum_autonomy_level: int | None) -> Any:
    from cmm.domains.permission_contracts import DomainAutonomyLimits

    return _university_policy(
        autonomy_limits=DomainAutonomyLimits(
            maximum_autonomy_level=maximum_autonomy_level
        ),
    )


def test_domain_autonomy_lowers_incoming_ceiling() -> None:
    from dataclasses import replace as _replace

    integrator, _, request = _build_permission_integrator((_autonomy_policy(0),))
    incoming = _replace(request.agent_request, max_autonomy_level=2)
    specialized, decision = integrator._apply_autonomy_ceiling(
        incoming, (_autonomy_policy(0),)
    )

    assert specialized.max_autonomy_level == 0
    assert decision is not None
    assert decision.code is DomainAgentRuntimeDecisionCode.DOMAIN_AUTONOMY_RESTRICTED


def test_domain_autonomy_cannot_raise_incoming_ceiling() -> None:
    from dataclasses import replace as _replace

    integrator, _, request = _build_permission_integrator((_autonomy_policy(3),))
    incoming = _replace(request.agent_request, max_autonomy_level=1)
    specialized, decision = integrator._apply_autonomy_ceiling(
        incoming, (_autonomy_policy(3),)
    )

    assert specialized.max_autonomy_level == 1
    assert decision is None


def test_domain_autonomy_absent_limit_preserves_incoming_value() -> None:
    from dataclasses import replace as _replace

    integrator, _, request = _build_permission_integrator((_university_policy(),))
    incoming = _replace(request.agent_request, max_autonomy_level=2)
    specialized, decision = integrator._apply_autonomy_ceiling(
        incoming, (_university_policy(),)
    )

    assert specialized.max_autonomy_level == 2
    assert decision is None


def test_autonomy_ceiling_emits_restriction_decision_in_execution() -> None:
    integrator, monitors, request = _build_permission_integrator((_autonomy_policy(0),))
    result = _execute_boundary(integrator, request)

    assert monitors["agent_service"].execute_calls == 0
    codes = {decision.code for decision in result.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_AUTONOMY_RESTRICTED in codes


def test_autonomy_ceiling_narrows_permission_context_level() -> None:
    incoming = _agent_permission_context(
        allowed_operations=("documents.read",),
        maximum_autonomy_level=2,
    )
    integrator, _, request = _build_permission_integrator(
        (_autonomy_policy(0),),
        permission_context=incoming,
    )
    _execute_boundary(integrator, request)

    resolution = integrator._resolve_domain_permissions(
        request, integrator._prepare(request)
    )
    narrowed = integrator._narrow_permission_context(
        incoming,
        resolution.domain_policies,
        primary_domain_id="domain:university",
    )
    assert narrowed.maximum_autonomy_level == 0
