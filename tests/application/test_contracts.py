"""Phase 11.3 — versioned public application contract tests.

The Phase 11.3 application contracts are transport-neutral frozen values.  These
tests lock the public names, the command/query split, the bounded and
secret-free public metadata grammar and the response invariants.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    COMMAND_OPERATIONS,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    MAX_IDENTIFIER_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_METADATA_DEPTH,
    MAX_METADATA_ITEMS,
    MAX_STRING_LENGTH,
    QUERY_OPERATIONS,
    ApplicationCancellationRequest,
    ApplicationCapability,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationHealth,
    ApplicationMessage,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationRequest,
    ApplicationResponse,
    ApplicationSession,
    ApplicationStatus,
    ApplicationStreamEvent,
    CapabilityStatus,
    StreamEventKind,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _query(**overrides: object) -> ApplicationQuery:
    fields: dict[str, object] = {
        "request_id": "req-1",
        "api_version": APPLICATION_API_VERSION,
        "operation": ApplicationOperation.HEALTH_GET,
    }
    fields.update(overrides)
    return ApplicationQuery(**fields)  # type: ignore[arg-type]


def _command(**overrides: object) -> ApplicationCommand:
    fields: dict[str, object] = {
        "request_id": "req-1",
        "api_version": APPLICATION_API_VERSION,
        "operation": ApplicationOperation.SESSION_CREATE,
    }
    fields.update(overrides)
    return ApplicationCommand(**fields)  # type: ignore[arg-type]


def _nested_metadata(levels: int) -> dict[str, object]:
    """Return metadata whose deepest container sits at nesting *levels*."""

    value: object = "leaf"
    for _ in range(levels - 1):
        value = {"level": value}
    return {"level": value}


def _assert_public_value(value: object) -> None:
    """Assert *value* is a plain, JSON-safe, immutable public representation."""

    if isinstance(value, MappingProxyType):
        pytest.fail("a frozen proxy leaked into a public representation")
    if isinstance(value, Mapping):
        for key, item in value.items():
            assert isinstance(key, str)
            _assert_public_value(item)
        return
    if isinstance(value, tuple | list):
        for item in value:
            _assert_public_value(item)
        return
    assert value is None or isinstance(value, bool | int | float | str)


# ── Frozen public identity ───────────────────────────────────────────────────


def test_application_api_version_is_v1() -> None:
    assert APPLICATION_API_VERSION == "v1"


def test_command_query_types_are_distinct() -> None:
    assert ApplicationCommand is not ApplicationQuery
    assert issubclass(ApplicationCommand, ApplicationRequest)
    assert issubclass(ApplicationQuery, ApplicationRequest)
    assert ApplicationOperation.MESSAGE_SUBMIT.value == "messages.submit"


def test_public_operation_names_are_frozen() -> None:
    assert {operation.value for operation in ApplicationOperation} == {
        "health.get",
        "capabilities.list",
        "sessions.create",
        "sessions.get",
        "messages.submit",
        "requests.cancel",
    }


def test_operation_kind_map_is_frozen() -> None:
    assert QUERY_OPERATIONS == {
        ApplicationOperation.HEALTH_GET,
        ApplicationOperation.CAPABILITIES_LIST,
        ApplicationOperation.SESSION_GET,
    }
    assert COMMAND_OPERATIONS == {
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
        ApplicationOperation.REQUEST_CANCEL,
    }
    assert not QUERY_OPERATIONS & COMMAND_OPERATIONS


def test_public_error_codes_are_frozen() -> None:
    assert {code.value for code in ApplicationErrorCode} == {
        "INVALID_REQUEST",
        "UNSUPPORTED_VERSION",
        "RESOURCE_NOT_FOUND",
        "CONFLICT",
        "CAPABILITY_UNAVAILABLE",
        "IDEMPOTENCY_CONFLICT",
        "CONCURRENCY_CONFLICT",
        "CANCELLED",
        "POLICY_DENIED",
        "APPROVAL_REQUIRED",
        "INTERNAL_FAILURE",
    }


def test_application_statuses_are_frozen() -> None:
    assert {status.value for status in ApplicationStatus} == {
        "success",
        "routed",
        "needs_clarification",
        "blocked",
        "escalated",
        "cancelled",
        "failed",
    }


def test_capability_and_stream_kinds_are_frozen() -> None:
    assert {status.value for status in CapabilityStatus} == {
        "available",
        "unavailable",
        "deferred",
    }
    assert {kind.value for kind in StreamEventKind} == {
        "started",
        "data",
        "completed",
        "error",
        "cancelled",
    }


def test_public_metadata_limits_are_frozen() -> None:
    assert MAX_METADATA_DEPTH == 6
    assert MAX_METADATA_ITEMS == 128
    assert MAX_STRING_LENGTH == 16_384
    assert MAX_MESSAGE_LENGTH == 64_000
    assert MAX_IDENTIFIER_LENGTH == 256
    assert MAX_IDEMPOTENCY_KEY_LENGTH == 256


# ── Channels ─────────────────────────────────────────────────────────────────


def test_application_channel_exposes_conversation_without_changing_api_default() -> (
    None
):
    """Phase 11.5 adds the conversation origin; ``API`` stays the default."""

    assert ApplicationChannel.CONVERSATION.value == "conversation"
    # API and CLI keep their order and value spelling; CONVERSATION is additive.
    assert [member.value for member in ApplicationChannel] == [
        "api",
        "cli",
        "conversation",
    ]
    assert (
        ApplicationRequest(
            api_version="v1",
            request_id="req-1",
            operation=ApplicationOperation.HEALTH_GET,
        ).channel
        is ApplicationChannel.API
    )


# ── Request identity ─────────────────────────────────────────────────────────


def test_application_request_is_frozen() -> None:
    request = _query()

    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"  # type: ignore[misc]


def test_application_query_defaults_to_empty_payload_and_metadata() -> None:
    request = _query()

    assert request.actor_id is None
    assert request.session_id is None
    assert dict(request.payload) == {}
    assert dict(request.metadata) == {}


def test_request_identifier_is_trimmed() -> None:
    assert _query(request_id="  req-1  ").request_id == "req-1"


@pytest.mark.parametrize("request_id", ["", "   ", "\n"])
def test_request_identifier_must_be_non_empty(request_id: str) -> None:
    with pytest.raises(ValueError):
        _query(request_id=request_id)


def test_request_identifier_must_be_a_string() -> None:
    with pytest.raises(TypeError):
        _query(request_id=17)


def test_request_identifier_respects_the_frozen_length_limit() -> None:
    assert _query(request_id="r" * MAX_IDENTIFIER_LENGTH).request_id

    with pytest.raises(ValueError):
        _query(request_id="r" * (MAX_IDENTIFIER_LENGTH + 1))


def test_api_version_must_be_the_frozen_version() -> None:
    with pytest.raises(ValueError):
        _query(api_version="v2")


def test_operation_must_be_a_real_operation_member() -> None:
    with pytest.raises(TypeError):
        _query(operation="health.get")


def test_optional_references_normalize_blank_to_none() -> None:
    request = _query(actor_id="   ", session_id="")

    assert request.actor_id is None
    assert request.session_id is None


# ── Public metadata grammar ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "credential",
        "private_key",
        "authorization",
        "cookie",
        "PASSWORD",
        "Api-Key",
        "apiKey",
        "privateKey",
        "refreshToken",
        "my_secret_value",
    ],
)
def test_public_metadata_rejects_secret_keys(key: str) -> None:
    with pytest.raises(ValueError):
        _query(metadata={key: "value"})


@pytest.mark.parametrize(
    "key",
    [
        "x-api-key",
        "X-Api-Key",
        "refreshToken",
        "access-token",
        "client_secret",
        "userPassword",
        "db-credential",
        "privateKey",
        "Authorization",
        "Set-Cookie",
        "tokenizer",
        "passwordless",
        "max_tokens",
    ],
)
def test_public_metadata_rejects_secret_like_key_fragments(key: str) -> None:
    """The denylist fails closed on a normalized fragment match, not a whole-word one."""

    with pytest.raises(ValueError):
        _query(metadata={key: "value"})


@pytest.mark.parametrize(
    "key", ["note", "count", "level", "origin", "session", "domain"]
)
def test_public_metadata_allows_unrelated_keys(key: str) -> None:
    assert dict(_query(metadata={key: "value"}).metadata) == {key: "value"}


def test_public_metadata_rejects_binary_values() -> None:
    with pytest.raises(TypeError):
        _query(metadata={"blob": b"secret"})


def test_public_metadata_rejects_opaque_objects() -> None:
    with pytest.raises(TypeError):
        _query(metadata={"thing": object()})


def test_public_metadata_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError):
        _query(metadata={1: "value"})


def test_public_metadata_rejects_non_finite_floats() -> None:
    with pytest.raises(ValueError):
        _query(metadata={"ratio": float("nan")})

    with pytest.raises(ValueError):
        _query(metadata={"ratio": float("inf")})


def test_public_metadata_rejects_oversized_strings() -> None:
    assert _query(metadata={"note": "x" * MAX_STRING_LENGTH}).metadata

    with pytest.raises(ValueError):
        _query(metadata={"note": "x" * (MAX_STRING_LENGTH + 1)})


def test_public_metadata_rejects_excessive_nesting() -> None:
    _query(metadata=_nested_metadata(MAX_METADATA_DEPTH))

    with pytest.raises(ValueError):
        _query(metadata=_nested_metadata(MAX_METADATA_DEPTH + 1))


def test_public_metadata_rejects_excessive_items() -> None:
    allowed = {f"field-{index}": index for index in range(MAX_METADATA_ITEMS)}
    _query(metadata=allowed)

    rejected = {f"field-{index}": index for index in range(MAX_METADATA_ITEMS + 1)}
    with pytest.raises(ValueError):
        _query(metadata=rejected)


def test_public_metadata_item_limit_counts_nested_items() -> None:
    nested = {"outer": [index for index in range(MAX_METADATA_ITEMS)]}

    with pytest.raises(ValueError):
        _query(metadata=nested)


def test_public_metadata_is_recursively_frozen() -> None:
    request = _query(
        metadata={"nested": {"inner": [1, 2, {"deep": "value"}]}, "flag": True}
    )

    assert isinstance(request.metadata, MappingProxyType)
    nested = request.metadata["nested"]
    assert isinstance(nested, MappingProxyType)
    assert nested["inner"] == (1, 2, MappingProxyType({"deep": "value"}))
    assert isinstance(nested["inner"], tuple)


def test_request_payload_uses_the_same_safe_grammar() -> None:
    payload = {"session_id": "session-1", "count": 2}
    assert dict(_query(payload=payload).payload) == payload

    with pytest.raises(ValueError):
        _query(payload={"api_key": "secret"})

    with pytest.raises(TypeError):
        _query(payload={"blob": b"secret"})


def test_request_rejects_a_non_mapping_payload() -> None:
    with pytest.raises(TypeError):
        _query(payload=["not", "a", "mapping"])


def test_public_metadata_is_copied_not_aliased() -> None:
    source = {"field": "value"}
    request = _query(metadata=source)

    source["field"] = "mutated"

    assert dict(request.metadata) == {"field": "value"}


# ── Command-only fields ──────────────────────────────────────────────────────


def test_application_command_defaults_to_no_revision_and_no_key() -> None:
    command = _command()

    assert command.expected_session_revision is None
    assert command.idempotency_key is None


def test_application_command_accepts_a_zero_expected_revision() -> None:
    assert _command(expected_session_revision=0).expected_session_revision == 0


@pytest.mark.parametrize("revision", [-1, True, "1", 1.5])
def test_application_command_rejects_malformed_expected_revision(
    revision: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        _command(expected_session_revision=revision)


def test_application_command_rejects_overlong_idempotency_key() -> None:
    key = "k" * MAX_IDEMPOTENCY_KEY_LENGTH
    assert _command(idempotency_key=key).idempotency_key == key

    with pytest.raises(ValueError):
        _command(idempotency_key=key + "k")


@pytest.mark.parametrize("key", ["", "   "])
def test_application_command_rejects_blank_idempotency_key(key: str) -> None:
    with pytest.raises(ValueError):
        _command(idempotency_key=key)


# ── Errors and responses ─────────────────────────────────────────────────────


def test_application_error_is_frozen_and_requires_a_real_code() -> None:
    error = ApplicationError(
        code=ApplicationErrorCode.INVALID_REQUEST,
        message="Invalid application request",
    )

    with pytest.raises(FrozenInstanceError):
        error.message = "changed"  # type: ignore[misc]

    with pytest.raises(TypeError):
        ApplicationError(code="INVALID_REQUEST", message="nope")


def test_application_error_details_use_the_safe_grammar() -> None:
    error = ApplicationError(
        code=ApplicationErrorCode.CONFLICT,
        message="Conflict",
        details={"session_id": "session-1"},
    )

    assert isinstance(error.details, MappingProxyType)

    with pytest.raises(ValueError):
        ApplicationError(
            code=ApplicationErrorCode.CONFLICT,
            message="Conflict",
            details={"token": "value"},
        )


@pytest.mark.parametrize(
    "status", [ApplicationStatus.FAILED, ApplicationStatus.BLOCKED]
)
def test_application_response_requires_error_for_failed_status(
    status: ApplicationStatus,
) -> None:
    with pytest.raises(ValueError):
        ApplicationResponse(
            request_id="req-1",
            api_version=APPLICATION_API_VERSION,
            status=status,
        )


@pytest.mark.parametrize(
    "status",
    [
        ApplicationStatus.SUCCESS,
        ApplicationStatus.ROUTED,
        ApplicationStatus.NEEDS_CLARIFICATION,
        ApplicationStatus.ESCALATED,
    ],
)
def test_non_failure_responses_may_carry_data(status: ApplicationStatus) -> None:
    response = ApplicationResponse(
        request_id="req-1",
        api_version=APPLICATION_API_VERSION,
        status=status,
        data={"content": "safe"},
    )

    assert response.error is None
    assert response.status is status


def test_application_response_rejects_a_malformed_error() -> None:
    with pytest.raises(TypeError):
        ApplicationResponse(
            request_id="req-1",
            api_version=APPLICATION_API_VERSION,
            status=ApplicationStatus.FAILED,
            error="INTERNAL_FAILURE",
        )


def test_application_response_rejects_a_non_mapping_data_payload() -> None:
    with pytest.raises(TypeError):
        ApplicationResponse(
            request_id="req-1",
            api_version=APPLICATION_API_VERSION,
            status=ApplicationStatus.SUCCESS,
            data=["not", "a", "mapping"],
        )


def test_application_response_is_frozen() -> None:
    response = ApplicationResponse(
        request_id="req-1",
        api_version=APPLICATION_API_VERSION,
        status=ApplicationStatus.SUCCESS,
    )

    with pytest.raises(FrozenInstanceError):
        response.status = ApplicationStatus.FAILED  # type: ignore[misc]


# ── Session / message ────────────────────────────────────────────────────────


def test_application_session_projection_is_frozen_and_validated() -> None:
    session = ApplicationSession(
        session_id="session-1",
        revision=1,
        status="ACTIVE",
        created_at="2026-09-16T00:00:00+00:00",
        updated_at="2026-09-16T00:00:00+00:00",
    )

    assert session.revision == 1

    with pytest.raises(FrozenInstanceError):
        session.revision = 2  # type: ignore[misc]


@pytest.mark.parametrize("revision", [-1, True, "1"])
def test_application_session_rejects_a_malformed_revision(revision: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ApplicationSession(
            session_id="session-1",
            revision=revision,  # type: ignore[arg-type]
            status="ACTIVE",
            created_at="2026-09-16T00:00:00+00:00",
            updated_at="2026-09-16T00:00:00+00:00",
        )


@pytest.mark.parametrize(
    "timestamp",
    ["2026-09-16T00:00:00", "yesterday", ""],
)
def test_application_session_requires_an_explicit_offset_timestamp(
    timestamp: str,
) -> None:
    with pytest.raises(ValueError):
        ApplicationSession(
            session_id="session-1",
            revision=1,
            status="ACTIVE",
            created_at=timestamp,
            updated_at="2026-09-16T00:00:00+00:00",
        )


def test_application_message_defaults_and_limits() -> None:
    message = ApplicationMessage(
        message_id="msg-1",
        session_id="session-1",
        actor_id="actor-1",
        content="hello",
    )

    assert message.content_type == "text/plain"
    assert message.expected_session_revision is None
    assert message.idempotency_key is None
    assert dict(message.metadata) == {}

    longest = ApplicationMessage(
        message_id="msg-1",
        session_id="session-1",
        actor_id="actor-1",
        content="x" * MAX_MESSAGE_LENGTH,
    )
    assert len(longest.content) == MAX_MESSAGE_LENGTH

    with pytest.raises(ValueError):
        ApplicationMessage(
            message_id="msg-1",
            session_id="session-1",
            actor_id="actor-1",
            content="x" * (MAX_MESSAGE_LENGTH + 1),
        )


def test_application_message_requires_content() -> None:
    with pytest.raises(ValueError):
        ApplicationMessage(
            message_id="msg-1",
            session_id="session-1",
            actor_id="actor-1",
            content="",
        )


def test_application_message_preserves_text_verbatim() -> None:
    """Public text is never silently rewritten, trimmed or normalized."""

    content = "  keep  the  spacing  "
    message = ApplicationMessage(
        message_id="msg-1",
        session_id="session-1",
        actor_id="actor-1",
        content=content,
    )

    assert message.content == content


def test_application_message_requires_identity_fields() -> None:
    for field in ("message_id", "session_id", "actor_id"):
        fields: dict[str, object] = {
            "message_id": "msg-1",
            "session_id": "session-1",
            "actor_id": "actor-1",
            "content": "hello",
        }
        fields[field] = "   "

        with pytest.raises(ValueError):
            ApplicationMessage(**fields)  # type: ignore[arg-type]


# ── Capability / health / stream / cancellation ──────────────────────────────


def test_application_capability_freezes_operations_to_a_tuple() -> None:
    capability = ApplicationCapability(
        capability_id="sessions",
        status=CapabilityStatus.AVAILABLE,
        version="1.0.0",
        operations=["sessions.create", "sessions.get"],
    )

    assert capability.operations == ("sessions.create", "sessions.get")

    with pytest.raises(TypeError):
        ApplicationCapability(
            capability_id="sessions",
            status="available",
            version="1.0.0",
        )


def test_application_capability_rejects_blank_operations() -> None:
    with pytest.raises(ValueError):
        ApplicationCapability(
            capability_id="sessions",
            status=CapabilityStatus.AVAILABLE,
            version="1.0.0",
            operations=("  ",),
        )


def test_application_health_freezes_services_and_pins_the_api_version() -> None:
    health = ApplicationHealth(
        status="ok",
        api_version=APPLICATION_API_VERSION,
        platform_ready=True,
        services=["application.gateway"],
    )

    assert health.services == ("application.gateway",)
    assert health.platform_ready is True

    with pytest.raises(ValueError):
        ApplicationHealth(
            status="ok",
            api_version="v2",
            platform_ready=True,
            services=(),
        )


def test_application_stream_event_is_frozen_and_typed() -> None:
    event = ApplicationStreamEvent(
        request_id="req-1",
        sequence=0,
        kind=StreamEventKind.STARTED,
    )

    assert event.data is None
    assert event.error is None

    with pytest.raises(TypeError):
        ApplicationStreamEvent(request_id="req-1", sequence=0, kind="started")

    with pytest.raises(ValueError):
        ApplicationStreamEvent(
            request_id="req-1", sequence=-1, kind=StreamEventKind.DATA
        )


def test_application_cancellation_request_requires_a_request_identity() -> None:
    assert ApplicationCancellationRequest(request_id="req-1").request_id == "req-1"

    with pytest.raises(ValueError):
        ApplicationCancellationRequest(request_id="   ")


# ── Deterministic public serialization ───────────────────────────────────────


def _public_contracts() -> list[object]:
    error = ApplicationError(
        code=ApplicationErrorCode.INVALID_REQUEST,
        message="Invalid application request",
        details={"field": "operation"},
    )
    return [
        ApplicationRequest(
            request_id="req-1",
            api_version=APPLICATION_API_VERSION,
            operation=ApplicationOperation.HEALTH_GET,
            payload={"a": 1},
            metadata={"b": [1, 2]},
        ),
        _query(payload={"a": 1}, metadata={"b": [1, 2]}),
        _command(
            expected_session_revision=1,
            idempotency_key="idem-1",
            payload={"session_id": "session-1"},
        ),
        error,
        ApplicationResponse(
            request_id="req-1",
            api_version=APPLICATION_API_VERSION,
            status=ApplicationStatus.ROUTED,
            data={"route": "direct_response"},
            metadata={"safe": True},
        ),
        ApplicationResponse(
            request_id="req-1",
            api_version=APPLICATION_API_VERSION,
            status=ApplicationStatus.FAILED,
            error=error,
        ),
        ApplicationSession(
            session_id="session-1",
            revision=1,
            status="ACTIVE",
            created_at="2026-09-16T00:00:00+00:00",
            updated_at="2026-09-16T00:00:00+00:00",
        ),
        ApplicationMessage(
            message_id="msg-1",
            session_id="session-1",
            actor_id="actor-1",
            content="hello",
            metadata={"origin": "test"},
        ),
        ApplicationCapability(
            capability_id="sessions",
            status=CapabilityStatus.AVAILABLE,
            version="1.0.0",
            operations=("sessions.create",),
        ),
        ApplicationHealth(
            status="ok",
            api_version=APPLICATION_API_VERSION,
            platform_ready=True,
            services=("application.gateway",),
        ),
        ApplicationStreamEvent(
            request_id="req-1",
            sequence=0,
            kind=StreamEventKind.STARTED,
            data={"phase": "started"},
        ),
        ApplicationCancellationRequest(request_id="req-1"),
    ]


@pytest.mark.parametrize("contract", _public_contracts())
def test_to_dict_is_plain_immutable_and_json_safe(contract: object) -> None:
    payload = contract.to_dict()  # type: ignore[attr-defined]

    _assert_public_value(payload)
    assert json.loads(json.dumps(payload, sort_keys=True, allow_nan=False)) == payload


@pytest.mark.parametrize("contract", _public_contracts())
def test_to_dict_is_deterministic(contract: object) -> None:
    assert contract.to_dict() == contract.to_dict()  # type: ignore[attr-defined]


def test_to_dict_returns_a_fresh_detached_mapping() -> None:
    request = _query(payload={"nested": {"field": "value"}})

    payload = request.to_dict()["payload"]
    payload["nested"]["field"] = "mutated"
    payload["added"] = True

    assert dict(request.payload["nested"]) == {"field": "value"}
    assert "added" not in request.payload


# ── Public surface ───────────────────────────────────────────────────────────

FROZEN_CONTRACT_NAMES = frozenset(
    {
        "APPLICATION_API_VERSION",
        "ApplicationStatus",
        "ApplicationOperation",
        "ApplicationErrorCode",
        "CapabilityStatus",
        "StreamEventKind",
        "ApplicationRequest",
        "ApplicationQuery",
        "ApplicationCommand",
        "ApplicationError",
        "ApplicationResponse",
        "ApplicationSession",
        "ApplicationMessage",
        "ApplicationCapability",
        "ApplicationHealth",
        "ApplicationStreamEvent",
        "ApplicationCancellationRequest",
    }
)

PUBLIC_CONTRACT_TYPES = (
    ApplicationRequest,
    ApplicationQuery,
    ApplicationCommand,
    ApplicationError,
    ApplicationResponse,
    ApplicationSession,
    ApplicationMessage,
    ApplicationCapability,
    ApplicationHealth,
    ApplicationStreamEvent,
    ApplicationCancellationRequest,
)


def test_public_package_exports_every_frozen_contract_name() -> None:
    from cmm import application
    from cmm.application import contracts

    assert FROZEN_CONTRACT_NAMES <= set(application.__all__)
    for name in sorted(FROZEN_CONTRACT_NAMES):
        assert getattr(application, name) is getattr(contracts, name)


def test_public_package_does_not_export_internal_metadata_validators() -> None:
    from cmm import application

    assert not [name for name in application.__all__ if name.startswith("_")]
    assert "freeze_public_mapping" not in application.__all__
    assert "is_secret_like_key" not in application.__all__


@pytest.mark.parametrize("contract_type", PUBLIC_CONTRACT_TYPES)
def test_public_contracts_are_frozen_slotted_dataclasses(
    contract_type: type,
) -> None:
    import dataclasses

    assert dataclasses.is_dataclass(contract_type)
    assert contract_type.__dataclass_params__.frozen is True

    # Every field is declared in a ``__slots__`` along the MRO, so no instance
    # of a public contract ever carries a mutable ``__dict__``.
    declared_slots = {
        name
        for klass in contract_type.__mro__
        for name in getattr(klass, "__slots__", ())
    }
    field_names = {declared.name for declared in dataclasses.fields(contract_type)}
    assert field_names <= declared_slots


def test_query_and_command_separate_their_own_fields() -> None:
    """The command-only fields never appear on a query, and vice versa."""

    query = _query()
    command = _command(idempotency_key="idem-1", expected_session_revision=0)

    assert not hasattr(query, "idempotency_key")
    assert not hasattr(query, "expected_session_revision")
    assert command.idempotency_key == "idem-1"

    # Both kinds share one identity envelope, so a shared field is present in
    # the base representation of each.
    assert set(query.to_dict()) <= set(command.to_dict())


def test_operation_declarations_preserve_declared_order() -> None:
    """Frozen sequences keep the declared order and are never deduplicated."""

    capability = ApplicationCapability(
        capability_id="capabilities",
        status=CapabilityStatus.AVAILABLE,
        version="1.0.0",
        operations=("capabilities.list", "health.get", "capabilities.list"),
    )

    assert capability.operations == (
        "capabilities.list",
        "health.get",
        "capabilities.list",
    )
    assert capability.to_dict()["operations"] == [
        "capabilities.list",
        "health.get",
        "capabilities.list",
    ]
