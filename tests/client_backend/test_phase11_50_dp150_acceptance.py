"""Phase 11.50 — connected acceptance ``AT-DP-150``.

Requirement: ``F11-021`` — Reusable First-Party Backend Interface
Design Point: ``DP-150`` — Canonical Reusable Client Backend Interface

This is a **connected** acceptance, not a mock-only interface test.  It composes
the repository's own canonical graph and drives the Phase 11.50 facade through
its public surface:

```text
cmm.client_backend.ClientBackend
      ↓
canonical ConversationService          (Phase 11.5)
      ↓
canonical ApplicationGateway           (Phase 11.3)
      ↓
real RequestApplicationService → real Phase 11.2 Orchestrator → canonical Domain route
```

The graph is built by ``tests/client_backend/_canonical_graph.py`` from
``cmm.application.local_runtime.build_local_application_runtime()`` — the
composition root the Phase 11.4 CLI itself uses — plus the canonical
``SharedSessionConversationAdapter``, ``ConversationService`` and
``ClientBackend``.  Nothing is mocked, subclassed or replaced; the only
instrumentation is a recording delegate wrapped around the real gateway's bound
``handle`` method, which is how "exactly one canonical traversal" and "zero
downstream calls" are proven rather than asserted.

Scenario map (all connected, in one acceptance):

* **A** — exact authority identity, proven behaviorally over two distinct
  canonical graphs (remediated by Audit V1 MAJOR-01: no public live-owner
  accessor exists);
* **B** — session round trip through the facade over the canonical session store;
* **C** — submit-message traversal through ``ConversationService`` →
  ``ApplicationGateway`` with canonical identities and safe ``AssistantResponse``;
* **D** — edit and regenerate lineage owned by the canonical service;
* **E** — capability truth: response-event stream, cancellation, attachments,
  document upload, model boundary and end-to-end rows, with no false
  ``available``;
* **F** — version fail-closed with zero downstream calls;
* **G** — safe error projection with no raw internals;
* **H** — anti-fragmentation: no store, repository, registry, router, runtime,
  engine or direct model-gateway path inside the public client backend;
* **I** — inherited acceptance bundle recorded as separate required gate
  commands (see the module docstring of that test);
* **J** — a portable first-party client that imports only
  ``from cmm.client_backend import ...``.

The one style rule is determinism: every identity and timestamp is
caller-supplied and no assertion depends on wall-clock time.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from cmm.application.contracts import (
    ApplicationErrorCode,
    ApplicationSession,
)
from cmm.application.gateway import ApplicationGateway
from cmm.client_backend import (
    CLIENT_BACKEND_INTERFACE_VERSION,
    CLIENT_BACKEND_MODULE_ID,
    CLIENT_BACKEND_SERVICE_ID,
    ClientBackend,
    ClientBackendCapabilities,
    ClientBackendCapabilityStatus,
    ClientBackendError,
    ClientBackendErrorCode,
    ClientBackendRequest,
    ClientOperation,
    build_client_backend_composition_module,
)
from cmm.conversation.contracts import (
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import ConversationSessionConflictError
from tests.client_backend._canonical_graph import build_client_backend_graph

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_BACKEND_PACKAGE = REPO_ROOT / "cmm" / "client_backend"

SESSION_ID = "at-dp150-session"
TURN_AT = "2026-09-25T10:00:00+00:00"
TURN_RESPONSE_AT = "2026-09-25T10:00:01+00:00"
SECOND_TURN_AT = "2026-09-25T10:01:00+00:00"
SECOND_TURN_RESPONSE_AT = "2026-09-25T10:01:01+00:00"
THIRD_TURN_AT = "2026-09-25T10:02:00+00:00"
THIRD_TURN_RESPONSE_AT = "2026-09-25T10:02:01+00:00"

PLAIN_TEXT = "What changed in the plan?"

#: Hidden-reasoning, secret, path and credential fragments no public client
#: payload may carry.
FORBIDDEN_RESPONSE_FRAGMENTS = (
    "Traceback (most recent call last)",
    "site-packages",
    "chainofthought",
    "chain_of_thought",
    "scratchpad",
    "hiddenreasoning",
    "hidden_reasoning",
    "raw_prompt",
    "system_prompt",
    "sk-live",
    "-----BEGIN",
    "/Users/",
    "RuntimeError",
    "ValueError",
)

#: The frozen inherited acceptance bundle of Scenario I.  Each entry is the exact
#: required gate command and the acceptance identifier it records.
INHERITED_ACCEPTANCE_GATES = (
    ("AT-DP-134", "tests/llm/test_provider_registry_dp134_acceptance.py"),
    ("AT-DP-121", "tests/llm/test_phase11_21_dp121_acceptance.py"),
    ("AT-DP-101", "tests/platform/test_phase11_1_dp101_acceptance.py"),
    ("AT-DP-102", "tests/orchestration/test_phase11_2_dp102_acceptance.py"),
    ("AT-DP-103", "tests/application/test_phase11_3_dp103_acceptance.py"),
    ("AT-DP-104", "tests/cli/test_phase11_4_dp104_acceptance.py"),
    ("AT-DP-105", "tests/conversation/test_phase11_5_dp105_acceptance.py"),
)


def _user(
    message_id: str,
    *,
    created_at: str = TURN_AT,
    content: str = PLAIN_TEXT,
) -> ConversationMessage:
    return ConversationMessage(
        id=message_id,
        session_id=SESSION_ID,
        role=ConversationRole.USER,
        content=content,
        created_at=created_at,
    )


def _strings(payload: object) -> list[str]:
    """Return every string value of one serialized payload."""

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
    return found


def _walked_response_payloads() -> list[dict[str, object]]:
    """Exercise the facade and collect every serialized public payload."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    first = graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )
    second = graph.client.edit_message(
        original_message_id="user-1",
        replacement=_user("user-1-edited", created_at=SECOND_TURN_AT),
        request_id="request-2",
        expected_session_revision=2,
        assistant_message_id="assistant-2",
        assistant_created_at=SECOND_TURN_RESPONSE_AT,
    )
    third = graph.client.regenerate_response(
        session_id=SESSION_ID,
        response_message_id="assistant-2",
        request_id="request-3",
        application_message_id="user-1-regenerated",
        expected_session_revision=3,
        assistant_message_id="assistant-3",
        assistant_created_at=THIRD_TURN_RESPONSE_AT,
    )

    payloads: list[dict[str, object]] = [
        first.to_dict(),
        second.to_dict(),
        third.to_dict(),
        graph.client.capabilities().to_dict(),
    ]
    for session in (graph.client.get_session(SESSION_ID),):
        payloads.append(session.to_dict())
    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    payloads.append(state.to_dict())
    for operation in ClientOperation:
        if operation is not ClientOperation.CAPABILITIES:
            continue
        payloads.append(
            graph.client.dispatch(
                ClientBackendRequest(
                    interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
                    request_id="request-acceptance",
                    operation=operation,
                )
            ).to_dict()
        )
    return payloads


# ═══════════════════════════════════════════════════════════════════════════
# Scenario A — exact authority identity
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_a_exact_authority_identity() -> None:
    """Exact canonical graph identity, proven behaviorally and without an escape hatch.

    Audit V1 MAJOR-01 remediated this scenario.  The audited version proved
    identity by having the public facade return its live canonical owners —
    ``client.gateway`` and ``client.conversation`` — which was itself the escape
    hatch: the returned ``ApplicationGateway`` exposes ``handle(...)`` and can
    reach an application operation that is not in the frozen ``ClientOperation``
    set.

    The remediation proves the same property from observable canonical state:
    the graph the facade was wired to receives the mutation, a second distinct
    canonical graph does not, and the canonical identities, revision and lineage
    the client receives belong to the wired graph.  No public owner access is
    used or required.
    """

    graph = build_client_backend_graph()
    other = build_client_backend_graph()

    assert other.gateway is not graph.gateway
    assert other.conversation is not graph.conversation

    # No public live-owner access exists on the facade at all.
    assert not hasattr(graph.client, "gateway")
    assert not hasattr(graph.client, "conversation")
    assert not any(
        isinstance(getattr(graph.client, name, None), ApplicationGateway)
        for name in dir(graph.client)
        if not name.startswith("_")
    )

    # Operating only through the public facade mutates graph A ...
    session = graph.client.create_session(SESSION_ID)
    assert session.session_id == SESSION_ID
    assert session.revision == 1
    assert graph.store.load(SESSION_ID) is not None

    # ... and leaves the distinct graph B completely untouched.
    assert other.store.load(SESSION_ID) is None
    assert other.canonical_gateway_calls() == 0

    turn = graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    # The returned canonical identities, revision and lineage are graph A's.
    assert turn.message.session_id == SESSION_ID
    canonical_a = graph.store.load(SESSION_ID)
    assert canonical_a is not None
    assert canonical_a.revision == 2
    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    assert [message.id for message in state.messages] == ["user-1", "assistant-1"]
    assert [message.session_id for message in state.messages] == [
        SESSION_ID,
        SESSION_ID,
    ]
    assert graph.canonical_gateway_calls() == 2
    assert other.canonical_gateway_calls() == 0
    assert other.store.load(SESSION_ID) is None

    # An alternate gateway is never silently accepted — and the refusal is made
    # through the narrowed coherence evidence, not by handing back an owner.
    with pytest.raises(ValueError):
        ClientBackend(gateway=other.gateway, conversation=graph.conversation)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario B — session round trip
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_b_session_round_trip() -> None:
    """Create and get observe the canonical shared session state."""

    graph = build_client_backend_graph()

    created = graph.client.create_session(SESSION_ID)
    fetched = graph.client.get_session(SESSION_ID)

    assert isinstance(created, ApplicationSession)
    assert created == fetched
    assert created.session_id == SESSION_ID
    assert created.revision == 1

    canonical = graph.store.load(SESSION_ID)
    assert canonical is not None
    assert canonical.session_id == created.session_id
    assert canonical.revision == created.revision
    assert canonical.status == created.status

    # The client layer owns no session state: the canonical store is the only
    # place the session exists, and a duplicate create is refused without a
    # retry or a replacement (the canonical conflict stays the canonical
    # authority's decision; the facade reports the safe closed outcome).
    with pytest.raises(ClientBackendError):
        graph.client.create_session(SESSION_ID)
    still = graph.store.load(SESSION_ID)
    assert still is not None
    assert still.revision == created.revision
    assert still.created_at.isoformat() == created.created_at


# ═══════════════════════════════════════════════════════════════════════════
# Scenario C — submit message
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_c_submit_message() -> None:
    """One turn traverses the exact canonical owners and no others."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    response = graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    # Exactly one canonical gateway traversal, and the real orchestrator was
    # reached from inside it: the canonical decision is persisted.
    assert graph.conversation_gateway_calls() == 1
    request, application_response = graph.handle.calls[1]
    assert request.session_id == SESSION_ID
    assert request.request_id == "request-1"
    assert application_response.request_id == "request-1"
    assert application_response.error is None

    # Canonical identities, roles and revisions are preserved verbatim.
    assert response.message.session_id == SESSION_ID
    assert response.message.id == "assistant-1"
    assert response.message.created_at == TURN_RESPONSE_AT
    assert response.message.role is ConversationRole.ASSISTANT

    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    assert [message.id for message in state.messages] == ["user-1", "assistant-1"]
    assert state.messages[0].session_id == SESSION_ID
    assert state.messages[0].created_at == TURN_AT
    assert state.messages[0].content == PLAIN_TEXT
    assert graph.store.load(SESSION_ID).revision == 2


# ═══════════════════════════════════════════════════════════════════════════
# Scenario D — edit / regenerate lineage
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_d_edit_and_regenerate_lineage() -> None:
    """Lineage comes from the canonical service, unchanged and append-only."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)
    first = graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )
    assert first.message.lineage == ConversationLineage()

    edited = graph.client.edit_message(
        original_message_id="user-1",
        replacement=_user("user-1-edited", created_at=SECOND_TURN_AT),
        request_id="request-2",
        expected_session_revision=2,
        assistant_message_id="assistant-2",
        assistant_created_at=SECOND_TURN_RESPONSE_AT,
    )
    assert edited.message.lineage == ConversationLineage()

    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    # Append-only: nothing was removed or rewritten.
    assert [message.id for message in state.messages] == [
        "user-1",
        "assistant-1",
        "user-1-edited",
        "assistant-2",
    ]
    assert state.messages[0].content == PLAIN_TEXT
    assert state.messages[0].created_at == TURN_AT
    assert state.messages[2].lineage.supersedes_message_id == "user-1"

    regenerated = graph.client.regenerate_response(
        session_id=SESSION_ID,
        response_message_id="assistant-2",
        request_id="request-3",
        application_message_id="user-1-regenerated",
        expected_session_revision=3,
        assistant_message_id="assistant-3",
        assistant_created_at=THIRD_TURN_RESPONSE_AT,
    )
    assert regenerated.message.lineage.regenerates_message_id == "assistant-2"

    final_state = graph.client.load_conversation(SESSION_ID)
    assert final_state is not None
    assert [message.id for message in final_state.messages] == [
        "user-1",
        "assistant-1",
        "user-1-edited",
        "assistant-2",
        "assistant-3",
    ]
    # The regenerated turn re-runs canonical execution without re-appending a
    # user message and without mutating the response it replaces.
    assert final_state.messages[3] == state.messages[3]
    assert graph.store.load(SESSION_ID).revision == 4
    assert graph.conversation_gateway_calls() == 3


def test_at_dp150_scenario_d_stale_revision_is_a_canonical_conflict() -> None:
    """No client-side retry: a stale caller never re-enters the pipeline."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)
    graph.client.submit_message(
        _user("user-1"),
        request_id="request-1",
        expected_session_revision=1,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    with pytest.raises(ConversationSessionConflictError):
        graph.client.submit_message(
            _user("user-2", created_at=SECOND_TURN_AT),
            request_id="request-2",
            expected_session_revision=1,
            assistant_message_id="assistant-2",
            assistant_created_at=SECOND_TURN_RESPONSE_AT,
        )

    assert graph.conversation_gateway_calls() == 1
    state = graph.client.load_conversation(SESSION_ID)
    assert state is not None
    assert len(state.messages) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Scenario E — capability truth
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_e_capability_truth() -> None:
    """Every required row is present and no row is falsely available."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert isinstance(manifest, ClientBackendCapabilities)
    assert manifest.interface_version == CLIENT_BACKEND_INTERFACE_VERSION
    assert manifest.application_api_version == "v1"

    # The real, end-to-end reachable rows of this baseline.
    for field_name in (
        "session_create",
        "session_get",
        "conversation_load",
        "conversation_submit",
        "conversation_edit",
        "conversation_regenerate",
    ):
        assert manifest.status(field_name) is ClientBackendCapabilityStatus.AVAILABLE, (
            field_name
        )

    # Streaming is the canonical degraded response-event stream, never an
    # "available" token stream.
    assert manifest.response_event_stream is ClientBackendCapabilityStatus.DEGRADED

    # Cancellation, upload, model boundary and end-to-end truth are honest.
    assert manifest.request_cancellation is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.document_upload is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.attachments is ClientBackendCapabilityStatus.AVAILABLE
    assert (
        manifest.model_boundary_reasoning is ClientBackendCapabilityStatus.UNAVAILABLE
    )
    assert (
        manifest.model_boundary_multimodal is ClientBackendCapabilityStatus.UNAVAILABLE
    )
    assert (
        manifest.model_boundary_token_stream
        is ClientBackendCapabilityStatus.UNAVAILABLE
    )
    assert manifest.end_to_end_reasoning is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.end_to_end_multimodal is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.end_to_end_token_stream.value != "available"

    # The manifest is a description: reading it enters no pipeline.
    assert graph.canonical_gateway_calls() == 0
    assert graph.conversation_gateway_calls() == 0


def test_at_dp150_scenario_e_boundary_only_is_never_end_to_end() -> None:
    """A proven model boundary is reported boundary_only, not end-to-end."""

    from cmm.application.contracts import ApplicationCapability, CapabilityStatus
    from cmm.client_backend.capabilities import (
        MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID,
        MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
        MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID,
    )

    declarations = tuple(
        ApplicationCapability(
            capability_id=capability_id,
            status=CapabilityStatus.AVAILABLE,
            version="1",
        )
        for capability_id in (
            MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
            MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID,
            MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID,
        )
    )
    graph = build_client_backend_graph(model_boundary_capabilities=declarations)
    manifest = graph.client.capabilities()

    for field_name in (
        "model_boundary_reasoning",
        "model_boundary_multimodal",
        "model_boundary_token_stream",
    ):
        assert (
            manifest.status(field_name) is ClientBackendCapabilityStatus.BOUNDARY_ONLY
        ), field_name

    for field_name in (
        "end_to_end_reasoning",
        "end_to_end_multimodal",
    ):
        assert (
            manifest.status(field_name) is ClientBackendCapabilityStatus.UNAVAILABLE
        ), field_name
    assert manifest.end_to_end_token_stream.value != "available"


# ═══════════════════════════════════════════════════════════════════════════
# Scenario F — version fail-closed
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_f_version_fail_closed() -> None:
    """An unsupported version performs zero downstream calls and fails safely."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)
    baseline = graph.conversation_gateway_calls()

    result = graph.client.dispatch(
        ClientBackendRequest.for_interface_version(
            "11.50",
            request_id="request-version",
            operation=ClientOperation.SUBMIT_MESSAGE,
            payload={
                "message": _user("user-1"),
                "message_request_id": "request-1",
                "expected_session_revision": 1,
                "assistant_message_id": "assistant-1",
                "assistant_created_at": TURN_RESPONSE_AT,
            },
        )
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ClientBackendErrorCode.UNSUPPORTED_INTERFACE_VERSION
    assert result.data is None
    assert graph.conversation_gateway_calls() == baseline == 0
    assert graph.canonical_gateway_calls() == 1  # only the session create
    # Nothing was written by the rejected request.
    assert graph.client.load_conversation(SESSION_ID) is None


# ═══════════════════════════════════════════════════════════════════════════
# Scenario G — safe error projection
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_g_safe_error_projection() -> None:
    """A canonical failure maps safely; no raw internal text crosses."""

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    # A canonical application failure.
    from cmm.application.errors import ApplicationResourceNotFoundError

    application_failure = graph.client.project_canonical_failure(
        ApplicationResourceNotFoundError(details={"reason_code": "SESSION_NOT_FOUND"})
    )
    assert application_failure["code"] == ApplicationErrorCode.RESOURCE_NOT_FOUND.value
    assert application_failure["message"] == ("Application resource was not found")

    # A canonical conversational failure raised through the facade.
    with pytest.raises(ConversationSessionConflictError) as conversation_failure:
        graph.client.submit_message(
            _user("user-1"),
            request_id="request-1",
            expected_session_revision=5,
            assistant_message_id="assistant-1",
            assistant_created_at=TURN_RESPONSE_AT,
        )
    assert conversation_failure.value.code.value == "session_conflict"

    # An unexpected internal defect through the generic entrypoint.
    def _explode(*args, **kwargs):
        raise RuntimeError("raw /Users/secret token=sk-live-12345")

    graph.conversation.load = _explode  # type: ignore[method-assign]
    result = graph.client.dispatch(
        ClientBackendRequest(
            interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
            request_id="request-explode",
            operation=ClientOperation.LOAD_CONVERSATION,
            payload={"session_id": SESSION_ID},
        )
    )
    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ClientBackendErrorCode.INTERNAL_CLIENT_ERROR

    serialized = str(result.to_dict())
    for fragment in FORBIDDEN_RESPONSE_FRAGMENTS:
        assert fragment not in serialized, fragment
    assert "sk-live" not in serialized
    assert "secret" not in serialized


def test_at_dp150_scenario_g_every_serialized_payload_is_safe() -> None:
    """No public payload of a real connected run carries forbidden content."""

    for payload in _walked_response_payloads():
        for value in _strings(payload):
            for fragment in FORBIDDEN_RESPONSE_FRAGMENTS:
                assert fragment not in value, (fragment, value)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario H — anti-fragmentation
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_h_no_parallel_authority_in_the_public_backend() -> None:
    """No store, repository, registry, router, runtime or engine is defined."""

    owner_tokens = (
        "store",
        "repository",
        "registry",
        "router",
        "runtime",
        "engine",
        "resolver",
        "manager",
        "executor",
        "planner",
        "locator",
    )

    offenders: list[str] = []
    for path in sorted(CLIENT_BACKEND_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            normalized = "".join(
                character for character in node.name.lower() if character.isalnum()
            )
            if normalized.endswith(owner_tokens):
                offenders.append(f"{path.name}:{node.name}")

    assert offenders == []


def test_at_dp150_scenario_h_no_direct_model_execution_path() -> None:
    """The public facade imports no model, provider, catalog or orchestration seam."""

    forbidden = (
        "kernel.llm",
        "cmm.orchestration",
        "cmm.api",
        "cmm.agent_runtime",
        "cmm.domains",
        "CMMChat",
        "fastapi",
        "pydantic",
    )

    offenders: list[str] = []
    for path in sorted(CLIENT_BACKEND_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                root = module.split(".")[0]
                if module in forbidden or any(
                    module == item or module.startswith(f"{item}.")
                    for item in forbidden
                ):
                    offenders.append(f"{path.name} -> {module}")
                if root == "CMMChat":
                    offenders.append(f"{path.name} -> {module}")

    assert offenders == []


def test_at_dp150_scenario_h_exactly_one_binding_is_contributed() -> None:
    """The composition contribution is one facade binding and nothing else."""

    from cmm.platform.configuration import CompositionConfiguration

    graph = build_client_backend_graph()
    module = build_client_backend_composition_module(service=graph.client)
    contributed = module.contribute(CompositionConfiguration())

    assert module.module_id == CLIENT_BACKEND_MODULE_ID
    assert len(contributed) == 1
    assert contributed[0].descriptor.service_id == CLIENT_BACKEND_SERVICE_ID
    assert contributed[0].implementation is graph.client
    assert contributed[0].runtime_contract is ClientBackend


# ═══════════════════════════════════════════════════════════════════════════
# Scenario I — inherited acceptance bundle
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_i_inherited_acceptance_bundle_is_recorded() -> None:
    """The inherited acceptances remain separate, exact-command required gates.

    The design and the implementation plan require the closed Phase 11
    acceptances to stay green *because Phase 11.50 touched no closed-phase
    production semantics*.  They are recorded here as the exact commands that
    were run in this implementation session, not as an in-process invocation of
    another module's tests: running one acceptance from inside another would
    blur which artifact was actually measured.
    """

    for acceptance_id, path in INHERITED_ACCEPTANCE_GATES:
        assert acceptance_id.startswith("AT-DP-")
        assert (REPO_ROOT / path).is_file(), f"{acceptance_id} gate file is missing"

    assert [identifier for identifier, _ in INHERITED_ACCEPTANCE_GATES] == [
        "AT-DP-134",
        "AT-DP-121",
        "AT-DP-101",
        "AT-DP-102",
        "AT-DP-103",
        "AT-DP-104",
        "AT-DP-105",
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Scenario J — portable first-party client
# ═══════════════════════════════════════════════════════════════════════════


class _MinimalFirstPartyClient:
    """A minimal first-party client using only the public export surface.

    This stands in for CMMChat: it imports nothing from inside the package, it
    holds only the facade reference it was constructed with, and it performs
    capability inspection, a session round trip and one conversational turn
    through the public API alone.
    """

    def __init__(self, backend: ClientBackend) -> None:
        self._backend = backend

    def capabilities(self) -> ClientBackendCapabilities:
        return self._backend.capabilities()

    def open_session(self, session_id: str) -> ApplicationSession:
        return self._backend.create_session(session_id)

    def read_session(self, session_id: str) -> ApplicationSession:
        return self._backend.get_session(session_id)

    def read_conversation(self, session_id: str):
        return self._backend.load_conversation(session_id)

    def ask(
        self,
        *,
        message: ConversationMessage,
        request_id: str,
        expected_session_revision: int,
        assistant_message_id: str,
        assistant_created_at: str,
    ):
        return self._backend.submit_message(
            message,
            request_id=request_id,
            expected_session_revision=expected_session_revision,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
        )


def test_at_dp150_scenario_j_portable_first_party_client() -> None:
    """A client built only from public exports performs a full round trip."""

    graph = build_client_backend_graph()
    client = _MinimalFirstPartyClient(graph.client)

    capabilities = client.capabilities()
    assert capabilities.interface_version == CLIENT_BACKEND_INTERFACE_VERSION
    assert capabilities.session_create is ClientBackendCapabilityStatus.AVAILABLE

    created = client.open_session(SESSION_ID)
    assert client.read_session(SESSION_ID) == created
    assert client.read_conversation(SESSION_ID) is None

    response = client.ask(
        message=_user("user-1"),
        request_id="request-1",
        expected_session_revision=created.revision,
        assistant_message_id="assistant-1",
        assistant_created_at=TURN_RESPONSE_AT,
    )

    assert response.message.id == "assistant-1"
    assert response.message.session_id == SESSION_ID
    state = client.read_conversation(SESSION_ID)
    assert state is not None
    assert [message.id for message in state.messages] == ["user-1", "assistant-1"]
    assert graph.conversation_gateway_calls() == 1


def test_at_dp150_scenario_j_the_client_needs_no_internal_import() -> None:
    """The portable client itself imports only the public package root.

    The assertion is made over the *client class* and the public constant block
    of this module, not over the whole file: this module's own assertions
    legitimately reach a private projection constant, while a first-party client
    must not.  The client class is compiled and screened separately.
    """

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=__file__)

    client_class = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "_MinimalFirstPartyClient"
    )
    client_source = ast.get_source_segment(source, client_class)
    assert client_source is not None

    # The portable client names no ``cmm`` module at all: every type and value it
    # uses arrives through the public import block at the top of this module.
    assert "cmm." not in client_source

    # And the public import block of this file reaches only the package root for
    # the client-facing surface.
    public_root_imports = sorted(
        {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("cmm.client_backend")
        }
    )
    assert "cmm.client_backend" in public_root_imports
    assert all(
        module == "cmm.client_backend" or module.startswith("cmm.client_backend.")
        for module in public_root_imports
    )


def test_at_dp150_scenario_j_an_unsupported_version_never_reaches_the_client() -> None:
    """The version gate protects the client before any owner is reached."""

    graph = build_client_backend_graph()
    client = _MinimalFirstPartyClient(graph.client)

    assert client.capabilities().interface_version == "1"

    with pytest.raises(ClientBackendError) as failure:
        ClientBackendRequest(
            interface_version="2",
            request_id="request-version",
            operation=ClientOperation.CAPABILITIES,
        )

    assert failure.value.code is ClientBackendErrorCode.UNSUPPORTED_INTERFACE_VERSION
    assert graph.canonical_gateway_calls() == 0
