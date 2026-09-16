"""Phase 11.3 — the frozen v1 OpenAPI contract gate.

The document served for ``CMM OS Application API`` is a client-visible artifact:
a path, an operation identifier or a schema name that changes here changes the
published v1 contract.  These tests therefore lock the document *structurally*
instead of snapshotting it:

* exactly the seven frozen ``/v1`` paths are published, and no unversioned
  duplicate or out-of-surface path is served instead of them;
* every operation has one frozen, unique operation identifier, and the document
  is byte-identical for independently composed applications, so nothing in it is
  generated from randomness, identity or import order;
* success is published as the one public response envelope under the frozen
  success status, the public application error model is published with the
  closed public error codes and statuses, and the streaming operation is never
  published as a JSON envelope response;
* the document carries no internal implementation name — no canonical owner, no
  ``cmm.*``/``kernel.*`` module authority, no internal seam such as the gateway
  or the idempotency repository, no private schema class and no secret-shaped or
  debug-shaped field;
* no authentication or authorization scheme is declared, because Phase 11.3
  ships no auth/RBAC implementation.

The application is built from the real Phase 11.1/11.2/11.3 composition rather
than from doubles, so the document under test is the one the product serves.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI

from cmm.api.app import create_app
from cmm.api.errors import success_status_code
from cmm.application import (
    APPLICATION_API_VERSION,
    ApplicationErrorCode,
    ApplicationGateway,
    ApplicationOperation,
    ApplicationStatus,
    CapabilityApplicationService,
    RequestApplicationService,
    SessionApplicationService,
    build_default_capabilities,
)
from cmm.application.health import HealthApplicationService
from cmm.application.idempotency import InMemoryIdempotencyRepository
from cmm.domains.resolver import DefaultDomainResolver
from cmm.orchestration.agent_router import CanonicalAgentRouter
from cmm.orchestration.context import DefaultContextResolver
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from cmm.orchestration.domain_router import CanonicalDomainRouter
from cmm.orchestration.events import RecordingOrchestrationEventSink
from cmm.orchestration.intent import DeterministicIntentResolver
from cmm.orchestration.orchestrator import Orchestrator
from cmm.orchestration.policy import DefaultOrchestrationPolicy
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDescriptor,
)
from cmm.platform.modules import StaticCompositionModule
from cmm.runtime.sessions import InMemorySessionStore

#: ``(method, path)`` of the frozen v1 route surface; it grows only when the
#: plan freezes a new route.
FROZEN_V1_ROUTES = (
    ("get", "/v1/health"),
    ("get", "/v1/capabilities"),
    ("post", "/v1/sessions"),
    ("get", "/v1/sessions/{session_id}"),
    ("post", "/v1/sessions/{session_id}/messages"),
    ("post", "/v1/sessions/{session_id}/messages/stream"),
    ("post", "/v1/requests/{request_id}/cancel"),
)

#: The frozen v1 route surface as a set of paths.
FROZEN_V1_PATHS = frozenset(path for _method, path in FROZEN_V1_ROUTES)

#: Frozen, client-visible operation identifiers keyed by ``(method, path)``.
#: They are derived from the route function and the versioned path, so a rename
#: or a path change is a published-contract change and must be frozen
#: deliberately here.
FROZEN_V1_OPERATION_IDS = {
    ("get", "/v1/health"): "get_health_v1_health_get",
    ("get", "/v1/capabilities"): "get_capabilities_v1_capabilities_get",
    ("post", "/v1/sessions"): "create_session_v1_sessions_post",
    ("get", "/v1/sessions/{session_id}"): "get_session_v1_sessions__session_id__get",
    (
        "post",
        "/v1/sessions/{session_id}/messages",
    ): "submit_message_v1_sessions__session_id__messages_post",
    (
        "post",
        "/v1/sessions/{session_id}/messages/stream",
    ): "stream_message_v1_sessions__session_id__messages_stream_post",
    (
        "post",
        "/v1/requests/{request_id}/cancel",
    ): "cancel_request_v1_requests__request_id__cancel_post",
}

#: The application operation each frozen route dispatches.  The streaming route
#: dispatches the same versioned ``MESSAGE_SUBMIT`` command as the non-streaming
#: one, which is what keeps the two public surfaces one application operation.
FROZEN_V1_OPERATIONS = {
    ("get", "/v1/health"): ApplicationOperation.HEALTH_GET,
    ("get", "/v1/capabilities"): ApplicationOperation.CAPABILITIES_LIST,
    ("post", "/v1/sessions"): ApplicationOperation.SESSION_CREATE,
    ("get", "/v1/sessions/{session_id}"): ApplicationOperation.SESSION_GET,
    (
        "post",
        "/v1/sessions/{session_id}/messages",
    ): ApplicationOperation.MESSAGE_SUBMIT,
    (
        "post",
        "/v1/sessions/{session_id}/messages/stream",
    ): ApplicationOperation.MESSAGE_SUBMIT,
    (
        "post",
        "/v1/requests/{request_id}/cancel",
    ): ApplicationOperation.REQUEST_CANCEL,
}

#: The status the published document declares for a successful call.  Only
#: session creation creates a public resource, so only it answers ``201``.
FROZEN_V1_SUCCESS_STATUS = {
    ("get", "/v1/health"): 200,
    ("get", "/v1/capabilities"): 200,
    ("post", "/v1/sessions"): 201,
    ("get", "/v1/sessions/{session_id}"): 200,
    ("post", "/v1/sessions/{session_id}/messages"): 200,
    ("post", "/v1/sessions/{session_id}/messages/stream"): 200,
    ("post", "/v1/requests/{request_id}/cancel"): 200,
}

#: The route that answers with server-sent events instead of the JSON envelope.
STREAM_ROUTE = ("post", "/v1/sessions/{session_id}/messages/stream")

#: Frozen schema set of the published document: the schemas the application and
#: the adapter own, plus the two the framework contributes to every validated
#: operation.  A new schema is a document change and must be frozen here.
FROZEN_APPLICATION_SCHEMAS = frozenset(
    {
        "ApplicationErrorCode",
        "ApplicationErrorModel",
        "ApplicationResponseModel",
        "ApplicationStatus",
        "CreateSessionBody",
        "JsonValue",
        "MessageBody",
    }
)

#: Framework-owned schemas; they may only appear in these exact shapes.
FRAMEWORK_SCHEMAS = frozenset({"HTTPValidationError", "ValidationError"})

#: The one schema every JSON operation publishes as its success response.
PUBLIC_ENVELOPE_REF = "#/components/schemas/ApplicationResponseModel"

#: The one schema every JSON operation publishes as its public failure model.
PUBLIC_ERROR_REF = "#/components/schemas/ApplicationErrorModel"

#: Canonical owners, internal seams and internal packages.  None of them may
#: appear in the published document: the document publishes the public contract,
#: never the implementation that serves it.
FORBIDDEN_DOCUMENT_TOKENS = (
    "ApplicationGateway",
    "ApplicationContainer",
    "IntegrationServiceRegistry",
    "DomainRegistry",
    "AgentRegistry",
    "AgentRuntime",
    "ProviderRegistry",
    "WorkflowRegistry",
    "ExecutorRegistry",
    "OperationRegistry",
    "ToolRegistry",
    "SessionStore",
    "Orchestrator",
    "OrchestrationRequest",
    "IntentResolver",
    "ContextResolver",
    "DomainRouter",
    "AgentRouter",
    "ModelGateway",
    "ModelRouter",
    "RoutingPolicyEngine",
    "EventBus",
    "EventStore",
    "ValidationEngine",
    "WorkflowEngine",
    "Planner",
    "IdempotencyRepository",
    "IdempotencyRecord",
    "ResourceExtractionService",
)

#: Internal module names; matched exactly, because Python module paths are
#: lower-case and prose may legitimately spell the product name in capitals.
FORBIDDEN_DOCUMENT_MODULES = (
    "cmm.",
    "kernel.",
    "fastapi",
    "starlette",
    "pydantic",
    "sqlalchemy",
    "sqlite3",
)

#: Field names that would publish a secret or a debug trace structure.
FORBIDDEN_PUBLIC_FIELDS = (
    "secret",
    "token",
    "password",
    "credential",
    "credentials",
    "api_key",
    "apikey",
    "authorization",
    "traceback",
    "stack_trace",
    "exception",
    "exception_message",
    "debug",
    "raw_reasoning",
    "reasoning",
    "prompt",
    "provider_payload",
    "internal_state",
)


def _ready_container() -> ApplicationContainer:
    """Build a ready composition; the document tests never resolve a service."""

    service_id = "orchestration.orchestrator"
    module = StaticCompositionModule(
        "openapi-document-doubles",
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
                    implementation_id="tests.api.test_openapi.double",
                ),
                implementation=object(),
            ),
        ),
    )
    return ApplicationContainer.build(
        CompositionConfiguration(
            required_services=(service_id,),
            enabled_modules=("openapi-document-doubles",),
        ),
        modules=(module,),
    )


def _application() -> FastAPI:
    """Build the v1 adapter over one real, minimally composed application graph."""

    sessions = SessionApplicationService(InMemorySessionStore())
    orchestrator = Orchestrator(
        intent_resolver=DeterministicIntentResolver(),
        context_resolver=DefaultContextResolver(session_store=None),
        domain_router=CanonicalDomainRouter(resolver=DefaultDomainResolver()),
        agent_router=CanonicalAgentRouter(registry_service=None),
        policy=DefaultOrchestrationPolicy(),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=RecordingOrchestrationEventSink(),
    )
    return create_app(
        ApplicationGateway(
            sessions=sessions,
            requests=RequestApplicationService(
                sessions=sessions, orchestrator=orchestrator
            ),
            capabilities=CapabilityApplicationService(build_default_capabilities()),
            health=HealthApplicationService(_ready_container()),
            idempotency=InMemoryIdempotencyRepository(),
        )
    )


def _document() -> dict[str, Any]:
    """Return the published OpenAPI document of one composed application."""

    return _application().openapi()


def _operations(
    document: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Return ``(method, path, operation)`` for every published operation."""

    operations: list[tuple[str, str, dict[str, Any]]] = []
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            operations.append((method, path, operation))
    return operations


def _schemas(document: dict[str, Any]) -> dict[str, Any]:
    return document["components"]["schemas"]


def _success_schema(operation: dict[str, Any], status: int) -> Any:
    """Return the declared success schema published under *status*, if any."""

    success = operation["responses"][str(status)]
    if not success.get("content"):
        return None
    return success["content"]["application/json"]["schema"]


# ── Frozen route surface ─────────────────────────────────────────────────────


def test_openapi_document_publishes_exactly_the_frozen_v1_paths() -> None:
    assert set(_document()["paths"]) == FROZEN_V1_PATHS


def test_openapi_document_serves_no_unversioned_or_out_of_surface_path() -> None:
    paths = set(_document()["paths"])

    unversioned_twins = {path.removeprefix("/v1") for path in FROZEN_V1_PATHS}

    assert unversioned_twins & paths == set()
    assert {path for path in paths if not path.startswith("/v1/")} == set()


def test_openapi_document_publishes_one_operation_per_frozen_route_method() -> None:
    published = {
        (method, path) for method, path, _operation in _operations(_document())
    }

    assert published == set(FROZEN_V1_ROUTES)


# ── Operation identifiers ────────────────────────────────────────────────────


def test_openapi_operation_ids_are_unique() -> None:
    operation_ids = [
        operation["operationId"]
        for _method, _path, operation in _operations(_document())
    ]

    assert len(operation_ids) == len(FROZEN_V1_ROUTES)
    assert len(set(operation_ids)) == len(operation_ids)


def test_openapi_operation_ids_are_frozen_public_identifiers() -> None:
    published = {
        (method, path): operation["operationId"]
        for method, path, operation in _operations(_document())
    }

    assert published == FROZEN_V1_OPERATION_IDS


def test_openapi_operation_ids_are_deterministic_across_applications() -> None:
    """The document is a pure function of the frozen adapter, not of its graph."""

    gateway = _application().state.application_gateway
    rebuilt = create_app(gateway).openapi()

    first = _document()
    second = _document()

    assert first == second == rebuilt


def test_openapi_publishes_a_summary_for_every_operation() -> None:
    summaries = {
        operation["summary"] for _method, _path, operation in _operations(_document())
    }

    assert len(summaries) == len(FROZEN_V1_ROUTES)
    assert all(summary.strip() for summary in summaries)


# ── Public response contract ─────────────────────────────────────────────────


def test_openapi_publishes_the_frozen_success_status_for_every_operation() -> None:
    """The published status and the adapter's frozen status map must agree."""

    published: dict[tuple[str, str], int] = {}

    for method, path, operation in _operations(_document()):
        successes = [
            int(status) for status in operation["responses"] if status.startswith("2")
        ]
        assert len(successes) == 1, f"{method.upper()} {path} -> {successes}"
        published[(method, path)] = successes[0]

    assert published == FROZEN_V1_SUCCESS_STATUS


def test_openapi_success_status_matches_the_application_operation_it_dispatches() -> (
    None
):
    """A 201 may only publish the one operation the status map creates."""

    for route, status in FROZEN_V1_SUCCESS_STATUS.items():
        assert status == success_status_code(FROZEN_V1_OPERATIONS[route])

    creating = {
        route for route, status in FROZEN_V1_SUCCESS_STATUS.items() if status == 201
    }
    assert creating == {
        route
        for route, operation in FROZEN_V1_OPERATIONS.items()
        if operation is ApplicationOperation.SESSION_CREATE
    }


def test_openapi_publishes_the_one_public_envelope_for_every_json_operation() -> None:
    envelope_operations = 0

    for method, path, operation in _operations(_document()):
        if (method, path) == STREAM_ROUTE:
            continue
        assert _success_schema(operation, FROZEN_V1_SUCCESS_STATUS[(method, path)]) == {
            "$ref": PUBLIC_ENVELOPE_REF
        }
        envelope_operations += 1

    assert envelope_operations == len(FROZEN_V1_ROUTES) - 1


def test_openapi_stream_operation_is_not_published_as_a_json_envelope() -> None:
    """The stream route answers with SSE frames, never with the JSON envelope."""

    operations = {
        (method, path): operation
        for method, path, operation in _operations(_document())
    }
    stream = operations[STREAM_ROUTE]

    assert _success_schema(stream, FROZEN_V1_SUCCESS_STATUS[STREAM_ROUTE]) == {}
    assert json.dumps(stream).count(PUBLIC_ENVELOPE_REF) == 0


def test_openapi_stream_operation_takes_the_frozen_message_command() -> None:
    operations = {
        (method, path): operation
        for method, path, operation in _operations(_document())
    }
    stream = operations[STREAM_ROUTE]

    body_schema = stream["requestBody"]["content"]["application/json"]["schema"]
    parameters = {parameter["name"]: parameter for parameter in stream["parameters"]}

    assert body_schema == {"$ref": "#/components/schemas/MessageBody"}
    assert stream["requestBody"]["required"] is True
    assert parameters["session_id"]["in"] == "path"
    assert parameters["session_id"]["required"] is True


def test_openapi_publishes_the_public_application_error_schema() -> None:
    error_schema = _schemas(_document())["ApplicationErrorModel"]

    assert set(error_schema["properties"]) == {
        "code",
        "message",
        "retryable",
        "details",
    }
    assert error_schema["required"] == ["code", "message"]
    assert error_schema["additionalProperties"] is False
    assert error_schema["properties"]["code"] == {
        "$ref": "#/components/schemas/ApplicationErrorCode"
    }


def test_openapi_publishes_exactly_the_closed_public_error_codes() -> None:
    code_schema = _schemas(_document())["ApplicationErrorCode"]

    assert set(code_schema["enum"]) == {code.value for code in ApplicationErrorCode}
    assert code_schema["type"] == "string"


def test_openapi_publishes_exactly_the_closed_public_response_statuses() -> None:
    status_schema = _schemas(_document())["ApplicationStatus"]

    assert set(status_schema["enum"]) == {status.value for status in ApplicationStatus}
    assert status_schema["type"] == "string"


def test_openapi_envelope_carries_the_public_error_and_api_version() -> None:
    envelope = _schemas(_document())["ApplicationResponseModel"]
    properties = envelope["properties"]

    assert envelope["required"] == ["request_id", "api_version", "status"]
    assert properties["status"] == {"$ref": "#/components/schemas/ApplicationStatus"}
    assert {"$ref": PUBLIC_ERROR_REF} in properties["error"]["anyOf"]
    assert {"type": "null"} in properties["error"]["anyOf"]
    assert properties["api_version"]["type"] == "string"
    assert APPLICATION_API_VERSION == "v1"


def test_openapi_publishes_the_bounded_public_request_bodies() -> None:
    schemas = _schemas(_document())

    assert set(schemas["MessageBody"]["properties"]) == {
        "message_id",
        "actor_id",
        "content",
        "content_type",
        "metadata",
        "expected_session_revision",
    }
    assert schemas["MessageBody"]["required"] == ["actor_id", "content"]
    assert set(schemas["CreateSessionBody"]["properties"]) == {"session_id"}
    assert schemas["CreateSessionBody"]["additionalProperties"] is False


def test_openapi_publishes_exactly_the_frozen_schema_set() -> None:
    schemas = set(_schemas(_document()))

    assert schemas - FRAMEWORK_SCHEMAS == FROZEN_APPLICATION_SCHEMAS
    assert schemas & FRAMEWORK_SCHEMAS <= FRAMEWORK_SCHEMAS


# ── No internal implementation in the published document ─────────────────────


def test_openapi_exposes_no_internal_implementation_name() -> None:
    document = json.dumps(_document(), sort_keys=True)

    owners = sorted(token for token in FORBIDDEN_DOCUMENT_TOKENS if token in document)
    modules = sorted(token for token in FORBIDDEN_DOCUMENT_MODULES if token in document)

    assert not owners, f"internal owner published in OpenAPI: {owners}"
    assert not modules, f"internal module published in OpenAPI: {modules}"


def test_openapi_exposes_no_private_schema_class() -> None:
    private = sorted(name for name in _schemas(_document()) if name.startswith("_"))

    assert not private, f"private schema class published: {private}"


def test_openapi_exposes_no_secret_or_debug_shaped_field() -> None:
    offenders: list[str] = []

    for name, schema in _schemas(_document()).items():
        if name in FRAMEWORK_SCHEMAS:
            continue
        for field_name in schema.get("properties", {}):
            if field_name.lower() in FORBIDDEN_PUBLIC_FIELDS:
                offenders.append(f"{name}.{field_name}")

    assert not offenders, f"secret/debug shaped public field: {sorted(offenders)}"


def test_openapi_declares_no_authentication_or_authorization_scheme() -> None:
    document = _document()

    assert "securitySchemes" not in document["components"]
    assert "security" not in document
    assert not [
        path
        for _method, path, operation in _operations(document)
        if "security" in operation
    ]
