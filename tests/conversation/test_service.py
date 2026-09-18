"""Phase 11.5 — ``ConversationService`` over the canonical application gateway.

Task 6 locks the conversational coordinator.  One ``ConversationService`` turns a
public conversational turn into exactly one canonical ``ApplicationCommand``
entered through the one real ``ApplicationGateway``, projects the safe
``ApplicationResponse`` back through the authorized domain projection and the
requested/effective capability resolver, and commits the transcript through
``SharedSessionConversationAdapter`` on the canonical ``SessionStore``.

The composition is the real one the Phase 11.3 acceptance pattern uses: the
official ``InMemorySessionStore``, the real ``SessionApplicationService``, the
real ``RequestApplicationService`` over a real ``Orchestrator`` (real
``DeterministicIntentResolver``, ``DefaultContextResolver``,
``CanonicalDomainRouter``, ``CanonicalAgentRouter``,
``DefaultOrchestrationPolicy``, ``InMemoryOrchestrationDecisionRepository`` and
``RecordingOrchestrationEventSink``) and the one real ``ApplicationGateway``.
The gateway's ``handle`` is wrapped by a recording delegate — the gateway class
is never replaced or subclassed — so every constructed command is observed while
the call itself still lands on the canonical gateway.

Proven here:

- ``submit``: role ``USER`` required; the canonical session must exist; the
  caller's expected revision is verified before the gateway call (a mistyped
  revision fails closed as ``INVALID_REQUEST`` and a well-typed but stale one as
  the safe conversation conflict, either way with no gateway call and no write);
  a caller-supplied lineage and a turn identity that is already stored or reused
  within the turn fail closed as ``INVALID_REQUEST`` before the gateway;
  exactly one ``ApplicationCommand`` with ``MESSAGE_SUBMIT``/``CONVERSATION``/
  the canonical session/``CONVERSATION_ACTOR_ID``/no idempotency key and a
  payload carrying only the application message identity, the public content and
  ``text/plain``, carrying exactly the caller-supplied ``request_id``; the
  caller's opaque ``bot_id``, references, attachments and metadata stay in
  conversation state and never enter the application payload; user + assistant
  messages are persisted in one canonical commit with the same expected previous
  revision; the caller-supplied ``ConversationalDomainView`` is projected and
  the capability state is resolved from the requested capabilities; a structured
  failed application response and a structured blocked application response are
  preserved through the safe projection and persisted (no exception text enters
  conversation state); a persistence race propagates as the safe conversation
  conflict, never a silent retry with a new revision;
- ``edit``: the original must exist and be a ``USER`` message; the original is
  resolved inside the replacement's *own* session, so a replacement bound to a
  foreign session fails closed at that lookup; the service enforces lineage
  itself (``lineage.supersedes_message_id == original.id``) and a caller-supplied
  lineage is rejected rather than replaced; a replacement identity that already
  exists (including the original's) or reuses the assistant identity of the turn
  fails closed; the original is preserved byte-identical; the gateway is
  traversed again exactly once with the caller-supplied ``request_id``; the new
  assistant response receives the caller-supplied identity; a stale revision
  causes zero persistence;
- ``regenerate``: the target must exist and be an ``ASSISTANT`` message (also
  when a preceding user turn exists and the preceding-user scan would resolve);
  the caller-supplied ``application_message_id`` must be a fresh identity,
  distinct from the assistant identity, and is the application message identity
  — no new user message is appended; the nearest preceding ``USER`` message is
  located without being mutated (also across an edit); the gateway is traversed
  again with the caller-supplied ``request_id``; the new assistant message
  carries ``lineage.regenerates_message_id == response_message_id``; the
  original response is preserved; no hidden reasoning is persisted or reused;
- ``cancel``: the service delegates to the canonical gateway with
  ``REQUEST_CANCEL``/``CONVERSATION``/payload ``{"request_id": target}``/
  ``session_id=None`` and returns the canonical response unchanged — at the
  baseline ``CAPABILITY_UNAVAILABLE`` — keeping no active-request registry and
  touching no state.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 9, 11, 12, 14, 18, 22 and 23) and the committed Phase 11.5 plan.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.agent_registry_store import InMemoryAgentRegistryStore
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.application.capabilities import (
    CapabilityApplicationService,
    build_default_capabilities,
)
from cmm.application.contracts import (
    ApplicationChannel,
    ApplicationCommand,
    ApplicationErrorCode,
    ApplicationOperation,
    ApplicationRequest,
    ApplicationResponse,
    ApplicationStatus,
)
from cmm.application.errors import (
    InvalidApplicationRequestError,
    PolicyDeniedApplicationError,
)
from cmm.application.gateway import (
    CANCELLATION_UNAVAILABLE_MESSAGE,
    ApplicationGateway,
)
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import InMemoryIdempotencyRepository
from cmm.application.requests import RequestApplicationService
from cmm.application.sessions import SessionApplicationService
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.contracts import (
    INTERNAL_DETAIL_METADATA_KEYS,
    MAX_METADATA_DEPTH,
    SECRET_LIKE_METADATA_KEYS,
    AssistantResponse,
    ConversationAttachmentRef,
    ConversationCapabilityStatus,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import (
    ConversationBoundaryError,
    ConversationErrorCode,
    ConversationProjectionBindingError,
    ConversationSessionConflictError,
    ConversationSessionNotFoundError,
)
from cmm.conversation.projection import (
    ConversationResponseProjector,
    canonical_domain_resolution_reference,
)
from cmm.conversation.service import CONVERSATION_ACTOR_ID, ConversationService
from cmm.conversation.state import (
    CONVERSATION_EXTENSION_KEY,
    CONVERSATION_EXTENSION_VERSION,
    ConversationState,
    SharedSessionConversationAdapter,
)
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.identifiers import DomainId
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    DomainInterfaceProjection,
    DomainInterfaceStatus,
)
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolver import DefaultDomainResolver
from cmm.orchestration.agent_router import CanonicalAgentRouter
from cmm.orchestration.context import DefaultContextResolver
from cmm.orchestration.contracts import OrchestrationChannel
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.domain_router import CanonicalDomainRouter
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.intent import DeterministicIntentResolver
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.policy import (
    DefaultOrchestrationPolicy,
    OrchestrationConfiguration,
)
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDescriptor,
)
from cmm.platform.modules import StaticCompositionModule
from cmm.runtime.sessions import InMemorySessionStore, SharedSessionState

# ── Fixture constants ────────────────────────────────────────────────────────

NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)

TIMESTAMP = "2026-09-17T10:00:00+00:00"
ASSISTANT_TIMESTAMP = "2026-09-17T10:00:01+00:00"

SESSION_ID = "session-1"
OTHER_SESSION_ID = "session-2"

#: The pinned public text of a canonical routed conversational outcome: a plain
#: conversational message is presented through the canonical ``question``
#: signal (remediation MAJOR-01), so the deterministic canonical resolver
#: classifies it as ``QUESTION`` and the canonical pipeline routes it.
ROUTED_TEXT = "The request was routed through the canonical application boundary."

GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")

GENERAL_POLICY = DomainPermissionPolicy(
    policy_id="general.policy",
    domain_id="domain:general",
    version="1.0.0",
    allowed_capabilities=(PermissionCapability.GOAL_UPDATE,),
)

HEALTH_PROFILE = DomainProfileDefinition(
    id="health.default",
    domain_id=HEALTH,
    profile_name="Health",
)

ALL_CHANNELS = (
    OrchestrationChannel.CONVERSATION,
    OrchestrationChannel.CLI,
    OrchestrationChannel.INTERNAL,
    OrchestrationChannel.API,
)


# ── Canonical graph (the Phase 11.3 acceptance composition pattern) ──────────


def _domain_registry() -> DomainRegistry:
    registry = DomainRegistry()
    for slug in ("general", "health", "university"):
        registry.register(
            DomainDefinition(
                id=f"domain:{slug}",
                name=slug,
                display_name=slug.title(),
                version="1.0.0",
                kind=DomainKind.CORE,
                description=f"{slug} domain",
                manifest_id=f"manifest:{slug}:1.0.0",
            )
        )
        registry.enable(f"domain:{slug}")
    return registry


def _platform_container() -> ApplicationContainer:
    """Return a real container for the gateway's health projection.

    The health projection is not on the conversational path, so only the
    container binding ``HealthApplicationService`` validates is composed; this
    is the same minimal-container pattern the Phase 11.3 gateway tests use.
    """

    service_id = "orchestration.orchestrator"
    module = StaticCompositionModule(
        "test-doubles",
        (
            ServiceBinding(
                descriptor=ServiceDescriptor(
                    service_id=service_id,
                    contract=ContractMetadata(
                        contract_name=service_id,
                        contract_version="1.0.0",
                        schema_version="1",
                        owner="cmm.test.doubles",
                    ),
                    implementation_id="tests.conversation.test_service.double",
                ),
                implementation=object(),
            ),
        ),
    )
    return ApplicationContainer.build(
        CompositionConfiguration(
            required_services=(service_id,),
            enabled_modules=("test-doubles",),
        ),
        modules=(module,),
    )


class _RecordingStore:
    """Delegates to the official in-memory store and counts the canonical calls.

    Observation only: every call lands on the real ``InMemorySessionStore``, so
    the adapter is exercised against the canonical store as wired.
    """

    def __init__(self, inner: InMemorySessionStore) -> None:
        self._inner = inner
        self.loads = 0
        self.saves = 0
        self.committed: list[SharedSessionState] = []

    def load(self, session_id: str) -> SharedSessionState | None:
        self.loads += 1
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.saves += 1
        committed = self._inner.save(state)
        self.committed.append(committed)
        return committed


class _RacingStore:
    """A competing writer commits between the adapter's read and its commit.

    ``save`` delegates to a real ``InMemorySessionStore``, so the raised
    ``SessionPersistenceError`` is the canonical store's own revision-conflict
    error and the adapter's remap is exercised against it.  ``save_calls``
    proves the service does not silently retry.
    """

    def __init__(self, inner: InMemorySessionStore) -> None:
        self._inner = inner
        self.save_calls = 0
        self.competing_writes = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.save_calls += 1
        existing = self._inner.load(state.session_id)
        if existing is not None and existing.revision == state.revision:
            self._inner.save(existing)
            self.competing_writes += 1
        return self._inner.save(state)


class _GatewayRecorder:
    """A recording delegate in front of the real gateway's ``handle``.

    The delegate wraps the real bound method; the gateway class is never
    replaced or subclassed, so every observed command still lands on the one
    canonical ``ApplicationGateway``.
    """

    def __init__(self, gateway: ApplicationGateway) -> None:
        self.commands: list[ApplicationRequest] = []
        self._handle = gateway.handle
        gateway.handle = self  # type: ignore[method-assign]

    def __call__(self, request: ApplicationRequest) -> ApplicationResponse:
        self.commands.append(request)
        return self._handle(request)


class _StructuredResponseGateway(_GatewayRecorder):
    """A recording delegate answering with one canonical structured response.

    Like ``_GatewayRecorder`` it wraps the real bound ``handle`` of the one
    canonical gateway (the class is never replaced, subclassed or mutated) and
    records every constructed command, but it answers with the structured
    ``BLOCKED``/``POLICY_DENIED`` envelope the application boundary produces for
    a policy denial (``cmm/application/requests.py``), built from the
    application-owned ``PolicyDeniedApplicationError``.

    The composed real graph cannot reach that response for a conversational
    turn — deterministic intent resolution stops every plain conversational
    message at clarification before the policy is ever evaluated — so the
    structured outcome is supplied here and the conversational preservation and
    single-commit persistence of a genuinely structured ``BLOCKED`` response are
    exercised end to end through the real service.
    """

    def __call__(self, request: ApplicationRequest) -> ApplicationResponse:
        self.commands.append(request)
        return ApplicationResponse(
            request_id=request.request_id,
            api_version=request.api_version,
            status=ApplicationStatus.BLOCKED,
            data={
                "session_id": request.session_id,
                "request_id": request.request_id,
                "status": ApplicationStatus.BLOCKED.value,
            },
            error=PolicyDeniedApplicationError().to_public_error(),
            metadata={},
        )


@dataclass
class _Harness:
    canonical_store: InMemorySessionStore
    adapter_store: Any
    sessions: SessionApplicationService
    gateway: ApplicationGateway
    orchestrator: Orchestrator
    adapter: SharedSessionConversationAdapter
    service: ConversationService
    recorder: _GatewayRecorder

    def create_session(self, session_id: str) -> None:
        self.sessions.create_session(session_id)

    def conversation(self, session_id: str = SESSION_ID) -> ConversationState | None:
        return SharedSessionConversationAdapter(self.canonical_store).load_conversation(
            session_id
        )

    def revision(self, session_id: str = SESSION_ID) -> int:
        state = self.canonical_store.load(session_id)
        assert state is not None
        return state.revision


def _compose(
    *,
    canonical_store: InMemorySessionStore,
    adapter_store: Any,
    session_ids: tuple[str, ...],
    domain_projections: Any = None,
) -> _Harness:
    """Compose the real canonical graph over the given canonical store."""

    domain_registry = _domain_registry()

    permission_registry = DomainPermissionRegistry()
    permission_registry.register(GENERAL_POLICY)
    permission_resolver = DomainPermissionResolver(
        permission_registry, trust_policy_lookup=None
    )

    profile_registry = InMemoryDomainProfileRegistry()
    profile_registry.register(HEALTH_PROFILE)

    domain_router = CanonicalDomainRouter(
        resolver=DefaultDomainResolver(fallback_domain=GENERAL, clock=lambda: NOW),
        registry=domain_registry,
        context_builder=DomainResolutionContextBuilder(clock=lambda: NOW),
        profile_registry=profile_registry,
        permission_registry=permission_registry,
        permission_resolver=permission_resolver,
    )

    agent_service = AgentRegistryService(
        registry=AgentRegistry(store=InMemoryAgentRegistryStore()),
        factory_registry=AgentFactoryRegistry(),
    )
    agent_router = CanonicalAgentRouter(registry_service=agent_service)

    context_resolver = DefaultContextResolver(session_store=canonical_store)
    policy = DefaultOrchestrationPolicy(
        configuration=OrchestrationConfiguration(allowed_channels=ALL_CHANNELS)
    )

    orchestrator = Orchestrator(
        intent_resolver=DeterministicIntentResolver(),
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        policy=policy,
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=RecordingOrchestrationEventSink(),
    )

    sessions = SessionApplicationService(canonical_store)
    for session_id in session_ids:
        sessions.create_session(session_id)

    gateway = ApplicationGateway(
        sessions=sessions,
        requests=RequestApplicationService(
            sessions=sessions, orchestrator=orchestrator
        ),
        capabilities=CapabilityApplicationService(build_default_capabilities()),
        health=HealthApplicationService(_platform_container()),
        idempotency=InMemoryIdempotencyRepository(),
    )

    adapter = SharedSessionConversationAdapter(adapter_store)
    service = ConversationService(
        gateway=gateway,
        state=adapter,
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
        domain_projections=domain_projections,
    )

    return _Harness(
        canonical_store=canonical_store,
        adapter_store=adapter_store,
        sessions=sessions,
        gateway=gateway,
        orchestrator=orchestrator,
        adapter=adapter,
        service=service,
        recorder=_GatewayRecorder(gateway),
    )


def _harness(
    *,
    session_ids: tuple[str, ...] = (SESSION_ID,),
    domain_projections: Any = None,
) -> _Harness:
    """A real graph whose adapter store counts the canonical calls."""

    canonical_store = InMemorySessionStore()
    return _compose(
        canonical_store=canonical_store,
        adapter_store=_RecordingStore(canonical_store),
        session_ids=session_ids,
        domain_projections=domain_projections,
    )


def _racing_harness(*, session_ids: tuple[str, ...] = (SESSION_ID,)) -> _Harness:
    """A real graph whose commit races one competing canonical writer."""

    canonical_store = InMemorySessionStore()
    return _compose(
        canonical_store=canonical_store,
        adapter_store=_RacingStore(canonical_store),
        session_ids=session_ids,
    )


# ── Public conversational input builders ─────────────────────────────────────


#: The separator-free denied key fragments of the production runtime screen, so
#: this walker weakens in lockstep with the screen it mirrors (remediation
#: MAJOR-03 makes the production screen the load-bearing one).
_FORBIDDEN_KEY_FRAGMENTS = tuple(
    sorted(
        {
            key.replace("_", "")
            for key in SECRET_LIKE_METADATA_KEYS | INTERNAL_DETAIL_METADATA_KEYS
        }
    )
)


def _keys(payload: Any) -> tuple[str, ...]:
    """Return every mapping key of one payload."""

    found: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            found.append(str(key))
            found.extend(_keys(value))
    elif isinstance(payload, Sequence) and not isinstance(
        payload, str | bytes | bytearray | memoryview
    ):
        for item in payload:
            found.extend(_keys(item))
    return tuple(found)


def _forbidden_key_hits(payload: Any) -> tuple[str, ...]:
    """Return every key of *payload* the production screen would refuse."""

    return tuple(
        key
        for key in _keys(payload)
        if any(
            fragment in key.lower().replace("_", "")
            for fragment in _FORBIDDEN_KEY_FRAGMENTS
        )
    )


def _message(
    message_id: str = "user-001",
    *,
    session_id: str = SESSION_ID,
    role: ConversationRole = ConversationRole.USER,
    content: str = "What changed in the plan?",
    **overrides: Any,
) -> ConversationMessage:
    fields: dict[str, Any] = {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": TIMESTAMP,
    }
    fields.update(overrides)
    return ConversationMessage(**fields)


def _domain_view() -> ConversationalDomainView:
    return ConversationalDomainView(
        primary_domain="domain:health",
        supporting_domains=("domain:general",),
        workflow_refs=("workflow:1",),
        question_refs=("question:1",),
        approval_refs=("approval:1",),
        source_refs=("source:1",),
        contradiction_refs=(),
        result_refs=("result:1",),
        memory_proposal_refs=("memory:1",),
        confidence=0.9,
        warning_refs=("warning:1",),
        status=DomainInterfaceStatus.READY,
    )


# ── Test doubles of the trusted projection source (remediation MAJOR-02) ─────


def _projection_for(
    *,
    application_response: ApplicationResponse,
    request_id: str | None = None,
    session_reference_id: str | None = None,
    resolution_reference_id: str | None = None,
    primary_domain: str | None = None,
    supporting_domains: tuple[str, ...] | None = None,
    source_refs: tuple[str, ...] = ("source:1",),
) -> DomainInterfaceProjection:
    """One genuine Phase 10.45 projection of the turn's own canonical route.

    Every default is derived from the canonical application response the turn
    itself produced, so the projection is *bound* unless a test deliberately
    overrides one binding field to make it foreign.
    """

    data = application_response.data
    assert isinstance(data, Mapping)
    reference = canonical_domain_resolution_reference(application_response)
    assert reference is not None
    session_id = data["session_id"]
    return DomainInterfaceProjection(
        projection_id=f"interface-projection:{request_id or data['request_id']}",
        request_id=data["request_id"] if request_id is None else request_id,
        resolution_reference_id=(
            reference if resolution_reference_id is None else resolution_reference_id
        ),
        composition_reference_id="composition:1",
        session_reference_id=(
            session_id if session_reference_id is None else session_reference_id
        ),
        conversational=ConversationalDomainView(
            primary_domain=data["primary_domain"]
            if primary_domain is None
            else primary_domain,
            supporting_domains=(
                tuple(data["supporting_domains"])
                if supporting_domains is None
                else supporting_domains
            ),
            workflow_refs=("workflow:1",),
            question_refs=("question:1",),
            approval_refs=("approval:1",),
            source_refs=source_refs,
            contradiction_refs=(),
            result_refs=("result:1",),
            memory_proposal_refs=("memory:1",),
            confidence=0.9,
            warning_refs=("warning:1",),
            status=DomainInterfaceStatus.READY,
        ),
        selector=None,
        domain_center=None,
        cross_domain=None,
        review_center=None,
    )


class _FakeProjectionSource:
    """An observation-only test projection source (read-only by construction).

    Test code only.  It stores nothing durable, resolves nothing, composes
    nothing and authorizes nothing: it answers with the projection its factory
    builds for the request it is asked about, and records every call.
    """

    def __init__(self, factory: Any = None) -> None:
        self.factory = factory
        self.calls: list[tuple[str, str, ApplicationResponse]] = []

    def get_projection(
        self,
        *,
        request_id: str,
        session_id: str,
        application_response: ApplicationResponse,
    ) -> DomainInterfaceProjection | None:
        self.calls.append((request_id, session_id, application_response))
        if self.factory is None:
            return None
        return self.factory(
            request_id=request_id,
            session_id=session_id,
            application_response=application_response,
        )


def _same_turn_source(**overrides: Any) -> _FakeProjectionSource:
    """A source answering with the verified projection of the current turn."""

    def factory(
        *, request_id: str, session_id: str, application_response: ApplicationResponse
    ) -> DomainInterfaceProjection:
        return _projection_for(application_response=application_response, **overrides)

    return _FakeProjectionSource(factory)


def _submit(
    harness: _Harness,
    message: ConversationMessage,
    **overrides: Any,
) -> AssistantResponse:
    fields: dict[str, Any] = {
        "request_id": "req-submit-1",
        "expected_session_revision": harness.revision(message.session_id),
        "assistant_message_id": "assistant-001",
        "assistant_created_at": ASSISTANT_TIMESTAMP,
    }
    fields.update(overrides)
    return harness.service.submit(message, **fields)


# ═══════════════════════════════════════════════════════════════════════════
# Constructor and module identity
# ═══════════════════════════════════════════════════════════════════════════


def test_constructor_fails_closed_on_each_wrong_collaborator() -> None:
    harness = _harness()

    with pytest.raises(TypeError):
        ConversationService(
            gateway=object(),  # type: ignore[arg-type]
            state=harness.adapter,
            capabilities=ConversationCapabilityResolver(),
            projector=ConversationResponseProjector(),
        )
    with pytest.raises(TypeError):
        ConversationService(
            gateway=harness.gateway,
            state=object(),  # type: ignore[arg-type]
            capabilities=ConversationCapabilityResolver(),
            projector=ConversationResponseProjector(),
        )
    with pytest.raises(TypeError):
        ConversationService(
            gateway=harness.gateway,
            state=harness.adapter,
            capabilities=object(),  # type: ignore[arg-type]
            projector=ConversationResponseProjector(),
        )
    with pytest.raises(TypeError):
        ConversationService(
            gateway=harness.gateway,
            state=harness.adapter,
            capabilities=ConversationCapabilityResolver(),
            projector=object(),  # type: ignore[arg-type]
        )

    service = ConversationService(
        gateway=harness.gateway,
        state=harness.adapter,
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )
    assert isinstance(service, ConversationService)


def test_the_conversation_actor_identity_is_one_module_constant() -> None:
    """The descriptive public actor identity is the frozen module constant."""

    assert CONVERSATION_ACTOR_ID == "conversation"


# ═══════════════════════════════════════════════════════════════════════════
# submit
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("role", [ConversationRole.ASSISTANT, ConversationRole.SYSTEM])
def test_submit_requires_a_user_message(role: ConversationRole) -> None:
    harness = _harness()

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(harness, _message(role=role))

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None


def test_submit_rejects_a_non_message_before_any_gateway_call() -> None:
    harness = _harness()

    with pytest.raises(ConversationBoundaryError) as failure:
        harness.service.submit(  # type: ignore[arg-type]
            None,
            request_id="req-submit-1",
            expected_session_revision=1,
            assistant_message_id="assistant-001",
            assistant_created_at=ASSISTANT_TIMESTAMP,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0


def test_submit_requires_an_existing_canonical_session() -> None:
    harness = _harness()

    with pytest.raises(ConversationSessionNotFoundError):
        harness.service.submit(
            _message(session_id="session-missing"),
            request_id="req-submit-1",
            expected_session_revision=1,
            assistant_message_id="assistant-001",
            assistant_created_at=ASSISTANT_TIMESTAMP,
        )

    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0


@pytest.mark.parametrize("expected_revision", [0, 2])
def test_submit_verifies_the_expected_revision_before_the_gateway(
    expected_revision: int,
) -> None:
    harness = _harness()

    with pytest.raises(ConversationSessionConflictError):
        _submit(harness, _message(), expected_session_revision=expected_revision)

    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None
    assert harness.revision() == 1


@pytest.mark.parametrize("expected_revision", [True, False, 1.0, -1, "1"])
def test_submit_rejects_a_mistyped_expected_revision_before_the_gateway(
    expected_revision: object,
) -> None:
    """A mis-typed revision is caller input error, not a stale revision.

    ``True`` and ``1.0`` compare equal to the current revision, so the pinned
    ``!=`` guard alone would let them through to an application-layer failure;
    every mis-typed value fails closed as the conversational ``INVALID_REQUEST``
    before the gateway and before any write.
    """

    harness = _harness()

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(harness, _message(), expected_session_revision=expected_revision)

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None
    assert harness.revision() == 1


def test_submit_builds_exactly_one_canonical_conversation_command() -> None:
    harness = _harness()
    message = _message()

    _submit(harness, message)

    assert len(harness.recorder.commands) == 1
    command = harness.recorder.commands[0]
    assert isinstance(command, ApplicationCommand)
    assert command.request_id == "req-submit-1"
    assert command.operation is ApplicationOperation.MESSAGE_SUBMIT
    assert command.channel is ApplicationChannel.CONVERSATION
    assert command.api_version == "v1"
    assert command.session_id == SESSION_ID
    assert command.expected_session_revision == 1
    assert command.actor_id == CONVERSATION_ACTOR_ID
    assert command.idempotency_key is None
    assert dict(command.payload) == {
        "message_id": message.id,
        "content": message.content,
        "content_type": "text/plain",
    }
    assert dict(command.metadata) == {}


def test_submit_keeps_bot_id_references_and_attachments_in_conversation_state() -> None:
    harness = _harness()
    attachment = ConversationAttachmentRef(
        ref="attachment:1",
        kind="document",
        name="plan.pdf",
        media_type="application/pdf",
    )
    message = _message(
        bot_id="bot:untrusted",
        references=("reference:1",),
        attachments=(attachment,),
        metadata={"topic": "plan"},
    )

    _submit(harness, message)

    command = harness.recorder.commands[0]
    assert dict(command.payload) == {
        "message_id": message.id,
        "content": message.content,
        "content_type": "text/plain",
    }
    assert "bot_id" not in command.payload
    assert "references" not in command.payload
    assert "attachments" not in command.payload
    assert dict(command.metadata) == {}

    state = harness.conversation()
    assert state is not None
    stored = state.messages[0]
    assert stored.bot_id == "bot:untrusted"
    assert stored.references == ("reference:1",)
    assert stored.attachments == (attachment,)
    assert dict(stored.metadata) == {"topic": "plan"}


def test_hidden_reasoning_and_prompt_metadata_never_enters_conversation_state() -> None:
    """Remediation MAJOR-03: the runtime screen gates the submit path."""

    harness = _harness()

    for key in (
        "private_reasoning",
        "privateReasoning",
        "raw_prompt",
        "raw_prompt",
        "system_prompt",
        "prompt",
    ):
        with pytest.raises(ValueError):
            _message(metadata={key: "hidden"})

    # No turn and no canonical write can follow an unsafe message: the
    # boundary never sanitizes-and-continues and never persists.
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None


def test_submit_edit_and_regeneration_responses_carry_no_forbidden_keys() -> None:
    """Every response of the canonical turn paths passes the runtime screen."""

    harness = _harness()
    response = _submit(harness, _message())
    assert _forbidden_key_hits(response.to_dict()) == ()

    edited = harness.service.edit(
        original_message_id="user-001",
        replacement=_message("user-002", content="edited question"),
        request_id="request-2",
        expected_session_revision=2,
        assistant_message_id="assistant-002",
        assistant_created_at=TIMESTAMP,
    )
    assert _forbidden_key_hits(edited.to_dict()) == ()

    regenerated = harness.service.regenerate(
        session_id=SESSION_ID,
        response_message_id="assistant-002",
        request_id="request-3",
        application_message_id="application-message-3",
        expected_session_revision=3,
        assistant_message_id="assistant-003",
        assistant_created_at=TIMESTAMP,
    )
    persisted = harness.conversation()
    assert persisted is not None
    hit_keys = _forbidden_key_hits(edited.to_dict()) + _forbidden_key_hits(
        regenerated.to_dict()
    )
    hit_keys += _forbidden_key_hits(persisted.to_dict())
    assert hit_keys == ()
    # The stored transcript is the only durable shape, and it is clean.
    assert all(
        _forbidden_key_hits(message.to_dict()) == () for message in persisted.messages
    )


def test_submit_persists_user_and_assistant_in_one_canonical_commit() -> None:
    harness = _harness()
    message = _message()

    response = _submit(harness, message)

    assert harness.adapter_store.saves == 1
    state = harness.conversation()
    assert state is not None
    assert state.session_id == SESSION_ID
    assert state.messages == (message, response.message)

    assert response.message.role is ConversationRole.ASSISTANT
    assert response.message.id == "assistant-001"
    assert response.message.session_id == SESSION_ID
    assert response.message.created_at == ASSISTANT_TIMESTAMP
    assert response.message.content == ROUTED_TEXT
    assert response.message.references == ()
    assert response.message.attachments == ()

    envelope = harness.canonical_store.load(SESSION_ID)
    assert envelope is not None
    assert CONVERSATION_EXTENSION_KEY in envelope.extensions
    assert envelope.revision == 2
    assert harness.revision() == 2


def test_submit_commits_once_with_the_verified_expected_previous_revision() -> None:
    harness = _harness()
    commits: list[int | None] = []
    save = harness.adapter.save_conversation

    def recording(state: ConversationState, *, expected_previous_revision: int | None):
        commits.append(expected_previous_revision)
        return save(state, expected_previous_revision=expected_previous_revision)

    harness.adapter.save_conversation = recording  # type: ignore[method-assign]

    _submit(harness, _message())

    # Exactly one conversation commit, carrying the same revision the caller's
    # assertion was verified against.
    assert commits == [1]
    assert harness.adapter_store.saves == 1


# ── Request/session-bound Domain projection (remediation MAJOR-02) ───────────


def test_submit_projects_only_the_verified_same_turn_projection() -> None:
    """Domain visibility comes from the bound projection of this same turn."""

    source = _same_turn_source()
    harness = _harness(domain_projections=source)
    message = _message()

    response = _submit(harness, message)

    # The source was asked about this exact turn: the request identity the
    # service is serving, the canonical session and the application result.
    assert len(source.calls) == 1
    request_id, session_id, application_response = source.calls[0]
    assert request_id == "req-submit-1"
    assert session_id == SESSION_ID
    assert application_response.request_id == request_id
    assert application_response.data["session_id"] == SESSION_ID

    view = _domain_view()
    assert response.sources == view.source_refs == ("source:1",)
    assert response.pending_questions == view.question_refs
    assert response.approval_requests == view.approval_refs
    assert response.workflow_updates == view.workflow_refs
    assert response.memory_updates == view.memory_proposal_refs
    assert response.warnings == view.warning_refs
    assert response.reasoning_summary["result_refs"] == ("result:1",)
    # The visible Domain membership is the turn's own canonical membership.
    assert (
        dict(response.domain_state)["primary_domain"]
        == (application_response.data["primary_domain"])
    )
    assert tuple(response.domain_state["supporting_domains"]) == tuple(
        application_response.data["supporting_domains"]
    )


def test_submit_without_a_projection_source_exposes_no_domain_visibility() -> None:
    """No composed source means no Domain visibility: nothing is reconstructed."""

    harness = _harness(domain_projections=None)

    response = _submit(harness, _message())

    assert response.sources == ()
    assert response.pending_questions == ()
    assert response.approval_requests == ()
    assert response.workflow_updates == ()
    assert response.memory_updates == ()
    assert response.warnings == ()
    assert dict(response.reasoning_summary) == {}
    assert dict(response.domain_state) == {}


def test_a_source_returning_no_projection_leaves_the_turn_domain_free() -> None:
    harness = _harness(domain_projections=_FakeProjectionSource())

    response = _submit(harness, _message())

    assert response.sources == ()
    assert dict(response.domain_state) == {}


def _assert_binding_failure(harness: _Harness, message: ConversationMessage) -> None:
    """One unbound projection fails closed with zero exposure and zero writes."""

    saves_before = harness.adapter_store.saves
    revision_before = harness.revision(message.session_id)
    with pytest.raises(ConversationProjectionBindingError) as failure:
        _submit(harness, message)

    assert failure.value.code is ConversationErrorCode.INTERNAL_FAILURE
    assert harness.adapter_store.saves == saves_before
    assert harness.revision(message.session_id) == revision_before
    # Nothing was persisted: no foreign reference can be read back.
    assert harness.conversation() is None


def test_a_projection_of_another_request_fails_closed_through_the_service() -> None:
    harness = _harness(domain_projections=_same_turn_source(request_id="req-other"))

    _assert_binding_failure(harness, _message())


def test_a_projection_of_another_session_fails_closed_through_the_service() -> None:
    harness = _harness(
        domain_projections=_same_turn_source(session_reference_id="session-2")
    )

    _assert_binding_failure(harness, _message())


def test_a_projection_with_another_resolution_reference_fails_closed() -> None:
    harness = _harness(
        domain_projections=_same_turn_source(
            resolution_reference_id="resolution:foreign"
        )
    )

    _assert_binding_failure(harness, _message())


def test_a_projection_with_another_primary_domain_fails_closed() -> None:
    harness = _harness(
        domain_projections=_same_turn_source(primary_domain="domain:university")
    )

    _assert_binding_failure(harness, _message())


def test_a_projection_with_other_supporting_domains_fails_closed() -> None:
    harness = _harness(
        domain_projections=_same_turn_source(supporting_domains=("domain:university",))
    )

    _assert_binding_failure(harness, _message())


def test_a_raw_mapping_pretending_to_be_a_projection_fails_closed() -> None:
    raw = _FakeProjectionSource(
        lambda **_kwargs: {"request_id": "req-submit-1", "conversational": {}}
    )
    harness = _harness(domain_projections=raw)

    _assert_binding_failure(harness, _message())


def test_a_bare_view_is_not_a_projection_and_fails_closed() -> None:
    harness = _harness(
        domain_projections=_FakeProjectionSource(lambda **_kwargs: _domain_view())
    )

    _assert_binding_failure(harness, _message())


def test_edit_and_regenerate_use_the_verified_projection_of_their_own_turn() -> None:
    """Each turn obtains its own bound projection; none is reused across turns."""

    source = _same_turn_source()
    harness = _harness(domain_projections=source)
    first = _submit(harness, _message())

    edited = harness.service.edit(
        original_message_id="user-001",
        replacement=_message("user-002", content="edited question"),
        request_id="req-edit-1",
        expected_session_revision=2,
        assistant_message_id="assistant-002",
        assistant_created_at=ASSISTANT_TIMESTAMP,
    )
    regenerated = harness.service.regenerate(
        session_id=SESSION_ID,
        response_message_id="assistant-002",
        request_id="req-regenerate-1",
        application_message_id="application-message-3",
        expected_session_revision=3,
        assistant_message_id="assistant-003",
        assistant_created_at=ASSISTANT_TIMESTAMP,
    )

    assert [call[0] for call in source.calls] == [
        "req-submit-1",
        "req-edit-1",
        "req-regenerate-1",
    ]
    assert [call[1] for call in source.calls] == [SESSION_ID, SESSION_ID, SESSION_ID]
    for response in (first, edited, regenerated):
        assert response.sources == ("source:1",)


def test_the_constructor_rejects_anything_but_a_read_only_source() -> None:
    harness = _harness()

    for value in (object(), {"get_projection": lambda **_: None}, "source"):
        with pytest.raises(TypeError):
            ConversationService(
                gateway=harness.gateway,
                state=harness.adapter,
                capabilities=ConversationCapabilityResolver(),
                projector=ConversationResponseProjector(),
                domain_projections=value,  # type: ignore[arg-type]
            )


def test_public_turn_methods_no_longer_accept_a_caller_domain_view() -> None:
    """Remediation MAJOR-02: a bare caller view is never per-turn Domain authority.

    The V1 audit reproduced a public caller supplying a detached
    ``ConversationalDomainView`` and having its references projected.  The
    public per-turn surface no longer accepts one at all.
    """

    harness = _harness()
    view = _domain_view()

    for call in (
        lambda: _submit(harness, _message("user-001"), domain_view=view),
        lambda: harness.service.edit(
            original_message_id="user-001",
            replacement=_message("user-002"),
            request_id="req-edit-1",
            expected_session_revision=harness.revision(),
            domain_view=view,
            assistant_message_id="assistant-edit-1",
            assistant_created_at=ASSISTANT_TIMESTAMP,
        ),
        lambda: harness.service.regenerate(
            session_id=SESSION_ID,
            response_message_id="assistant-001",
            request_id="req-regen-1",
            application_message_id="application-1",
            expected_session_revision=harness.revision(),
            domain_view=view,
            assistant_message_id="assistant-regen-1",
            assistant_created_at=ASSISTANT_TIMESTAMP,
        ),
    ):
        with pytest.raises(TypeError):
            call()

    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None


def test_submit_returns_the_capability_state_of_the_requested_capabilities() -> None:
    harness = _harness()
    requested = ("response_streaming", "request_cancellation", "document_upload")

    response = _submit(harness, _message(), requested_capabilities=requested)

    assert response.capability_state == ConversationCapabilityResolver().resolve(
        requested
    )
    by_id = {state.capability: state for state in response.capability_state}
    assert by_id["response_streaming"].status is ConversationCapabilityStatus.DEGRADED
    assert by_id["response_streaming"].effective == "response_event_stream"
    assert (
        by_id["request_cancellation"].status is ConversationCapabilityStatus.UNAVAILABLE
    )
    assert by_id["document_upload"].status is ConversationCapabilityStatus.UNAVAILABLE
    assert (
        by_id["continuous_conversation"].status
        is ConversationCapabilityStatus.AVAILABLE
    )
    assert by_id["continuous_conversation"].requested is False


def test_submit_preserves_a_structured_failed_application_response() -> None:
    harness = _harness()
    # Empty content is representable conversationally but is not a valid public
    # application message: the real gateway answers with a structured failed
    # response, which must be preserved through the safe projection and
    # persisted with the user turn in the same commit.
    message = _message(content="")

    response = _submit(harness, message)

    assert len(harness.recorder.commands) == 1
    assert response.message.content == InvalidApplicationRequestError.safe_message
    assert harness.adapter_store.saves == 1
    state = harness.conversation()
    assert state is not None
    assert state.messages == (message, response.message)


def test_submit_preserves_a_structured_blocked_response_in_the_same_commit() -> None:
    """A structured ``BLOCKED``/``POLICY_DENIED`` outcome is preserved and persisted.

    The committed structured-failure test covers ``FAILED`` only; this drives the
    structured ``BLOCKED`` envelope the canonical application boundary produces
    for a policy denial (recording delegate over the real gateway) and asserts
    the public failure text of the blocked outcome is projected unchanged and
    that the user turn plus the blocked assistant turn land in the same single
    canonical commit.
    """

    harness = _harness()
    blocked = _StructuredResponseGateway(harness.gateway)
    message = _message()

    response = _submit(harness, message)

    assert len(blocked.commands) == 1
    assert blocked.commands[0].request_id == "req-submit-1"
    assert response.message.role is ConversationRole.ASSISTANT
    assert response.message.content == PolicyDeniedApplicationError.safe_message
    assert response.message.content != InvalidApplicationRequestError.safe_message

    assert harness.adapter_store.saves == 1
    state = harness.conversation()
    assert state is not None
    assert state.messages == (message, response.message)
    assert state.message(response.message.id).content == (
        PolicyDeniedApplicationError.safe_message
    )
    assert harness.revision() == 2


def test_submit_rejects_a_duplicate_user_message_id_before_the_gateway() -> None:
    """A stored user identity is never resubmitted through the pipeline."""

    harness = _harness()
    _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(
            harness,
            _message(),
            request_id="req-submit-2",
            assistant_message_id="assistant-002",
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == ["user-001", "assistant-001"]


def test_submit_rejects_an_assistant_id_that_collides_with_a_stored_message() -> None:
    """An assistant identity may not reuse any stored message identity."""

    harness = _harness()
    _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(
            harness,
            _message("user-002"),
            request_id="req-submit-2",
            assistant_message_id="user-001",
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


def test_submit_rejects_an_assistant_id_equal_to_the_user_message_id() -> None:
    """The two identities of one turn must be distinct, even when both are new."""

    harness = _harness()

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(harness, _message(), assistant_message_id="user-001")

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None


def test_submit_rejects_a_caller_supplied_lineage() -> None:
    """Lineage is service-owned: a submitted message carries none, by contract."""

    harness = _harness()
    message = _message(lineage=ConversationLineage(supersedes_message_id="ghost"))

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(harness, message)

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None
    assert harness.revision() == 1


def test_submit_race_propagates_the_safe_conflict_without_retry() -> None:
    harness = _racing_harness()

    with pytest.raises(ConversationSessionConflictError):
        _submit(harness, _message())

    # The gateway was traversed exactly once (the race is a commit race), the
    # commit was attempted exactly once and nothing of the conversational turn
    # was persisted; the competing writer's revision stands.
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.save_calls == 1
    assert harness.adapter_store.competing_writes == 1
    assert harness.conversation() is None
    assert harness.revision() == 2


# ═══════════════════════════════════════════════════════════════════════════
# edit
# ═══════════════════════════════════════════════════════════════════════════


def _edit(
    harness: _Harness,
    *,
    original_message_id: str,
    replacement: ConversationMessage,
    **overrides: Any,
) -> AssistantResponse:
    fields: dict[str, Any] = {
        "request_id": "req-edit-1",
        "expected_session_revision": harness.revision(replacement.session_id),
        "assistant_message_id": "assistant-002",
        "assistant_created_at": ASSISTANT_TIMESTAMP,
    }
    fields.update(overrides)
    return harness.service.edit(
        original_message_id=original_message_id, replacement=replacement, **fields
    )


def test_edit_requires_an_existing_original_message() -> None:
    harness = _harness()
    _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id="user-missing",
            replacement=_message("user-002", content="Edited."),
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1


def test_edit_requires_a_user_original_message() -> None:
    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=submitted.message.id,
            replacement=_message("user-002", content="Edited."),
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1


def test_edit_enforces_lineage_and_preserves_the_original() -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)
    before = harness.conversation()
    assert before is not None
    original_before = before.message(original.id).to_dict()

    replacement = _message("user-002", content="Edited question.")
    response = _edit(harness, original_message_id=original.id, replacement=replacement)

    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [
        original.id,
        "assistant-001",
        replacement.id,
        response.message.id,
    ]
    # The original and the first assistant response are preserved byte-identical.
    assert state.messages[:2] == before.messages
    assert state.message(original.id).to_dict() == original_before

    stored_replacement = state.message(replacement.id)
    assert stored_replacement.lineage.supersedes_message_id == original.id
    assert stored_replacement.content == "Edited question."
    assert stored_replacement.role is ConversationRole.USER

    assert response.message.id == "assistant-002"
    assert response.message.lineage.supersedes_message_id is None
    assert response.message.lineage.regenerates_message_id is None
    assert harness.adapter_store.saves == 2
    assert harness.revision() == 3


def test_edit_rejects_an_equal_replacement_identity() -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message(original.id, content="Edited."),
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    state = harness.conversation()
    assert state is not None
    assert len(state.messages) == 2


def test_edit_rejects_a_foreign_session_replacement_at_the_original_lookup() -> None:
    """The original is looked up inside the replacement's own session.

    No session-binding branch exists in the service: the replacement declares
    ``session-2``, so the service resolves the original identity inside *that*
    session's own transcript — where ``user-001`` does not exist — and the edit
    fails closed as ``INVALID_REQUEST`` before the gateway and before any write,
    leaving both transcripts exactly as they were.
    """

    harness = _harness(session_ids=(SESSION_ID, OTHER_SESSION_ID))
    original = _message()
    _submit(harness, original)
    _submit(
        harness,
        _message("user-9", session_id=OTHER_SESSION_ID, content="Other session turn."),
        request_id="req-other-1",
        assistant_message_id="assistant-9",
    )
    other_before = harness.conversation(OTHER_SESSION_ID)
    assert other_before is not None

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message("user-002", session_id=OTHER_SESSION_ID),
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 2
    assert harness.adapter_store.saves == 2
    other_after = harness.conversation(OTHER_SESSION_ID)
    assert other_after is not None
    assert other_after == other_before
    assert [message.id for message in other_after.messages] == [
        "user-9",
        "assistant-9",
    ]
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [original.id, "assistant-001"]


def test_edit_rejects_a_replacement_id_that_collides_with_a_stored_message() -> None:
    """A replacement identity may not reuse any stored message identity."""

    harness = _harness()
    original = _message()
    submitted = _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message(submitted.message.id, content="Edited."),
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


def test_edit_rejects_an_assistant_id_equal_to_the_replacement_id() -> None:
    """The two identities of an edit turn must be distinct."""

    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message("user-002", content="Edited."),
            assistant_message_id="user-002",
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


def test_edit_rejects_a_caller_supplied_lineage_on_the_replacement() -> None:
    """Lineage is service-owned: a replacement lineage is rejected, not replaced."""

    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message(
                "user-002",
                content="Edited.",
                lineage=ConversationLineage(supersedes_message_id="ghost"),
            ),
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [original.id, "assistant-001"]


@pytest.mark.parametrize("expected_revision", [True, False, 1.0, -1, "1"])
def test_edit_rejects_a_mistyped_expected_revision_before_the_gateway(
    expected_revision: object,
) -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message("user-002", content="Edited."),
            expected_session_revision=expected_revision,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


def test_edit_traverses_the_gateway_again_exactly_once() -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)

    replacement = _message("user-002", content="Edited.")
    _edit(harness, original_message_id=original.id, replacement=replacement)

    assert len(harness.recorder.commands) == 2
    command = harness.recorder.commands[1]
    assert command.request_id == "req-edit-1"
    assert command.operation is ApplicationOperation.MESSAGE_SUBMIT
    assert command.channel is ApplicationChannel.CONVERSATION
    assert command.session_id == SESSION_ID
    assert command.expected_session_revision == 2
    assert command.actor_id == CONVERSATION_ACTOR_ID
    assert command.idempotency_key is None
    assert dict(command.payload) == {
        "message_id": "user-002",
        "content": "Edited.",
        "content_type": "text/plain",
    }


def test_edit_stale_revision_causes_zero_persistence() -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationSessionConflictError):
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message("user-002", content="Edited."),
            expected_session_revision=1,
        )

    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert len(state.messages) == 2


# ═══════════════════════════════════════════════════════════════════════════
# regenerate
# ═══════════════════════════════════════════════════════════════════════════


def _regenerate(
    harness: _Harness,
    *,
    response_message_id: str,
    **overrides: Any,
) -> AssistantResponse:
    fields: dict[str, Any] = {
        "request_id": "req-regenerate-1",
        "application_message_id": "application-user-002",
        "expected_session_revision": harness.revision(SESSION_ID),
        "assistant_message_id": "assistant-002",
        "assistant_created_at": ASSISTANT_TIMESTAMP,
    }
    fields.update(overrides)
    return harness.service.regenerate(
        session_id=SESSION_ID, response_message_id=response_message_id, **fields
    )


def test_regenerate_requires_an_existing_assistant_target() -> None:
    harness = _harness()
    _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(harness, response_message_id="assistant-missing")

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1


def test_regenerate_requires_an_assistant_target_even_with_a_preceding_user_turn() -> (
    None
):
    """The ASSISTANT role guard is what rejects a USER target here.

    ``user-002`` is a stored ``USER`` message that *does* have a preceding user
    turn (``user-001``), so the preceding-user scan would resolve, and the
    caller-supplied identities are fresh, so the identity check would resolve
    too; only the role guard can fail closed for this target.
    """

    harness = _harness()
    original = _message()
    _submit(harness, original)
    _edit(
        harness,
        original_message_id=original.id,
        replacement=_message("user-002", content="Edited."),
    )

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id="user-002",
            application_message_id="application-user-003",
            assistant_message_id="assistant-003",
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 2
    assert harness.adapter_store.saves == 2
    assert harness.revision() == 3
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [
        "user-001",
        "assistant-001",
        "user-002",
        "assistant-002",
    ]


def test_regenerate_rejects_a_stored_application_message_id() -> None:
    """The caller-supplied application identity must not already exist."""

    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            application_message_id="user-001",
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


def test_regenerate_rejects_an_assistant_id_that_collides_with_a_stored_message() -> (
    None
):
    """An assistant identity may not reuse any stored message identity."""

    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            assistant_message_id="user-001",
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


def test_regenerate_rejects_an_assistant_id_equal_to_the_application_message_id() -> (
    None
):
    """The two identities of a regeneration turn must be distinct."""

    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            application_message_id="application-user-002",
            assistant_message_id="application-user-002",
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


@pytest.mark.parametrize("expected_revision", [True, False, 1.0, -1, "1"])
def test_regenerate_rejects_a_mistyped_expected_revision_before_the_gateway(
    expected_revision: object,
) -> None:
    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            expected_session_revision=expected_revision,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2


def test_regenerate_reuses_the_preceding_user_turn_without_appending_it() -> None:
    harness = _harness()
    submitted = _submit(harness, _message())
    before = harness.conversation()
    assert before is not None
    user_before = before.message("user-001").to_dict()

    response = _regenerate(harness, response_message_id=submitted.message.id)

    assert len(harness.recorder.commands) == 2
    command = harness.recorder.commands[1]
    assert isinstance(command, ApplicationCommand)
    assert command.request_id == "req-regenerate-1"
    assert command.operation is ApplicationOperation.MESSAGE_SUBMIT
    assert command.channel is ApplicationChannel.CONVERSATION
    assert command.session_id == SESSION_ID
    assert command.expected_session_revision == 2
    assert command.actor_id == CONVERSATION_ACTOR_ID
    assert command.idempotency_key is None
    assert dict(command.payload) == {
        "message_id": "application-user-002",
        "content": "What changed in the plan?",
        "content_type": "text/plain",
    }

    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [
        "user-001",
        "assistant-001",
        "assistant-002",
    ]
    # The preceding user turn and the original response are preserved unchanged.
    assert state.message("user-001").to_dict() == user_before
    assert (
        state.message("assistant-001").to_dict()
        == before.message("assistant-001").to_dict()
    )

    assert response.message.role is ConversationRole.ASSISTANT
    assert response.message.id == "assistant-002"
    assert response.message.lineage.regenerates_message_id == "assistant-001"
    assert response.message.lineage.supersedes_message_id is None
    assert harness.adapter_store.saves == 2
    assert harness.revision() == 3


def test_regenerate_uses_the_nearest_preceding_user_message() -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)
    replacement = _message("user-002", content="Edited question.")
    _edit(harness, original_message_id=original.id, replacement=replacement)

    response = _regenerate(
        harness,
        response_message_id="assistant-002",
        application_message_id="application-user-003",
        assistant_message_id="assistant-003",
    )

    command = harness.recorder.commands[2]
    assert dict(command.payload)["message_id"] == "application-user-003"
    assert dict(command.payload)["content"] == "Edited question."
    assert response.message.lineage.regenerates_message_id == "assistant-002"


def test_regenerate_stale_revision_causes_zero_persistence() -> None:
    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationSessionConflictError):
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            expected_session_revision=1,
        )

    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert len(state.messages) == 2


def test_regenerate_persists_no_hidden_reasoning() -> None:
    harness = _harness()
    submitted = _submit(harness, _message())

    response = _regenerate(harness, response_message_id=submitted.message.id)

    assert dict(response.reasoning_summary) == {}
    assert response.sources == ()

    state = harness.conversation()
    assert state is not None
    new_message = state.message("assistant-002").to_dict()
    assert set(new_message) == {
        "id",
        "session_id",
        "role",
        "content",
        "created_at",
        "bot_id",
        "references",
        "attachments",
        "lineage",
        "metadata",
    }
    walked = json.dumps(state.to_dict()).lower()
    for denied in (
        "chainofthought",
        "scratchpad",
        "hiddenreasoning",
        "privatereasoning",
        "rawprompt",
        "traceback",
        "stacktrace",
    ):
        assert denied not in walked


# ═══════════════════════════════════════════════════════════════════════════
# caller-supplied turn inputs at the conversational boundary
# ═══════════════════════════════════════════════════════════════════════════

#: Blank caller-supplied identities of one turn (empty and whitespace-only).
NON_IDENTIFIER_INPUTS = (
    pytest.param("", id="empty"),
    pytest.param("   ", id="blank"),
)

#: Caller-supplied assistant timestamps that are not UTC-offset ISO-8601 values.
MALFORMED_ASSISTANT_TIMESTAMPS = (
    pytest.param("", id="empty"),
    pytest.param("   ", id="blank"),
    pytest.param("not-a-timestamp", id="non-timestamp"),
    pytest.param("2026-09-17T10:00:00", id="no-utc-offset"),
)


@pytest.mark.parametrize("request_id", NON_IDENTIFIER_INPUTS)
def test_submit_rejects_a_non_identifier_request_id_before_the_gateway(
    request_id: str,
) -> None:
    """A blank request identity is caller input error, never a raw contract error."""

    harness = _harness()

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(harness, _message(), request_id=request_id)

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None
    assert harness.revision() == 1


@pytest.mark.parametrize("assistant_message_id", NON_IDENTIFIER_INPUTS)
def test_submit_rejects_a_non_identifier_assistant_message_id_before_the_gateway(
    assistant_message_id: str,
) -> None:
    """A blank assistant identity fails at the boundary, not after the gateway."""

    harness = _harness()

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(harness, _message(), assistant_message_id=assistant_message_id)

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None
    assert harness.revision() == 1


@pytest.mark.parametrize("assistant_created_at", MALFORMED_ASSISTANT_TIMESTAMPS)
def test_submit_rejects_a_malformed_assistant_created_at_before_the_gateway(
    assistant_created_at: str,
) -> None:
    """The assistant timestamp must be ISO-8601 with an explicit UTC offset."""

    harness = _harness()

    with pytest.raises(ConversationBoundaryError) as failure:
        _submit(harness, _message(), assistant_created_at=assistant_created_at)

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert harness.recorder.commands == []
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None
    assert harness.revision() == 1


@pytest.mark.parametrize("request_id", NON_IDENTIFIER_INPUTS)
def test_edit_rejects_a_non_identifier_request_id_before_the_gateway(
    request_id: str,
) -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message("user-002", content="Edited."),
            request_id=request_id,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [original.id, "assistant-001"]


@pytest.mark.parametrize("assistant_message_id", NON_IDENTIFIER_INPUTS)
def test_edit_rejects_a_non_identifier_assistant_message_id_before_the_gateway(
    assistant_message_id: str,
) -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message("user-002", content="Edited."),
            assistant_message_id=assistant_message_id,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [original.id, "assistant-001"]


@pytest.mark.parametrize("assistant_created_at", MALFORMED_ASSISTANT_TIMESTAMPS)
def test_edit_rejects_a_malformed_assistant_created_at_before_the_gateway(
    assistant_created_at: str,
) -> None:
    harness = _harness()
    original = _message()
    _submit(harness, original)

    with pytest.raises(ConversationBoundaryError) as failure:
        _edit(
            harness,
            original_message_id=original.id,
            replacement=_message("user-002", content="Edited."),
            assistant_created_at=assistant_created_at,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == [original.id, "assistant-001"]


@pytest.mark.parametrize("request_id", NON_IDENTIFIER_INPUTS)
def test_regenerate_rejects_a_non_identifier_request_id_before_the_gateway(
    request_id: str,
) -> None:
    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness, response_message_id=submitted.message.id, request_id=request_id
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == ["user-001", "assistant-001"]


@pytest.mark.parametrize("assistant_message_id", NON_IDENTIFIER_INPUTS)
def test_regenerate_rejects_a_non_identifier_assistant_message_id_before_the_gateway(
    assistant_message_id: str,
) -> None:
    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            assistant_message_id=assistant_message_id,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == ["user-001", "assistant-001"]


@pytest.mark.parametrize("assistant_created_at", MALFORMED_ASSISTANT_TIMESTAMPS)
def test_regenerate_rejects_a_malformed_assistant_created_at_before_the_gateway(
    assistant_created_at: str,
) -> None:
    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            assistant_created_at=assistant_created_at,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == ["user-001", "assistant-001"]


@pytest.mark.parametrize("application_message_id", NON_IDENTIFIER_INPUTS)
def test_regenerate_rejects_a_non_identifier_application_message_id_before_the_gateway(
    application_message_id: str,
) -> None:
    """A blank application identity is rejected, never persisted as a failure.

    The application identity of a regeneration is caller input: an empty or
    blank value must fail closed as the conversational ``INVALID_REQUEST``
    boundary error with zero gateway calls and zero writes, instead of
    travelling into the application payload and being persisted as a normal
    structured ``FAILED`` turn.
    """

    harness = _harness()
    submitted = _submit(harness, _message())

    with pytest.raises(ConversationBoundaryError) as failure:
        _regenerate(
            harness,
            response_message_id=submitted.message.id,
            application_message_id=application_message_id,
        )

    assert failure.value.code is ConversationErrorCode.INVALID_REQUEST
    assert len(harness.recorder.commands) == 1
    assert harness.adapter_store.saves == 1
    assert harness.revision() == 2
    state = harness.conversation()
    assert state is not None
    assert [message.id for message in state.messages] == ["user-001", "assistant-001"]
    assert InvalidApplicationRequestError.safe_message not in [
        message.content for message in state.messages
    ]


# ═══════════════════════════════════════════════════════════════════════════
# request identity passthrough
# ═══════════════════════════════════════════════════════════════════════════


def test_every_message_command_carries_the_caller_supplied_request_id() -> None:
    """The caller's request identity is never replaced by a constant.

    The recorded ``MESSAGE_SUBMIT`` command of submit, edit *and* regenerate
    carries exactly the caller-supplied ``request_id`` of that turn.
    """

    harness = _harness()
    original = _message()
    _submit(harness, original, request_id="req-submit-42")
    _edit(
        harness,
        original_message_id=original.id,
        replacement=_message("user-002", content="Edited."),
        request_id="req-edit-42",
    )
    _regenerate(
        harness,
        response_message_id="assistant-002",
        application_message_id="application-user-003",
        assistant_message_id="assistant-003",
        request_id="req-regenerate-42",
    )

    assert [command.request_id for command in harness.recorder.commands] == [
        "req-submit-42",
        "req-edit-42",
        "req-regenerate-42",
    ]


# ═══════════════════════════════════════════════════════════════════════════
# cancel
# ═══════════════════════════════════════════════════════════════════════════


def test_cancel_delegates_to_the_canonical_gateway() -> None:
    harness = _harness()

    response = harness.service.cancel(
        request_id="req-cancel-1", target_request_id="req-target-1"
    )

    assert isinstance(response, ApplicationResponse)
    assert len(harness.recorder.commands) == 1
    command = harness.recorder.commands[0]
    assert isinstance(command, ApplicationCommand)
    assert command.operation is ApplicationOperation.REQUEST_CANCEL
    assert command.channel is ApplicationChannel.CONVERSATION
    assert command.request_id == "req-cancel-1"
    assert command.session_id is None
    assert command.actor_id == CONVERSATION_ACTOR_ID
    assert command.idempotency_key is None
    assert command.expected_session_revision is None
    assert dict(command.payload) == {"request_id": "req-target-1"}

    # Baseline truth: the canonical application boundary reports cancellation
    # as unavailable because no canonical cancellable-request owner exists.
    assert response.status is ApplicationStatus.FAILED
    assert response.error is not None
    assert response.error.code is ApplicationErrorCode.CAPABILITY_UNAVAILABLE
    assert response.error.message == CANCELLATION_UNAVAILABLE_MESSAGE
    assert response.error.retryable is False

    # Cancellation touches no conversational or canonical session state.
    assert harness.adapter_store.loads == 0
    assert harness.adapter_store.saves == 0
    envelope = harness.canonical_store.load(SESSION_ID)
    assert envelope is not None
    assert envelope.revision == 1


def test_cancel_is_stateless_and_keeps_no_active_request_registry() -> None:
    harness = _harness()

    first = harness.service.cancel(
        request_id="req-cancel-1", target_request_id="req-target-1"
    )
    second = harness.service.cancel(
        request_id="req-cancel-2", target_request_id="req-target-1"
    )

    # Two cancellations are two independent commands returning the same
    # canonical truth: no registry is consulted, updated or introduced.
    assert [command.request_id for command in harness.recorder.commands] == [
        "req-cancel-1",
        "req-cancel-2",
    ]
    assert first.error == second.error
    assert set(vars(harness.service)) == {
        "_gateway",
        "_state",
        "_capabilities",
        "_projector",
        # The one composition-time read-only projection source reference
        # (remediation MAJOR-02); it is a collaborator, never a store: the
        # cancellation path above never touches it.
        "_domain_projections",
    }
    assert harness.adapter_store.saves == 0


# ═══════════════════════════════════════════════════════════════════════════
# security adversaries: attacker metadata never reaches canonical state
# ═══════════════════════════════════════════════════════════════════════════


def _deepest_attacker_metadata(key: str) -> dict[str, object]:
    """Nest *key* at the deepest mapping level the public recursion admits.

    ``MAX_METADATA_DEPTH`` nested mappings is that level; the recursion bound
    is pinned by the architecture gate
    (``test_the_recursion_boundary_is_where_the_deepest_payload_says_it_is``).
    """

    payload: dict[str, object] = {key: "sk-attacker"}
    for level in range(MAX_METADATA_DEPTH - 1, 0, -1):
        payload = {f"level-{level}": payload}
    return payload


def test_attacker_metadata_is_rejected_before_any_turn_can_be_persisted() -> None:
    """The deepest attacker payload never becomes a turn to persist.

    The payload carries a secret-shaped key at the deepest mapping level the
    public recursion admits, so construction fails closed before any turn
    exists; the identical shape with a benign key is accepted, so the rejection
    is the key screen and not the recursion bound.

    The zero-interaction assertions are the rejected payload's, not an inert
    harness's: the recording gateway delegate and the recording store are
    proven live by the control that follows — the same turn with the benign key
    at the same depth is submitted through the same harness and every recorded
    interaction fires.
    """

    harness = _harness()

    with pytest.raises(ValueError):
        _message("attacker-001", metadata=_deepest_attacker_metadata("api_key"))

    # No turn exists to submit: nothing entered the gateway, no canonical
    # session was read or written and no conversational state exists.
    assert harness.recorder.commands == []
    assert harness.adapter_store.loads == 0
    assert harness.adapter_store.saves == 0
    assert harness.conversation() is None

    control = _message("control-001", metadata=_deepest_attacker_metadata("note"))

    assert control.metadata

    _submit(harness, control)

    assert [command.request_id for command in harness.recorder.commands] == [
        "req-submit-1"
    ]
    assert harness.adapter_store.loads > 0
    assert harness.adapter_store.saves == 1
    conversation = harness.conversation()
    assert conversation is not None
    assert "control-001" in [message.id for message in conversation.messages]


def test_a_direct_store_write_of_attacker_metadata_fails_closed() -> None:
    """A hand-edited canonical envelope is rejected, never laundered.

    An attacker who writes the deepest attacker metadata straight into the
    canonical session extension — bypassing the conversational boundary —
    receives a fail-closed conflict from the service's read: the violating
    payload is rejected rather than silently sanitized into a cleaned
    conversation, and the service writes nothing.  The same envelope with a
    benign key at the same depth loads cleanly through the same boundary, so
    the conflict is caused by the attacker key alone.
    """

    harness = _harness()
    envelope = harness.canonical_store.load(SESSION_ID)
    assert envelope is not None

    extension = {
        "version": CONVERSATION_EXTENSION_VERSION,
        "session_id": SESSION_ID,
        "mode": "general",
        "messages": [
            {
                "id": "attacker-001",
                "session_id": SESSION_ID,
                "role": ConversationRole.USER.value,
                "content": "attacker",
                "created_at": TIMESTAMP,
                "metadata": _deepest_attacker_metadata("api_key"),
            }
        ],
    }

    # The payload really violates the frozen extension contract …
    with pytest.raises(ValueError):
        ConversationState.from_dict(extension)

    # … and the generic canonical store still accepts the envelope, so the
    # rejection below is the conversational boundary's own, not the store's.
    committed = harness.canonical_store.save(
        envelope.with_extension(CONVERSATION_EXTENSION_KEY, extension)
    )
    assert CONVERSATION_EXTENSION_KEY in committed.extensions
    saves_before = harness.adapter_store.saves

    with pytest.raises(ConversationSessionConflictError):
        harness.service.load(SESSION_ID)

    assert harness.adapter_store.saves == saves_before

    control = dict(extension)
    control["messages"] = [
        {
            "id": "control-001",
            "session_id": SESSION_ID,
            "role": ConversationRole.USER.value,
            "content": "control",
            "created_at": TIMESTAMP,
            "metadata": _deepest_attacker_metadata("note"),
        }
    ]
    harness.canonical_store.save(
        committed.with_extension(CONVERSATION_EXTENSION_KEY, control)
    )

    state = harness.service.load(SESSION_ID)

    assert state is not None
    assert [message.id for message in state.messages] == ["control-001"]
