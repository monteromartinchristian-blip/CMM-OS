"""Phase 11.4 — the canonical local application runtime composition.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

These tests prove the composition helper is a composition root and nothing
more: it returns the real Phase 11.1 container, the one real
``ApplicationGateway`` and the real canonical ``Orchestrator``; the container is
ready with exactly the canonical service set; the graph answers the application
surface through the gateway; and every call builds a fresh, independent graph
with no global state and no second authority.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from cmm.application import (
    APPLICATION_API_VERSION,
    APPLICATION_AUTHORITY,
    APPLICATION_CONTRACT_VERSION,
    APPLICATION_OWNER,
    APPLICATION_SCHEMA_VERSION,
    APPLICATION_SERVICE_ID,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationErrorCode,
    ApplicationGateway,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationStatus,
)
from cmm.application.local_runtime import (
    LocalApplicationRuntime,
    build_local_application_runtime,
)
from cmm.application.platform_module import ORCHESTRATOR_DEPENDENCY_ID
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.platform_module import ORCHESTRATION_SERVICE_IDS
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import ContainerState

#: The canonical services the local composition must bind.
CANONICAL_SERVICE_IDS = (
    "agent.runtime.integration",
    "domain.registry",
    "execution.registry",
    "provider.registry",
    "workflow.registry",
)

SESSION_ID = "session-local"
ACTOR_ID = "actor-local"
MESSAGE_CONTENT = "What changed in the plan?"


def _query(operation: ApplicationOperation, **overrides: object) -> ApplicationQuery:
    fields: dict[str, object] = {
        "request_id": "request-local",
        "api_version": APPLICATION_API_VERSION,
        "operation": operation,
        "channel": ApplicationChannel.CLI,
    }
    fields.update(overrides)
    return ApplicationQuery(**fields)  # type: ignore[arg-type]


def _message_command(**overrides: object) -> ApplicationCommand:
    fields: dict[str, object] = {
        "request_id": "request-local",
        "api_version": APPLICATION_API_VERSION,
        "operation": ApplicationOperation.MESSAGE_SUBMIT,
        "actor_id": ACTOR_ID,
        "session_id": SESSION_ID,
        "channel": ApplicationChannel.CLI,
        "payload": {
            "message_id": "message-local",
            "content": MESSAGE_CONTENT,
            "content_type": "text/plain",
            "metadata": {},
        },
    }
    fields.update(overrides)
    return ApplicationCommand(**fields)  # type: ignore[arg-type]


def _session_create_command() -> ApplicationCommand:
    return ApplicationCommand(
        request_id="request-create",
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.SESSION_CREATE,
        channel=ApplicationChannel.CLI,
        payload={"session_id": SESSION_ID},
    )


# ── Composition identity ─────────────────────────────────────────────────────


def test_the_factory_returns_the_frozen_runtime_types() -> None:
    runtime = build_local_application_runtime()

    assert isinstance(runtime, LocalApplicationRuntime)
    assert type(runtime.container) is ApplicationContainer
    assert type(runtime.gateway) is ApplicationGateway
    assert type(runtime.orchestrator) is Orchestrator


def test_the_container_exposes_the_one_gateway_and_the_canonical_orchestrator() -> None:
    runtime = build_local_application_runtime()

    assert runtime.container.get_service(APPLICATION_SERVICE_ID) is runtime.gateway
    assert runtime.container.get_service("orchestration.orchestrator") is (
        runtime.orchestrator
    )
    assert runtime.container.get_service("domain.registry") is not None
    assert runtime.container.get_service("agent.runtime.integration") is not None


def test_the_container_is_ready_and_carries_no_failure() -> None:
    runtime = build_local_application_runtime()

    assert runtime.container.state is ContainerState.READY
    assert runtime.container.failure() is None


def test_the_composed_service_set_is_the_canonical_one() -> None:
    runtime = build_local_application_runtime()

    service_ids = {
        service.service_id for service in runtime.container.snapshot().services
    }

    assert service_ids == set(ORCHESTRATION_SERVICE_IDS) | set(
        CANONICAL_SERVICE_IDS
    ) | {APPLICATION_SERVICE_ID}


def test_the_composition_is_local_and_declares_no_other_mode() -> None:
    runtime = build_local_application_runtime()

    modes = {service.mode.value for service in runtime.container.snapshot().services}

    assert modes == {"local"}


def test_the_application_service_declares_canonical_metadata_and_dependency() -> None:
    runtime = build_local_application_runtime()
    services = {
        service["service_id"]: service
        for service in runtime.container.snapshot().to_dict()["services"]
    }

    application = services[APPLICATION_SERVICE_ID]

    assert application["owner"] == APPLICATION_OWNER
    assert application["contract_version"] == APPLICATION_CONTRACT_VERSION
    assert application["schema_version"] == APPLICATION_SCHEMA_VERSION
    assert application["authority"] == APPLICATION_AUTHORITY
    assert application["mode"] == "local"
    assert application["dependency_ids"] == [ORCHESTRATOR_DEPENDENCY_ID]


# ── The composed graph answers the public application surface ────────────────


def test_the_graph_answers_health_and_capabilities_through_the_gateway() -> None:
    runtime = build_local_application_runtime()

    health = runtime.gateway.handle(
        _query(ApplicationOperation.HEALTH_GET, request_id="request-health")
    )
    capabilities = runtime.gateway.handle(
        _query(
            ApplicationOperation.CAPABILITIES_LIST, request_id="request-capabilities"
        )
    )

    assert health.status is ApplicationStatus.SUCCESS
    assert health.error is None
    assert health.data is not None
    assert health.data["platform_ready"] is True
    assert health.data["api_version"] == "v1"
    assert set(health.data["services"]) == set(ORCHESTRATION_SERVICE_IDS) | set(
        CANONICAL_SERVICE_IDS
    )

    assert capabilities.status is ApplicationStatus.SUCCESS
    declared = {
        capability["capability_id"]
        for capability in capabilities.data["capabilities"]  # type: ignore[index]
    }
    assert {"health", "capabilities", "sessions", "messages"} <= declared


def test_a_cli_message_reaches_the_canonical_pipeline() -> None:
    runtime = build_local_application_runtime()

    created = runtime.gateway.handle(_session_create_command())
    submitted = runtime.gateway.handle(_message_command())

    assert created.status is ApplicationStatus.SUCCESS

    # The canonical deterministic resolver answers honestly for a message that
    # carries no structured intent; the important part is that the request
    # really traversed the canonical pipeline and produced a canonical decision.
    assert submitted.status is ApplicationStatus.NEEDS_CLARIFICATION
    assert submitted.data is not None
    assert submitted.data["session_id"] == SESSION_ID
    assert submitted.data["decision_id"] == ("orchestration-decision:request-local")


def test_the_domain_graph_carries_the_canonical_core_domains() -> None:
    runtime = build_local_application_runtime()
    registry = runtime.container.get_service("domain.registry")

    registered = {definition.id.slug for definition in registry.list()}

    assert {"general", "health", "university"} <= registered


# ── Independence and locality ────────────────────────────────────────────────


def test_repeated_calls_build_independent_graphs() -> None:
    first = build_local_application_runtime()
    second = build_local_application_runtime()

    assert first is not second
    assert first.container is not second.container
    assert first.gateway is not second.gateway
    assert first.orchestrator is not second.orchestrator

    first.gateway.handle(_session_create_command())
    elsewhere = second.gateway.handle(
        _query(
            ApplicationOperation.SESSION_GET,
            request_id="request-read",
            session_id=SESSION_ID,
        )
    )

    # A session created in one runtime is invisible to the other: no shared
    # store, no shared container and no process-wide singleton.
    assert elsewhere.status is ApplicationStatus.FAILED
    assert elsewhere.error is not None
    assert elsewhere.error.code is ApplicationErrorCode.RESOURCE_NOT_FOUND


def test_the_factory_keeps_no_global_singleton_state() -> None:
    import cmm.application.local_runtime as local_runtime_module

    build_local_application_runtime()
    build_local_application_runtime()

    held = [
        name
        for name, value in vars(local_runtime_module).items()
        if isinstance(value, LocalApplicationRuntime)
    ]

    assert held == []


def test_the_factory_mutates_no_global_registry() -> None:
    """Two independent graphs never share a registry instance."""

    first = build_local_application_runtime()
    second = build_local_application_runtime()

    assert first.container.get_service("domain.registry") is not (
        second.container.get_service("domain.registry")
    )
    assert first.container.get_service("agent.runtime.integration") is not (
        second.container.get_service("agent.runtime.integration")
    )


def test_the_runtime_owns_only_its_canonical_composition() -> None:
    runtime = build_local_application_runtime()

    assert [field.name for field in fields(runtime)] == [
        "container",
        "gateway",
        "orchestrator",
        # Phase 11.5 (DP-105) sanctioned additive field: the canonical shared
        # session store a conversational consumer composes over.
        "session_store",
    ]
    assert runtime.container is not None
    assert runtime.gateway is not None
    assert runtime.orchestrator is not None


def test_the_runtime_is_a_frozen_composition_value() -> None:
    runtime = build_local_application_runtime()

    with pytest.raises(FrozenInstanceError):
        runtime.gateway = None  # type: ignore[misc]


def test_the_gateway_owns_only_its_five_collaborators() -> None:
    runtime = build_local_application_runtime()

    owned = vars(runtime.gateway)

    assert set(owned) == {
        "_sessions",
        "_requests",
        "_capabilities",
        "_health",
        "_idempotency",
        "_idempotency_lock",
    }
