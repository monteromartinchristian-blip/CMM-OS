"""Phase 11.50 — client-facing contracts of the reusable first-party backend.

This module owns the *client-interface* values of Phase 11.50 and nothing else.
It defines no session, conversation, message, response, stream or application
contract: those stay with their canonical owners in ``cmm.application`` and
``cmm.conversation``, and this layer reuses them verbatim rather than creating
semantic copies.

What the layer owns is exactly four things:

* one interface version (:data:`CLIENT_BACKEND_INTERFACE_VERSION`), which
  identifies the facade contract only and replaces no canonical version;
* one closed operation identity set (:class:`ClientOperation`) — never an
  arbitrary string dispatch, and never a service name, module path or callable;
* one closed set of *interface-shape* failures
  (:class:`ClientBackendErrorCode`) with module-owned constant messages.  A
  canonical application/conversation failure is projected through the canonical
  safe error projection instead, so no canonical code is duplicated here:
  ``ClientBackendError`` carries either a client-interface code or — for a known
  canonical downstream failure preserved verbatim — a member of the canonical
  closed error taxonomy itself (Audit V1 MAJOR-03 remediation);
* one narrow, transport-neutral request/result envelope
  (:class:`ClientBackendRequest` / :class:`ClientBackendResult`) whose payload
  is primitive-safe public data or canonical public values.

The envelope exists so a first-party client can speak the facade contract
without importing an internal module; it is deliberately *not* a second message
schema, a second session schema or a second error hierarchy.

See ``docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md``
(sections 10 to 13 and 24 to 26) and
``docs/reference/phase-11-reusable-backend-interfaces.md``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.application.contracts import APPLICATION_API_VERSION, ApplicationErrorCode
from cmm.conversation.errors import ConversationErrorCode

__all__ = [
    "APPLICATION_API_VERSION",
    "CANONICAL_PAYLOAD_TYPE_NAMES",
    "CLIENT_BACKEND_ERROR_MESSAGES",
    "CLIENT_BACKEND_INTERFACE_VERSION",
    "CLIENT_BACKEND_MAX_IDENTIFIER_LENGTH",
    "CLIENT_BACKEND_MAX_STRING_LENGTH",
    "CLIENT_BACKEND_MODULE_ID",
    "CLIENT_BACKEND_SERVICE_ID",
    "ClientBackendError",
    "ClientBackendErrorCode",
    "ClientBackendRequest",
    "ClientBackendResult",
    "ClientOperation",
    "require_supported_interface_version",
]

#: The one supported Phase 11.50 client-backend interface version.
#:
#: It identifies the facade contract of this package only.  It deliberately does
#: not replace ``APPLICATION_API_VERSION``, the conversational serialization, the
#: Phase 11.21 model-gateway contract versions or the ``cmm.api`` HTTP/OpenAPI
#: versions, each of which keeps its own canonical owner.
CLIENT_BACKEND_INTERFACE_VERSION = "1"

#: The frozen Phase 11.1 composition identity of the facade (see
#: ``cmm.client_backend.platform_module``).
CLIENT_BACKEND_SERVICE_ID = "client.backend"
CLIENT_BACKEND_MODULE_ID = "phase11.client-backend"

#: Frozen public input bounds, mirroring the canonical public identifier and
#: string limits so a client value is never bounded more loosely than the
#: canonical value it becomes.
CLIENT_BACKEND_MAX_IDENTIFIER_LENGTH = 256
CLIENT_BACKEND_MAX_STRING_LENGTH = 16_384


class ClientOperation(str, Enum):
    """Closed set of Phase 11.50 first-party client operations.

    Every member delegates to an existing canonical owner; none of them performs
    canonical work here.  There is no ``OTHER``, no free-form service name and no
    dynamic dispatch, so an operation a caller invents can never be reached.
    """

    CAPABILITIES = "capabilities"
    CREATE_SESSION = "create_session"
    GET_SESSION = "get_session"
    LOAD_CONVERSATION = "load_conversation"
    SUBMIT_MESSAGE = "submit_message"
    EDIT_MESSAGE = "edit_message"
    REGENERATE_RESPONSE = "regenerate_response"
    CANCEL_REQUEST = "cancel_request"


class ClientBackendErrorCode(str, Enum):
    """Closed set of client-interface-shape failures.

    Only failures *of this interface* live here.  A canonical application or
    conversational failure keeps its canonical code and is projected through the
    canonical safe projection (``safe_error_from_exception`` /
    ``ConversationBoundaryError.code``); it is never re-coded as a client error
    and never copied raw.
    """

    UNSUPPORTED_INTERFACE_VERSION = "UNSUPPORTED_INTERFACE_VERSION"
    INVALID_CLIENT_OPERATION = "INVALID_CLIENT_OPERATION"
    INVALID_CLIENT_CONTRACT = "INVALID_CLIENT_CONTRACT"
    INTERNAL_CLIENT_ERROR = "INTERNAL_CLIENT_ERROR"


#: The module-owned constant public message of every closed client error code.
#: ``ClientBackendError`` accepts nothing else, so an exception repr, a traceback,
#: a filesystem path, a credential or hidden reasoning can never travel through
#: a client-interface failure.
CLIENT_BACKEND_ERROR_MESSAGES: Mapping[ClientBackendErrorCode, str] = MappingProxyType(
    {
        ClientBackendErrorCode.UNSUPPORTED_INTERFACE_VERSION: (
            "Client backend interface version is not supported"
        ),
        ClientBackendErrorCode.INVALID_CLIENT_OPERATION: (
            "Client backend operation is not valid"
        ),
        ClientBackendErrorCode.INVALID_CLIENT_CONTRACT: (
            "Client backend request is not valid"
        ),
        ClientBackendErrorCode.INTERNAL_CLIENT_ERROR: (
            "Client backend request failed closed"
        ),
    }
)


# ── Closed scalar validation ─────────────────────────────────────────────────


def _code_member(value: object) -> ClientBackendErrorCode:
    """Require a real closed error code; a raw string is never coerced."""

    if not isinstance(value, ClientBackendErrorCode):
        raise TypeError("code must be a ClientBackendErrorCode")
    return value


#: The closed set of codes a :class:`ClientBackendError` may carry: one of the
#: four reserved client-interface codes, or — for a failure that preserves a
#: canonical downstream failure — a member of the canonical application or
#: conversational closed error taxonomy.  Nothing else is representable.
_ClientFailureCode = (
    ClientBackendErrorCode | ApplicationErrorCode | ConversationErrorCode
)

#: The canonical safe failure codes this layer may preserve verbatim.  The table
#: is derived from the canonical enums themselves, so the client backend can never
#: invent, rename or duplicate a canonical failure identity — and the two
#: canonical value vocabularies are disjoint (application codes are upper-case,
#: conversational codes are lower-case), so no entry is ambiguous.
_CANONICAL_FAILURE_CODES: Mapping[str, ApplicationErrorCode | ConversationErrorCode] = (
    MappingProxyType(
        {
            **{member.value: member for member in ApplicationErrorCode},
            **{member.value: member for member in ConversationErrorCode},
        }
    )
)


def _canonical_failure_code(
    value: object,
) -> ApplicationErrorCode | ConversationErrorCode:
    """Require one real canonical failure code; an invented code fails closed."""

    if not isinstance(value, str):
        raise TypeError("a canonical failure code must be a string")
    member = _CANONICAL_FAILURE_CODES.get(value)
    if member is None:
        raise ValueError(
            "a canonical failure code must be a member of the canonical "
            "ApplicationErrorCode or ConversationErrorCode taxonomy"
        )
    return member


def _canonical_failure_message(value: object) -> str:
    """Require one canonical bounded safe message; raw text is never accepted."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("a canonical failure message must be a non-empty string")
    if len(value) > CLIENT_BACKEND_MAX_STRING_LENGTH:
        raise ValueError(
            "a canonical failure message must not exceed "
            f"{CLIENT_BACKEND_MAX_STRING_LENGTH} characters"
        )
    return value


def _operation_member(value: object) -> ClientOperation:
    """Require a real closed operation member; a raw string is never coerced."""

    if not isinstance(value, ClientOperation):
        raise TypeError("operation must be a ClientOperation")
    return value


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if len(normalized) > CLIENT_BACKEND_MAX_IDENTIFIER_LENGTH:
        raise ValueError(
            f"{field_name} must not exceed {CLIENT_BACKEND_MAX_IDENTIFIER_LENGTH} "
            "characters"
        )
    return normalized


#: Canonical public values a client payload may carry **verbatim** (design §12:
#: "the ``payload`` must contain canonical values or safe serialized forms of
#: canonical values").  These are the frozen, immutable, secret-free public
#: contracts of the Phase 11.3 application backend and the Phase 11.5
#: conversational boundary; passing one through is the *point* of the envelope
#: and is not a wrapper.  Anything else must be primitive-safe data.  A control
#: test pins the inventory so a new type cannot enter silently.
CANONICAL_PAYLOAD_TYPE_NAMES = frozenset(
    {
        "cmm.application.contracts.ApplicationCapability",
        "cmm.application.contracts.ApplicationCancellationRequest",
        "cmm.application.contracts.ApplicationCommand",
        "cmm.application.contracts.ApplicationError",
        "cmm.application.contracts.ApplicationHealth",
        "cmm.application.contracts.ApplicationMessage",
        "cmm.application.contracts.ApplicationQuery",
        "cmm.application.contracts.ApplicationRequest",
        "cmm.application.contracts.ApplicationResponse",
        "cmm.application.contracts.ApplicationSession",
        "cmm.application.contracts.ApplicationStreamEvent",
        "cmm.conversation.contracts.AssistantResponse",
        "cmm.conversation.contracts.ConversationActionState",
        "cmm.conversation.contracts.ConversationAttachmentRef",
        "cmm.conversation.contracts.ConversationCapabilityState",
        "cmm.conversation.contracts.ConversationLineage",
        "cmm.conversation.contracts.ConversationMessage",
    }
)


def _is_canonical_payload_value(value: object) -> bool:
    """Return whether *value* is a frozen canonical public contract value.

    The identity test is a structural rule (a frozen dataclass) plus the frozen
    canonical type inventory, so a live client object, a raw exception, a
    provider adapter or any other opaque runtime object still fails closed.
    """

    value_type = type(value)
    qualified = f"{value_type.__module__}.{value_type.__qualname__}"
    if qualified not in CANONICAL_PAYLOAD_TYPE_NAMES:
        return False
    return bool(getattr(value_type, "__dataclass_params__", None)) and bool(
        getattr(value_type.__dataclass_params__, "frozen", False)
    )


def _primitive_safe(value: object, *, label: str, depth: int = 1) -> Any:
    """Return an immutable, primitive-safe representation of *value*.

    Public client payloads carry descriptions and canonical identities, never
    executable material: binary data, callables, modules and opaque runtime
    objects fail closed, and a mapping key must be a string.  A frozen canonical
    public contract value is passed through unchanged — it is already immutable
    and carries no executable material.  No content heuristic is applied here: a
    canonical contract applies its own secret-free screen.
    """

    if value is None or isinstance(value, bool | int | str):
        if isinstance(value, str) and len(value) > CLIENT_BACKEND_MAX_STRING_LENGTH:
            raise ValueError(
                f"{label} must not contain a string longer than "
                f"{CLIENT_BACKEND_MAX_STRING_LENGTH} characters"
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must not contain a non-finite number")
        return value
    if _is_canonical_payload_value(value):
        return value
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError(f"{label} must not carry binary data")
    if isinstance(value, Enum):
        return _primitive_safe(value.value, label=label, depth=depth)
    if isinstance(value, Mapping):
        if depth > 6:
            raise ValueError(f"{label} must not nest deeper than 6 levels")
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{label} keys must be strings")
            frozen[key] = _primitive_safe(item, label=label, depth=depth + 1)
        return MappingProxyType(frozen)
    if isinstance(value, tuple | list):
        if depth > 6:
            raise ValueError(f"{label} must not nest deeper than 6 levels")
        return tuple(
            _primitive_safe(item, label=label, depth=depth + 1) for item in value
        )
    raise TypeError(
        f"{label} must be primitive-safe public data, not {type(value).__name__}"
    )


def _thaw(value: object) -> Any:
    """Return a fresh, plain, JSON-native representation of a frozen value."""

    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


class ClientBackendError(Exception):
    """One safe client-visible failure, of exactly one of two disjoint kinds.

    * a **client-interface** failure, carrying one of the four reserved
      :class:`ClientBackendErrorCode` values and its module-owned constant
      message.  ``canonical_code`` is ``None`` and :attr:`code` is the closed
      client-interface member;
    * a **canonical downstream** failure, preserving the canonical owner's own
      safe code and safe message verbatim.  Audit V1 MAJOR-03 remediation: a
      known canonical ``RESOURCE_NOT_FOUND``, ``CONFLICT``, ``SESSION_CONFLICT``,
      ``CAPABILITY_UNAVAILABLE``, ``POLICY_DENIED``, ``APPROVAL_REQUIRED``,
      ``CANCELLED``, ``INVALID_REQUEST`` or ``UNSUPPORTED_VERSION`` must not be
      lossily re-coded as ``INTERNAL_CLIENT_ERROR`` merely because it crossed the
      client facade.

    The canonical kind duplicates **no** taxonomy: :meth:`from_canonical` accepts
    only a code that is a real member of the canonical closed
    ``ApplicationErrorCode`` or ``ConversationErrorCode`` enum, and the message it
    carries is the canonical owner's own bounded safe message.  A canonical
    *internal* failure is deliberately not preserved: it is an internal defect and
    is projected as the one generic client error instead.
    """

    def __init__(self, code: ClientBackendErrorCode) -> None:
        self.code: _ClientFailureCode = _code_member(code)
        self.message = CLIENT_BACKEND_ERROR_MESSAGES[self.code]
        #: The canonical safe code when this failure preserves a canonical
        #: downstream failure, and ``None`` for a client-interface failure.
        self.canonical_code: str | None = None
        super().__init__(self.message)

    @classmethod
    def from_canonical(cls, *, code: str, message: str) -> ClientBackendError:
        """Return one canonical downstream failure preserved in its own identity.

        The canonical code must be a member of the canonical closed application or
        conversational error taxonomy, and the message must be the canonical
        owner's bounded safe message.  An unknown code fails closed rather than
        creating a third taxonomy.
        """

        canonical = _canonical_failure_code(code)
        failure = cls.__new__(cls)
        failure.code = canonical
        failure.message = _canonical_failure_message(message)
        failure.canonical_code = canonical.value
        Exception.__init__(failure, failure.message)
        return failure

    @property
    def is_canonical(self) -> bool:
        """Return whether this failure preserves a canonical downstream failure."""

        return self.canonical_code is not None

    def to_dict(self) -> dict[str, str]:
        """Return the deterministic public representation of this failure."""

        code = self.canonical_code
        if code is None:
            code = self.code.value
        return {"code": code, "message": self.message}


def require_supported_interface_version(value: object) -> str:
    """Return *value* when it is the one supported interface version.

    This is the version gate of the layer.  An absent, blank or non-textual
    version is an invalid client contract, and any textual version other than the
    frozen :data:`CLIENT_BACKEND_INTERFACE_VERSION` fails closed as
    ``UNSUPPORTED_INTERFACE_VERSION``.  The gate runs before any canonical owner
    is reached, so an unsupported version can never cause a downstream call.
    """

    if not isinstance(value, str) or not value.strip():
        raise ClientBackendError(ClientBackendErrorCode.INVALID_CLIENT_CONTRACT)
    if value != CLIENT_BACKEND_INTERFACE_VERSION:
        raise ClientBackendError(ClientBackendErrorCode.UNSUPPORTED_INTERFACE_VERSION)
    return value


@dataclass(frozen=True, slots=True)
class ClientBackendRequest:
    """One narrow, transport-neutral client request envelope.

    The envelope carries the interface version, a caller-supplied request
    identity, one closed operation and a primitive-safe payload.  It is not a
    second message or session schema: a canonical public value travels inside
    ``payload`` verbatim, and the envelope adds only correlation and operation
    identity.

    A payload may never carry a callable, a module, an import path, a service
    name or binary data, so the envelope can never become a service locator or a
    dynamic dispatch channel.
    """

    interface_version: str
    request_id: str
    operation: ClientOperation
    payload: Mapping[str, Any] = field(default_factory=dict)
    #: Test-only seam: build an envelope for an unsupported version so the
    #: *dispatch* boundary's own fail-closed gate can be observed.  It is not an
    #: execution bypass — ``dispatch`` validates the version again, and this flag
    #: only suppresses the constructor's own gate.
    _skip_version_gate: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.interface_version, str):
            raise TypeError("interface_version must be a string")
        object.__setattr__(
            self,
            "request_id",
            _identifier(self.request_id, "request_id"),
        )
        object.__setattr__(
            self,
            "operation",
            _operation_member(self.operation),
        )
        object.__setattr__(
            self,
            "payload",
            _primitive_safe(self.payload, label="payload"),
        )
        if not isinstance(self._skip_version_gate, bool):
            raise TypeError("_skip_version_gate must be a bool")
        if not self._skip_version_gate:
            # The version gate runs last so the frozen request value is only ever
            # built for a supported interface version.
            require_supported_interface_version(self.interface_version)

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic public representation of this request."""

        return {
            "interface_version": self.interface_version,
            "request_id": self.request_id,
            "operation": self.operation.value,
            "payload": _thaw(self.payload),
        }

    @classmethod
    def for_interface_version(
        cls,
        interface_version: str,
        *,
        request_id: str,
        operation: ClientOperation,
        payload: Mapping[str, Any] | None = None,
    ) -> ClientBackendRequest:
        """Build an envelope for *any* interface version without the version gate.

        The normal constructor is the version gate.  This alternative exists only
        so a caller can hand an unsupported version to
        :meth:`~cmm.client_backend.interface.ClientBackend.dispatch` and observe
        the fail-closed result of the *dispatch* boundary, which validates the
        version again before reaching any canonical owner.  It is not a bypass of
        that gate: it constructs a value, it executes nothing.
        """

        return cls(
            interface_version=interface_version,
            request_id=request_id,
            operation=operation,
            payload={} if payload is None else payload,
            _skip_version_gate=True,
        )


@dataclass(frozen=True, slots=True)
class ClientBackendResult:
    """One deterministic, primitive-safe client result envelope.

    ``data`` carries primitive-safe public data derived from canonical public
    values; ``error`` carries one closed client-interface failure.  Exactly one
    of the two is present, so ``ok`` is never ambiguous.
    """

    interface_version: str
    request_id: str
    operation: ClientOperation
    ok: bool
    data: Mapping[str, Any] | None = None
    error: ClientBackendError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.interface_version, str):
            raise TypeError("interface_version must be a string")
        object.__setattr__(
            self, "request_id", _identifier(self.request_id, "request_id")
        )
        object.__setattr__(self, "operation", _operation_member(self.operation))
        if not isinstance(self.ok, bool):
            raise TypeError("ok must be a bool")
        if self.error is not None and not isinstance(self.error, ClientBackendError):
            raise TypeError("error must be a ClientBackendError or None")
        if self.ok == (self.error is not None):
            raise ValueError(
                "a failed client result must carry an error and a successful one "
                "must not"
            )
        if self.data is not None:
            object.__setattr__(self, "data", _primitive_safe(self.data, label="data"))

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic public representation of this result."""

        return {
            "interface_version": self.interface_version,
            "request_id": self.request_id,
            "operation": self.operation.value,
            "ok": self.ok,
            "data": None if self.data is None else _thaw(self.data),
            "error": None if self.error is None else self.error.to_dict(),
        }
