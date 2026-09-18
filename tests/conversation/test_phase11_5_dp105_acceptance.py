"""Phase 11.5 — `AT-DP-105` connected canonical conversational acceptance.

One connected acceptance over the real canonical vertical:

```text
canonical SharedSessionState
→ official SessionStore (InMemorySessionStore)
→ ConversationService
→ ApplicationGateway
→ RequestApplicationService
→ real Phase 11.2 Orchestrator
→ real canonical domain routing / authorized projection
→ genuine authorized ConversationalDomainView
→ AssistantResponse
→ persisted conversation.v1 through the canonical SessionStore
```

Nothing critical is mocked.  The graph is built from the canonical production
components (``InMemorySessionStore``, ``SessionApplicationService``,
``ApplicationGateway``, ``RequestApplicationService``, the real ``Orchestrator``
with the real ``DeterministicIntentResolver`` / ``DefaultContextResolver`` /
``CanonicalDomainRouter`` / ``CanonicalAgentRouter`` /
``DefaultOrchestrationPolicy`` / ``InMemoryOrchestrationDecisionRepository`` /
``RecordingOrchestrationEventSink``, ``SharedSessionConversationAdapter``,
``ConversationCapabilityResolver``, ``ConversationResponseProjector`` and
``ConversationService``) exactly as ``tests/application/test_phase11_3_dp103_acceptance.py``
composes it, and the authorized ``ConversationalDomainView`` is a genuine
``DefaultDomainAPI.project_interface`` projection produced by a real
``DefaultDomainInterfaceIntegrator`` over the real
``DefaultDomainResolver`` → ``DefaultDomainComposer`` → ``DomainPresentationPlan``
chain (the composition ``tests/domains/test_domain_interface_dp045_acceptance.py``
exercises).  The view is never hand-built.

Traversal is proven with instrumented *real* components: the real gateway's
``handle`` is wrapped by a recording delegate (the gateway class is never
subclassed or replaced) and every turn is cross-checked against the canonical
orchestration decision record read back from the real decision repository.

The one style rule is determinism: every identity and timestamp is
caller-supplied, the only clock is a constant, and no assertion depends on
wall-clock time.

Scenario map (all connected, in one acceptance):

- A first turn — canonical session → service → gateway → orchestrator →
  authorized projection → ``AssistantResponse`` → ``conversation.v1`` read back
  from the canonical store;
- B second-turn continuity — the same session, its updated revision, the
  previous messages preserved, the path traversed again and no client-owned
  transcript;
- C stale revision — safe conflict, no new message, no silent retry;
- D edit lineage — the original preserved and ``supersedes_message_id`` bound;
- E regeneration lineage — the original response preserved,
  ``regenerates_message_id`` bound, no hidden reasoning;
- F capabilities and cancellation — ``response_streaming`` /
  ``request_cancellation`` / ``document_upload`` and the canonical
  ``CAPABILITY_UNAVAILABLE`` cancellation;
- G Bot and attachment non-authority — visible, persisted, authoritative for
  nothing, no file bytes;
- H visibility is not authorization — an authorized approval ref never becomes
  approved, a proposed action never executes, and the refs the canonical
  projection omits on effective-visibility grounds (an item flagged
  ``visible=False``, an item placed only in a non-visible section, and stale
  group refs with no effectively visible display item) stay absent;
- I public safety — attacker metadata fails before persistence and every
  acceptance response dict is walked for forbidden fragments.

The acceptance closes with one in-graph, mock-free positive control: two
directly built structured ``OrchestrationRequest``s driven through the same real
orchestrator prove that the composed canonical domain route is live (a
goal-shaped request escalates through a real domain route; a question-shaped
request routes with a primary domain), complementing the conversational
clarification route pinned by A–I.  The control is not a conversational turn and
is excluded from the conversational traversal totals.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
§29 and the committed Phase 11.5 plan (Task 10).
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
from cmm.agent_runtime.approval_contracts import ApprovalRequest
from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.enums import ApprovalRequestStatus
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
from cmm.application.gateway import (
    CANCELLATION_UNAVAILABLE_MESSAGE,
    ApplicationGateway,
)
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import InMemoryIdempotencyRepository
from cmm.application.requests import RequestApplicationService
from cmm.application.sessions import SessionApplicationService
from cmm.conversation.capabilities import (
    CONVERSATION_CAPABILITY_IDS,
    REASON_NO_CANCELLABLE_OWNER,
    REASON_NO_CANONICAL_STORAGE_OWNER,
    REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE,
    ConversationCapabilityResolver,
)
from cmm.conversation.contracts import (
    INTERNAL_DETAIL_METADATA_KEYS,
    SECRET_LIKE_METADATA_KEYS,
    AssistantResponse,
    ConversationAttachmentRef,
    ConversationCapabilityStatus,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import (
    ConversationErrorCode,
    ConversationSessionConflictError,
)
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.service import CONVERSATION_ACTOR_ID, ConversationService
from cmm.conversation.state import (
    CONVERSATION_EXTENSION_KEY,
    ConversationState,
    SharedSessionConversationAdapter,
)
from cmm.domains.api import DefaultDomainAPI
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainResolutionStatus
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.interface_integration import DefaultDomainInterfaceIntegrator
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    DomainInterfaceProjection,
    DomainInterfaceProjectionRequest,
    DomainInterfaceViewKind,
)
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.presentation_contracts import (
    DomainPresentationItemRef,
    DomainPresentationItemType,
    DomainPresentationPlan,
    DomainPresentationSectionPlan,
)
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_builder import DomainResolutionContextBuilder
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionResource,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainResolutionResult, DomainScoringPolicy
from cmm.domains.university.definition import build_university_domain_definition
from cmm.orchestration.agent_router import CanonicalAgentRouter
from cmm.orchestration.context import DefaultContextResolver
from cmm.orchestration.contracts import (
    ExecutionRoute,
    IntentKind,
    OrchestrationChannel,
    OrchestrationRequest,
    OrchestrationStatus,
    PolicyDisposition,
)
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
from tests.domains.test_domain_api_contracts import _make_collaborators
from tests.domains.test_domain_interface_integration import (
    _make_item,
    _make_operation_approval,
    _make_presentation_with_items,
)

# ── Deterministic fixture constants (caller-supplied, clock-free) ────────────

#: The one frozen constant clock.  Nothing in the acceptance reads the wall
#: clock: every identity and timestamp below is caller-supplied.
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)

SESSION_ID = "conversation-acceptance-session"

TURN_1_AT = "2026-09-17T10:00:00+00:00"
TURN_1_RESPONSE_AT = "2026-09-17T10:00:01+00:00"
TURN_2_AT = "2026-09-17T10:01:00+00:00"
TURN_2_RESPONSE_AT = "2026-09-17T10:01:01+00:00"
TURN_3_AT = "2026-09-17T10:02:00+00:00"
TURN_4_AT = "2026-09-17T10:03:00+00:00"
TURN_4_RESPONSE_AT = "2026-09-17T10:03:01+00:00"
TURN_5_RESPONSE_AT = "2026-09-17T10:04:01+00:00"
TURN_6_AT = "2026-09-17T10:05:00+00:00"
TURN_6_RESPONSE_AT = "2026-09-17T10:05:01+00:00"
TURN_7_AT = "2026-09-17T10:06:00+00:00"
TURN_7_RESPONSE_AT = "2026-09-17T10:06:01+00:00"
TURN_8_AT = "2026-09-17T10:07:00+00:00"
TURN_8_RESPONSE_AT = "2026-09-17T10:07:01+00:00"

#: The pinned public text of a canonical routed conversational outcome: a plain
#: public conversational message is presented through the existing canonical
#: ``question`` structural signal (remediation MAJOR-01), so the deterministic
#: canonical resolver classifies it as ``QUESTION`` and the canonical pipeline
#: routes the selection instead of stopping at clarification.
ROUTED_TEXT = "The request was routed through the canonical application boundary."

GENERAL = DomainId(slug="general")
HEALTH = DomainId(slug="health")
UNIVERSITY = DomainId(slug="university")

PRIMARY_DOMAIN = "domain:university"
SUPPORTING_DOMAIN = "domain:health"

FIRST_RESOLUTION_ID = "domain-resolution:dp105:first"
FIRST_COMPOSITION_ID = "domain-composition:dp105:first"
VISIBILITY_RESOLUTION_ID = "domain-resolution:dp105:visibility"
VISIBILITY_COMPOSITION_ID = "domain-composition:dp105:visibility"

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

#: The reference the visible approval item and the canonical approval carry.
APPROVAL_REF = "approval:dp105:plan"
WORKFLOW_REF = "workflow:dp105:review"
QUESTION_REF = "question:dp105:exam-date"

#: Authorized refs of the visibility projection.
VISIBLE_SOURCES = ("finding:dp105:study-plan", "finding:dp105:health-regimen")

#: Refs the canonical Phase 10.45 projection omits: two items flagged
#: ``visible=False`` (one of them of an unselected domain, which is omitted for
#: that visibility flag — see the scenario H note), one item placed only in a
#: non-visible section, and three stale group refs with no effectively visible
#: display item.  The conversational boundary must never reconstruct them.
OMITTED_REFS = (
    "finding:dp105:legal-hidden",
    "finding:dp105:suppressed-section",
    "finding:dp105:oppositions-unselected",
    "approval:dp105:stale",
    "workflow:dp105:stale",
    "question:dp105:stale",
)

# ── Bounded forbidden-fragment screen (mirrors the public contract's screen) ──

#: The separator-free denied key fragments of the conversational contract.
#: Deliberately derived from the production denial constants, so this walk
#: weakens in lockstep with production; the independent, load-bearing part is
#: the shaped-key ``pytest.raises`` probes in scenario I (mutant g proves they
#: bite).
_FORBIDDEN_KEY_FRAGMENTS = tuple(
    sorted(
        {
            key.replace("_", "")
            for key in SECRET_LIKE_METADATA_KEYS | INTERNAL_DETAIL_METADATA_KEYS
        }
    )
)

#: Value fragments that name an internal failure, a hidden-reasoning artefact, a
#: filesystem path or a credential shape.  Deliberately narrow: the honest
#: capability reason codes (which legitimately contain words such as ``TOKEN``)
#: must stay reportable.
_FORBIDDEN_VALUE_FRAGMENTS = (
    "Traceback (most recent call last)",
    "site-packages",
    "chainofthought",
    "chain_of_thought",
    "scratchpad",
    "hiddenreasoning",
    "hidden_reasoning",
    "raw_exception",
    "ValueError",
    "RuntimeError",
    "sk-live",
    "-----BEGIN",
    "/Users/",
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


def _strings(payload: Any) -> tuple[str, ...]:
    """Return every string value of one payload."""

    found: list[str] = []
    if isinstance(payload, Mapping):
        for value in payload.values():
            found.extend(_strings(value))
    elif isinstance(payload, str):
        found.append(payload)
    elif isinstance(payload, Sequence) and not isinstance(
        payload, bytes | bytearray | memoryview
    ):
        for item in payload:
            found.extend(_strings(item))
    return tuple(found)


def _forbidden_key_hits(payload: Any) -> tuple[str, ...]:
    """Return every key of *payload* that a public contract would refuse."""

    return tuple(
        key
        for key in _keys(payload)
        if any(
            fragment in key.lower().replace("_", "")
            for fragment in _FORBIDDEN_KEY_FRAGMENTS
        )
    )


def _forbidden_value_hits(payload: Any) -> tuple[str, ...]:
    """Return every string value of *payload* carrying a forbidden fragment."""

    return tuple(
        value
        for value in _strings(payload)
        if any(fragment in value for fragment in _FORBIDDEN_VALUE_FRAGMENTS)
    )


def _binary_hits(payload: Any) -> tuple[str, ...]:
    """Return the type name of every non-JSON-safe (binary) value."""

    found: list[str] = []
    if isinstance(payload, bytes | bytearray | memoryview):
        found.append(type(payload).__name__)
    elif isinstance(payload, Mapping):
        for value in payload.values():
            found.extend(_binary_hits(value))
    elif isinstance(payload, Sequence) and not isinstance(payload, str):
        for item in payload:
            found.extend(_binary_hits(item))
    return tuple(found)


# ── Instrumented real components (observation only) ──────────────────────────


class _ObservedStore:
    """Observation-only delegate in front of the official in-memory store.

    Copied from ``tests/conversation/test_service.py::_RecordingStore`` (the
    Phase 11.3 acceptance graph pattern).  Every call lands on the real
    ``InMemorySessionStore``; the counters only observe that the canonical store
    itself was read and written, so nothing here replaces or re-implements it.
    """

    def __init__(self, inner: InMemorySessionStore) -> None:
        self.inner = inner
        self.loads = 0
        self.saves = 0
        self.committed: list[SharedSessionState] = []

    def load(self, session_id: str) -> SharedSessionState | None:
        self.loads += 1
        return self.inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.saves += 1
        committed = self.inner.save(state)
        self.committed.append(committed)
        return committed


class _ObservedGatewayHandle:
    """Recording delegate in front of the real gateway's ``handle``.

    Adapted from ``tests/conversation/test_service.py::_GatewayRecorder`` with
    two deliberate differences: the original records the request BEFORE the
    call and keeps no response, while this delegate records the
    ``(request, response)`` pair AFTER the call returns — so a raised gateway
    exception is never counted as a traversal — and it adds the type-filtered
    ``commands`` helper.  As in the original, the delegate wraps the real bound
    method; the gateway class is never replaced or subclassed, so every
    observed command still lands on the one canonical ``ApplicationGateway``.
    """

    def __init__(self, gateway: ApplicationGateway) -> None:
        self.calls: list[tuple[ApplicationRequest, ApplicationResponse]] = []
        self._handle = gateway.handle
        gateway.handle = self  # type: ignore[method-assign]

    def __call__(self, request: ApplicationRequest) -> ApplicationResponse:
        response = self._handle(request)
        self.calls.append((request, response))
        return response

    def commands(self, operation: ApplicationOperation) -> list[ApplicationCommand]:
        """Return every observed command of *operation*, in gateway order."""

        return [
            request
            for request, _ in self.calls
            if isinstance(request, ApplicationCommand)
            and request.operation is operation
        ]


# ── The real canonical graph ─────────────────────────────────────────────────


def _domain_registry() -> DomainRegistry:
    """Return the canonical registry (copied from the Phase 11.3 acceptance)."""

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

    Copied from ``tests/conversation/test_service.py::_platform_container``: the
    health projection is not on the conversational path, so only the container
    binding ``HealthApplicationService`` validates is composed.
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
                    implementation_id="tests.conversation.dp105.double",
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


@dataclass(slots=True)
class _ConnectedGraph:
    """The one connected conversational graph over the canonical vertical."""

    store: InMemorySessionStore
    observed: _ObservedStore
    registry: DomainRegistry
    sessions: SessionApplicationService
    gateway: ApplicationGateway
    handle: _ObservedGatewayHandle
    orchestrator: Orchestrator
    decisions: InMemoryOrchestrationDecisionRepository
    events: RecordingOrchestrationEventSink
    adapter: SharedSessionConversationAdapter
    service: ConversationService

    def revision(self) -> int:
        state = self.store.load(SESSION_ID)
        assert state is not None
        return state.revision

    def conversation(self) -> ConversationState:
        state = _stored_conversation(self.store, SESSION_ID)
        assert state is not None
        return state

    def message_ids(self) -> list[str]:
        return [message.id for message in self.conversation().messages]


def _connected_graph(
    *, session_ids: tuple[str, ...] = (SESSION_ID,)
) -> _ConnectedGraph:
    """Compose the real canonical graph (the Phase 11.3 acceptance pattern).

    Copied from ``tests/conversation/test_service.py::_compose`` /
    ``tests/application/test_phase11_3_dp103_acceptance.py::_backend``: the
    official ``InMemorySessionStore``, the real ``SessionApplicationService``,
    the real ``RequestApplicationService`` over a real ``Orchestrator`` (real
    ``DeterministicIntentResolver``, ``DefaultContextResolver``,
    ``CanonicalDomainRouter``, ``CanonicalAgentRouter``,
    ``DefaultOrchestrationPolicy``, ``InMemoryOrchestrationDecisionRepository``
    and ``RecordingOrchestrationEventSink``) and the one real
    ``ApplicationGateway``.
    """

    canonical_store = InMemorySessionStore()
    observed = _ObservedStore(canonical_store)

    registry = _domain_registry()

    permission_registry = DomainPermissionRegistry()
    permission_registry.register(GENERAL_POLICY)
    permission_resolver = DomainPermissionResolver(
        permission_registry, trust_policy_lookup=None
    )

    profile_registry = InMemoryDomainProfileRegistry()
    profile_registry.register(HEALTH_PROFILE)

    domain_router = CanonicalDomainRouter(
        resolver=DefaultDomainResolver(fallback_domain=GENERAL, clock=lambda: NOW),
        registry=registry,
        context_builder=DomainResolutionContextBuilder(clock=lambda: NOW),
        profile_registry=profile_registry,
        permission_registry=permission_registry,
        permission_resolver=permission_resolver,
    )

    agent_router = CanonicalAgentRouter(
        registry_service=AgentRegistryService(
            registry=AgentRegistry(store=InMemoryAgentRegistryStore()),
            factory_registry=AgentFactoryRegistry(),
        )
    )

    context_resolver = DefaultContextResolver(session_store=canonical_store)
    policy = DefaultOrchestrationPolicy(
        configuration=OrchestrationConfiguration(allowed_channels=ALL_CHANNELS)
    )
    decisions = InMemoryOrchestrationDecisionRepository()
    events = RecordingOrchestrationEventSink()

    orchestrator = Orchestrator(
        intent_resolver=DeterministicIntentResolver(),
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        policy=policy,
        decision_repository=decisions,
        event_sink=events,
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

    adapter = SharedSessionConversationAdapter(observed)
    service = ConversationService(
        gateway=gateway,
        state=adapter,
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )

    return _ConnectedGraph(
        store=canonical_store,
        observed=observed,
        registry=registry,
        sessions=sessions,
        gateway=gateway,
        handle=_ObservedGatewayHandle(gateway),
        orchestrator=orchestrator,
        decisions=decisions,
        events=events,
        adapter=adapter,
        service=service,
    )


# ── The genuine authorized Domain projection ─────────────────────────────────


@dataclass(frozen=True, slots=True)
class _AuthorizedProjection:
    """One genuine authorized projection of canonical Domain authority."""

    resolution: DomainResolutionResult
    composition: Any
    presentation: DomainPresentationPlan
    projection: DomainInterfaceProjection
    view: ConversationalDomainView


def _authorized_projection(
    *,
    request_id: str,
    resolution_id: str,
    composition_id: str,
    presentation: DomainPresentationPlan,
    approvals: tuple[ApprovalRequest, ...] = (),
) -> _AuthorizedProjection:
    """Build one ConversationalDomainView through the real Phase 10.45 chain.

    The chain is the one ``tests/domains/test_domain_interface_dp045_acceptance.py``
    exercises: real ``DefaultDomainResolver`` → real ``DefaultDomainComposer`` →
    canonical ``DomainPresentationPlan`` → ``DefaultDomainAPI.project_interface``
    delegated to a real ``DefaultDomainInterfaceIntegrator`` (the integrator is
    the only collaborator replaced, exactly as the DP-045 acceptance does; the
    remaining collaborators are the canonical ones the shared
    ``tests/domains/test_domain_api_contracts.py::_make_collaborators`` helper
    wires).
    """

    definitions = (
        build_university_domain_definition(),
        build_health_domain_definition(),
    )
    resolver = DefaultDomainResolver(
        fallback_domain=GENERAL,
        scoring_policy=DomainScoringPolicy(
            max_supporting_domains=3, supporting_margin=100.0
        ),
        clock=lambda: NOW,
        id_factory=lambda: resolution_id,
    )
    resolution = resolver.resolve(
        DomainResolutionContext(
            id=f"{resolution_id}:context",
            user_input=(
                "University study plan and the health regimen of the current plan"
            ),
            available_domains=(UNIVERSITY, HEALTH),
            authorized_domains=(UNIVERSITY, HEALTH),
            explicit_domains=(UNIVERSITY,),
            active_domains=(),
            resources=(
                DomainResolutionResource(
                    id=f"{resolution_id}:resource:health",
                    resource_type="document",
                    source="user",
                    domain_ids=(HEALTH,),
                ),
            ),
            created_at=NOW,
        )
    )
    composition = DefaultDomainComposer(
        id_factory=lambda: composition_id, clock=lambda: NOW
    ).compose(resolution, definitions)

    collaborators = _make_collaborators()
    collaborators["interface_integrator"] = DefaultDomainInterfaceIntegrator(
        resolver=resolver,
        permission_resolver=DomainPermissionResolver(DomainPermissionRegistry()),
    )
    api = DefaultDomainAPI(**collaborators)  # type: ignore[arg-type]
    projection = api.project_interface(
        DomainInterfaceProjectionRequest(
            request_id=request_id,
            resolution_reference_id=resolution.id,
            composition_reference_id=composition.id,
            session_reference_id=SESSION_ID,
            requested_views=(DomainInterfaceViewKind.CONVERSATIONAL,),
        ),
        resolution=resolution,
        composition=composition,
        presentation=presentation,
        approvals=approvals,
    )
    conversational = projection.conversational
    assert conversational is not None
    return _AuthorizedProjection(
        resolution=resolution,
        composition=composition,
        presentation=presentation,
        projection=projection,
        view=conversational,
    )


def _first_turn_projection() -> _AuthorizedProjection:
    """The baseline authorized projection of the first turn (sources only)."""

    presentation = _make_presentation_with_items(
        (
            _make_item(
                VISIBLE_SOURCES[0],
                DomainPresentationItemType.FINDING,
                source_order=1,
                domain_ids=(PRIMARY_DOMAIN,),
                confidence=0.8,
                requires_provenance=True,
            ),
            _make_item(
                VISIBLE_SOURCES[1],
                DomainPresentationItemType.FINDING,
                source_order=2,
                domain_ids=(SUPPORTING_DOMAIN,),
                confidence=0.9,
                requires_provenance=True,
            ),
        ),
        composition_id=FIRST_COMPOSITION_ID,
        plan_id="presentation-plan:dp105:first",
        request_id="presentation-request:dp105:first",
    )
    return _authorized_projection(
        request_id="interface-request:dp105:first",
        resolution_id=FIRST_RESOLUTION_ID,
        composition_id=FIRST_COMPOSITION_ID,
        presentation=presentation,
    )


def _visibility_projection(
    *, approvals: tuple[ApprovalRequest, ...]
) -> _AuthorizedProjection:
    """The authorized projection carrying question/approval/workflow/source refs.

    The plan also carries refs the canonical projection must omit: an item that
    is not visible, an item placed in a non-visible section, an item of an
    unselected domain, and group refs with no visible item at all.
    """

    approval_item = DomainPresentationItemRef(
        ref_id=APPROVAL_REF,
        item_type=DomainPresentationItemType.APPROVAL,
        source_order=3,
        domain_ids=(PRIMARY_DOMAIN,),
        pending=True,
        requires_approval=True,
    )
    presentation = _make_presentation_with_items(
        (
            _make_item(
                VISIBLE_SOURCES[0],
                DomainPresentationItemType.FINDING,
                source_order=1,
                domain_ids=(PRIMARY_DOMAIN,),
                confidence=0.8,
                requires_provenance=True,
            ),
            _make_item(
                VISIBLE_SOURCES[1],
                DomainPresentationItemType.FINDING,
                source_order=2,
                domain_ids=(SUPPORTING_DOMAIN,),
                confidence=0.9,
                requires_provenance=True,
            ),
            approval_item,
            _make_item(
                QUESTION_REF,
                DomainPresentationItemType.QUESTION,
                source_order=4,
                domain_ids=(PRIMARY_DOMAIN,),
            ),
            _make_item(
                WORKFLOW_REF,
                DomainPresentationItemType.WORKFLOW,
                source_order=5,
                domain_ids=(PRIMARY_DOMAIN,),
            ),
            _make_item(
                "finding:dp105:legal-hidden",
                DomainPresentationItemType.FINDING,
                source_order=6,
                domain_ids=("domain:legal",),
                visible=False,
                confidence=0.99,
                requires_provenance=True,
            ),
            _make_item(
                "finding:dp105:suppressed-section",
                DomainPresentationItemType.FINDING,
                source_order=7,
                domain_ids=(PRIMARY_DOMAIN,),
                confidence=0.99,
                requires_provenance=True,
            ),
            _make_item(
                OMITTED_REFS[2],
                DomainPresentationItemType.FINDING,
                source_order=8,
                domain_ids=("domain:oppositions",),
                visible=False,
                confidence=0.99,
                requires_provenance=True,
            ),
        ),
        sections=(
            DomainPresentationSectionPlan(
                section_id="findings",
                item_refs=(
                    VISIBLE_SOURCES[0],
                    VISIBLE_SOURCES[1],
                    APPROVAL_REF,
                    QUESTION_REF,
                    WORKFLOW_REF,
                    "finding:dp105:legal-hidden",
                ),
            ),
            DomainPresentationSectionPlan(
                section_id="suppressed",
                item_refs=("finding:dp105:suppressed-section",),
                visible=False,
            ),
        ),
        composition_id=VISIBILITY_COMPOSITION_ID,
        plan_id="presentation-plan:dp105:visibility",
        request_id="presentation-request:dp105:visibility",
        approval_refs=(APPROVAL_REF, "approval:dp105:stale"),
        workflow_refs=(WORKFLOW_REF, "workflow:dp105:stale"),
        question_refs=(QUESTION_REF, "question:dp105:stale"),
    )
    return _authorized_projection(
        request_id="interface-request:dp105:visibility",
        resolution_id=VISIBILITY_RESOLUTION_ID,
        composition_id=VISIBILITY_COMPOSITION_ID,
        presentation=presentation,
        approvals=approvals,
    )


# ── Canonical-store readers ──────────────────────────────────────────────────


def _raw_extension(
    store: InMemorySessionStore, session_id: str = SESSION_ID
) -> Mapping[str, Any]:
    """Read the ``conversation.v1`` payload straight out of the canonical store."""

    envelope = store.load(session_id)
    assert envelope is not None
    extension = envelope.extensions[CONVERSATION_EXTENSION_KEY]
    assert isinstance(extension, Mapping)
    return extension


def _stored_conversation(
    store: InMemorySessionStore, session_id: str = SESSION_ID
) -> ConversationState | None:
    """Read the conversation extension back from the canonical store itself."""

    envelope = store.load(session_id)
    if envelope is None or CONVERSATION_EXTENSION_KEY not in envelope.extensions:
        return None
    return ConversationState.from_dict(envelope.extensions[CONVERSATION_EXTENSION_KEY])


# ── Public conversational input builders ─────────────────────────────────────


def _user(
    message_id: str,
    content: str = "What changed in the plan?",
    *,
    created_at: str = TURN_1_AT,
    **overrides: Any,
) -> ConversationMessage:
    """Build one public user message with caller-supplied identity and time."""

    fields: dict[str, Any] = {
        "id": message_id,
        "session_id": SESSION_ID,
        "role": ConversationRole.USER,
        "content": content,
        "created_at": created_at,
    }
    fields.update(overrides)
    return ConversationMessage(**fields)


# ═══════════════════════════════════════════════════════════════════════════
# AT-DP-105 — the one connected acceptance
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp105_connected_canonical_conversation() -> None:
    """Execute the complete connected AT-DP-105 acceptance workflow."""

    # ─────────────────────────────────────────────────────────────────────────
    # Step 0 — the one real graph, the canonical approval store and the two
    # genuine authorized Domain projections (never hand-built views).
    # ─────────────────────────────────────────────────────────────────────────
    graph = _connected_graph()
    approval_repository = InMemoryApprovalRepository()
    approval = approval_repository.add_request(
        _make_operation_approval(
            APPROVAL_REF,
            primary_domain=PRIMARY_DOMAIN,
            supporting_domains=(SUPPORTING_DOMAIN,),
            operation_id="operation:dp105:assess",
            workflow_id=WORKFLOW_REF,
        )
    )
    assert approval_repository.get_request(APPROVAL_REF).status is (
        ApprovalRequestStatus.PENDING
    )

    baseline = _first_turn_projection()
    visibility = _visibility_projection(approvals=(approval,))

    # The views are genuine: the real resolver/composition/presentation chain
    # produced them, and the projection carries exactly the requested view.
    assert baseline.projection.conversational is baseline.view
    assert baseline.projection.selector is None
    assert baseline.resolution.id == FIRST_RESOLUTION_ID
    assert baseline.composition.resolution_id == baseline.resolution.id
    assert baseline.view.primary_domain == PRIMARY_DOMAIN
    assert baseline.view.supporting_domains == (SUPPORTING_DOMAIN,)
    assert baseline.view.source_refs == VISIBLE_SOURCES
    assert visibility.view.primary_domain == PRIMARY_DOMAIN
    assert visibility.view.supporting_domains == (SUPPORTING_DOMAIN,)

    responses: list[AssistantResponse] = []
    serialized: list[dict[str, Any]] = []

    def submit(
        message: ConversationMessage,
        *,
        request_id: str,
        assistant_message_id: str,
        assistant_created_at: str,
        expected_session_revision: int,
        domain_view: ConversationalDomainView | None,
        requested_capabilities: tuple[str, ...] = (),
    ) -> AssistantResponse:
        response = graph.service.submit(
            message,
            request_id=request_id,
            expected_session_revision=expected_session_revision,
            requested_capabilities=requested_capabilities,
            domain_view=domain_view,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
        )
        responses.append(response)
        serialized.append(response.to_dict())
        return response

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario A — first turn
    # ─────────────────────────────────────────────────────────────────────────
    revision_before = graph.revision()
    assert revision_before == 1
    loads_before = graph.observed.loads
    turn_one = _user("user-001", created_at=TURN_1_AT)
    first = submit(
        turn_one,
        request_id="req-001",
        assistant_message_id="assistant-001",
        assistant_created_at=TURN_1_RESPONSE_AT,
        expected_session_revision=revision_before,
        domain_view=baseline.view,
    )

    # The canonical session was read through the official store and the
    # canonical application boundary was entered exactly once, with the one
    # canonical MESSAGE_SUBMIT command of a conversational turn.
    assert graph.observed.loads > loads_before
    assert len(graph.handle.calls) == 1
    command, application_response = graph.handle.calls[0]
    assert isinstance(command, ApplicationCommand)
    assert command.operation is ApplicationOperation.MESSAGE_SUBMIT
    assert command.channel is ApplicationChannel.CONVERSATION
    assert command.actor_id == CONVERSATION_ACTOR_ID
    assert command.session_id == SESSION_ID
    assert command.request_id == "req-001"
    assert command.expected_session_revision == 1
    assert command.idempotency_key is None
    assert set(command.payload) == {"message_id", "content", "content_type"}
    assert command.payload["message_id"] == "user-001"
    assert command.payload["content"] == "What changed in the plan?"
    assert command.payload["content_type"] == "text/plain"

    # The real Orchestrator was reached exactly once and its canonical decision
    # is the one persisted in the real decision repository.
    decision = graph.decisions.get_by_request_id("req-001")
    assert decision is not None
    assert decision.session_id == SESSION_ID
    assert decision.channel is OrchestrationChannel.CONVERSATION
    assert decision.intent is IntentKind.QUESTION
    assert decision.execution_route is ExecutionRoute.DIRECT_RESPONSE
    assert [event.event_type for event in graph.events.events()].count(
        "orchestration.request_received"
    ) == 1

    # The canonical route selects the registered General fallback domain for one
    # plain public conversational message (remediation MAJOR-01: the message is
    # presented through the canonical ``question`` signal), and the application
    # response mirrors that decision without fabricating domain evidence.
    assert decision.primary_domain == str(GENERAL)
    assert decision.supporting_domains == ()
    assert application_response.status is ApplicationStatus.ROUTED
    assert application_response.error is None
    assert set(application_response.data) == {
        "session_id",
        "request_id",
        "status",
        "intent",
        "primary_domain",
        "supporting_domains",
        "profile_id",
        "route",
        "agent_id",
        "workflow_id",
        "approval_refs",
        "decision_id",
        "trace_refs",
        "reason_codes",
    }
    assert application_response.data["session_id"] == SESSION_ID
    assert application_response.data["status"] == ApplicationStatus.ROUTED.value
    # The canonical fallback reason of the persisted decision is the route the
    # application layer reports: nothing is upgraded beyond the canonical route.
    assert "DOMAIN_FALLBACK_SELECTED" in decision.reason_codes
    assert decision.policy_disposition is PolicyDisposition.ALLOW_ROUTE
    assert application_response.data["intent"] == decision.intent.value
    assert application_response.data["primary_domain"] == decision.primary_domain
    assert list(application_response.data["supporting_domains"]) == list(
        decision.supporting_domains
    )
    assert application_response.data["route"] == decision.execution_route.value
    assert application_response.data["decision_id"] == decision.decision_id
    assert application_response.data["agent_id"] == decision.selected_agent_id
    assert application_response.data["workflow_id"] == decision.workflow_id
    assert first.message.content == ROUTED_TEXT

    # The Domain evidence of the response is exactly the authorized projection's
    # evidence, and its primary domain is a canonical, registered and enabled
    # domain of the same registry the canonical domain router consults.
    assert first.domain_state["primary_domain"] == baseline.view.primary_domain
    assert first.domain_state["supporting_domains"] == tuple(
        baseline.view.supporting_domains
    )
    assert first.domain_state["confidence"] == baseline.view.confidence
    assert first.domain_state["status"] == baseline.view.status.value
    record = graph.registry.get_record(UNIVERSITY.slug)
    assert record is not None
    assert record.definition.enabled is True

    # Only visible Domain refs appear in the AssistantResponse.
    assert first.sources == baseline.view.source_refs == VISIBLE_SOURCES
    assert first.pending_questions == baseline.view.question_refs == ()
    assert first.approval_requests == baseline.view.approval_refs == ()
    assert first.workflow_updates == baseline.view.workflow_refs == ()
    assert first.memory_updates == baseline.view.memory_proposal_refs == ()
    assert first.warnings == baseline.view.warning_refs == ()
    assert first.proposed_actions == ()
    assert list(first.reasoning_summary["result_refs"]) == list(
        baseline.view.result_refs
    )
    assert list(first.reasoning_summary["contradiction_refs"]) == list(
        baseline.view.contradiction_refs
    )

    # conversation.v1 was persisted through the canonical SessionStore: it is
    # read back from the store itself, never from a side structure.
    assert graph.revision() == 2
    envelope = graph.store.load(SESSION_ID)
    assert envelope is not None
    assert envelope.revision == 2
    assert set(envelope.extensions) == {CONVERSATION_EXTENSION_KEY}
    assert graph.observed.committed[-1] == envelope
    stored = _stored_conversation(graph.store)
    assert stored is not None
    assert stored.session_id == SESSION_ID
    assert [message.id for message in stored.messages] == [
        "user-001",
        "assistant-001",
    ]
    assert stored.messages[0] == turn_one
    assert stored.messages[0].role is ConversationRole.USER
    assert stored.messages[1].role is ConversationRole.ASSISTANT
    assert stored.messages[1].content == ROUTED_TEXT
    assert ConversationState.from_dict(_raw_extension(graph.store)) == stored

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario B — second turn continuity
    # ─────────────────────────────────────────────────────────────────────────
    loads_before = graph.observed.loads
    assert graph.revision() == 2
    turn_two = _user(
        "user-002",
        "Add the health regimen to my plan.",
        created_at=TURN_2_AT,
    )
    second = submit(
        turn_two,
        request_id="req-002",
        assistant_message_id="assistant-002",
        assistant_created_at=TURN_2_RESPONSE_AT,
        expected_session_revision=2,
        domain_view=baseline.view,
    )

    # The same canonical session was loaded again through the official store and
    # the Domain/application/orchestration path was traversed again.
    assert graph.observed.loads > loads_before
    assert len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)) == 2
    assert graph.decisions.get_by_request_id("req-002") is not None
    assert len(graph.decisions.list_for_session(SESSION_ID)) == 2
    assert [event.event_type for event in graph.events.events()].count(
        "orchestration.request_received"
    ) == 2

    # Previous messages remain, the second exchange appends and the canonical
    # revision advances.
    assert graph.revision() == 3
    stored = graph.conversation()
    assert [message.id for message in stored.messages] == [
        "user-001",
        "assistant-001",
        "user-002",
        "assistant-002",
    ]
    assert stored.messages[0] == turn_one
    assert stored.messages[1] == first.message
    assert stored.messages[2] == turn_two
    assert second.message.id == "assistant-002"
    assert second.message.role is ConversationRole.ASSISTANT

    # No client transcript store participates: a brand-new client object over
    # the canonical store already reads the complete transcript, and the service
    # exposes no transcript of its own.
    fresh_client = SharedSessionConversationAdapter(graph.store)
    assert fresh_client.load_conversation(SESSION_ID) == stored
    assert graph.service.load(SESSION_ID) == stored
    # The canonical envelope still carries exactly the one conversation
    # extension: no second conversational persistence owner exists.
    second_envelope = graph.store.load(SESSION_ID)
    assert second_envelope is not None
    assert set(second_envelope.extensions) == {CONVERSATION_EXTENSION_KEY}

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario C — stale revision
    # ─────────────────────────────────────────────────────────────────────────
    saves_before = graph.observed.saves
    submits_before = len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT))
    stale = _user("user-003", "This turn must never be accepted.", created_at=TURN_3_AT)
    with pytest.raises(ConversationSessionConflictError) as failure:
        graph.service.submit(
            stale,
            request_id="req-stale-001",
            expected_session_revision=1,
            domain_view=baseline.view,
            assistant_message_id="assistant-stale-001",
            assistant_created_at=TURN_3_AT,
        )

    # Safe conflict: the stable public code, no gateway entry, no write, no new
    # message and no silent retry.
    assert failure.value.code is ConversationErrorCode.SESSION_CONFLICT
    assert len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)) == (
        submits_before
    )
    assert graph.observed.saves == saves_before
    assert graph.revision() == 3
    assert graph.message_ids() == [
        "user-001",
        "assistant-001",
        "user-002",
        "assistant-002",
    ]
    assert graph.decisions.get_by_request_id("req-stale-001") is None

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario D — edit lineage
    # ─────────────────────────────────────────────────────────────────────────
    replacement = _user(
        "user-001-edit",
        "What changed in the plan, and why?",
        created_at=TURN_4_AT,
    )
    edited = graph.service.edit(
        original_message_id="user-001",
        replacement=replacement,
        request_id="req-edit-001",
        expected_session_revision=3,
        domain_view=baseline.view,
        assistant_message_id="assistant-001-edit",
        assistant_created_at=TURN_4_RESPONSE_AT,
    )
    responses.append(edited)
    serialized.append(edited.to_dict())

    assert graph.revision() == 4
    stored = graph.conversation()
    assert [message.id for message in stored.messages] == [
        "user-001",
        "assistant-001",
        "user-002",
        "assistant-002",
        "user-001-edit",
        "assistant-001-edit",
    ]
    original = stored.message("user-001")
    effective = stored.message("user-001-edit")
    # The original is preserved byte-identical and the replacement carries the
    # service-enforced lineage.
    assert original == turn_one
    assert original.content == "What changed in the plan?"
    assert effective.lineage.supersedes_message_id == original.id
    assert effective.lineage.regenerates_message_id is None
    assert effective.content == "What changed in the plan, and why?"
    # A new assistant response exists and the canonical path was traversed again.
    assert edited.message.id == "assistant-001-edit"
    assert edited.message.lineage == ConversationLineage()
    assert graph.message_ids().count("assistant-001-edit") == 1
    assert len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)) == 3
    assert graph.decisions.get_by_request_id("req-edit-001") is not None

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario E — regeneration lineage
    # ─────────────────────────────────────────────────────────────────────────
    regenerated = graph.service.regenerate(
        session_id=SESSION_ID,
        response_message_id="assistant-001",
        request_id="req-regen-001",
        application_message_id="regen-input-001",
        expected_session_revision=4,
        domain_view=baseline.view,
        assistant_message_id="assistant-001-regen",
        assistant_created_at=TURN_5_RESPONSE_AT,
    )
    responses.append(regenerated)
    serialized.append(regenerated.to_dict())

    assert graph.revision() == 5
    stored = graph.conversation()
    # Regeneration appends no user message: it re-enters the canonical path.
    assert [message.id for message in stored.messages] == [
        "user-001",
        "assistant-001",
        "user-002",
        "assistant-002",
        "user-001-edit",
        "assistant-001-edit",
        "assistant-001-regen",
    ]
    assert stored.message("assistant-001") == first.message
    regenerated_message = stored.message("assistant-001-regen")
    assert regenerated_message.lineage.regenerates_message_id == "assistant-001"
    assert regenerated_message.lineage.supersedes_message_id is None
    assert regenerated.message.id == "assistant-001-regen"
    assert len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)) == 4
    assert graph.decisions.get_by_request_id("req-regen-001") is not None

    # No hidden reasoning exists anywhere in the regenerated response: the one
    # explanation surface is the bounded public reasoning summary.
    assert set(regenerated.reasoning_summary) == {
        "result_refs",
        "contradiction_refs",
    }
    assert dict(regenerated.message.metadata) == {}
    assert _forbidden_key_hits(regenerated.to_dict()) == ()
    assert _forbidden_value_hits(regenerated.to_dict()) == ()

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario F — capabilities and cancellation
    # ─────────────────────────────────────────────────────────────────────────
    capability_turn = _user(
        "user-003-caps",
        "Stream the answer, let me cancel it and upload a document.",
        created_at=TURN_6_AT,
    )
    capability_response = submit(
        capability_turn,
        request_id="req-caps-001",
        assistant_message_id="assistant-003",
        assistant_created_at=TURN_6_RESPONSE_AT,
        expected_session_revision=5,
        domain_view=baseline.view,
        requested_capabilities=(
            "response_streaming",
            "request_cancellation",
            "document_upload",
        ),
    )

    assert graph.revision() == 6
    rows = {state.capability: state for state in capability_response.capability_state}
    assert tuple(rows) == CONVERSATION_CAPABILITY_IDS
    streaming = rows["response_streaming"]
    assert streaming.requested is True
    assert streaming.status is ConversationCapabilityStatus.DEGRADED
    assert streaming.effective == "response_event_stream"
    assert streaming.reason == REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE
    cancellation = rows["request_cancellation"]
    assert cancellation.requested is True
    assert cancellation.status is ConversationCapabilityStatus.UNAVAILABLE
    assert cancellation.effective is None
    assert cancellation.reason == REASON_NO_CANCELLABLE_OWNER
    upload = rows["document_upload"]
    assert upload.requested is True
    assert upload.status is ConversationCapabilityStatus.UNAVAILABLE
    assert upload.effective is None
    assert upload.reason == REASON_NO_CANONICAL_STORAGE_OWNER
    # A request flag is descriptive only: the one command of the turn still
    # carries the public message alone.
    capability_command = graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)[-1]
    assert set(capability_command.payload) == {
        "message_id",
        "content",
        "content_type",
    }

    # Cancellation is delegated to the canonical gateway and reported honestly.
    saves_before = graph.observed.saves
    cancel_response = graph.service.cancel(
        request_id="req-cancel-001", target_request_id="req-001"
    )
    assert isinstance(cancel_response, ApplicationResponse)
    assert cancel_response.request_id == "req-cancel-001"
    assert cancel_response.status is ApplicationStatus.FAILED
    assert cancel_response.data is None
    assert cancel_response.error is not None
    assert cancel_response.error.code is ApplicationErrorCode.CAPABILITY_UNAVAILABLE
    assert cancel_response.error.message == CANCELLATION_UNAVAILABLE_MESSAGE
    assert cancel_response.error.retryable is False
    assert dict(cancel_response.error.details) == {}
    cancel_command, cancel_echo = graph.handle.calls[-1]
    assert isinstance(cancel_command, ApplicationCommand)
    assert cancel_command.operation is ApplicationOperation.REQUEST_CANCEL
    assert cancel_command.channel is ApplicationChannel.CONVERSATION
    assert cancel_command.session_id is None
    assert dict(cancel_command.payload) == {"request_id": "req-001"}
    assert cancel_echo == cancel_response
    # Cancellation owns no state: no write, no re-version, no retry.
    assert graph.observed.saves == saves_before
    assert graph.revision() == 6
    serialized.append(cancel_response.to_dict())

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario G — Bot and attachment non-authority
    # ─────────────────────────────────────────────────────────────────────────
    attachment = ConversationAttachmentRef(
        ref="artifact:123",
        kind="document",
        name="plan.txt",
        media_type="text/plain",
    )
    bot_turn = _user(
        "user-004",
        "Please keep this attachment for later.",
        created_at=TURN_7_AT,
        bot_id="bot-untrusted",
        references=("source:artifact:123",),
        attachments=(attachment,),
        metadata={"public_label": "attachment turn"},
    )
    bot_response = submit(
        bot_turn,
        request_id="req-bot-001",
        assistant_message_id="assistant-004",
        assistant_created_at=TURN_7_RESPONSE_AT,
        expected_session_revision=6,
        domain_view=baseline.view,
    )

    assert graph.revision() == 7
    stored = graph.conversation()
    persisted = stored.message("user-004")
    # Both are visible and persisted, as public conversation metadata/reference.
    assert persisted.bot_id == "bot-untrusted"
    assert persisted.attachments == (attachment,)
    assert persisted.references == ("source:artifact:123",)
    assert dict(persisted.metadata) == {"public_label": "attachment turn"}
    assert bot_response.message.bot_id == "bot-untrusted"
    assert bot_response.message.attachments == ()
    assert bot_response.message.references == ()

    # Neither changes the selected domain, the application role, the capability
    # state, the approval state or the orchestration authority.
    assert bot_response.domain_state["primary_domain"] == PRIMARY_DOMAIN
    assert bot_response.domain_state["supporting_domains"] == (SUPPORTING_DOMAIN,)
    bot_command = graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)[-1]
    assert bot_command.actor_id == CONVERSATION_ACTOR_ID
    assert bot_command.channel is ApplicationChannel.CONVERSATION
    assert set(bot_command.payload) == {"message_id", "content", "content_type"}
    assert bot_response.capability_state == ConversationCapabilityResolver().resolve(())
    bot_rows = {state.capability: state for state in bot_response.capability_state}
    assert bot_rows["bot_association"].status is (
        ConversationCapabilityStatus.AVAILABLE
    )
    assert bot_rows["bot_association"].effective == "opaque_non_authoritative"
    assert bot_rows["bot_association"].requested is False
    assert bot_rows["document_upload"].status is (
        ConversationCapabilityStatus.UNAVAILABLE
    )
    assert approval_repository.get_request(APPROVAL_REF).status is (
        ApprovalRequestStatus.PENDING
    )
    bot_decision = graph.decisions.get_by_request_id("req-bot-001")
    assert bot_decision is not None
    # The opaque bot association selected nothing: the turn takes the same
    # canonical question route every conversational turn takes (remediation
    # MAJOR-01), and no agent, workflow or domain authority was derived from it.
    assert bot_decision.execution_route is ExecutionRoute.DIRECT_RESPONSE
    assert bot_decision.primary_domain == str(GENERAL)
    assert bot_decision.selected_agent_id is None
    assert bot_decision.workflow_id is None

    # An attachment reference creates no parallel file store and no file bytes.
    assert set(attachment.to_dict()) == {"ref", "kind", "name", "media_type"}
    assert all(isinstance(value, str | None) for value in attachment.to_dict().values())
    bot_envelope = graph.store.load(SESSION_ID)
    assert bot_envelope is not None
    assert _binary_hits(bot_envelope.extensions) == ()
    assert _binary_hits(bot_response.to_dict()) == ()
    assert not any(
        value.startswith(("/", "file://", "~/", "C:\\"))
        for value in _strings(dict(bot_envelope.extensions))
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario H — visibility is not authorization
    # ─────────────────────────────────────────────────────────────────────────
    assert visibility.view.source_refs == VISIBLE_SOURCES
    assert visibility.view.question_refs == (QUESTION_REF,)
    assert visibility.view.approval_refs == (APPROVAL_REF,)
    assert visibility.view.workflow_refs == (WORKFLOW_REF,)
    assert visibility.view.supporting_domains == (SUPPORTING_DOMAIN,)

    # The canonical approval state captured before the turn: the assertions
    # after the turn prove it transitioned nowhere by comparing the full
    # recorded state (see below).
    approval_state_before = approval_repository.get_request(APPROVAL_REF).to_dict()

    visibility_turn = _user(
        "user-005",
        "Show me the reviewed plan and its approvals.",
        created_at=TURN_8_AT,
    )
    visible = submit(
        visibility_turn,
        request_id="req-visible-001",
        assistant_message_id="assistant-005",
        assistant_created_at=TURN_8_RESPONSE_AT,
        expected_session_revision=7,
        domain_view=visibility.view,
    )

    assert graph.revision() == 8
    # The authorized refs appear in the assistant response.
    assert visible.sources == VISIBLE_SOURCES
    assert visible.pending_questions == (QUESTION_REF,)
    assert visible.approval_requests == (APPROVAL_REF,)
    assert visible.workflow_updates == (WORKFLOW_REF,)
    # No ref beyond the authorized projection appears: the response ref surface
    # is exactly the view's ref surface.
    response_refs = (
        set(visible.sources)
        | set(visible.pending_questions)
        | set(visible.approval_requests)
        | set(visible.workflow_updates)
        | set(visible.memory_updates)
        | set(visible.warnings)
        | set(visible.reasoning_summary["result_refs"])
        | set(visible.reasoning_summary["contradiction_refs"])
    )
    view_refs = (
        set(visibility.view.source_refs)
        | set(visibility.view.question_refs)
        | set(visibility.view.approval_refs)
        | set(visibility.view.workflow_refs)
        | set(visibility.view.memory_proposal_refs)
        | set(visibility.view.warning_refs)
        | set(visibility.view.contradiction_refs)
        | set(visibility.view.result_refs)
    )
    assert response_refs == view_refs

    # An approval_ref in the output does not become approved: the canonical
    # approval authority still reports the request pending, and the response
    # fabricated no approval outcome.  The PENDING check is the load-bearing
    # evidence; the full-state comparison is what keeps it non-vacuous — it
    # fails the moment any seam approves, resolves or otherwise touches the
    # canonical request.  (The earlier
    # ``list_requests(status=APPROVED) == ()`` / ``list_decisions(APPROVAL_REF)
    # == ()`` pair was deliberately removed: nothing in this vertical can
    # record an approval decision, so those assertions passed vacuously.)
    assert approval_repository.get_request(APPROVAL_REF).status is (
        ApprovalRequestStatus.PENDING
    )
    assert (
        approval_repository.get_request(APPROVAL_REF).to_dict() == approval_state_before
    )
    assert visible.message.content == ROUTED_TEXT
    assert visible.domain_state["primary_domain"] == PRIMARY_DOMAIN

    # A proposed action reference does not execute: the response materializes no
    # action.  The canonical decision of this turn is the same canonical
    # question route every conversational turn takes (remediation MAJOR-01):
    # it selects the fallback domain and the direct-response route, and it
    # records no agent, no workflow and no approval of its own.
    assert visible.proposed_actions == ()
    visible_decision = graph.decisions.get_by_request_id("req-visible-001")
    assert visible_decision is not None
    assert visible_decision.execution_route is ExecutionRoute.DIRECT_RESPONSE
    assert visible_decision.selected_agent_id is None
    assert visible_decision.workflow_id is None
    assert visible_decision.approval_refs == ()
    assert visible_decision.policy_disposition is PolicyDisposition.ALLOW_ROUTE

    # Refs the canonical Phase 10.45 projection omits stay absent from both the
    # authorized view and the conversational response.  The plan genuinely
    # carried them, so their absence proves a real canonical filter, never a
    # vacuous expectation.  Stated exactly, what is proven here is
    # VISIBILITY-based omission: an item flagged ``visible=False``, an item
    # placed only in a non-visible section, and a stale group ref with no
    # effectively visible display item (the real filter is
    # ``_visible_item_ref_ids`` / ``_visible_group_refs``).  It is NOT a
    # domain-unselection proof: ``finding:dp105:oppositions-unselected``
    # carries ``visible=False`` (and sits in no section), and the canonical
    # item filter consults no domain selection at all — item ``domain_ids``
    # only narrow ``supporting_domains`` — so an effectively visible
    # unselected-domain item is not omitted by that filter.  Domain-based
    # omission is not a behaviour of this projection and is not claimed here.
    plan_text = _strings(visibility.presentation.to_dict())
    for reference in OMITTED_REFS:
        assert reference in plan_text
        assert reference not in _strings(visibility.view.to_dict())
        assert reference not in _strings(visible.to_dict())
        assert reference not in graph.message_ids()
    assert "domain:legal" in plan_text
    assert "domain:oppositions" in plan_text
    assert "domain:legal" not in _strings(visibility.view.to_dict())
    assert "domain:oppositions" not in _strings(visibility.view.to_dict())
    assert visibility.view.supporting_domains == (SUPPORTING_DOMAIN,)

    # ─────────────────────────────────────────────────────────────────────────
    # Scenario I — public safety
    # ─────────────────────────────────────────────────────────────────────────
    saves_before = graph.observed.saves
    submits_before = len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT))
    stored_before = graph.conversation()

    # Attacker metadata with secret-like keys and nested raw-exception-like
    # content is rejected before persistence.
    with pytest.raises(ValueError):
        _user(
            "user-attacker-001",
            created_at=TURN_8_AT,
            metadata={"api_key": "sk-live-attacker"},
        )
    with pytest.raises(ValueError):
        _user(
            "user-attacker-002",
            created_at=TURN_8_AT,
            metadata={"outer": {"refreshToken": "attacker"}},
        )
    with pytest.raises(ValueError):
        _user(
            "user-attacker-003",
            created_at=TURN_8_AT,
            metadata={"stack_trace": "attacker"},
        )
    with pytest.raises(TypeError):
        _user(
            "user-attacker-004",
            created_at=TURN_8_AT,
            metadata={"detail": ValueError("canonical parser blew up")},
        )
    with pytest.raises(TypeError):
        _user(
            "user-attacker-005",
            created_at=TURN_8_AT,
            metadata={"payload": b"raw-bytes"},
        )

    assert graph.observed.saves == saves_before
    assert len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)) == (
        submits_before
    )
    assert graph.revision() == 8
    assert graph.conversation() == stored_before
    assert not any(
        message_id.startswith("user-attacker") for message_id in graph.message_ids()
    )
    assert _forbidden_key_hits(_raw_extension(graph.store)) == ()
    assert _forbidden_value_hits(_raw_extension(graph.store)) == ()

    # The bounded screens are not vacuous: every one of them rejects a shaped
    # positive control before it is trusted over the acceptance payloads.
    assert _forbidden_key_hits({"api_key": "sk-live-attacker"}) == ("api_key",)
    assert _forbidden_key_hits({"outer": {"refreshToken": "attacker"}}) == (
        "refreshToken",
    )
    assert _forbidden_key_hits({"stack_trace": "attacker"}) == ("stack_trace",)
    assert _forbidden_value_hits({"detail": "Traceback (most recent call last)"})
    assert _forbidden_value_hits({"detail": "ValueError: canonical parser"})
    assert _binary_hits({"payload": b"raw-bytes"}) == ("bytes",)

    # Every acceptance response dict, walked for forbidden
    # private-reasoning/secret fragments.
    assert len(serialized) == 8
    inspected: list[Any] = [*serialized, _raw_extension(graph.store)]
    inspected.append(visibility.projection.to_dict())
    inspected.append(baseline.projection.to_dict())
    inspected.append(dict(bot_envelope.extensions))
    for payload in inspected:
        assert _forbidden_key_hits(payload) == ()
        assert _forbidden_value_hits(payload) == ()
        assert _binary_hits(payload) == ()

    # Every public acceptance payload is JSON-native: each projected response,
    # the persisted extension and each interface projection must survive a JSON
    # round trip with a stable sorted-key encoding (a payload that is not
    # JSON-native fails to serialize, and one that loses information fails the
    # byte-identical re-encoding).
    json_native: list[Any] = [*serialized, graph.conversation().to_dict()]
    json_native.append(visibility.projection.to_dict())
    json_native.append(baseline.projection.to_dict())
    for payload in json_native:
        encoded = json.dumps(payload, sort_keys=True)
        assert json.dumps(json.loads(encoded), sort_keys=True) == encoded

    # The connected traversal count is the frozen one: seven canonical message
    # turns (A, B, D, E, F, G, H) plus the request-scoped cancellation.
    assert len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)) == 7
    assert len(graph.handle.calls) == 8
    assert len(graph.decisions.list_for_session(SESSION_ID)) == 7
    assert [event.event_type for event in graph.events.events()].count(
        "orchestration.request_received"
    ) == 7
    assert graph.revision() == 8
    assert graph.observed.committed[-1].revision == 8

    # ─────────────────────────────────────────────────────────────────────────
    # Domain-route positive control — the composed canonical domain leg is live
    # ─────────────────────────────────────────────────────────────────────────
    # This is the SAME graph whose conversational turns above canonically
    # clarify: one plain public conversational message carries no structured
    # intent shape, so the real pipeline stops at clarification and never
    # reaches domain routing.  That is a property of the conversational entry
    # point, not of the domain leg.  The two requests below are built directly
    # as structured canonical ``OrchestrationRequest``s and driven through the
    # SAME real orchestrator with no mock added (the non-conversational pattern
    # ``tests/application/test_phase11_3_dp103_acceptance.py`` uses).  They are
    # NOT conversational turns: they never call ``ConversationService``, never
    # enter the gateway and never persist a message, so they are excluded from
    # the conversational traversal totals re-stated at the end of this block.
    composed_router = vars(graph.orchestrator)["_domain_router"]
    assert isinstance(composed_router, CanonicalDomainRouter)
    assert isinstance(vars(composed_router)["_resolver"], DefaultDomainResolver)

    goal_control = graph.orchestrator.orchestrate(
        OrchestrationRequest(
            request_id="control-domain-goal-001",
            user_id=CONVERSATION_ACTOR_ID,
            channel=OrchestrationChannel.CONVERSATION,
            session_id=SESSION_ID,
            input={"goal": {"title": "Complete task"}},
        )
    )
    question_control = graph.orchestrator.orchestrate(
        OrchestrationRequest(
            request_id="control-domain-question-001",
            user_id=CONVERSATION_ACTOR_ID,
            channel=OrchestrationChannel.CONVERSATION,
            session_id=SESSION_ID,
            input={"question": "What changed in the plan?"},
        )
    )

    # The routing observation is the real composed router's own decision
    # surfaced canonically: the real orchestrator emits one
    # ``orchestration.domain_resolved`` event per request whose domain leg it
    # ran, carrying the real ``DomainRouteDecision`` facts.  Nine exist: the
    # seven conversational turns (each now presented through the canonical
    # question signal by remediation MAJOR-01) plus the two controls, and the
    # two control events are the last two in emission order.
    domain_events = [
        event
        for event in graph.events.events()
        if event.event_type == "orchestration.domain_resolved"
    ]
    assert [event.request_id for event in domain_events][-2:] == [
        "control-domain-goal-001",
        "control-domain-question-001",
    ]
    for event in domain_events:
        assert event.payload["status"] == (
            DomainResolutionStatus.INSUFFICIENT_INFORMATION.value
        )
        assert event.payload["primary_domain"] == str(GENERAL)
        assert event.payload["needs_clarification"] is False

    # The goal-shaped request escalates through a real domain route: the real
    # canonical resolver selected the registered General fallback (the request
    # carries no explicit domain evidence) and the restrictive policy escalated
    # the resulting human-escalation route.
    goal_decision = graph.decisions.get_by_request_id("control-domain-goal-001")
    assert goal_decision is not None
    assert goal_control.status is OrchestrationStatus.ESCALATED
    assert goal_control.route is ExecutionRoute.HUMAN_ESCALATION
    assert goal_control.primary_domain == str(GENERAL)
    assert goal_decision.intent is IntentKind.GOAL
    assert goal_decision.execution_route is ExecutionRoute.HUMAN_ESCALATION
    assert goal_decision.policy_disposition is PolicyDisposition.ESCALATE
    assert goal_decision.primary_domain == str(GENERAL)
    assert goal_decision.supporting_domains == ()
    assert goal_decision.selected_agent_id is None
    assert "DOMAIN_FALLBACK_SELECTED" in goal_decision.reason_codes

    # The question-shaped request routes with a primary domain: the same real
    # resolver/registry chain selected General and the deterministic policy
    # allowed the direct-response route.
    question_decision = graph.decisions.get_by_request_id("control-domain-question-001")
    assert question_decision is not None
    assert question_control.status is OrchestrationStatus.ROUTED
    assert question_control.route is ExecutionRoute.DIRECT_RESPONSE
    assert question_control.primary_domain == str(GENERAL)
    assert question_decision.intent is IntentKind.QUESTION
    assert question_decision.execution_route is ExecutionRoute.DIRECT_RESPONSE
    assert question_decision.policy_disposition is PolicyDisposition.ALLOW_ROUTE
    assert question_decision.primary_domain == str(GENERAL)
    assert question_decision.supporting_domains == ()
    assert "DOMAIN_FALLBACK_SELECTED" in question_decision.reason_codes

    # The routed domain is a real domain of the same registry the composed
    # router consults, and both decisions carry the trace references of the
    # real canonical resolution that produced them (asserted by shape: the
    # composed graph generates those identities internally and nothing here
    # reads a clock).
    general_record = graph.registry.get_record(GENERAL.slug)
    assert general_record is not None
    assert general_record.definition.enabled is True
    for decision in (goal_decision, question_decision):
        assert len(decision.trace_refs) == 2
        assert decision.trace_refs[0].startswith("domain-resolution:")
        assert decision.trace_refs[1].startswith("domain-resolution-context:")
        assert all(ref.split(":", 1)[1] for ref in decision.trace_refs)

    # Every conversational decision of this session carries the canonical
    # question route (remediation MAJOR-01) — the same registered General
    # fallback domain and the same real canonical resolution trace references
    # the two structured control requests carry, through the SAME composed
    # routers — while the control's structured goal request additionally
    # escalates.
    session_decisions = graph.decisions.list_for_session(SESSION_ID)
    conversational_decisions = [
        decision
        for decision in session_decisions
        if not decision.request_id.startswith("control-domain-")
    ]
    assert len(conversational_decisions) == 7
    assert all(
        decision.primary_domain == str(GENERAL)
        and decision.trace_refs[0].startswith("domain-resolution:")
        for decision in conversational_decisions
    )

    # Conversational traversal totals, re-stated after the positive control:
    # the seven canonical message turns (A, B, D, E, F, G, H) and the
    # request-scoped cancellation reached the gateway exactly as before — the
    # control is not a conversational turn — while the canonical decision
    # repository and the event stream now also hold the control's two requests.
    assert len(graph.handle.commands(ApplicationOperation.MESSAGE_SUBMIT)) == 7
    assert len(graph.handle.calls) == 8
    assert len(session_decisions) == 9
    assert [event.event_type for event in graph.events.events()].count(
        "orchestration.request_received"
    ) == 9
    assert [event.event_type for event in graph.events.events()].count(
        "orchestration.domain_resolved"
    ) == 9
    assert not any(
        message_id.startswith("control-domain-") for message_id in graph.message_ids()
    )
    assert graph.revision() == 8
    assert graph.observed.committed[-1].revision == 8
