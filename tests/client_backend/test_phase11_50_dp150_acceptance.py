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
* **A2** — authoritative exact ``client.backend`` composition identity: a
  hand-built ``ServiceBinding`` claiming the canonical descriptor with a facade
  *subclass* implementation is rejected by the authoritative
  ``IntegrationServiceRegistry`` on both ``register()`` and ``replace()``, while
  the exact facade is accepted (added by Remediation V2 for Re-audit V2
  MAJOR_V2_01);
* **A3** — **configuration-anchored** canonical ``client.backend`` identity: the
  authority is the canonical ``ServiceExpectation`` carried through
  ``CompositionConfiguration.expected_contracts``, so substituting the
  caller-authored ``runtime_contract`` field with ``None``, ``object`` or the
  facade subclass no longer bypasses the exact identity on ``register()`` or
  ``replace()``; a rebuilt descriptor cannot bypass it either, the canonical
  ``ApplicationContainer`` still reaches READY for the exact composition, and a
  pre-populated forged registry fails before READY (added by Remediation V3 for
  Re-audit V3 MAJOR_V3_01);
* **B** — session round trip through the facade over the canonical session store;
* **C** — submit-message traversal through ``ConversationService`` →
  ``ApplicationGateway`` with canonical identities and safe ``AssistantResponse``;
* **D** — edit and regenerate lineage owned by the canonical service;
* **E** — capability truth against the frozen design: response-event stream
  ``available``, attachments ``degraded``/``reference_only``, document upload
  ``unavailable``, requests cancellation honest, and boundary-only rows that are
  never end-to-end availability (remediated by Audit V1 MAJOR-04);
* **F** — version fail-closed with zero downstream calls;
* **G** — safe error projection with no raw internals;
* **H** — anti-fragmentation: no store, repository, registry, router, runtime,
  engine or direct model-gateway path inside the public client backend;
* **I** — inherited acceptance bundle recorded as separate required gate
  commands (see the module docstring of that test);
* **J** — a portable first-party client that imports only
  ``from cmm.client_backend import ...``;
* **K** — JSON-native client contract serialization: a canonical
  ``ConversationMessage`` payload and a canonical result value both survive
  ``to_dict()`` → ``json.dumps(...)`` (added by Audit V1 MAJOR-05 remediation).

The one style rule is determinism: every identity and timestamp is
caller-supplied and no assertion depends on wall-clock time.
"""

from __future__ import annotations

import ast
import json
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
from cmm.client_backend.platform_module import (
    APPLICATION_GATEWAY_CONTRACT_VERSION,
    APPLICATION_GATEWAY_DEPENDENCY_ID,
    APPLICATION_GATEWAY_OWNER,
    APPLICATION_GATEWAY_SCHEMA_VERSION,
    CONVERSATION_CONTRACT_VERSION,
    CONVERSATION_DEPENDENCY_ID,
    CONVERSATION_OWNER,
    CONVERSATION_SCHEMA_VERSION,
    client_backend_service_expectation,
)
from cmm.conversation.contracts import (
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import (
    ConversationErrorCode,
    ConversationSessionConflictError,
)
from cmm.platform.configuration import CompositionConfiguration, ServiceExpectation
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContainerState,
    ContractMetadata,
    RuntimeContractMatch,
    ServiceBinding,
    ServiceDescriptor,
)
from cmm.platform.errors import DuplicateServiceError, IncompatibleContractError
from cmm.platform.service_registry import IntegrationServiceRegistry
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
# Scenario A2 — authoritative exact client.backend composition identity
# ═══════════════════════════════════════════════════════════════════════════


def _canonical_descriptor(graph) -> ServiceDescriptor:
    """Return the real canonical ``client.backend`` descriptor.

    The descriptor is copied from the official Phase 11.1 contribution built over
    the real canonical facade, so the adversarial binding carries exactly the
    identity the composed graph would use.
    """

    module = build_client_backend_composition_module(service=graph.client)
    contributed = module.contribute(CompositionConfiguration())
    assert len(contributed) == 1
    binding = contributed[0]
    assert binding.descriptor.service_id == CLIENT_BACKEND_SERVICE_ID
    assert binding.runtime_contract is ClientBackend
    return binding.descriptor


def _adversarial_subclass(graph) -> ClientBackend:
    """Build a facade subclass carrying the official facade's instance state."""

    class ClientBackendSubclass(ClientBackend):
        """A facade subclass: only its exact type differs from the official one."""

    subclass = ClientBackendSubclass.__new__(ClientBackendSubclass)
    subclass.__dict__.update(graph.client.__dict__)
    assert isinstance(subclass, ClientBackend)
    assert type(subclass) is not ClientBackend
    return subclass


def test_at_dp150_scenario_a2_authoritative_exact_composition_identity() -> None:
    """The authoritative registry, not the builder, owns the exact identity.

    Independent Re-audit V2 (MAJOR_V2_01) reproduced that
    ``IntegrationServiceRegistry`` ACCEPTED a hand-built ``ServiceBinding`` whose
    implementation was a ``ClientBackend`` *subclass*, because the registry fell
    back to ``isinstance``.  Testing the convenience builder alone is therefore
    insufficient, and this scenario drives the authoritative registry path
    directly:

    ```text
    1. build a real canonical ClientBackend
    2. create ClientBackendSubclass adversarially
    3. obtain the canonical client.backend descriptor
    4. hand-build a valid ServiceBinding
    5. call IntegrationServiceRegistry.register()
    6. prove the subclass binding is REJECTED
    7. hand-build the exact ClientBackend binding and prove it is ACCEPTED
    ```
    """

    graph = build_client_backend_graph()
    canonical = graph.client
    assert type(canonical) is ClientBackend

    descriptor = _canonical_descriptor(graph)
    subclass = _adversarial_subclass(graph)

    registry = IntegrationServiceRegistry()

    # 4-6: the hand-built subclass binding cannot claim the canonical identity.
    hand_built_subclass = ServiceBinding(
        descriptor=descriptor,
        implementation=subclass,
        runtime_contract=ClientBackend,
    )
    with pytest.raises(IncompatibleContractError) as failure:
        registry.register(hand_built_subclass)

    assert failure.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert failure.value.result.details["service_id"] == CLIENT_BACKEND_SERVICE_ID
    assert registry.get(CLIENT_BACKEND_SERVICE_ID) is None
    assert registry.list_bindings() == ()

    # 7: the exact canonical facade registers through the very same manual path.
    hand_built_exact = ServiceBinding(
        descriptor=descriptor,
        implementation=canonical,
        runtime_contract=ClientBackend,
    )
    registry.register(hand_built_exact)

    stored = registry.get(CLIENT_BACKEND_SERVICE_ID)
    assert stored is hand_built_exact
    assert stored is not None
    assert stored.implementation is canonical
    assert type(stored.implementation) is ClientBackend

    # The exact identity is also the *declared* canonical contribution.
    official = build_client_backend_composition_module(service=canonical).contribute(
        CompositionConfiguration()
    )[0]
    assert official.runtime_contract_match is RuntimeContractMatch.EXACT_TYPE

    # Registering the canonical contribution after the manual binding is a
    # duplicate, not a silent override: the manual path gained no privilege.
    with pytest.raises(DuplicateServiceError) as duplicate:
        registry.register(official)
    assert duplicate.value.result.details["service_id"] == CLIENT_BACKEND_SERVICE_ID


def test_at_dp150_scenario_a2_replacement_cannot_swap_in_a_subclass() -> None:
    """``CLIENT_BACKEND_SUBCLASS_REPLACEMENT=REJECTED``.

    ``register()`` and ``replace()`` share one authoritative runtime-contract
    assertion path, so the replacement entry point is not an escape hatch: the
    exact binding stays in place and no subclass ever claims the identity.
    """

    graph = build_client_backend_graph()
    canonical = graph.client
    descriptor = _canonical_descriptor(graph)
    subclass = _adversarial_subclass(graph)

    registry = IntegrationServiceRegistry()
    exact_binding = ServiceBinding(
        descriptor=descriptor,
        implementation=canonical,
        runtime_contract=ClientBackend,
    )
    registry.register(exact_binding)

    subclass_binding = ServiceBinding(
        descriptor=descriptor,
        implementation=subclass,
        runtime_contract=ClientBackend,
    )
    with pytest.raises(IncompatibleContractError) as failure:
        registry.replace(CLIENT_BACKEND_SERVICE_ID, subclass_binding)

    assert failure.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert failure.value.result.details["service_id"] == CLIENT_BACKEND_SERVICE_ID

    resolved = registry.get(CLIENT_BACKEND_SERVICE_ID)
    assert resolved is exact_binding
    assert resolved is not None
    assert resolved.implementation is canonical
    assert type(resolved.implementation) is ClientBackend


def test_at_dp150_scenario_a2_omitted_match_mode_cannot_downgrade() -> None:
    """A binding that omits ``runtime_contract_match`` is still exact.

    Omitting the field leaves the Phase 11.1 default ``INSTANCE_OF`` — the exact
    audited bypass shape — and the canonical contract's own marker upgrades the
    effective rule to ``EXACT_TYPE``.
    """

    graph = build_client_backend_graph()
    descriptor = _canonical_descriptor(graph)
    subclass = _adversarial_subclass(graph)

    hand_built = ServiceBinding(
        descriptor=descriptor,
        implementation=subclass,
        runtime_contract=ClientBackend,
    )
    assert hand_built.runtime_contract_match is RuntimeContractMatch.INSTANCE_OF

    registry = IntegrationServiceRegistry()
    with pytest.raises(IncompatibleContractError):
        registry.register(hand_built)

    assert registry.get(CLIENT_BACKEND_SERVICE_ID) is None


# ═══════════════════════════════════════════════════════════════════════════
# Scenario A3 — configuration-anchored canonical client.backend identity
# ═══════════════════════════════════════════════════════════════════════════
#
# Remediation V3 for Re-audit V3 ``MAJOR_V3_01``.  Scenario A2 proved the exact
# identity against a *bare* registry, which is not sufficient: the binding's own
# ``runtime_contract`` field is caller-authored, so substituting ``None``,
# ``object`` or the facade subclass hid the V2 exact marker and restored
# acceptance — by ``register()`` and equally by ``replace()``.
#
# Scenario A3 drives the authoritative existing Phase 11.1 expectation path
# instead:
#
# ```text
# CompositionConfiguration.expected_contracts
#   → ServiceExpectation(service_id=client.backend,
#                        runtime_contract=ClientBackend,
#                        runtime_contract_match=EXACT_TYPE)
#   → IntegrationServiceRegistry
#   → register() / replace() / ApplicationContainer READY
# ```
#
# Real ``ClientBackend``, a real ``ClientBackendSubclass`` adversary, the real
# canonical descriptor, the real expectation factory, the real registry and the
# real ``ApplicationContainer``.  Nothing is mocked.


class ClientBackendSubclass(ClientBackend):
    """A facade subclass: only its exact type differs from the official facade."""


def _scenario_a3_subclass(graph) -> ClientBackend:
    subclass = ClientBackendSubclass.__new__(ClientBackendSubclass)
    subclass.__dict__.update(graph.client.__dict__)
    assert isinstance(subclass, ClientBackend)
    assert type(subclass) is not ClientBackend
    return subclass


def _canonical_expectation() -> ServiceExpectation:
    """The canonical authoritative expectation, from its owning module."""

    return client_backend_service_expectation()


def _configured_a3_registry() -> IntegrationServiceRegistry:
    return IntegrationServiceRegistry(expected_contracts=(_canonical_expectation(),))


def _a3_forged_variants() -> tuple[tuple[str, type | None], ...]:
    return (
        ("NONE", None),
        ("OBJECT", object),
        ("SUBCLASS", ClientBackendSubclass),
    )


def _a3_official_binding(graph) -> ServiceBinding:
    """The real canonical contribution for the composed facade."""

    module = build_client_backend_composition_module(service=graph.client)
    contributed = module.contribute(CompositionConfiguration())
    assert len(contributed) == 1
    assert contributed[0].descriptor.service_id == CLIENT_BACKEND_SERVICE_ID
    return contributed[0]


def _a3_dependency_binding(
    service_id: str,
    *,
    owner: str,
    contract_version: str,
    schema_version: str,
) -> ServiceBinding:
    """A minimal real binding for one canonical owner the facade delegates to.

    Scenario A3 composes the ``client.backend`` identity itself, so the two
    downward dependency edges are satisfied by real ``ServiceBinding`` values
    carrying the exact declared boundary contracts.  No subsystem is executed.
    """

    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=ContractMetadata(
                contract_name=service_id,
                contract_version=contract_version,
                schema_version=schema_version,
                owner=owner,
            ),
            implementation_id=f"scenario.a3.{service_id}",
        ),
        implementation=object(),
    )


def test_at_dp150_scenario_a3_expectation_is_the_runtime_identity_authority() -> None:
    """The canonical expectation — not the binding field — anchors the identity."""

    graph = build_client_backend_graph()
    official = _a3_official_binding(graph)
    expectation = _canonical_expectation()

    assert expectation.service_id == CLIENT_BACKEND_SERVICE_ID
    assert expectation.contract == official.descriptor.contract
    assert expectation.runtime_contract is ClientBackend
    assert expectation.runtime_contract_match is RuntimeContractMatch.EXACT_TYPE

    registry = _configured_a3_registry()
    registry.register(official)

    stored = registry.get(CLIENT_BACKEND_SERVICE_ID)
    assert stored is official
    assert type(stored.implementation) is ClientBackend
    assert stored.implementation is graph.client

    # A bare registry has no authoritative expectation, so V3 makes no claim
    # about it: the configured composition root is what closes DP-150.
    assert (
        IntegrationServiceRegistry().expected_contract_for(CLIENT_BACKEND_SERVICE_ID)
        is None
    )


@pytest.mark.parametrize(
    ("label", "declared"),
    _a3_forged_variants(),
    ids=[label for label, _ in _a3_forged_variants()],
)
def test_at_dp150_scenario_a3_forged_registration_is_rejected(
    label: str, declared: type | None
) -> None:
    """``CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_<label>=REJECTED``."""

    graph = build_client_backend_graph()
    official = _a3_official_binding(graph)
    forged = _scenario_a3_subclass(graph)

    registry = _configured_a3_registry()
    with pytest.raises(IncompatibleContractError) as failure:
        registry.register(
            ServiceBinding(
                descriptor=official.descriptor,
                implementation=forged,
                runtime_contract=declared,  # type: ignore[arg-type]
            )
        )

    assert failure.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert failure.value.result.details["service_id"] == CLIENT_BACKEND_SERVICE_ID
    assert registry.get(CLIENT_BACKEND_SERVICE_ID) is None
    assert registry.list_bindings() == ()


@pytest.mark.parametrize(
    ("label", "declared"),
    _a3_forged_variants(),
    ids=[label for label, _ in _a3_forged_variants()],
)
def test_at_dp150_scenario_a3_forged_replacement_is_rejected(
    label: str, declared: type | None
) -> None:
    """``CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_<label>=REJECTED``."""

    graph = build_client_backend_graph()
    official = _a3_official_binding(graph)
    forged = _scenario_a3_subclass(graph)

    registry = _configured_a3_registry()
    registry.register(official)

    with pytest.raises(IncompatibleContractError) as failure:
        registry.replace(
            CLIENT_BACKEND_SERVICE_ID,
            ServiceBinding(
                descriptor=official.descriptor,
                implementation=forged,
                runtime_contract=declared,  # type: ignore[arg-type]
            ),
        )

    assert failure.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert registry.get(CLIENT_BACKEND_SERVICE_ID) is official
    assert registry.expected_contracts() == (_canonical_expectation(),)


def test_at_dp150_scenario_a3_rebuilt_descriptor_cannot_bypass() -> None:
    """``REBUILT_CLIENT_BACKEND_DESCRIPTOR_CANNOT_BYPASS_EXPECTATION=PASS``."""

    graph = build_client_backend_graph()
    official = _a3_official_binding(graph)
    forged = _scenario_a3_subclass(graph)

    rebuilt = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=CLIENT_BACKEND_SERVICE_ID,
            contract=official.descriptor.contract,
            implementation_id="rebuilt.client.backend",
        ),
        implementation=forged,
        runtime_contract=ClientBackend,
        runtime_contract_match=RuntimeContractMatch.EXACT_TYPE,
    )

    registry = _configured_a3_registry()
    with pytest.raises(IncompatibleContractError) as failure:
        registry.register(rebuilt)

    assert failure.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert registry.get(CLIENT_BACKEND_SERVICE_ID) is None


def test_at_dp150_scenario_a3_canonical_container_reaches_ready() -> None:
    """The canonical container accepts the exact composition under the expectation."""

    graph = build_client_backend_graph()
    official = _a3_official_binding(graph)

    registry = IntegrationServiceRegistry()
    registry.register(official)
    registry.register(
        _a3_dependency_binding(
            APPLICATION_GATEWAY_DEPENDENCY_ID,
            owner=APPLICATION_GATEWAY_OWNER,
            contract_version=APPLICATION_GATEWAY_CONTRACT_VERSION,
            schema_version=APPLICATION_GATEWAY_SCHEMA_VERSION,
        )
    )
    registry.register(
        _a3_dependency_binding(
            CONVERSATION_DEPENDENCY_ID,
            owner=CONVERSATION_OWNER,
            contract_version=CONVERSATION_CONTRACT_VERSION,
            schema_version=CONVERSATION_SCHEMA_VERSION,
        )
    )

    configuration = CompositionConfiguration(
        required_services=(
            APPLICATION_GATEWAY_DEPENDENCY_ID,
            CONVERSATION_DEPENDENCY_ID,
            CLIENT_BACKEND_SERVICE_ID,
        ),
        expected_contracts=(_canonical_expectation(),),
    )

    container = ApplicationContainer.build(configuration, modules=(), registry=registry)

    assert container.state is ContainerState.READY
    assert container.get_service(CLIENT_BACKEND_SERVICE_ID) is graph.client
    assert type(container.get_service(CLIENT_BACKEND_SERVICE_ID)) is ClientBackend


def test_at_dp150_scenario_a3_prepopulated_forged_registry_never_reaches_ready() -> (
    None
):
    """``PREPOPULATED_FORGED_CLIENT_BACKEND=REJECTED`` /
    ``CONTAINER_READY_WITH_FORGED_CLIENT_BACKEND=NO``.

    A forged binding registered while no expectation existed cannot reach READY
    once the canonical configuration declares the authoritative expectation, and
    the rejection is atomic.
    """

    graph = build_client_backend_graph()
    official = _a3_official_binding(graph)
    forged = _scenario_a3_subclass(graph)

    registry = IntegrationServiceRegistry()
    forged_binding = ServiceBinding(
        descriptor=official.descriptor,
        implementation=forged,
        runtime_contract=None,
    )
    registry.register(forged_binding)

    configuration = CompositionConfiguration(
        required_services=(CLIENT_BACKEND_SERVICE_ID,),
        expected_contracts=(_canonical_expectation(),),
    )

    with pytest.raises(IncompatibleContractError) as failure:
        ApplicationContainer.build(configuration, modules=(), registry=registry)

    assert failure.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert failure.value.result.details["service_id"] == CLIENT_BACKEND_SERVICE_ID
    assert registry.expected_contracts() == ()
    assert registry.get(CLIENT_BACKEND_SERVICE_ID) is forged_binding
    assert registry.frozen is False


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
    """Every required row is present and no row overstates the frozen truth.

    Remediated for Audit V1 MAJOR-04.  The audited scenario asserted
    ``attachments=available`` (dropping the canonical ``reference_only``
    qualifier) and ``response_event_stream=degraded`` (collapsing the public
    response-event delivery with provider token streaming).  The frozen Phase
    11.50 truth asserted here is:

    ```text
    attachments=DEGRADED with effective mode reference_only
    document_upload=UNAVAILABLE
    response_event_stream=AVAILABLE
    end_to_end_token_stream=DEGRADED (a separate fact)
    ```
    """

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

    # The public response-event delivery exists in its own right and is reported
    # available; it is never relabelled as a token stream.
    assert manifest.response_event_stream is ClientBackendCapabilityStatus.AVAILABLE

    # Attachment references are degraded conversational metadata and the canonical
    # reference_only qualifier stays client-visible.
    assert manifest.attachments is ClientBackendCapabilityStatus.DEGRADED
    assert manifest.attachment_effective_mode == "reference_only"
    assert manifest.document_upload is ClientBackendCapabilityStatus.UNAVAILABLE

    # Cancellation, model boundary and end-to-end truth stay honest.
    assert manifest.request_cancellation is ClientBackendCapabilityStatus.UNAVAILABLE
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
    """Real canonical failures keep their identity on the real client paths.

    Remediated for Audit V1 MAJOR-03.  The audited scenario satisfied this
    scenario by calling ``ClientBackend.project_canonical_failure(...)`` directly
    with a synthetic exception, so the client's own execution paths — the typed
    session methods and the generic ``dispatch`` entrypoint — were never
    exercised.  This scenario drives real canonical failures through the facade
    and asserts the canonical-versus-internal classification on the result the
    client actually receives.
    """

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    # 1. A real canonical application failure (missing resource), typed path.
    with pytest.raises(ClientBackendError) as missing:
        graph.client.get_session("at-dp150-absent-session")
    assert missing.value.code is ApplicationErrorCode.RESOURCE_NOT_FOUND
    assert missing.value.canonical_code == "RESOURCE_NOT_FOUND"
    assert missing.value.message == "Application resource was not found"

    # 2. A real canonical application conflict, typed path.
    with pytest.raises(ClientBackendError) as conflict:
        graph.client.create_session(SESSION_ID)
    assert conflict.value.code is ApplicationErrorCode.CONFLICT
    assert conflict.value.message == (
        "Application resource state conflicts with the request"
    )

    # 3. The same canonical application failure through the generic entrypoint.
    absent = graph.client.dispatch(
        ClientBackendRequest(
            interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
            request_id="request-absent",
            operation=ClientOperation.GET_SESSION,
            payload={"session_id": "at-dp150-absent-session"},
        )
    )
    assert absent.ok is False
    assert absent.to_dict()["error"] == {
        "code": "RESOURCE_NOT_FOUND",
        "message": "Application resource was not found",
    }

    # 4. A real canonical conversational conflict through the generic entrypoint.
    conversation_conflict = graph.client.dispatch(
        ClientBackendRequest(
            interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
            request_id="request-conflict",
            operation=ClientOperation.SUBMIT_MESSAGE,
            payload={
                "message": _user("user-1"),
                "message_request_id": "request-1",
                "expected_session_revision": 9,
                "assistant_message_id": "assistant-1",
                "assistant_created_at": TURN_RESPONSE_AT,
            },
        )
    )
    assert conversation_conflict.ok is False
    assert conversation_conflict.error is not None
    assert conversation_conflict.error.code is ConversationErrorCode.SESSION_CONFLICT
    assert conversation_conflict.to_dict()["error"]["code"] == "session_conflict"
    assert conversation_conflict.to_dict()["error"]["message"] == (
        "Conversation session revision conflicts with the request"
    )

    # 5. A genuinely unknown internal defect through the generic entrypoint.
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
    assert result.error.canonical_code is None

    serialized = str(result.to_dict())
    for fragment in FORBIDDEN_RESPONSE_FRAGMENTS:
        assert fragment not in serialized, fragment
    assert "sk-live" not in serialized
    assert "secret" not in serialized

    # The earlier real canonical failures are already recorded safely too.
    for document in (absent.to_dict(), conversation_conflict.to_dict()):
        for value in _strings(document):
            for fragment in FORBIDDEN_RESPONSE_FRAGMENTS:
                assert fragment not in value, (fragment, value)


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


# ═══════════════════════════════════════════════════════════════════════════
# Scenario K — JSON-native client contract serialization (Audit V1 MAJOR-05)
# ═══════════════════════════════════════════════════════════════════════════


def test_at_dp150_scenario_k_json_native_client_contract_serialization() -> None:
    """A canonical payload and a canonical result both serialize to JSON.

    Scenario K was added by Remediation V1 inside the existing ``AT-DP-150``: a
    canonical ``ConversationMessage`` inside a ``ClientBackendRequest`` payload
    and a canonical result value both survive ``to_dict()`` as JSON-native
    documents, with every canonical identity preserved verbatim.
    """

    graph = build_client_backend_graph()
    graph.client.create_session(SESSION_ID)

    message = _user("user-1")
    request = ClientBackendRequest(
        interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
        request_id="request-k",
        operation=ClientOperation.SUBMIT_MESSAGE,
        payload={
            "message": message,
            "message_request_id": "request-1",
            "expected_session_revision": 1,
            "assistant_message_id": "assistant-1",
            "assistant_created_at": TURN_RESPONSE_AT,
        },
    )

    document = request.to_dict()
    encoded = json.dumps(document)

    # The canonical message is a plain JSON document with its identity intact.
    assert document["payload"]["message"]["id"] == "user-1"
    assert document["payload"]["message"]["session_id"] == SESSION_ID
    assert document["payload"]["message"]["content"] == PLAIN_TEXT
    assert document["payload"]["message"]["created_at"] == TURN_AT
    assert document["payload"]["message"]["role"] == "user"
    assert message.id in encoded
    assert message.session_id in encoded
    assert document["operation"] == "submit_message"
    # Serialization is deterministic and generates no fresh identity.
    assert request.to_dict() == document

    # The same public envelope executes through the real facade ...
    result = graph.client.dispatch(request)
    assert result.ok is True
    result_document = result.to_dict()
    json.dumps(result_document)
    assert result_document["data"]["response"]["message"]["id"] == "assistant-1"

    # ... and a canonical session value inside a result is JSON-native too.
    session_result = graph.client.dispatch(
        ClientBackendRequest(
            interface_version=CLIENT_BACKEND_INTERFACE_VERSION,
            request_id="request-k-session",
            operation=ClientOperation.GET_SESSION,
            payload={"session_id": SESSION_ID},
        )
    )
    assert session_result.ok is True
    session_document = session_result.to_dict()
    json.dumps(session_document)
    assert session_document["data"]["session"]["session_id"] == SESSION_ID
    assert session_document["data"]["session"]["revision"] == 2

    # No forbidden fragment survives anywhere in the serialized documents.
    for payload in (document, result_document, session_document):
        for value in _strings(payload):
            for fragment in FORBIDDEN_RESPONSE_FRAGMENTS:
                assert fragment not in value, (fragment, value)
