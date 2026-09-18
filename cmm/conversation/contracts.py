"""Phase 11.5 — public conversational contracts.

This module owns the public conversational boundary values of CMM OS.  It
defines no conversational authority: canonical session persistence, application
dispatch, orchestration, approval, workflow, execution, memory and knowledge
ownership all stay with their canonical packages.  These values adapt public
conversational input to those owners and project safe public output back.

Every public value here is frozen at construction, validated against the frozen
public limits, recursively normalized to immutable representations and
deterministically serializable through ``to_dict()`` and ``from_dict()`` so a
persisted conversation extension round-trips exactly.

Public conversational values use one bounded, secret-free grammar: only
``None``, ``bool``, ``int``, finite ``float``, ``str``, mappings of those values
and sequences of them are accepted.  Binary data, opaque runtime objects, raw
exceptions, unbounded nesting, traceback-shaped keys, hidden-reasoning keys and
secret-shaped keys fail closed, so a credential, a live client, a raw exception
or hidden reasoning can never enter a public conversational contract.

Mapping keys are screened structurally rather than heuristically: a key must be
ASCII and must leave at least one alphanumeric character once separators are
removed, and the separator-free lowercase fragment is then rejected when it
contains a denied fragment.  A non-ASCII spelling (a Cyrillic homoglyph or a
full-width form) and a separator-only spelling therefore fail closed instead of
normalizing past the screen, while non-ASCII text stays fully supported in
values.

The frozen public bounds mirror the frozen public application limits exactly, so
a conversational message is never bounded more loosely than the public
application message it becomes; the module itself stays standard-library only.
``references``, ``attachments`` and ``capability_state`` are additionally
bounded by ``MAX_COLLECTION_ITEMS``.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``.
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

#: Frozen public conversational input bounds.  They mirror the frozen public
#: application limits exactly, so a conversational message can never be bounded
#: more loosely than the public application message it becomes, while this
#: module stays free of a backend dependency.  The equality is pinned by
#: ``tests/conversation/test_contracts.py``.
MAX_METADATA_DEPTH = 6
MAX_METADATA_ITEMS = 128
MAX_STRING_LENGTH = 16_384
MAX_MESSAGE_LENGTH = 64_000
MAX_IDENTIFIER_LENGTH = 256

#: Frozen maximum number of items in one public conversational collection
#: (``references``, ``attachments`` and ``capability_state``); a longer
#: collection fails closed with ``ValueError``.  The bound matches the frozen
#: public metadata item bound.
MAX_COLLECTION_ITEMS = 128

__all__ = [
    "INTERNAL_DETAIL_METADATA_KEYS",
    "MAX_COLLECTION_ITEMS",
    "MAX_IDENTIFIER_LENGTH",
    "MAX_MESSAGE_LENGTH",
    "MAX_METADATA_DEPTH",
    "MAX_METADATA_ITEMS",
    "MAX_STRING_LENGTH",
    "SECRET_LIKE_METADATA_KEYS",
    "AssistantResponse",
    "ConversationActionState",
    "ConversationActionStatus",
    "ConversationAttachmentRef",
    "ConversationCapabilityState",
    "ConversationCapabilityStatus",
    "ConversationInteractionMode",
    "ConversationLineage",
    "ConversationMessage",
    "ConversationRole",
]

#: Normalized public field names that fail closed inside one serialized payload.
_ATTACHMENT_FIELDS = frozenset({"ref", "kind", "name", "media_type"})
_LINEAGE_FIELDS = frozenset({"supersedes_message_id", "regenerates_message_id"})
_MESSAGE_FIELDS = frozenset(
    {
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
)
_CAPABILITY_STATE_FIELDS = frozenset(
    {"capability", "requested", "effective", "status", "reason"}
)
_ACTION_STATE_FIELDS = frozenset({"reference", "status", "reason", "kind"})
_RESPONSE_FIELDS = frozenset(
    {
        "message",
        "sources",
        "reasoning_summary",
        "pending_questions",
        "proposed_actions",
        "approval_requests",
        "workflow_updates",
        "action_state",
        "domain_state",
        "capability_state",
        "memory_updates",
        "warnings",
    }
)

#: Normalized metadata key names that fail closed because they name secrets.
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

#: Normalized metadata key names that fail closed because they name internal
#: failure detail, hidden reasoning or hidden prompt content rather than public
#: conversational content.  ``prompt`` covers every normalized spelling that
#: contains it (``rawPrompt``, ``system_prompt``, ``private-prompt``), so a
#: prompt-bearing key cannot become public conversational metadata.
INTERNAL_DETAIL_METADATA_KEYS = frozenset(
    {
        "traceback",
        "stacktrace",
        "chainofthought",
        "scratchpad",
        "hiddenreasoning",
        "privatereasoning",
        "rawprompt",
        "systemprompt",
        "prompt",
    }
)

#: Separator-free denied forms, so camelCase and joined spellings compare equal,
#: e.g. ``apiKey``, ``Api-Key``, ``private_key`` and ``stack_trace``.
_DENIED_KEY_FRAGMENTS = tuple(
    sorted(
        {
            key.replace("_", "")
            for key in SECRET_LIKE_METADATA_KEYS | INTERNAL_DETAIL_METADATA_KEYS
        }
    )
)

_KEY_SEPARATOR = re.compile(r"[^a-z0-9]+")


# ── Enums ────────────────────────────────────────────────────────────────────


class ConversationRole(str, Enum):
    """Closed public role of one conversational message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationInteractionMode(str, Enum):
    """Closed public interaction mode of one canonical conversation.

    The seven values are the roadmap interaction modes.  A mode is
    interface/session metadata only: it creates no runtime and grants no
    capability, no Domain, no goal, no workflow and no permission, and it adds
    no behavior beyond the existing canonical message path.  An unsupported
    mode is never accepted and never silently becomes ``general``.
    """

    GENERAL = "general"
    DOMAIN = "domain"
    LINKED_GOAL = "linked_goal"
    LINKED_WORKFLOW = "linked_workflow"
    REFLECTION = "reflection"
    REVIEW = "review"
    CONFIGURATION = "configuration"


class ConversationCapabilityStatus(str, Enum):
    """Descriptive public availability of one requested conversational capability.

    Capability state is descriptive only: it never grants authority and never
    infers that an owner exists because a capability was requested.
    """

    AVAILABLE = "available"
    DEGRADED = "degraded"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


#: Statuses that provide no effective mode; ``effective`` must stay absent.
_EFFECTIVELESS_STATUSES = frozenset({ConversationCapabilityStatus.UNAVAILABLE})


class ConversationActionStatus(str, Enum):
    """Closed public interaction status of one projected action or approval.

    The status is descriptive only: only the canonical approval, permission and
    execution authorities may change real state, and the conversational layer
    never infers a terminal status (``approved``, ``rejected``, ``completed``)
    without canonical state that says so.
    """

    PROPOSED = "proposed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Secret-free key detection ────────────────────────────────────────────────


def _metadata_key_fragment(key: str) -> str:
    """Return the separator-free, lowercase form of one metadata key."""

    return _KEY_SEPARATOR.sub("", key.lower())


def _screened_mapping_key(key: object, label: str) -> str:
    """Return one screening-passed mapping key; every other key fails closed.

    Keys are screened structurally rather than heuristically: a key must be a
    string, must be pure ASCII, must leave at least one alphanumeric character
    once separators are removed, and its separator-free lowercase fragment must
    not contain a denied fragment.  ``Api-Key``, ``apiKey``, ``refreshToken``
    and ``db-credential`` therefore still fail closed by containment, while a
    Cyrillic-homoglyph, full-width or separator-only spelling fails closed here
    instead of normalizing past the screen.
    """

    if not isinstance(key, str):
        raise TypeError(f"{label} keys must be strings")
    if not key.isascii():
        raise ValueError(
            f"{label} keys must be ASCII so a homoglyph or full-width spelling "
            "can never pass the key screen"
        )
    fragment = _metadata_key_fragment(key)
    if not fragment:
        raise ValueError(f"{label} keys must not be empty or contain only separators")
    if any(denied in fragment for denied in _DENIED_KEY_FRAGMENTS):
        raise ValueError(
            f"{label} must not carry a secret-shaped or internal-detail key"
        )
    return key


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

    if isinstance(value, Enum):
        # A string-mixin enum is still a ``str`` subclass; normalizing it here
        # keeps the frozen representation exactly JSON-native.
        return _freeze_safe_value(value.value, label=label, depth=depth, budget=budget)
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
            screened = _screened_mapping_key(key, label)
            budget.spend(label)
            frozen[screened] = _freeze_safe_value(
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
    if not isinstance(frozen, Mapping):
        # A mapping input always freezes to a mapping proxy; this keeps the
        # fail-closed convention explicit under ``python -O``.
        raise TypeError(f"{field_name} must be a mapping")
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


def _optional_text(value: object, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    return _bounded_text(value, field_name, max_length) if value.strip() else None


def _content(value: object) -> str:
    """Return conversational text unchanged; public text is never rewritten.

    Text is bounded by the one public message limit but is not required to be
    non-empty: an attachment-only or structured-failure message must stay
    representable without inventing content.
    """

    if not isinstance(value, str):
        raise TypeError("content must be a string")
    if len(value) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"content must not exceed {MAX_MESSAGE_LENGTH} characters")
    return value


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


def _enum_from_value(value: object, enum_type: Any, field_name: str) -> Any:
    """Read one closed enum back out of a serialized public payload."""

    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a {enum_type.__name__}")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} is not a supported {enum_type.__name__}"
        ) from exc


def _sequence_items(value: object, field_name: str) -> Sequence[Any]:
    """Require a real sequence; a bare string is never read as item characters."""

    if isinstance(value, str | bytes | bytearray | memoryview) or not isinstance(
        value, Sequence
    ):
        raise TypeError(f"{field_name} must be a sequence")
    return value


def _check_collection_size(items: Sequence[Any], field_name: str) -> None:
    """Fail closed when one public collection exceeds its frozen bound."""

    if len(items) > MAX_COLLECTION_ITEMS:
        raise ValueError(
            f"{field_name} must not contain more than {MAX_COLLECTION_ITEMS} items"
        )


def _freeze_reference_tuple(value: object, field_name: str) -> tuple[str, ...]:
    """Freeze an ordered reference tuple, rejecting blanks and duplicates."""

    if value is None:
        return ()
    references = tuple(
        _identifier(item, field_name) for item in _sequence_items(value, field_name)
    )
    _check_collection_size(references, field_name)
    if len(set(references)) != len(references):
        raise ValueError(f"{field_name} must not contain duplicate references")
    return references


def _freeze_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    """Freeze an ordered public text tuple, preserving order and repeats."""

    if value is None:
        return ()
    texts = tuple(
        _bounded_text(item, field_name, MAX_STRING_LENGTH)
        for item in _sequence_items(value, field_name)
    )
    _check_collection_size(texts, field_name)
    return texts


def _attachment_refs(value: object, field_name: str) -> tuple[Any, ...]:
    """Freeze attachment references; only reference values are accepted."""

    if value is None:
        return ()
    attachments: list[Any] = []
    for item in _sequence_items(value, field_name):
        if not isinstance(item, ConversationAttachmentRef):
            raise TypeError(
                f"{field_name} must contain ConversationAttachmentRef values"
            )
        attachments.append(item)
    _check_collection_size(attachments, field_name)
    return tuple(attachments)


def _lineage_member(value: object) -> ConversationLineage:
    if not isinstance(value, ConversationLineage):
        raise TypeError("lineage must be a ConversationLineage")
    return value


def _action_states(value: object, field_name: str) -> tuple[Any, ...]:
    """Freeze action state; raw payloads are never silently coerced."""

    if value is None:
        return ()
    states: list[Any] = []
    for item in _sequence_items(value, field_name):
        if not isinstance(item, ConversationActionState):
            raise TypeError(f"{field_name} must contain ConversationActionState values")
        states.append(item)
    _check_collection_size(states, field_name)
    return tuple(states)


def _capability_states(value: object, field_name: str) -> tuple[Any, ...]:
    """Freeze capability state; raw payloads are never silently coerced."""

    if value is None:
        return ()
    states: list[Any] = []
    for item in _sequence_items(value, field_name):
        if not isinstance(item, ConversationCapabilityState):
            raise TypeError(
                f"{field_name} must contain ConversationCapabilityState values"
            )
        states.append(item)
    _check_collection_size(states, field_name)
    return tuple(states)


# ── Serialized payload readers ────────────────────────────────────────────────


def _payload(
    value: object, field_name: str, allowed: frozenset[str]
) -> Mapping[str, Any]:
    """Require one closed serialized payload; unknown fields fail closed."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    for key in value:
        if not isinstance(key, str) or key not in allowed:
            raise ValueError(f"{field_name} contains an unsupported field")
    return value


def _require(value: Mapping[str, Any], key: str, field_name: str) -> Any:
    if key not in value:
        raise ValueError(f"{field_name} is missing required field {key!r}")
    return value[key]


# ── Attachment and lineage values ────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationAttachmentRef:
    """One reference to an attachment owned by a canonical authority.

    Attachments are references only: this value never embeds a parallel object
    store, never carries content and never grants access.
    """

    ref: str
    kind: str
    name: str | None = None
    media_type: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref", _identifier(self.ref, "ref"))
        object.__setattr__(self, "kind", _identifier(self.kind, "kind"))
        object.__setattr__(
            self, "name", _optional_text(self.name, "name", MAX_STRING_LENGTH)
        )
        object.__setattr__(
            self,
            "media_type",
            _optional_text(self.media_type, "media_type", MAX_STRING_LENGTH),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "kind": self.kind,
            "name": self.name,
            "media_type": self.media_type,
        }

    @classmethod
    def from_dict(cls, data: object) -> ConversationAttachmentRef:
        payload = _payload(data, "attachment", _ATTACHMENT_FIELDS)
        return cls(
            ref=_require(payload, "ref", "attachment"),
            kind=_require(payload, "kind", "attachment"),
            name=payload.get("name"),
            media_type=payload.get("media_type"),
        )


@dataclass(frozen=True, slots=True)
class ConversationLineage:
    """Edit and regeneration relationships of one conversational message.

    Lineage records relationships only.  It never mutates the message it points
    at and never authorizes a rewrite of historical state.
    """

    supersedes_message_id: str | None = None
    regenerates_message_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "supersedes_message_id",
            _optional_identifier(self.supersedes_message_id, "supersedes_message_id"),
        )
        object.__setattr__(
            self,
            "regenerates_message_id",
            _optional_identifier(self.regenerates_message_id, "regenerates_message_id"),
        )
        if (
            self.supersedes_message_id is not None
            and self.supersedes_message_id == self.regenerates_message_id
        ):
            raise ValueError(
                "lineage must not supersede and regenerate the same message"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "supersedes_message_id": self.supersedes_message_id,
            "regenerates_message_id": self.regenerates_message_id,
        }

    @classmethod
    def from_dict(cls, data: object) -> ConversationLineage:
        payload = _payload(data, "lineage", _LINEAGE_FIELDS)
        return cls(
            supersedes_message_id=payload.get("supersedes_message_id"),
            regenerates_message_id=payload.get("regenerates_message_id"),
        )


# ── Message contract ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """One public conversational message bound to a canonical session.

    The message carries public-safe content only: no hidden reasoning, no raw
    exception, no provider credential and no canonical workflow/approval/domain
    state.  ``bot_id`` is an opaque association and has no authorization
    semantics.
    """

    id: str
    session_id: str
    role: ConversationRole
    content: str
    created_at: str
    bot_id: str | None = None
    references: tuple[str, ...] = ()
    attachments: tuple[ConversationAttachmentRef, ...] = ()
    lineage: ConversationLineage = ConversationLineage()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _identifier(self.id, "id"))
        object.__setattr__(
            self, "session_id", _identifier(self.session_id, "session_id")
        )
        object.__setattr__(
            self, "role", _enum_member(self.role, ConversationRole, "role")
        )
        object.__setattr__(self, "content", _content(self.content))
        object.__setattr__(
            self, "created_at", _timestamp(self.created_at, "created_at")
        )
        object.__setattr__(self, "bot_id", _optional_identifier(self.bot_id, "bot_id"))
        object.__setattr__(
            self, "references", _freeze_reference_tuple(self.references, "references")
        )
        object.__setattr__(
            self, "attachments", _attachment_refs(self.attachments, "attachments")
        )
        object.__setattr__(self, "lineage", _lineage_member(self.lineage))
        object.__setattr__(
            self, "metadata", _freeze_public_mapping(self.metadata, "metadata")
        )
        if self.id in (
            self.lineage.supersedes_message_id,
            self.lineage.regenerates_message_id,
        ):
            raise ValueError("lineage must not reference the message it belongs to")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role.value,
            "content": self.content,
            "created_at": self.created_at,
            "bot_id": self.bot_id,
            "references": list(self.references),
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "lineage": self.lineage.to_dict(),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: object) -> ConversationMessage:
        payload = _payload(data, "message", _MESSAGE_FIELDS)
        lineage = payload.get("lineage")
        return cls(
            id=_require(payload, "id", "message"),
            session_id=_require(payload, "session_id", "message"),
            role=_enum_from_value(
                _require(payload, "role", "message"), ConversationRole, "role"
            ),
            content=_require(payload, "content", "message"),
            created_at=_require(payload, "created_at", "message"),
            bot_id=payload.get("bot_id"),
            references=payload.get("references", ()),
            attachments=_serialized_attachments(payload.get("attachments", ())),
            lineage=(
                ConversationLineage()
                if lineage is None
                else lineage
                if isinstance(lineage, ConversationLineage)
                else ConversationLineage.from_dict(lineage)
            ),
            metadata=payload.get("metadata", {}),
        )


def _serialized_attachments(value: object) -> tuple[ConversationAttachmentRef, ...]:
    """Read attachment references back out of a serialized public payload."""

    if value is None:
        return ()
    attachments: list[ConversationAttachmentRef] = []
    for item in _sequence_items(value, "attachments"):
        if isinstance(item, ConversationAttachmentRef):
            attachments.append(item)
        elif isinstance(item, Mapping):
            attachments.append(ConversationAttachmentRef.from_dict(item))
        else:
            raise TypeError("attachments must contain ConversationAttachmentRef values")
    return tuple(attachments)


# ── Capability state contract ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationCapabilityState:
    """Requested versus effective public state of one conversational capability.

    A requested capability creates no authority; ``effective`` names what CMM OS
    can actually provide at this baseline, and ``unavailable`` never carries one.
    """

    capability: str
    requested: bool
    effective: str | None
    status: ConversationCapabilityStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "capability", _identifier(self.capability, "capability")
        )
        if not isinstance(self.requested, bool):
            raise TypeError("requested must be a bool")
        object.__setattr__(
            self, "effective", _optional_identifier(self.effective, "effective")
        )
        object.__setattr__(
            self,
            "status",
            _enum_member(self.status, ConversationCapabilityStatus, "status"),
        )
        object.__setattr__(
            self, "reason", _optional_text(self.reason, "reason", MAX_STRING_LENGTH)
        )
        if self.status in _EFFECTIVELESS_STATUSES and self.effective is not None:
            raise ValueError(
                f"effective must be absent when status is {self.status.value}"
            )
        if (
            self.status is ConversationCapabilityStatus.AVAILABLE
            and self.effective is None
        ):
            raise ValueError(
                "effective must name the provided mode when status is available"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "requested": self.requested,
            "effective": self.effective,
            "status": self.status.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: object) -> ConversationCapabilityState:
        payload = _payload(data, "capability_state", _CAPABILITY_STATE_FIELDS)
        return cls(
            capability=_require(payload, "capability", "capability_state"),
            requested=_require(payload, "requested", "capability_state"),
            effective=payload.get("effective"),
            status=_enum_from_value(
                _require(payload, "status", "capability_state"),
                ConversationCapabilityStatus,
                "status",
            ),
            reason=payload.get("reason"),
        )


# ── Action-state contract ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationActionState:
    """One public projection of a canonical action or approval state.

    The value carries a public reference and a closed status only: it never
    carries an executable payload, a callback, an authority token or arbitrary
    metadata, and visibility is never authorization.
    """

    reference: str
    status: ConversationActionStatus
    reason: str | None = None
    kind: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference", _identifier(self.reference, "reference"))
        object.__setattr__(
            self,
            "status",
            _enum_member(self.status, ConversationActionStatus, "status"),
        )
        object.__setattr__(
            self, "reason", _optional_text(self.reason, "reason", MAX_STRING_LENGTH)
        )
        object.__setattr__(self, "kind", _optional_identifier(self.kind, "kind"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "status": self.status.value,
            "reason": self.reason,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: object) -> ConversationActionState:
        payload = _payload(data, "action_state", _ACTION_STATE_FIELDS)
        return cls(
            reference=_require(payload, "reference", "action_state"),
            status=_enum_from_value(
                _require(payload, "status", "action_state"),
                ConversationActionStatus,
                "status",
            ),
            reason=payload.get("reason"),
            kind=payload.get("kind"),
        )


# ── Assistant response contract ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AssistantResponse:
    """One public conversational response projected from canonical owners.

    Every structured surface is either a public reference/projection of a
    canonical owner or a bounded public value; ``reasoning_summary`` is a public
    explanation surface only and never chain-of-thought.
    """

    message: ConversationMessage
    sources: tuple[str, ...] = ()
    reasoning_summary: Mapping[str, Any] = field(default_factory=dict)
    pending_questions: tuple[str, ...] = ()
    proposed_actions: tuple[str, ...] = ()
    approval_requests: tuple[str, ...] = ()
    workflow_updates: tuple[str, ...] = ()
    action_state: tuple[ConversationActionState, ...] = ()
    domain_state: Mapping[str, Any] = field(default_factory=dict)
    capability_state: tuple[ConversationCapabilityState, ...] = ()
    memory_updates: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.message, ConversationMessage):
            raise TypeError("message must be a ConversationMessage")
        object.__setattr__(self, "sources", _freeze_text_tuple(self.sources, "sources"))
        object.__setattr__(
            self,
            "reasoning_summary",
            _freeze_public_mapping(self.reasoning_summary, "reasoning_summary"),
        )
        object.__setattr__(
            self,
            "pending_questions",
            _freeze_text_tuple(self.pending_questions, "pending_questions"),
        )
        object.__setattr__(
            self,
            "proposed_actions",
            _freeze_text_tuple(self.proposed_actions, "proposed_actions"),
        )
        object.__setattr__(
            self,
            "approval_requests",
            _freeze_text_tuple(self.approval_requests, "approval_requests"),
        )
        object.__setattr__(
            self,
            "workflow_updates",
            _freeze_text_tuple(self.workflow_updates, "workflow_updates"),
        )
        object.__setattr__(
            self,
            "action_state",
            _action_states(self.action_state, "action_state"),
        )
        object.__setattr__(
            self,
            "domain_state",
            _freeze_public_mapping(self.domain_state, "domain_state"),
        )
        object.__setattr__(
            self,
            "capability_state",
            _capability_states(self.capability_state, "capability_state"),
        )
        object.__setattr__(
            self,
            "memory_updates",
            _freeze_text_tuple(self.memory_updates, "memory_updates"),
        )
        object.__setattr__(
            self, "warnings", _freeze_text_tuple(self.warnings, "warnings")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message.to_dict(),
            "sources": list(self.sources),
            "reasoning_summary": _thaw(self.reasoning_summary),
            "pending_questions": list(self.pending_questions),
            "proposed_actions": list(self.proposed_actions),
            "approval_requests": list(self.approval_requests),
            "workflow_updates": list(self.workflow_updates),
            "action_state": [state.to_dict() for state in self.action_state],
            "domain_state": _thaw(self.domain_state),
            "capability_state": [state.to_dict() for state in self.capability_state],
            "memory_updates": list(self.memory_updates),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: object) -> AssistantResponse:
        payload = _payload(data, "assistant_response", _RESPONSE_FIELDS)
        return cls(
            message=_serialized_message(
                _require(payload, "message", "assistant_response")
            ),
            sources=payload.get("sources", ()),
            reasoning_summary=payload.get("reasoning_summary", {}),
            pending_questions=payload.get("pending_questions", ()),
            proposed_actions=payload.get("proposed_actions", ()),
            approval_requests=payload.get("approval_requests", ()),
            workflow_updates=payload.get("workflow_updates", ()),
            action_state=_serialized_action_states(payload.get("action_state", ())),
            domain_state=payload.get("domain_state", {}),
            capability_state=_serialized_capability_states(
                payload.get("capability_state", ())
            ),
            memory_updates=payload.get("memory_updates", ()),
            warnings=payload.get("warnings", ()),
        )


def _serialized_message(value: object) -> ConversationMessage:
    if isinstance(value, ConversationMessage):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("message must be a ConversationMessage or a mapping")
    return ConversationMessage.from_dict(value)


def _serialized_action_states(
    value: object,
) -> tuple[ConversationActionState, ...]:
    """Read action state back out of a serialized public payload."""

    if value is None:
        return ()
    states: list[ConversationActionState] = []
    for item in _sequence_items(value, "action_state"):
        if isinstance(item, ConversationActionState):
            states.append(item)
        elif isinstance(item, Mapping):
            states.append(ConversationActionState.from_dict(item))
        else:
            raise TypeError("action_state must contain ConversationActionState values")
    return tuple(states)


def _serialized_capability_states(
    value: object,
) -> tuple[ConversationCapabilityState, ...]:
    """Read capability state back out of a serialized public payload."""

    if value is None:
        return ()
    states: list[ConversationCapabilityState] = []
    for item in _sequence_items(value, "capability_state"):
        if isinstance(item, ConversationCapabilityState):
            states.append(item)
        elif isinstance(item, Mapping):
            states.append(ConversationCapabilityState.from_dict(item))
        else:
            raise TypeError(
                "capability_state must contain ConversationCapabilityState values"
            )
    return tuple(states)
