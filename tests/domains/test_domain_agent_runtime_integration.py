"""Phase 10.41 — DefaultDomainAgentRuntimeIntegrator behavior tests (Task 3)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
)
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
            "supporting_profiles": (),
            "overlays": (),
        }

    return provider


def _permission_stack() -> tuple[DomainPermissionResolver, DomainPermissionGate]:
    permission_resolver = DomainPermissionResolver(DomainPermissionRegistry())
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
