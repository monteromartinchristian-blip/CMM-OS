"""Phase 11.2 — canonical domain router tests.

``CanonicalDomainRouter`` is an orchestration facade over Domain Intelligence.
It calls the canonical ``DefaultDomainResolver`` for selection and the canonical
``DomainPermissionResolver`` for permission evidence; it reimplements no scoring
weight, fallback rule, ambiguity rule or permission semantic.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainResolutionStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import DomainResolutionSignal
from cmm.domains.resolver import DefaultDomainResolver
from cmm.orchestration.contracts import (
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationRequest,
    ResolvedContext,
)
from cmm.orchestration.domain_router import (
    CanonicalDomainRouter,
    DomainRouter,
)
from cmm.orchestration.errors import DomainRoutingError

DOMAIN_ROUTER_MODULE = (
    Path(__file__).resolve().parents[2] / "cmm" / "orchestration" / "domain_router.py"
)

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)
GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")
UNIVERSITY = DomainId(slug="university")

FORBIDDEN_OWNER_CLASSES = (
    "DomainRegistry",
    "DomainResolver",
    "DefaultDomainResolver",
    "DomainPermissionRegistry",
    "DomainPermissionResolver",
    "DomainProfileRegistry",
    "DefaultCrossDomainEngine",
    "DomainComposer",
    "DomainCandidateScorer",
)


# ── Canonical fixtures ───────────────────────────────────────────────────────


def _definition(slug: str, *, kind: DomainKind = DomainKind.CORE) -> DomainDefinition:
    return DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=slug.title(),
        version="1.0.0",
        kind=kind,
        description=f"{slug} domain",
        manifest_id=f"manifest:{slug}:1.0.0",
    )


def _domain_registry(*slugs: str) -> DomainRegistry:
    registry = DomainRegistry()
    for slug in slugs:
        registry.register(_definition(slug))
        registry.enable(f"domain:{slug}")
    return registry


def _signal(slug: str, *, value: str, confidence: float) -> DomainResolutionSignal:
    return DomainResolutionSignal(
        kind="intent",
        source="phase11.2-test",
        value=value,
        domain_ids=(DomainId(slug=slug),),
        confidence=confidence,
        provenance={"source": "phase11.2-test"},
    )


def _resolver() -> DefaultDomainResolver:
    return DefaultDomainResolver(
        fallback_domain=GENERAL,
        clock=lambda: NOW,
        id_factory=lambda: "resolution-1",
    )


def _builder() -> DomainResolutionContextBuilder:
    return DomainResolutionContextBuilder(
        clock=lambda: NOW,
        id_factory=lambda: "context-1",
    )


def _router(**overrides: object) -> CanonicalDomainRouter:
    payload: dict[str, object] = {
        "resolver": _resolver(),
        "registry": _domain_registry("general", "health", "university"),
        "context_builder": _builder(),
    }
    payload.update(overrides)
    return CanonicalDomainRouter(**payload)  # type: ignore[arg-type]


def _request(**overrides: object) -> OrchestrationRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "user_id": "user-1",
        "channel": OrchestrationChannel.CONVERSATION,
        "session_id": "session-1",
    }
    values.update(overrides)
    return OrchestrationRequest(**values)  # type: ignore[arg-type]


def _base_context() -> ResolvedContext:
    return ResolvedContext(request_id="request-1", stage="base")


def _intent(kind: IntentKind = IntentKind.QUESTION) -> IntentResolution:
    return IntentResolution(
        intent=kind, needs_clarification=False, source_kind="structured_input"
    )


def _route_domain(
    router: CanonicalDomainRouter, request: OrchestrationRequest, **kwargs
):
    intent = kwargs.pop("intent", _intent())
    return router.route_domain(request, intent, _base_context())


# ── Delegation ───────────────────────────────────────────────────────────────


def test_router_satisfies_its_protocol() -> None:
    assert isinstance(_router(), DomainRouter)


def test_router_requires_real_inputs() -> None:
    router = _router()

    with pytest.raises(TypeError):
        router.route_domain(object(), _intent(), _base_context())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        router.route_domain(_request(), object(), _base_context())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        router.route_domain(_request(), _intent(), object())  # type: ignore[arg-type]


def test_router_delegates_to_the_canonical_domain_resolver() -> None:
    class _RecordingResolver:
        def __init__(self, inner: DefaultDomainResolver) -> None:
            self._inner = inner
            self.calls = 0
            self.last_context = None

        def resolve(self, context):  # type: ignore[no-untyped-def]
            self.calls += 1
            self.last_context = context
            return self._inner.resolve(context)

    recorder = _RecordingResolver(_resolver())
    router = _router(resolver=recorder)

    decision = _route_domain(router, _request(input={"question": "What changed?"}))

    assert recorder.calls == 1
    assert decision.status
    assert recorder.last_context is not None
    assert recorder.last_context.intent == IntentKind.QUESTION.value


def test_router_fails_closed_when_the_canonical_resolver_raises() -> None:
    class _BrokenResolver:
        def resolve(self, context):  # type: ignore[no-untyped-def]
            raise RuntimeError("resolver unavailable")

    router = _router(resolver=_BrokenResolver())

    with pytest.raises(DomainRoutingError) as captured:
        _route_domain(router, _request(input={"question": "What changed?"}))

    assert captured.value.category == "domain"


def test_router_rejects_a_foreign_resolver_result() -> None:
    class _ForeignResolver:
        def resolve(self, context):  # type: ignore[no-untyped-def]
            return {"status": "resolved"}

    router = _router(resolver=_ForeignResolver())

    with pytest.raises(DomainRoutingError):
        _route_domain(router, _request(input={"question": "What changed?"}))


# ── Canonical selection ──────────────────────────────────────────────────────


def test_simple_question_resolves_to_the_general_domain() -> None:
    decision = _route_domain(_router(), _request(input={"question": "What changed?"}))

    assert decision.status == DomainResolutionStatus.INSUFFICIENT_INFORMATION.value
    assert decision.primary_domain == "domain:general"
    assert decision.needs_clarification is False
    assert decision.fallback_used is True


def test_primary_and_supporting_domains_are_preserved() -> None:
    request = _request(
        context={
            "domain_signals": [
                {"value": "medical", "domains": ["health"], "confidence": 0.9},
                {"value": "study", "domains": ["university"], "confidence": 0.6},
            ]
        }
    )

    decision = _route_domain(_router(), request)

    assert decision.status == DomainResolutionStatus.RESOLVED.value
    assert decision.primary_domain == "domain:health"
    assert decision.supporting_domains == ("domain:university",)
    assert decision.trace_refs


def test_ambiguous_domains_require_clarification() -> None:
    request = _request(context={"explicit_domains": ["health", "university"]})

    decision = _route_domain(_router(), request)

    assert decision.status == DomainResolutionStatus.AMBIGUOUS.value
    assert decision.needs_clarification is True
    assert set(decision.ambiguous_domains) == {"domain:health", "domain:university"}
    assert "DOMAIN_AMBIGUOUS_SCORE" in decision.reason_codes
    assert decision.primary_domain is None
    assert decision.supporting_domains == ()
    assert decision.profile_id is None


def test_blocked_canonical_resolution_is_not_a_clarification() -> None:
    request = _request(
        context={
            "domain_signals": [
                {"value": "medical", "domains": ["health"], "confidence": 0.9},
            ]
        }
    )
    registry = _domain_registry("general")
    router = _router(registry=registry)

    decision = _route_domain(router, request)

    assert decision.status == DomainResolutionStatus.BLOCKED.value
    assert decision.needs_clarification is False
    assert decision.primary_domain is None


def test_no_domain_candidate_requires_clarification() -> None:
    router = _router(registry=_domain_registry())

    decision = _route_domain(router, _request(input={"question": "What changed?"}))

    assert decision.status == DomainResolutionStatus.UNSUPPORTED.value
    assert decision.needs_clarification is True
    assert decision.primary_domain is None


def test_profile_reference_comes_from_the_canonical_profile_registry() -> None:
    profiles = InMemoryDomainProfileRegistry()
    profiles.register(
        DomainProfileDefinition(
            id="health.default",
            domain_id=HEALTH,
            profile_name="Health",
        )
    )
    request = _request(
        context={
            "domain_signals": [
                {"value": "medical", "domains": ["health"], "confidence": 0.9},
            ]
        }
    )

    decision = _route_domain(_router(profile_registry=profiles), request)

    assert decision.profile_id == "health.default"


def test_router_ignores_caller_asserted_domain_availability() -> None:
    """The caller cannot widen the domain set: availability is canonical."""

    request = _request(
        input={"question": "What changed?"},
        context={
            "available_domains": ["health"],
            "authorized_domains": ["health"],
            "domain_signals": [
                {"value": "medical", "domains": ["health"], "confidence": 0.9},
            ],
        },
    )

    decision = _route_domain(_router(registry=_domain_registry("general")), request)

    assert decision.primary_domain is None
    assert decision.status == DomainResolutionStatus.BLOCKED.value


# ── Canonical permission evidence ────────────────────────────────────────────


def _permission_router(
    policy: DomainPermissionPolicy,
) -> CanonicalDomainRouter:
    registry = DomainPermissionRegistry()
    registry.register(policy)
    return _router(
        permission_registry=registry,
        permission_resolver=DomainPermissionResolver(
            registry, trust_policy_lookup=None
        ),
    )


def _command_request(**overrides: object) -> OrchestrationRequest:
    return _request(
        input={"command": {"operation": "project.inspect"}},
        **overrides,  # type: ignore[arg-type]
    )


def _health_signal_context() -> dict[str, object]:
    return {
        "domain_signals": [
            {"value": "medical", "domains": ["health"], "confidence": 0.9},
        ]
    }


def test_allow_evidence_is_projected() -> None:
    policy = DomainPermissionPolicy(
        policy_id="health.policy",
        domain_id="domain:health",
        version="1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.inspect",),
    )
    router = _permission_router(policy)

    decision = _route_domain(
        router,
        _command_request(context=_health_signal_context()),
        intent=_intent(IntentKind.COMMAND),
    )

    assert decision.primary_domain == "domain:health"
    assert decision.permission_disposition == "allow"
    assert decision.permission_refs
    assert decision.approval_refs == ()


def test_canonical_deny_evidence_is_projected_verbatim() -> None:
    policy = DomainPermissionPolicy(
        policy_id="health.policy",
        domain_id="domain:health",
        version="1.0.0",
        prohibited_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
    )
    router = _permission_router(policy)

    decision = _route_domain(
        router,
        _command_request(context=_health_signal_context()),
        intent=_intent(IntentKind.COMMAND),
    )

    assert decision.permission_disposition == "deny"


def test_canonical_approval_evidence_is_projected() -> None:
    policy = DomainPermissionPolicy(
        policy_id="health.policy",
        domain_id="domain:health",
        version="1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.inspect",),
        approval_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
    )
    router = _permission_router(policy)

    decision = _route_domain(
        router,
        _command_request(context=_health_signal_context()),
        intent=_intent(IntentKind.COMMAND),
    )

    assert decision.permission_disposition == "approval_required"
    assert decision.approval_refs


def test_absence_of_canonical_policy_is_not_a_deny() -> None:
    registry = DomainPermissionRegistry()
    router = _router(
        permission_registry=registry,
        permission_resolver=DomainPermissionResolver(
            registry, trust_policy_lookup=None
        ),
    )

    decision = _route_domain(
        router,
        _command_request(context=_health_signal_context()),
        intent=_intent(IntentKind.COMMAND),
    )

    assert decision.permission_disposition is None
    assert decision.permission_refs == ()


def test_permission_registry_and_resolver_must_be_provided_together() -> None:
    with pytest.raises(TypeError):
        _router(permission_registry=DomainPermissionRegistry())
    with pytest.raises(TypeError):
        _router(
            permission_resolver=DomainPermissionResolver(DomainPermissionRegistry())
        )


def test_side_effecting_intent_without_its_canonical_identifier_has_no_evidence() -> (
    None
):
    policy = DomainPermissionPolicy(
        policy_id="health.policy",
        domain_id="domain:health",
        version="1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.inspect",),
    )
    router = _permission_router(policy)
    request = _request(
        input={"command": {}},
        context=_health_signal_context(),
    )

    decision = _route_domain(router, request, intent=_intent(IntentKind.COMMAND))

    assert decision.permission_disposition is None


def test_read_only_intents_do_not_claim_permission_evidence() -> None:
    policy = DomainPermissionPolicy(
        policy_id="general.policy",
        domain_id="domain:general",
        version="1.0.0",
        prohibited_capabilities=(PermissionCapability.RESOURCE_READ,),
    )
    router = _permission_router(policy)

    decision = _route_domain(router, _request(input={"question": "What changed?"}))

    assert decision.permission_disposition is None


def test_permission_evidence_is_skipped_without_a_session() -> None:
    policy = DomainPermissionPolicy(
        policy_id="health.policy",
        domain_id="domain:health",
        version="1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.inspect",),
    )
    router = _permission_router(policy)
    request = _request(
        input={"command": {"operation": "project.inspect"}},
        context=_health_signal_context(),
        session_id=None,
    )

    decision = _route_domain(router, request, intent=_intent(IntentKind.COMMAND))

    assert decision.permission_disposition is None


def test_supporting_domains_are_submitted_to_the_canonical_permission_resolver() -> (
    None
):
    class _RecordingPermissionResolver(DomainPermissionResolver):
        def __init__(self, registry: DomainPermissionRegistry) -> None:
            super().__init__(registry, trust_policy_lookup=None)
            self.supporting_domains: tuple[str, ...] | None = None

        def resolve(self, request, **kwargs):  # type: ignore[no-untyped-def]
            self.supporting_domains = kwargs.get("supporting_domains")
            return super().resolve(request, **kwargs)

    policy = DomainPermissionPolicy(
        policy_id="health.policy",
        domain_id="domain:health",
        version="1.0.0",
        allowed_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
        allowed_operations=("project.inspect",),
        allow_cross_domain_access=True,
    )
    registry = DomainPermissionRegistry()
    registry.register(policy)
    recorder = _RecordingPermissionResolver(registry)
    router = _router(permission_registry=registry, permission_resolver=recorder)
    request = _request(
        input={"command": {"operation": "project.inspect"}},
        context={
            "domain_signals": [
                {"value": "medical", "domains": ["health"], "confidence": 0.9},
                {"value": "study", "domains": ["university"], "confidence": 0.6},
            ]
        },
    )

    decision = _route_domain(router, request, intent=_intent(IntentKind.COMMAND))

    assert decision.supporting_domains == ("domain:university",)
    assert recorder.supporting_domains == ("domain:university",)


# ── Projection safety ────────────────────────────────────────────────────────


def test_projection_exposes_only_safe_references() -> None:
    decision = _route_domain(_router(), _request(input={"question": "What changed?"}))

    payload = decision.to_dict()

    assert set(payload) == {
        "status",
        "primary_domain",
        "supporting_domains",
        "rejected_domains",
        "ambiguous_domains",
        "profile_id",
        "permission_disposition",
        "permission_refs",
        "approval_refs",
        "trace_refs",
        "reason_codes",
        "needs_clarification",
        "fallback_used",
    }


def test_routing_is_deterministic() -> None:
    router = _router()
    request = _request(input={"question": "What changed?"})

    assert _route_domain(router, request).to_dict() == (
        _route_domain(router, request).to_dict()
    )


# ── Architecture ─────────────────────────────────────────────────────────────


def test_domain_router_defines_no_canonical_owner() -> None:
    tree = ast.parse(DOMAIN_ROUTER_MODULE.read_text())

    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name in FORBIDDEN_OWNER_CLASSES
    ]

    assert not offenders, f"domain router must not define canonical owners: {offenders}"


def test_domain_router_imports_no_scoring_module() -> None:
    tree = ast.parse(DOMAIN_ROUTER_MODULE.read_text())

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for forbidden in (
        "cmm.domains.resolver_scoring",
        "cmm.domains.selection",
        "cmm.domains.permission_evaluator",
        "cmm.domains.conflict_resolution",
    ):
        assert forbidden not in imported, f"domain router must not import {forbidden}"


def test_domain_router_holds_no_scoring_weight() -> None:
    tree = ast.parse(DOMAIN_ROUTER_MODULE.read_text())

    offenders = [
        node.targets[0].id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and "weight" in node.targets[0].id
    ]

    assert not offenders, f"domain router must not hold scoring weights: {offenders}"
