"""Phase 11.5 — public conversational contract tests.

The Phase 11.5 conversational contracts are transport-neutral frozen values
owned by ``cmm.conversation``.  These tests lock the public names, the frozen
field order, the bounded and secret-free public value grammar, the lineage and
capability invariants, the constant public error messages and the
deterministic ``to_dict()`` / ``from_dict()`` round-trip.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from cmm.application.contracts import (
    MAX_IDENTIFIER_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_METADATA_DEPTH,
    MAX_METADATA_ITEMS,
    MAX_STRING_LENGTH,
    ApplicationResponse,
    ApplicationStatus,
)
from cmm.conversation import (
    AssistantResponse,
    ConversationAttachmentRef,
    ConversationCapabilityState,
    ConversationCapabilityStatus,
    ConversationError,
    ConversationErrorCode,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.contracts import MAX_COLLECTION_ITEMS
from cmm.conversation.errors import (
    CONVERSATION_ERROR_MESSAGES,
    GENERIC_CONVERSATION_FAILURE_MESSAGE,
)
from cmm.conversation.projection import ConversationResponseProjector
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    DomainInterfaceStatus,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

TIMESTAMP = "2026-09-17T09:00:00+00:00"


def _attachment(**overrides: object) -> ConversationAttachmentRef:
    fields: dict[str, object] = {
        "ref": "attachment://document-1",
        "kind": "document",
    }
    fields.update(overrides)
    return ConversationAttachmentRef(**fields)  # type: ignore[arg-type]


def _lineage(**overrides: object) -> ConversationLineage:
    fields: dict[str, object] = {}
    fields.update(overrides)
    return ConversationLineage(**fields)  # type: ignore[arg-type]


def _message(**overrides: object) -> ConversationMessage:
    fields: dict[str, object] = {
        "id": "msg-1",
        "session_id": "session-1",
        "role": ConversationRole.USER,
        "content": "hello",
        "created_at": TIMESTAMP,
    }
    fields.update(overrides)
    return ConversationMessage(**fields)  # type: ignore[arg-type]


def _capability(**overrides: object) -> ConversationCapabilityState:
    fields: dict[str, object] = {
        "capability": "response_streaming",
        "requested": True,
        "effective": "response_event_stream",
        "status": ConversationCapabilityStatus.DEGRADED,
    }
    fields.update(overrides)
    return ConversationCapabilityState(**fields)  # type: ignore[arg-type]


def _response(**overrides: object) -> AssistantResponse:
    fields: dict[str, object] = {"message": _message()}
    fields.update(overrides)
    return AssistantResponse(**fields)  # type: ignore[arg-type]


def _error(**overrides: object) -> ConversationError:
    fields: dict[str, object] = {
        "code": ConversationErrorCode.SESSION_NOT_FOUND,
        "message": CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.SESSION_NOT_FOUND],
    }
    fields.update(overrides)
    return ConversationError(**fields)  # type: ignore[arg-type]


def _application_response() -> ApplicationResponse:
    return ApplicationResponse(
        request_id="request-1",
        api_version="v1",
        status=ApplicationStatus.SUCCESS,
        data={"echo": "ok"},
    )


def _domain_view(**overrides: object) -> ConversationalDomainView:
    """Construct the frozen canonical view the projector consumes directly."""

    fields: dict[str, object] = {
        "primary_domain": "domain:general",
        "supporting_domains": (),
        "workflow_refs": (),
        "question_refs": (),
        "approval_refs": (),
        "source_refs": (),
        "contradiction_refs": (),
        "result_refs": (),
        "memory_proposal_refs": (),
        "confidence": None,
        "warning_refs": (),
        "status": DomainInterfaceStatus.READY,
    }
    fields.update(overrides)
    return ConversationalDomainView(**fields)  # type: ignore[arg-type]


def _project(view: ConversationalDomainView | None) -> AssistantResponse:
    return ConversationResponseProjector().project(
        request_message=_message(),
        assistant_message_id="msg-2",
        created_at=TIMESTAMP,
        application_response=_application_response(),
        domain_view=view,
        capability_state=(),
    )


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


def _contract_instances() -> list[object]:
    """Return one fully populated instance of every public conversational contract."""

    return [
        _attachment(name="notes.txt", media_type="text/plain"),
        _lineage(supersedes_message_id="msg-0"),
        _message(
            references=("source://document-1",),
            attachments=(_attachment(),),
            lineage=_lineage(regenerates_message_id="msg-0"),
            metadata={"origin": "test", "count": 1},
        ),
        _capability(reason="response_event_stream_only"),
        _response(
            sources=("source://document-1",),
            reasoning_summary={"outcome": "routed", "route": "direct_response"},
            pending_questions=("continue?",),
            proposed_actions=("action://restart",),
            approval_requests=("approval://request-1",),
            workflow_updates=("workflow://run-1",),
            domain_state={"domain": "finance"},
            capability_state=(_capability(),),
            memory_updates=("memory://proposal-1",),
            warnings=("streaming is degraded",),
        ),
        _error(),
    ]


CONTRACT_TYPES = (
    ConversationAttachmentRef,
    ConversationLineage,
    ConversationMessage,
    ConversationCapabilityState,
    AssistantResponse,
    ConversationError,
)

EXPECTED_FIELDS: dict[type, tuple[str, ...]] = {
    ConversationAttachmentRef: ("ref", "kind", "name", "media_type"),
    ConversationLineage: ("supersedes_message_id", "regenerates_message_id"),
    ConversationMessage: (
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
    ),
    ConversationCapabilityState: (
        "capability",
        "requested",
        "effective",
        "status",
        "reason",
    ),
    AssistantResponse: (
        "message",
        "sources",
        "reasoning_summary",
        "pending_questions",
        "proposed_actions",
        "approval_requests",
        "workflow_updates",
        "domain_state",
        "capability_state",
        "memory_updates",
        "warnings",
    ),
    ConversationError: ("code", "message"),
}

FROZEN_CONTRACT_NAMES = frozenset(
    {
        "ConversationRole",
        "ConversationCapabilityStatus",
        "ConversationAttachmentRef",
        "ConversationLineage",
        "ConversationMessage",
        "ConversationCapabilityState",
        "AssistantResponse",
        "ConversationErrorCode",
        "ConversationError",
    }
)


# ── Frozen public identity ───────────────────────────────────────────────────


def test_conversation_roles_are_frozen() -> None:
    assert {role.value for role in ConversationRole} == {"user", "assistant", "system"}


def test_conversation_capability_statuses_are_frozen() -> None:
    assert {status.value for status in ConversationCapabilityStatus} == {
        "available",
        "degraded",
        "approval_required",
        "blocked",
        "unavailable",
    }


def test_conversation_error_codes_are_frozen() -> None:
    assert {code.value for code in ConversationErrorCode} == {
        "invalid_request",
        "session_not_found",
        "session_conflict",
        "capability_unavailable",
        "policy_denied",
        "approval_required",
        "internal_failure",
    }


def test_public_limits_mirror_the_application_limits() -> None:
    """A message is never bounded more loosely than the application message it becomes."""

    from cmm.conversation import contracts

    assert contracts.MAX_METADATA_DEPTH == MAX_METADATA_DEPTH
    assert contracts.MAX_METADATA_ITEMS == MAX_METADATA_ITEMS
    assert contracts.MAX_STRING_LENGTH == MAX_STRING_LENGTH
    assert contracts.MAX_MESSAGE_LENGTH == MAX_MESSAGE_LENGTH
    assert contracts.MAX_IDENTIFIER_LENGTH == MAX_IDENTIFIER_LENGTH


def test_public_collection_limit_is_the_frozen_cap() -> None:
    """The one documented collection bound is 128 items for every collection field."""

    assert MAX_COLLECTION_ITEMS == 128


@pytest.mark.parametrize("contract_type", CONTRACT_TYPES)
def test_public_contracts_are_frozen_slotted_dataclasses(contract_type: type) -> None:
    assert dataclasses.is_dataclass(contract_type)
    assert contract_type.__dataclass_params__.frozen is True

    # Declared fields stay frozen: every field is declared in a ``__slots__``
    # along the MRO.  A plain subclass may still carry its own mutable
    # ``__dict__`` and pass ``isinstance`` gates (inherited house pattern).
    declared_slots = {
        name
        for klass in contract_type.__mro__
        for name in getattr(klass, "__slots__", ())
    }
    field_names = {declared.name for declared in dataclasses.fields(contract_type)}
    assert field_names <= declared_slots


@pytest.mark.parametrize(
    "contract_type", sorted(EXPECTED_FIELDS, key=lambda contract: contract.__name__)
)
def test_frozen_field_order_is_preserved(contract_type: type) -> None:
    declared = tuple(field.name for field in dataclasses.fields(contract_type))

    assert declared == EXPECTED_FIELDS[contract_type]


def _mutation_targets() -> list[tuple[object, str, object]]:
    return [
        (_attachment(), "ref", "changed"),
        (_lineage(), "supersedes_message_id", "msg-9"),
        (_message(), "content", "changed"),
        (_capability(), "capability", "changed"),
        (_response(), "warnings", ()),
        (_error(), "message", "changed"),
    ]


@pytest.mark.parametrize(("instance", "attribute", "value"), _mutation_targets())
def test_contracts_reject_mutation(
    instance: object, attribute: str, value: object
) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, value)


@pytest.mark.parametrize("contract_type", CONTRACT_TYPES)
def test_contracts_expose_to_dict_and_from_dict(contract_type: type) -> None:
    assert callable(contract_type.to_dict)
    assert callable(contract_type.from_dict)


def test_message_is_frozen_and_round_trips() -> None:
    message = ConversationMessage(
        id="msg-1",
        session_id="session-1",
        role=ConversationRole.USER,
        content="hello",
        created_at="2026-09-17T09:00:00+00:00",
        metadata={"safe": ["value"]},
    )
    assert ConversationMessage.from_dict(message.to_dict()) == message
    with pytest.raises(dataclasses.FrozenInstanceError):
        message.content = "changed"  # type: ignore[misc]


# ── Message identity and bounds ──────────────────────────────────────────────


def test_message_defaults_to_no_optional_branches() -> None:
    message = _message()

    assert message.bot_id is None
    assert message.references == ()
    assert message.attachments == ()
    assert message.lineage == ConversationLineage()
    assert dict(message.metadata) == {}


def test_message_identifiers_are_trimmed() -> None:
    message = _message(id="  msg-1  ", session_id="  session-1  ", bot_id="  bot-1  ")

    assert message.id == "msg-1"
    assert message.session_id == "session-1"
    assert message.bot_id == "bot-1"


@pytest.mark.parametrize("field", ["id", "session_id"])
@pytest.mark.parametrize("value", ["", "   ", "\n"])
def test_message_rejects_blank_identifiers(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        _message(**{field: value})


def test_message_rejects_non_string_identifiers() -> None:
    with pytest.raises(TypeError):
        _message(id=17)

    with pytest.raises(TypeError):
        _message(session_id=17)

    with pytest.raises(TypeError):
        _message(bot_id=17)


def test_message_identifier_respects_the_frozen_length_limit() -> None:
    assert _message(id="m" * MAX_IDENTIFIER_LENGTH).id

    with pytest.raises(ValueError):
        _message(id="m" * (MAX_IDENTIFIER_LENGTH + 1))


def test_message_optional_identifiers_normalize_blank_to_none() -> None:
    assert _message(bot_id="   ").bot_id is None


def test_message_role_must_be_a_real_role_member() -> None:
    with pytest.raises(TypeError):
        _message(role="user")

    assert _message(role=ConversationRole.ASSISTANT).role is ConversationRole.ASSISTANT


def test_message_content_respects_the_application_message_limit() -> None:
    longest = _message(content="x" * MAX_MESSAGE_LENGTH)

    assert len(longest.content) == MAX_MESSAGE_LENGTH

    with pytest.raises(ValueError):
        _message(content="x" * (MAX_MESSAGE_LENGTH + 1))


def test_message_content_must_be_a_string() -> None:
    with pytest.raises(TypeError):
        _message(content=b"hello")

    with pytest.raises(TypeError):
        _message(content=None)


def test_message_content_is_never_rewritten() -> None:
    content = "  keep  the  spacing  "

    assert _message(content=content).content == content


@pytest.mark.parametrize("created_at", ["2026-09-17T09:00:00", "yesterday", "", "   "])
def test_message_requires_an_explicit_offset_timestamp(created_at: str) -> None:
    with pytest.raises(ValueError):
        _message(created_at=created_at)


def test_message_timestamp_is_preserved_verbatim() -> None:
    assert _message(created_at=TIMESTAMP).created_at == TIMESTAMP


# ── Lineage ──────────────────────────────────────────────────────────────────


def test_lineage_defaults_to_no_relationships() -> None:
    lineage = ConversationLineage()

    assert lineage.supersedes_message_id is None
    assert lineage.regenerates_message_id is None


def test_lineage_normalizes_blank_identifiers_to_none() -> None:
    lineage = _lineage(supersedes_message_id="   ", regenerates_message_id="")

    assert lineage.supersedes_message_id is None
    assert lineage.regenerates_message_id is None


def test_lineage_rejects_non_identifier_values() -> None:
    with pytest.raises(TypeError):
        _lineage(supersedes_message_id=17)


def test_lineage_rejects_self_supersede() -> None:
    with pytest.raises(ValueError):
        _message(lineage=_lineage(supersedes_message_id="msg-1"))


def test_lineage_rejects_self_regeneration() -> None:
    with pytest.raises(ValueError):
        _message(lineage=_lineage(regenerates_message_id="msg-1"))


def test_lineage_rejects_superseding_and_regenerating_one_message() -> None:
    with pytest.raises(ValueError):
        ConversationLineage(
            supersedes_message_id="msg-9",
            regenerates_message_id="msg-9",
        )


def test_message_rejects_both_lineage_relationships_pointing_at_itself() -> None:
    with pytest.raises(ValueError):
        _message(
            lineage=ConversationLineage(
                supersedes_message_id="msg-1",
                regenerates_message_id="msg-1",
            )
        )


def test_message_rejects_a_foreign_lineage_value() -> None:
    with pytest.raises(TypeError):
        _message(lineage={"supersedes_message_id": "msg-0"})

    with pytest.raises(TypeError):
        _message(lineage=None)


def test_message_accepts_a_lineage_that_does_not_reference_itself() -> None:
    message = _message(lineage=_lineage(supersedes_message_id="msg-0"))

    assert message.lineage.supersedes_message_id == "msg-0"
    assert ConversationMessage.from_dict(message.to_dict()) == message


# ── Attachments ──────────────────────────────────────────────────────────────


def test_attachment_requires_a_ref_and_a_kind() -> None:
    for field in ("ref", "kind"):
        with pytest.raises(ValueError):
            _attachment(**{field: "   "})

        with pytest.raises(TypeError):
            _attachment(**{field: 17})


def test_attachment_optional_fields_normalize_blank_to_none() -> None:
    attachment = _attachment(name="   ", media_type="")

    assert attachment.name is None
    assert attachment.media_type is None


def test_attachment_preserves_its_declared_values() -> None:
    attachment = _attachment(name="notes.txt", media_type="text/plain")

    assert attachment.to_dict() == {
        "ref": "attachment://document-1",
        "kind": "document",
        "name": "notes.txt",
        "media_type": "text/plain",
    }
    assert ConversationAttachmentRef.from_dict(attachment.to_dict()) == attachment


def test_message_freezes_attachments_to_a_tuple() -> None:
    message = _message(attachments=[_attachment(), _attachment(ref="attachment://2")])

    assert message.attachments == (
        _attachment(),
        _attachment(ref="attachment://2"),
    )


def test_message_rejects_foreign_attachment_values() -> None:
    with pytest.raises(TypeError):
        _message(attachments=({"ref": "attachment://1", "kind": "document"},))

    with pytest.raises(TypeError):
        _message(attachments=("attachment://1",))

    with pytest.raises(TypeError):
        _message(attachments="attachment://1")


def test_message_bounds_the_attachment_collection() -> None:
    """``attachments`` is bounded by the frozen collection limit."""

    allowed = tuple(
        _attachment(ref=f"attachment://{index}")
        for index in range(MAX_COLLECTION_ITEMS)
    )

    assert _message(attachments=allowed).attachments == allowed

    with pytest.raises(ValueError):
        _message(attachments=allowed + (_attachment(ref="attachment://overflow"),))


def test_message_from_dict_bounds_the_attachment_collection() -> None:
    payload = _message(attachments=(_attachment(),)).to_dict()
    payload["attachments"] = [
        _attachment(ref=f"attachment://{index}").to_dict()
        for index in range(MAX_COLLECTION_ITEMS + 1)
    ]

    with pytest.raises(ValueError):
        ConversationMessage.from_dict(payload)


def test_message_from_dict_rejects_a_foreign_serialized_attachment() -> None:
    """A malformed persisted attachment entry is rejected, never dropped."""

    payload = _message(attachments=(_attachment(),)).to_dict()
    payload["attachments"] = [payload["attachments"][0], 17]

    with pytest.raises(TypeError):
        ConversationMessage.from_dict(payload)

    payload["attachments"] = [payload["attachments"][0], "attachment://1"]

    with pytest.raises(TypeError):
        ConversationMessage.from_dict(payload)


# ── References ───────────────────────────────────────────────────────────────


def test_message_freezes_references_in_declared_order() -> None:
    message = _message(references=["source://b", "source://a", "source://b2"])

    assert message.references == ("source://b", "source://a", "source://b2")


def test_message_trims_references() -> None:
    assert _message(references=("  source://a  ",)).references == ("source://a",)


def test_message_rejects_blank_references() -> None:
    with pytest.raises(ValueError):
        _message(references=("   ",))

    with pytest.raises(ValueError):
        _message(references=("source://a", ""))


def test_message_rejects_duplicate_references() -> None:
    with pytest.raises(ValueError):
        _message(references=("source://a", "source://a"))


def test_message_rejects_a_bare_string_as_the_reference_sequence() -> None:
    with pytest.raises(TypeError):
        _message(references="source://a")

    with pytest.raises(TypeError):
        _message(references=b"source://a")


def test_message_rejects_non_string_references() -> None:
    with pytest.raises(TypeError):
        _message(references=(17,))


def test_message_reference_limit_is_the_public_identifier_limit() -> None:
    reference = "ref://" + "r" * (MAX_IDENTIFIER_LENGTH - len("ref://"))
    assert _message(references=(reference,)).references == (reference,)

    with pytest.raises(ValueError):
        _message(references=(reference + "r",))


def test_message_bounds_the_reference_collection() -> None:
    """``references`` is bounded by the frozen collection limit."""

    allowed = tuple(f"source://{index}" for index in range(MAX_COLLECTION_ITEMS))

    assert _message(references=allowed).references == allowed

    with pytest.raises(ValueError):
        _message(references=allowed + ("source://overflow",))


def test_message_from_dict_bounds_the_reference_collection() -> None:
    payload = _message().to_dict()
    payload["references"] = [
        f"source://{index}" for index in range(MAX_COLLECTION_ITEMS + 1)
    ]

    with pytest.raises(ValueError):
        ConversationMessage.from_dict(payload)


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
        _message(metadata={key: "value"})


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
        _message(metadata={key: "value"})


#: Cyrillic ``o`` (U+043E) where the ASCII ``o`` of ``password`` belongs: a
#: homoglyph spelling that must not normalize past the key screen.
CYRILLIC_HOMOGLYPH_PASSWORD = "passw\u043erd"

#: Cyrillic ``e`` (U+0435) homoglyph inside ``credential``.
CYRILLIC_HOMOGLYPH_CREDENTIAL = "cr\u0435dential"

#: Full-width spelling of ``password`` (every character non-ASCII), whose
#: separator-free lowercase fragment would be empty.
FULLWIDTH_PASSWORD = "\uff50\uff41\uff53\uff53\uff57\uff4f\uff52\uff44"

#: Full-width spelling of ``token``.
FULLWIDTH_TOKEN = "\uff54\uff4f\uff4b\uff45\uff4e"

NON_ASCII_KEYS = (
    CYRILLIC_HOMOGLYPH_PASSWORD,
    CYRILLIC_HOMOGLYPH_CREDENTIAL,
    FULLWIDTH_PASSWORD,
    FULLWIDTH_TOKEN,
)

SEPARATOR_ONLY_KEYS = ("", "---", "___", " . ", "///")

KEY_SCREEN_SURFACES = ("metadata", "reasoning_summary", "domain_state")


def _construct_public_mapping(surface: str, mapping: Mapping[str, object]) -> object:
    """Bind *mapping* to one public mapping surface of the contract layer."""

    if surface == "metadata":
        return _message(metadata=mapping)
    return _response(**{surface: mapping})


@pytest.mark.parametrize("surface", KEY_SCREEN_SURFACES)
@pytest.mark.parametrize("key", NON_ASCII_KEYS)
def test_public_mapping_surfaces_reject_non_ascii_keys(surface: str, key: str) -> None:
    """A non-ASCII key (homoglyph or full-width) fails closed on every surface."""

    with pytest.raises(ValueError):
        _construct_public_mapping(surface, {key: "value"})


@pytest.mark.parametrize("surface", KEY_SCREEN_SURFACES)
@pytest.mark.parametrize("key", SEPARATOR_ONLY_KEYS)
def test_public_mapping_surfaces_reject_empty_and_separator_only_keys(
    surface: str, key: str
) -> None:
    """A key without one alphanumeric character left fails closed on every surface."""

    with pytest.raises(ValueError):
        _construct_public_mapping(surface, {key: "value"})


def test_nested_non_ascii_metadata_keys_fail_closed() -> None:
    """The key screen is applied to every nested mapping, not only the top one."""

    with pytest.raises(ValueError):
        _message(metadata={"outer": {FULLWIDTH_PASSWORD: "value"}})


def test_non_ascii_values_stay_accepted() -> None:
    """Only keys are ASCII-restricted; non-ASCII text in values keeps working."""

    content = "¿Dónde está la biblioteca? — 東京 jalapeño"
    metadata = {"note": "jalepeño — 日本語", "greeting": "こんにちは"}
    message = _message(content=content, metadata=metadata)

    assert message.content == content
    assert dict(message.metadata) == metadata

    response = _response(
        reasoning_summary={"outcome": "réussi"},
        domain_state={"domain": "финансы"},
    )

    assert dict(response.reasoning_summary) == {"outcome": "réussi"}
    assert dict(response.domain_state) == {"domain": "финансы"}


@pytest.mark.parametrize(
    "key",
    [
        "traceback",
        "stack_trace",
        "stackTrace",
        "exception_traceback",
        "rawTraceback",
        "chain_of_thought",
        "chainOfThought",
        "scratchpad",
        "hidden_reasoning",
    ],
)
def test_public_metadata_rejects_internal_detail_keys(key: str) -> None:
    """Traceback-like and hidden-reasoning keys are never public conversational data."""

    with pytest.raises(ValueError):
        _message(metadata={key: "value"})

    with pytest.raises(ValueError):
        _response(reasoning_summary={key: "value"})


@pytest.mark.parametrize(
    "key", ["note", "count", "level", "origin", "session", "domain"]
)
def test_public_metadata_allows_unrelated_keys(key: str) -> None:
    assert dict(_message(metadata={key: "value"}).metadata) == {key: "value"}


def test_public_metadata_rejects_binary_values() -> None:
    with pytest.raises(TypeError):
        _message(metadata={"blob": b"secret"})


def test_public_metadata_rejects_opaque_objects() -> None:
    with pytest.raises(TypeError):
        _message(metadata={"thing": object()})


def test_public_metadata_rejects_raw_exceptions() -> None:
    with pytest.raises(TypeError):
        _message(metadata={"error": ValueError("boom")})

    with pytest.raises(TypeError):
        _response(reasoning_summary={"error": RuntimeError("boom")})


def test_reasoning_summary_rejects_raw_exceptions_directly() -> None:
    with pytest.raises(TypeError):
        _response(reasoning_summary={"exception": ValueError("internal")})


def test_public_metadata_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError):
        _message(metadata={1: "value"})


def test_public_metadata_rejects_non_finite_floats() -> None:
    with pytest.raises(ValueError):
        _message(metadata={"ratio": float("nan")})

    with pytest.raises(ValueError):
        _message(metadata={"ratio": float("inf")})


def test_public_metadata_rejects_oversized_strings() -> None:
    assert _message(metadata={"note": "x" * MAX_STRING_LENGTH}).metadata

    with pytest.raises(ValueError):
        _message(metadata={"note": "x" * (MAX_STRING_LENGTH + 1)})


def test_public_metadata_rejects_excessive_nesting() -> None:
    _message(metadata=_nested_metadata(MAX_METADATA_DEPTH))

    with pytest.raises(ValueError):
        _message(metadata=_nested_metadata(MAX_METADATA_DEPTH + 1))


#: The secret-shaped key of the recursion-boundary adversary: it is placed at the
#: deepest mapping level the public grammar admits, so the case proves the key
#: screen is applied at the recursion boundary itself and not only near the root.
ATTACKER_METADATA_KEY = "api_key"


def _deepest_attacker_metadata(key: str) -> dict[str, object]:
    """Nest *key* at the deepest mapping level the public grammar admits."""

    payload: dict[str, object] = {key: "sk-attacker"}
    for level in range(MAX_METADATA_DEPTH - 1, 0, -1):
        payload = {f"level-{level}": payload}
    return payload


def test_deepest_attacker_metadata_at_the_recursion_boundary_is_rejected() -> None:
    """The deepest admissible payload fails closed; it is never sanitized.

    The attacker payload carries a secret-shaped key at the deepest mapping
    level the public grammar admits.  The identical shape with a benign key is
    accepted, so the failure is the key screen and not the recursion bound.  A
    violating payload never exists as a value, so nothing can persist it, and
    ``from_dict`` cannot read one back either.
    """

    attacker = _deepest_attacker_metadata(ATTACKER_METADATA_KEY)
    control = _deepest_attacker_metadata("note")

    assert _message(metadata=control).metadata

    with pytest.raises(ValueError):
        _message(metadata=attacker)

    serialized = _message(metadata=control).to_dict()
    serialized["metadata"] = attacker

    with pytest.raises(ValueError):
        ConversationMessage.from_dict(serialized)


def test_attacker_metadata_nested_through_sequences_is_rejected() -> None:
    """The key screen applies through sequence recursion, not mappings only."""

    payload = {"l1": {"l2": {"l3": {"l4": [{"apiKey": "leaked"}]}}}}

    with pytest.raises(ValueError):
        _message(metadata=payload)

    with pytest.raises(ValueError):
        _response(reasoning_summary=payload)


def test_public_metadata_rejects_excessive_items() -> None:
    allowed = {f"field-{index}": index for index in range(MAX_METADATA_ITEMS)}
    _message(metadata=allowed)

    rejected = {f"field-{index}": index for index in range(MAX_METADATA_ITEMS + 1)}
    with pytest.raises(ValueError):
        _message(metadata=rejected)


def test_public_metadata_item_limit_counts_nested_items() -> None:
    nested = {"outer": [index for index in range(MAX_METADATA_ITEMS)]}

    with pytest.raises(ValueError):
        _message(metadata=nested)


def test_public_metadata_is_recursively_frozen() -> None:
    message = _message(
        metadata={"nested": {"inner": [1, 2, {"deep": "value"}]}, "flag": True}
    )

    assert isinstance(message.metadata, MappingProxyType)
    nested = message.metadata["nested"]
    assert isinstance(nested, MappingProxyType)
    assert nested["inner"] == (1, 2, MappingProxyType({"deep": "value"}))
    assert isinstance(nested["inner"], tuple)


def test_public_metadata_is_copied_not_aliased() -> None:
    source = {"field": "value"}
    message = _message(metadata=source)

    source["field"] = "mutated"

    assert dict(message.metadata) == {"field": "value"}


def test_public_metadata_rejects_a_non_mapping_value() -> None:
    with pytest.raises(TypeError):
        _message(metadata=["not", "a", "mapping"])

    with pytest.raises(TypeError):
        _response(reasoning_summary=["not", "a", "mapping"])


# ── Assistant response ───────────────────────────────────────────────────────


def test_response_requires_a_conversation_message() -> None:
    with pytest.raises(TypeError):
        AssistantResponse(message="not-a-message")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        AssistantResponse(message=_message().to_dict())  # type: ignore[arg-type]


def test_response_defaults_to_empty_public_surfaces() -> None:
    response = _response()

    assert response.sources == ()
    assert dict(response.reasoning_summary) == {}
    assert response.pending_questions == ()
    assert response.proposed_actions == ()
    assert response.approval_requests == ()
    assert response.workflow_updates == ()
    assert dict(response.domain_state) == {}
    assert response.capability_state == ()
    assert response.memory_updates == ()
    assert response.warnings == ()


@pytest.mark.parametrize(
    "field",
    [
        "sources",
        "pending_questions",
        "proposed_actions",
        "approval_requests",
        "workflow_updates",
        "memory_updates",
        "warnings",
    ],
)
def test_response_freezes_text_tuples(field: str) -> None:
    response = _response(**{field: ["first", "second"]})

    assert getattr(response, field) == ("first", "second")


@pytest.mark.parametrize(
    "field",
    [
        "sources",
        "pending_questions",
        "proposed_actions",
        "approval_requests",
        "workflow_updates",
        "memory_updates",
        "warnings",
    ],
)
def test_response_rejects_blank_text_items(field: str) -> None:
    with pytest.raises(ValueError):
        _response(**{field: ["   "]})

    with pytest.raises(TypeError):
        _response(**{field: "first"})

    with pytest.raises(TypeError):
        _response(**{field: [17]})


@pytest.mark.parametrize(
    "field",
    [
        "sources",
        "pending_questions",
        "proposed_actions",
        "approval_requests",
        "workflow_updates",
        "memory_updates",
        "warnings",
    ],
)
def test_response_bounds_the_text_collections(field: str) -> None:
    """Every response text surface is bounded by the frozen collection limit."""

    allowed = tuple(f"item-{index}" for index in range(MAX_COLLECTION_ITEMS))

    assert getattr(_response(**{field: allowed}), field) == allowed

    with pytest.raises(ValueError) as excinfo:
        _response(**{field: allowed + ("overflow",)})

    assert excinfo.type is ValueError
    assert str(excinfo.value) == (
        f"{field} must not contain more than {MAX_COLLECTION_ITEMS} items"
    )


def test_response_warnings_preserve_declared_order_and_repeats() -> None:
    response = _response(warnings=["degraded", "degraded"])

    assert response.warnings == ("degraded", "degraded")


def test_response_bounds_repeated_text_items_by_count_not_uniqueness() -> None:
    """The text bound counts items; repeats stay legal up to the limit."""

    allowed = ("degraded",) * MAX_COLLECTION_ITEMS

    assert _response(warnings=allowed).warnings == allowed

    with pytest.raises(ValueError) as excinfo:
        _response(warnings=allowed + ("degraded",))

    assert str(excinfo.value) == (
        f"warnings must not contain more than {MAX_COLLECTION_ITEMS} items"
    )


def test_response_domain_state_uses_the_safe_grammar() -> None:
    response = _response(domain_state={"domain": "finance", "count": 2})

    assert dict(response.domain_state) == {"domain": "finance", "count": 2}

    with pytest.raises(ValueError):
        _response(domain_state={"api_key": "value"})

    with pytest.raises(TypeError):
        _response(domain_state={"blob": b"secret"})


def test_response_capability_state_requires_capability_states() -> None:
    with pytest.raises(TypeError):
        _response(capability_state=({"capability": "attachments"},))

    with pytest.raises(TypeError):
        _response(capability_state="response_streaming")

    assert _response(capability_state=[_capability()]).capability_state == (
        _capability(),
    )


def test_response_bounds_the_capability_state_collection() -> None:
    """``capability_state`` is bounded by the frozen collection limit."""

    allowed = tuple(
        _capability(capability=f"capability_{index}")
        for index in range(MAX_COLLECTION_ITEMS)
    )

    assert _response(capability_state=allowed).capability_state == allowed

    with pytest.raises(ValueError):
        _response(capability_state=allowed + (_capability(capability="overflow"),))


def test_response_from_dict_bounds_the_capability_state_collection() -> None:
    payload = _response(capability_state=(_capability(),)).to_dict()
    payload["capability_state"] = [
        _capability(capability=f"capability_{index}").to_dict()
        for index in range(MAX_COLLECTION_ITEMS + 1)
    ]

    with pytest.raises(ValueError):
        AssistantResponse.from_dict(payload)


def test_response_from_dict_bounds_the_text_collections() -> None:
    payload = _response(sources=("source://1",)).to_dict()
    payload["sources"] = [
        f"source://{index}" for index in range(MAX_COLLECTION_ITEMS + 1)
    ]

    with pytest.raises(ValueError) as excinfo:
        AssistantResponse.from_dict(payload)

    assert excinfo.type is ValueError
    assert str(excinfo.value) == (
        f"sources must not contain more than {MAX_COLLECTION_ITEMS} items"
    )


def test_projection_bounds_the_projected_text_surfaces() -> None:
    """An authorized view beyond the frozen bound fails closed at projection."""

    over_budget = tuple(
        f"knowledge:item:{index}" for index in range(MAX_COLLECTION_ITEMS + 1)
    )

    with pytest.raises(ValueError) as excinfo:
        _project(_domain_view(source_refs=over_budget))

    assert excinfo.type is ValueError
    assert str(excinfo.value) == (
        f"sources must not contain more than {MAX_COLLECTION_ITEMS} items"
    )

    # The review's reproduction: 5,000 authorized refs never project through.
    reproduction = tuple(f"knowledge:item:{index}" for index in range(5_000))

    with pytest.raises(ValueError) as excinfo:
        _project(_domain_view(source_refs=reproduction))

    assert str(excinfo.value) == (
        f"sources must not contain more than {MAX_COLLECTION_ITEMS} items"
    )


def test_projection_accepts_a_view_at_the_text_bound() -> None:
    at_budget = tuple(
        f"knowledge:item:{index}" for index in range(MAX_COLLECTION_ITEMS)
    )

    assert _project(_domain_view(source_refs=at_budget)).sources == at_budget


def test_response_from_dict_rejects_a_foreign_serialized_capability_state() -> None:
    """A malformed persisted capability entry is rejected, never dropped."""

    payload = _response(capability_state=(_capability(),)).to_dict()
    payload["capability_state"] = [payload["capability_state"][0], True]

    with pytest.raises(TypeError):
        AssistantResponse.from_dict(payload)

    payload["capability_state"] = [payload["capability_state"][0], "response_streaming"]

    with pytest.raises(TypeError):
        AssistantResponse.from_dict(payload)


def test_response_round_trips_with_every_field_populated() -> None:
    response = _response(
        sources=("source://document-1",),
        reasoning_summary={"outcome": "routed"},
        pending_questions=("continue?",),
        proposed_actions=("action://restart",),
        approval_requests=("approval://request-1",),
        workflow_updates=("workflow://run-1",),
        domain_state={"domain": "finance"},
        capability_state=(_capability(),),
        memory_updates=("memory://proposal-1",),
        warnings=("streaming is degraded",),
    )

    restored = AssistantResponse.from_dict(response.to_dict())

    assert restored == response
    assert restored.message == response.message
    assert restored.capability_state[0].status is ConversationCapabilityStatus.DEGRADED


# ── Requested vs effective capability state ─────────────────────────────────


def test_capability_state_defaults_to_no_reason() -> None:
    state = ConversationCapabilityState(
        capability="attachments",
        requested=False,
        effective="reference_only",
        status=ConversationCapabilityStatus.AVAILABLE,
    )

    assert state.reason is None


def test_capability_state_rejects_a_raw_status_string() -> None:
    with pytest.raises(TypeError):
        _capability(status="degraded")


def test_capability_state_requires_a_bool_requested_flag() -> None:
    with pytest.raises(TypeError):
        _capability(requested=1)

    with pytest.raises(TypeError):
        _capability(requested="yes")


def test_capability_state_requires_a_capability_identifier() -> None:
    with pytest.raises(ValueError):
        _capability(capability="   ")

    with pytest.raises(TypeError):
        _capability(capability=17)

    assert _capability(capability=" attachments ").capability == "attachments"


def test_unavailable_capability_rejects_an_effective_mode() -> None:
    with pytest.raises(ValueError):
        _capability(
            capability="document_upload",
            effective="document_store",
            status=ConversationCapabilityStatus.UNAVAILABLE,
        )

    state = _capability(
        capability="document_upload",
        requested=False,
        effective=None,
        status=ConversationCapabilityStatus.UNAVAILABLE,
    )
    assert state.effective is None


def test_available_capability_requires_an_effective_mode() -> None:
    with pytest.raises(ValueError):
        _capability(
            capability="attachments",
            effective=None,
            status=ConversationCapabilityStatus.AVAILABLE,
        )

    state = _capability(
        capability="attachments",
        effective="reference_only",
        status=ConversationCapabilityStatus.AVAILABLE,
    )
    assert state.effective == "reference_only"


def test_capability_state_rejects_a_non_string_effective_mode() -> None:
    with pytest.raises(TypeError):
        _capability(effective=17)


def test_capability_state_reason_is_optional_bounded_public_text() -> None:
    assert _capability(reason="   ").reason is None
    assert _capability(reason="degraded by baseline").reason == "degraded by baseline"

    with pytest.raises(ValueError):
        _capability(reason="r" * (MAX_STRING_LENGTH + 1))

    with pytest.raises(TypeError):
        _capability(reason=17)


def test_capability_state_round_trips() -> None:
    state = _capability(reason="application baseline")

    assert ConversationCapabilityState.from_dict(state.to_dict()) == state


# ── Safe conversation errors ────────────────────────────────────────────────


def test_error_messages_are_module_owned_constants() -> None:
    assert set(CONVERSATION_ERROR_MESSAGES) == set(ConversationErrorCode)
    assert all(
        isinstance(message, str) and message.strip()
        for message in CONVERSATION_ERROR_MESSAGES.values()
    )
    assert (
        CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.INTERNAL_FAILURE]
        == GENERIC_CONVERSATION_FAILURE_MESSAGE
    )


def test_error_message_mapping_is_immutable() -> None:
    with pytest.raises(TypeError):
        CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.INVALID_REQUEST] = "changed"  # type: ignore[index]


def test_error_requires_a_real_error_code() -> None:
    with pytest.raises(TypeError):
        ConversationError(
            code="invalid_request", message="Conversation request is not valid"
        )


def test_error_requires_a_module_owned_message() -> None:
    raw_message = "ValueError: boom at /Users/chris/private.py"

    with pytest.raises(ValueError):
        _error(message=raw_message)

    with pytest.raises(ValueError):
        _error(message="")

    with pytest.raises(TypeError):
        _error(message=17)


def test_error_rejects_a_constant_message_of_another_code() -> None:
    with pytest.raises(ValueError):
        ConversationError(
            code=ConversationErrorCode.SESSION_NOT_FOUND,
            message=CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.POLICY_DENIED],
        )


def test_error_for_code_returns_the_constant_public_failure() -> None:
    for code in ConversationErrorCode:
        error = ConversationError.for_code(code)

        assert error.code is code
        assert error.message == CONVERSATION_ERROR_MESSAGES[code]


def test_error_internal_failure_is_one_generic_category() -> None:
    error = ConversationError.for_code(ConversationErrorCode.INTERNAL_FAILURE)

    assert error.message == GENERIC_CONVERSATION_FAILURE_MESSAGE


def test_error_round_trips() -> None:
    error = _error()

    assert ConversationError.from_dict(error.to_dict()) == error


def test_error_from_dict_rejects_foreign_payloads() -> None:
    with pytest.raises(ValueError):
        ConversationError.from_dict({"code": "not_a_code", "message": "nope"})

    with pytest.raises(ValueError):
        ConversationError.from_dict(
            {"code": "invalid_request", "message": "raw internal text"}
        )

    with pytest.raises(ValueError):
        ConversationError.from_dict(_error().to_dict() | {"detail": "raw"})

    with pytest.raises(TypeError):
        ConversationError.from_dict(["not", "a", "mapping"])


def test_error_to_dict_is_json_safe_and_constant() -> None:
    payload = _error().to_dict()

    _assert_public_value(payload)
    assert payload == {
        "code": "session_not_found",
        "message": CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.SESSION_NOT_FOUND],
    }
    assert json.loads(json.dumps(payload, sort_keys=True, allow_nan=False)) == payload


# ── Error-path pins ─────────────────────────────────────────────────────────


def test_from_dict_rejects_a_missing_required_field() -> None:
    """A persisted payload missing a required field fails closed with ValueError."""

    message_payload = _message().to_dict()
    del message_payload["session_id"]

    with pytest.raises(ValueError, match="missing required field"):
        ConversationMessage.from_dict(message_payload)

    attachment_payload = _attachment().to_dict()
    del attachment_payload["kind"]

    with pytest.raises(ValueError, match="missing required field"):
        ConversationAttachmentRef.from_dict(attachment_payload)

    capability_payload = _capability().to_dict()
    del capability_payload["requested"]

    with pytest.raises(ValueError, match="missing required field"):
        ConversationCapabilityState.from_dict(capability_payload)

    response_payload = _response().to_dict()
    del response_payload["message"]

    with pytest.raises(ValueError, match="missing required field"):
        AssistantResponse.from_dict(response_payload)


def test_message_timestamp_must_be_a_string() -> None:
    with pytest.raises(TypeError):
        _message(created_at=17)


def test_message_blank_timestamp_fails_before_parsing() -> None:
    for blank in ("", "   "):
        with pytest.raises(ValueError, match="must be non-empty"):
            _message(created_at=blank)


def test_message_unparseable_timestamp_uses_the_module_message() -> None:
    with pytest.raises(ValueError, match="must be an ISO-8601 timestamp"):
        _message(created_at="yesterday")


def test_from_dict_requires_typed_enum_values() -> None:
    payload = _message().to_dict()
    payload["role"] = 17

    with pytest.raises(TypeError):
        ConversationMessage.from_dict(payload)

    state_payload = _capability().to_dict()
    state_payload["status"] = 17

    with pytest.raises(TypeError):
        ConversationCapabilityState.from_dict(state_payload)


def test_from_dict_rejects_an_unknown_enum_value_with_the_module_message() -> None:
    payload = _message().to_dict()
    payload["role"] = "superuser"

    with pytest.raises(ValueError, match="is not a supported ConversationRole"):
        ConversationMessage.from_dict(payload)

    state_payload = _capability().to_dict()
    state_payload["status"] = "streaming"

    with pytest.raises(
        ValueError, match="is not a supported ConversationCapabilityStatus"
    ):
        ConversationCapabilityState.from_dict(state_payload)


def test_response_from_dict_requires_a_serialized_message() -> None:
    payload = _response().to_dict()
    payload["message"] = 17

    with pytest.raises(TypeError, match="must be a ConversationMessage"):
        AssistantResponse.from_dict(payload)


def test_response_from_dict_accepts_an_already_typed_message() -> None:
    payload = _response().to_dict()
    payload["message"] = _message()

    assert AssistantResponse.from_dict(payload).message == _message()


def test_error_from_dict_requires_a_typed_code_value() -> None:
    message = CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.INVALID_REQUEST]

    with pytest.raises(TypeError):
        ConversationError.from_dict({"code": 17, "message": message})


def test_error_from_dict_rejects_an_unknown_code_with_the_module_message() -> None:
    message = CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.INVALID_REQUEST]

    with pytest.raises(
        ValueError, match="code is not a supported ConversationErrorCode"
    ):
        ConversationError.from_dict({"code": "not_a_code", "message": message})


def test_error_from_dict_rejects_a_missing_required_field() -> None:
    full = _error().to_dict()

    for field in ("code", "message"):
        payload = {key: value for key, value in full.items() if key != field}

        with pytest.raises(ValueError, match="missing a required field"):
            ConversationError.from_dict(payload)


# ── Deterministic public serialization ──────────────────────────────────────


@pytest.mark.parametrize("contract", _contract_instances())
def test_to_dict_is_plain_immutable_and_json_safe(contract: object) -> None:
    payload = contract.to_dict()  # type: ignore[attr-defined]

    _assert_public_value(payload)
    assert json.loads(json.dumps(payload, sort_keys=True, allow_nan=False)) == payload


@pytest.mark.parametrize("contract", _contract_instances())
def test_to_dict_is_deterministic(contract: object) -> None:
    assert contract.to_dict() == contract.to_dict()  # type: ignore[attr-defined]


@pytest.mark.parametrize("contract", _contract_instances())
def test_from_dict_round_trips_every_contract(contract: object) -> None:
    restored = type(contract).from_dict(contract.to_dict())  # type: ignore[attr-defined]

    assert restored == contract


def test_message_round_trip_preserves_metadata_and_attachments() -> None:
    message = _message(
        metadata={"nested": {"inner": [1, 2]}},
        references=("source://a",),
        attachments=(_attachment(name="notes.txt"),),
    )

    restored = ConversationMessage.from_dict(message.to_dict())

    assert restored == message
    assert dict(restored.metadata["nested"]) == {"inner": (1, 2)}
    assert restored.attachments[0].name == "notes.txt"


def test_to_dict_returns_a_fresh_detached_mapping() -> None:
    message = _message(metadata={"nested": {"field": "value"}})

    payload = message.to_dict()["metadata"]
    payload["nested"]["field"] = "mutated"
    payload["added"] = True

    assert dict(message.metadata["nested"]) == {"field": "value"}
    assert "added" not in message.metadata


@pytest.mark.parametrize("contract_type", CONTRACT_TYPES)
def test_from_dict_rejects_foreign_payloads(contract_type: type) -> None:
    with pytest.raises(TypeError):
        contract_type.from_dict(["not", "a", "mapping"])

    with pytest.raises(ValueError):
        contract_type.from_dict({"unsupported_field": "value"})


# ── Public surface ──────────────────────────────────────────────────────────


def test_public_package_exports_every_frozen_name() -> None:
    from cmm import conversation
    from cmm.conversation import contracts, errors

    assert FROZEN_CONTRACT_NAMES <= set(conversation.__all__)
    for name in sorted(FROZEN_CONTRACT_NAMES):
        source = contracts if hasattr(contracts, name) else errors
        assert getattr(conversation, name) is getattr(source, name)


def test_public_package_does_not_export_internal_helpers() -> None:
    from cmm import conversation

    assert not [name for name in conversation.__all__ if name.startswith("_")]
    assert "freeze_public_mapping" not in conversation.__all__
    assert "is_secret_like_key" not in conversation.__all__
    assert "thaw" not in conversation.__all__
