"""Phase 11.3 — versioned, transport-neutral public application contracts.

This module owns the public application boundary values of CMM OS.  It defines
no canonical subsystem contract: domain, agent, provider, workflow, operation,
execution, validation, session, memory, knowledge and orchestration ownership all
stay with their canonical packages.  These values adapt public input to those
owners and project safe public output back.

Every public value here is frozen at construction, validated against the frozen
public limits, recursively normalized to immutable representations, and
deterministically serializable through ``to_dict()``.  One request field,
``channel``, records the transport-neutral origin of a public request; it
selects no authority and defaults to ``API`` so every existing transport keeps
its current behavior.

Public metadata uses one bounded, secret-free grammar: only ``None``, ``bool``,
``int``, finite ``float``, ``str``, mappings of those values and sequences of
them are accepted.  Binary data, opaque runtime objects, unbounded nesting and
secret-shaped keys fail closed, so a credential, a live client, a raw exception
or hidden reasoning can never enter a public contract.  Key screening is
case-insensitive containment over the separator-free key, so it stays a
deterministic structural boundary rather than a content heuristic.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

__all__ = [
    "APPLICATION_API_VERSION",
    "COMMAND_OPERATIONS",
    "MAX_IDEMPOTENCY_KEY_LENGTH",
    "MAX_IDENTIFIER_LENGTH",
    "MAX_MESSAGE_LENGTH",
    "MAX_METADATA_DEPTH",
    "MAX_METADATA_ITEMS",
    "MAX_STRING_LENGTH",
    "QUERY_OPERATIONS",
    "ApplicationCancellationRequest",
    "ApplicationCapability",
    "ApplicationChannel",
    "ApplicationCommand",
    "ApplicationError",
    "ApplicationErrorCode",
    "ApplicationHealth",
    "ApplicationMessage",
    "ApplicationOperation",
    "ApplicationQuery",
    "ApplicationRequest",
    "ApplicationResponse",
    "ApplicationSession",
    "ApplicationStatus",
    "ApplicationStreamEvent",
    "CapabilityStatus",
    "StreamEventKind",
]

#: The one supported public application API version.
APPLICATION_API_VERSION = "v1"

#: Frozen public input bounds.  Oversized input fails before orchestration.
MAX_METADATA_DEPTH = 6
MAX_METADATA_ITEMS = 128
MAX_STRING_LENGTH = 16_384
MAX_MESSAGE_LENGTH = 64_000
MAX_IDENTIFIER_LENGTH = 256
MAX_IDEMPOTENCY_KEY_LENGTH = 256

#: Normalized metadata key names that fail closed.
SECRET_LIKE_METADATA_KEYS = frozenset(
    {
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
    }
)

#: Separator-free forms, so camelCase and joined spellings compare equal, e.g.
#: ``apiKey``, ``Api-Key`` and ``private_key``.
_SECRET_LIKE_KEY_FRAGMENTS = tuple(
    sorted({key.replace("_", "") for key in SECRET_LIKE_METADATA_KEYS})
)

_KEY_SEPARATOR = re.compile(r"[^a-z0-9]+")


# ── Enums ────────────────────────────────────────────────────────────────────


class ApplicationStatus(str, Enum):
    """Closed public status of one application response."""

    SUCCESS = "success"
    ROUTED = "routed"
    NEEDS_CLARIFICATION = "needs_clarification"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ApplicationOperation(str, Enum):
    """Closed public operation identity set."""

    HEALTH_GET = "health.get"
    CAPABILITIES_LIST = "capabilities.list"
    SESSION_CREATE = "sessions.create"
    SESSION_GET = "sessions.get"
    MESSAGE_SUBMIT = "messages.submit"
    REQUEST_CANCEL = "requests.cancel"


class ApplicationChannel(str, Enum):
    """Transport-neutral origin channel of one public application request.

    The channel is descriptive origin only: it selects no authority, grants no
    capability and changes no business rule.  It is carried into the canonical
    orchestration request so the canonical pipeline sees where a request came
    from, and it participates in the public request document so two otherwise
    identical commands from different channels are different commands for
    idempotency purposes.  ``API`` stays the default, so every existing
    transport that sets nothing keeps its current behavior.
    """

    API = "api"
    CLI = "cli"


class ApplicationErrorCode(str, Enum):
    """Closed public application error categories."""

    INVALID_REQUEST = "INVALID_REQUEST"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    CONCURRENCY_CONFLICT = "CONCURRENCY_CONFLICT"
    CANCELLED = "CANCELLED"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class CapabilityStatus(str, Enum):
    """Descriptive public availability of one capability."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEFERRED = "deferred"


class StreamEventKind(str, Enum):
    """Closed public stream event kinds."""

    STARTED = "started"
    DATA = "data"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


#: Operations that must never mutate state.
QUERY_OPERATIONS = frozenset(
    {
        ApplicationOperation.HEALTH_GET,
        ApplicationOperation.CAPABILITIES_LIST,
        ApplicationOperation.SESSION_GET,
    }
)

#: Operations that may request mutation through a canonical owner.
COMMAND_OPERATIONS = frozenset(
    {
        ApplicationOperation.SESSION_CREATE,
        ApplicationOperation.MESSAGE_SUBMIT,
        ApplicationOperation.REQUEST_CANCEL,
    }
)

#: Response statuses that must carry a public application error.
_ERROR_REQUIRED_STATUSES = frozenset(
    {ApplicationStatus.FAILED, ApplicationStatus.BLOCKED}
)


# ── Secret-free key detection ────────────────────────────────────────────────


def _metadata_key_fragment(key: str) -> str:
    """Return the separator-free, lowercase form of one metadata key."""

    return _KEY_SEPARATOR.sub("", key.lower())


def _is_secret_like_key(key: str) -> bool:
    """Return whether *key* names secret-bearing content.

    Comparison is containment over the separator-free lowercase key, so
    ``Api-Key``, ``apiKey``, ``refreshToken`` and ``db-credential`` all fail
    closed while the check stays deterministic and case-insensitive.
    """

    fragment = _metadata_key_fragment(key)
    return bool(fragment) and any(
        denied in fragment for denied in _SECRET_LIKE_KEY_FRAGMENTS
    )


# ── Bounded safe-value grammar ───────────────────────────────────────────────


class _SafeValueBudget:
    """Shared, bounded item budget for one public metadata value."""

    __slots__ = ("_remaining",)

    def __init__(self) -> None:
        self._remaining = MAX_METADATA_ITEMS

    def spend(self, label: str) -> None:
        """Consume one item, failing closed when the budget is exhausted."""

        self._remaining -= 1
        if self._remaining < 0:
            raise ValueError(
                f"{label} must not contain more than {MAX_METADATA_ITEMS} items"
            )


def _check_depth(depth: int, label: str) -> None:
    if depth > MAX_METADATA_DEPTH:
        raise ValueError(
            f"{label} must not nest deeper than {MAX_METADATA_DEPTH} levels"
        )


def _freeze_safe_value(
    value: object, *, label: str, depth: int, budget: _SafeValueBudget
) -> Any:
    """Return a recursively immutable, secret-free representation of *value*."""

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must not contain a non-finite number")
        return value
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise ValueError(
                f"{label} must not contain a string longer than "
                f"{MAX_STRING_LENGTH} characters"
            )
        return value
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError(f"{label} must not carry binary data")
    if isinstance(value, Mapping):
        _check_depth(depth, label)
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{label} keys must be strings")
            if _is_secret_like_key(key):
                raise ValueError(
                    f"{label} key {key!r} is not permitted in a public "
                    f"application value"
                )
            budget.spend(label)
            frozen[key] = _freeze_safe_value(
                item, label=label, depth=depth + 1, budget=budget
            )
        return MappingProxyType(frozen)
    if isinstance(value, Sequence):
        _check_depth(depth, label)
        items: list[Any] = []
        for item in value:
            budget.spend(label)
            items.append(
                _freeze_safe_value(item, label=label, depth=depth + 1, budget=budget)
            )
        return tuple(items)

    raise TypeError(
        f"{label} must be a JSON-safe public value, not {type(value).__name__}"
    )


def _freeze_public_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    """Freeze a public mapping field against the bounded safe grammar."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")

    frozen = _freeze_safe_value(
        value, label=field_name, depth=1, budget=_SafeValueBudget()
    )
    assert isinstance(frozen, Mapping)
    return frozen


def _thaw(value: object) -> Any:
    """Return a fresh, plain, JSON-native representation of a frozen value."""

    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


# ── Scalar validators ────────────────────────────────────────────────────────


def _api_version(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("api_version must be a string")
    if value != APPLICATION_API_VERSION:
        raise ValueError(f"api_version must be {APPLICATION_API_VERSION!r}")
    return value


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise ValueError(
            f"{field_name} must not exceed {MAX_IDENTIFIER_LENGTH} characters"
        )
    return normalized


def _optional_identifier(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    return _identifier(value, field_name) if value.strip() else None


def _bounded_text(value: object, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    if len(value) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")
    return value


def _message_content(value: object) -> str:
    """Return message text unchanged; public text is never silently rewritten."""

    if not isinstance(value, str):
        raise TypeError("content must be a string")
    if not value:
        raise ValueError("content must be non-empty")
    if len(value) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"content must not exceed {MAX_MESSAGE_LENGTH} characters")
    return value


def _optional_revision(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be a non-negative int or None")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value


def _optional_idempotency_key(value: object) -> str | None:
    if value is None:
        return None
    return _bounded_text(value, "idempotency_key", MAX_IDEMPOTENCY_KEY_LENGTH)


def _timestamp(value: object, field_name: str) -> str:
    """Require a public timestamp with an explicit UTC offset."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must carry an explicit UTC offset")
    return value


def _enum_member(value: object, enum_type: type[Enum], field_name: str) -> Any:
    """Require a real enum member; a raw string is never silently coerced."""

    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be a {enum_type.__name__}")
    return value


def _operations(value: object) -> tuple[str, ...]:
    """Freeze a declaration of operation or service names, order preserved."""

    if value is None:
        return ()
    if isinstance(value, str | bytes | bytearray) or not isinstance(value, Sequence):
        raise TypeError("expected a sequence of identifiers")

    return tuple(_identifier(item, "identifier") for item in value)


# ── Request contracts ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ApplicationRequest:
    """One versioned public application request.

    The contract deliberately does not validate the command/query kind of
    ``operation``: command/query semantic dispatch belongs to
    ``ApplicationGateway``, which owns that fail-closed decision.
    """

    request_id: str
    api_version: str
    operation: ApplicationOperation
    actor_id: str | None = None
    session_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    channel: ApplicationChannel = ApplicationChannel.API

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )
        object.__setattr__(self, "api_version", _api_version(self.api_version))
        object.__setattr__(
            self,
            "operation",
            _enum_member(self.operation, ApplicationOperation, "operation"),
        )
        object.__setattr__(
            self, "actor_id", _optional_identifier(self.actor_id, "actor_id")
        )
        object.__setattr__(
            self, "session_id", _optional_identifier(self.session_id, "session_id")
        )
        object.__setattr__(
            self, "payload", _freeze_public_mapping(self.payload, "payload")
        )
        object.__setattr__(
            self, "metadata", _freeze_public_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self, "channel", _enum_member(self.channel, ApplicationChannel, "channel")
        )

    def to_dict(self) -> dict[str, Any]:
        return _request_dict(self)


def _request_dict(request: ApplicationRequest) -> dict[str, Any]:
    """Return the deterministic public representation of one request."""

    return {
        "request_id": request.request_id,
        "api_version": request.api_version,
        "operation": request.operation.value,
        "actor_id": request.actor_id,
        "session_id": request.session_id,
        "payload": _thaw(request.payload),
        "metadata": _thaw(request.metadata),
        "channel": request.channel.value,
    }


@dataclass(frozen=True, slots=True)
class ApplicationQuery(ApplicationRequest):
    """A read-only public application request; it never mutates state."""


@dataclass(frozen=True, slots=True)
class ApplicationCommand(ApplicationRequest):
    """A public application request that may request mutation.

    ``expected_session_revision`` carries the caller's optimistic-concurrency
    assertion, and ``idempotency_key`` opts the command into repeatable replay.
    """

    idempotency_key: str | None = None
    expected_session_revision: int | None = None

    def __post_init__(self) -> None:
        # Called explicitly rather than through ``super()``: a slotted frozen
        # dataclass subclass is rebuilt by ``dataclasses``, which leaves the
        # zero-argument ``super()`` cell pointing at the pre-rebuild class.
        ApplicationRequest.__post_init__(self)
        object.__setattr__(
            self, "idempotency_key", _optional_idempotency_key(self.idempotency_key)
        )
        object.__setattr__(
            self,
            "expected_session_revision",
            _optional_revision(
                self.expected_session_revision, "expected_session_revision"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = _request_dict(self)
        payload["idempotency_key"] = self.idempotency_key
        payload["expected_session_revision"] = self.expected_session_revision
        return payload


# ── Error and response contracts ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ApplicationError:
    """One safe, public application error.

    The message is a public-safe constant chosen by the application layer.  No
    traceback, exception repr, filesystem path, credential value or hidden
    reasoning is ever carried here.
    """

    code: ApplicationErrorCode
    message: str
    retryable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "code",
            _enum_member(self.code, ApplicationErrorCode, "code"),
        )
        object.__setattr__(
            self,
            "message",
            _bounded_text(self.message, "message", MAX_STRING_LENGTH),
        )
        if not isinstance(self.retryable, bool):
            raise TypeError("retryable must be a bool")
        object.__setattr__(
            self, "details", _freeze_public_mapping(self.details, "details")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "details": _thaw(self.details),
        }


@dataclass(frozen=True, slots=True)
class ApplicationResponse:
    """One safe, versioned public application response envelope."""

    request_id: str
    api_version: str
    status: ApplicationStatus
    data: Mapping[str, Any] | None = None
    error: ApplicationError | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )
        object.__setattr__(self, "api_version", _api_version(self.api_version))
        object.__setattr__(
            self,
            "status",
            _enum_member(self.status, ApplicationStatus, "status"),
        )
        if self.error is not None and not isinstance(self.error, ApplicationError):
            raise TypeError("error must be an ApplicationError or None")
        if self.data is not None:
            object.__setattr__(self, "data", _freeze_public_mapping(self.data, "data"))
        object.__setattr__(
            self, "metadata", _freeze_public_mapping(self.metadata, "metadata")
        )
        if self.status in _ERROR_REQUIRED_STATUSES and self.error is None:
            raise ValueError(
                f"status {self.status.value} requires an application error"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "api_version": self.api_version,
            "status": self.status.value,
            "data": None if self.data is None else _thaw(self.data),
            "error": None if self.error is None else self.error.to_dict(),
            "metadata": _thaw(self.metadata),
        }


# ── Session and message contracts ────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ApplicationSession:
    """Safe public projection of one canonical shared session.

    Timestamps are descriptive, never authority, and always carry an explicit
    UTC offset so serialization stays deterministic.
    """

    session_id: str
    revision: int
    status: str
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "session_id", _identifier(self.session_id, "session_id")
        )
        object.__setattr__(
            self, "revision", _optional_revision(self.revision, "revision")
        )
        if self.revision is None:
            raise ValueError("revision must be a non-negative int")
        object.__setattr__(
            self,
            "status",
            _bounded_text(self.status, "status", MAX_IDENTIFIER_LENGTH),
        )
        object.__setattr__(
            self, "created_at", _timestamp(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "updated_at", _timestamp(self.updated_at, "updated_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "revision": self.revision,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class ApplicationMessage:
    """One public application message bound to a canonical session."""

    message_id: str
    session_id: str
    actor_id: str
    content: str
    content_type: str = "text/plain"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    expected_session_revision: int | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "message_id", _identifier(self.message_id, "message_id")
        )
        object.__setattr__(
            self, "session_id", _identifier(self.session_id, "session_id")
        )
        object.__setattr__(self, "actor_id", _identifier(self.actor_id, "actor_id"))
        object.__setattr__(self, "content", _message_content(self.content))
        object.__setattr__(
            self,
            "content_type",
            _bounded_text(self.content_type, "content_type", MAX_IDENTIFIER_LENGTH),
        )
        object.__setattr__(
            self, "metadata", _freeze_public_mapping(self.metadata, "metadata")
        )
        object.__setattr__(
            self,
            "expected_session_revision",
            _optional_revision(
                self.expected_session_revision, "expected_session_revision"
            ),
        )
        object.__setattr__(
            self, "idempotency_key", _optional_idempotency_key(self.idempotency_key)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "actor_id": self.actor_id,
            "content": self.content,
            "content_type": self.content_type,
            "metadata": _thaw(self.metadata),
            "expected_session_revision": self.expected_session_revision,
            "idempotency_key": self.idempotency_key,
        }


# ── Capability, health, stream and cancellation contracts ────────────────────


@dataclass(frozen=True, slots=True)
class ApplicationCapability:
    """One descriptive public capability declaration.

    Capability discovery is descriptive only: it never infers that an owner
    exists merely because a route name exists.
    """

    capability_id: str
    status: CapabilityStatus
    version: str
    operations: tuple[str, ...] = ()
    reason_code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "capability_id", _identifier(self.capability_id, "capability_id")
        )
        object.__setattr__(
            self,
            "status",
            _enum_member(self.status, CapabilityStatus, "status"),
        )
        object.__setattr__(
            self,
            "version",
            _bounded_text(self.version, "version", MAX_IDENTIFIER_LENGTH),
        )
        object.__setattr__(self, "operations", _operations(self.operations))
        object.__setattr__(
            self,
            "reason_code",
            _optional_identifier(self.reason_code, "reason_code"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "status": self.status.value,
            "version": self.version,
            "operations": list(self.operations),
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class ApplicationHealth:
    """Safe public readiness projection; it is not a metrics system."""

    status: str
    api_version: str
    platform_ready: bool
    services: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "status",
            _bounded_text(self.status, "status", MAX_IDENTIFIER_LENGTH),
        )
        object.__setattr__(self, "api_version", _api_version(self.api_version))
        if not isinstance(self.platform_ready, bool):
            raise TypeError("platform_ready must be a bool")
        object.__setattr__(self, "services", _operations(self.services))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "api_version": self.api_version,
            "platform_ready": self.platform_ready,
            "services": list(self.services),
        }


@dataclass(frozen=True, slots=True)
class ApplicationStreamEvent:
    """One public-safe delivery envelope for a public application stream.

    This is a delivery envelope only: it is not an Event Bus, an Event Store or
    an Event Router, and it carries no internal orchestration event payload.
    """

    request_id: str
    sequence: int
    kind: StreamEventKind
    data: Mapping[str, Any] | None = None
    error: ApplicationError | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "sequence", _optional_revision(self.sequence, "sequence")
        )
        if self.sequence is None:
            raise ValueError("sequence must be a non-negative int")
        object.__setattr__(
            self,
            "kind",
            _enum_member(self.kind, StreamEventKind, "kind"),
        )
        if self.error is not None and not isinstance(self.error, ApplicationError):
            raise TypeError("error must be an ApplicationError or None")
        if self.data is not None:
            object.__setattr__(self, "data", _freeze_public_mapping(self.data, "data"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "sequence": self.sequence,
            "kind": self.kind.value,
            "data": None if self.data is None else _thaw(self.data),
            "error": None if self.error is None else self.error.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ApplicationCancellationRequest:
    """Public cancellation request identity.

    Phase 11.3 exposes a stable cancellation surface without creating a global
    cancellation runtime; the application layer reports capability
    unavailability when no canonical cancellable owner exists.
    """

    request_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id}
