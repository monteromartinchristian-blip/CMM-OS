"""Phase 11.5 — typed conversational failures and their constant public messages.

``cmm.conversation.contracts`` owns the public conversational values.  This
module owns the closed public error categories of the conversational boundary
and the safe failure value that carries one of them.

The failure value is safe by construction: :class:`ConversationError` accepts a
real :class:`ConversationErrorCode` member plus the module-owned constant public
message for that code, and nothing else.  Caller text, an exception repr, a
traceback, a filesystem path, a credential and hidden reasoning therefore cannot
be carried, even by accident, because no field accepts them.  Unknown failures
must map to the one generic internal-failure category rather than being copied.

:class:`ConversationBoundaryError` and its subclasses are the raised
counterparts of the same closed codes: each carries the module-owned constant
public message of its code, and none accepts an argument, so an underlying store
exception message, a revision value, a session path or any other internal text
can never travel through a conversational failure.

HTTP status mapping deliberately does not live here: it belongs to ``cmm.api``.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

__all__ = [
    "CONVERSATION_ERROR_MESSAGES",
    "GENERIC_CONVERSATION_FAILURE_MESSAGE",
    "ConversationBoundaryError",
    "ConversationError",
    "ConversationErrorCode",
    "ConversationProjectionBindingError",
    "ConversationSessionConflictError",
    "ConversationSessionNotFoundError",
]


class ConversationErrorCode(str, Enum):
    """Closed public conversational error categories."""

    INVALID_REQUEST = "invalid_request"
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_CONFLICT = "session_conflict"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    POLICY_DENIED = "policy_denied"
    APPROVAL_REQUIRED = "approval_required"
    INTERNAL_FAILURE = "internal_failure"


#: The one safe public message used for an unexpected internal failure.
GENERIC_CONVERSATION_FAILURE_MESSAGE = "Conversation request failed closed"

#: The module-owned public message for every closed conversational code.
CONVERSATION_ERROR_MESSAGES: Mapping[ConversationErrorCode, str] = MappingProxyType(
    {
        ConversationErrorCode.INVALID_REQUEST: "Conversation request is not valid",
        ConversationErrorCode.SESSION_NOT_FOUND: "Conversation session was not found",
        ConversationErrorCode.SESSION_CONFLICT: (
            "Conversation session revision conflicts with the request"
        ),
        ConversationErrorCode.CAPABILITY_UNAVAILABLE: (
            "Requested conversation capability is unavailable"
        ),
        ConversationErrorCode.POLICY_DENIED: (
            "Conversation request was denied by policy"
        ),
        ConversationErrorCode.APPROVAL_REQUIRED: (
            "Conversation request requires approval"
        ),
        ConversationErrorCode.INTERNAL_FAILURE: GENERIC_CONVERSATION_FAILURE_MESSAGE,
    }
)

#: The one closed serialized payload shape of a public conversational failure.
_ERROR_FIELDS = frozenset({"code", "message"})


def _code_member(value: object) -> ConversationErrorCode:
    """Require a real closed error code; a raw string is never coerced."""

    if not isinstance(value, ConversationErrorCode):
        raise TypeError("code must be a ConversationErrorCode")
    return value


def _code_from_value(value: object) -> ConversationErrorCode:
    """Read one closed error code back out of a serialized public payload."""

    if isinstance(value, ConversationErrorCode):
        return value
    if not isinstance(value, str):
        raise TypeError("code must be a ConversationErrorCode")
    try:
        return ConversationErrorCode(value)
    except ValueError as exc:
        raise ValueError("code is not a supported ConversationErrorCode") from exc


def _constant_public_message(value: object, code: ConversationErrorCode) -> str:
    """Require the module-owned constant message for *code*."""

    if not isinstance(value, str):
        raise TypeError("message must be a string")
    if value != CONVERSATION_ERROR_MESSAGES[code]:
        raise ValueError(
            "message must be the constant public message of its code; "
            "raw exception text, paths and tracebacks are never carried"
        )
    return value


@dataclass(frozen=True, slots=True)
class ConversationError:
    """One safe, public conversational failure.

    The message is always the module-owned constant for ``code``, so a
    traceback, exception repr, filesystem path, credential value or hidden
    reasoning can never be carried here.
    """

    code: ConversationErrorCode
    message: str

    def __post_init__(self) -> None:
        code = _code_member(self.code)
        object.__setattr__(self, "code", code)
        object.__setattr__(
            self, "message", _constant_public_message(self.message, code)
        )

    @classmethod
    def for_code(cls, code: ConversationErrorCode) -> ConversationError:
        """Return the constant public failure for one closed error code."""

        return cls(code=code, message=CONVERSATION_ERROR_MESSAGES[_code_member(code)])

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message}

    @classmethod
    def from_dict(cls, data: object) -> ConversationError:
        if not isinstance(data, Mapping):
            raise TypeError("conversation error must be a mapping")
        for key in data:
            if not isinstance(key, str) or key not in _ERROR_FIELDS:
                raise ValueError("conversation error contains an unsupported field")
        if "code" not in data or "message" not in data:
            raise ValueError("conversation error is missing a required field")
        return cls(
            code=_code_from_value(data["code"]),
            message=data["message"],
        )


# ── Boundary failures ─────────────────────────────────────────────────────────


class ConversationBoundaryError(Exception):
    """Base safe conversational boundary failure carrying a stable closed code.

    The failure carries the module-owned constant public message of its code and
    accepts no argument: a store exception message, a revision value, a path, a
    credential or hidden reasoning can never be attached to it.  Subclasses fix
    the code; the base code is ``INVALID_REQUEST``, the code used when a
    requested public conversational value cannot be resolved (for example a
    message ID that is not part of the conversation state).
    """

    code: ConversationErrorCode = ConversationErrorCode.INVALID_REQUEST

    def __init__(self) -> None:
        super().__init__(CONVERSATION_ERROR_MESSAGES[_code_member(self.code)])


class ConversationSessionNotFoundError(ConversationBoundaryError):
    """Raised when the canonical shared session of a conversation is missing."""

    code = ConversationErrorCode.SESSION_NOT_FOUND


class ConversationSessionConflictError(ConversationBoundaryError):
    """Raised when the canonical session revision conflicts with the request.

    This is also the safe shape of a canonical persistence race: the durable
    state and the attempted conversational commit disagree, and the request must
    not silently retry with a different revision.
    """

    code = ConversationErrorCode.SESSION_CONFLICT


class ConversationProjectionBindingError(ConversationBoundaryError):
    """Raised when an authorized Domain projection does not bind to the turn.

    The projection source is a composition-time dependency of the conversational
    service, so a projection that does not bind to the current request, the
    current canonical session, the current canonical Domain-resolution route or
    the current application result is an internal inconsistency of the composed
    service rather than a caller error: the turn fails closed with the generic
    internal-failure code before any reference is exposed or persisted, and no
    foreign Domain reference can leak.
    """

    code = ConversationErrorCode.INTERNAL_FAILURE
