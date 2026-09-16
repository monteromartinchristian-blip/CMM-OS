"""Phase 11.3 — idempotency seam and canonical command fingerprint tests.

The application-owned idempotency boundary is deliberately narrow: one record
value, one repository protocol and one bounded in-memory implementation.  A
repeated equivalent command replays its stored safe response; a reused key with
a materially different command fails closed; nothing durable, distributed or
global is introduced.

The fingerprint must be canonical, so it is derived from the public command
semantics only — never from ``request_id``, ``idempotency_key``, ``hash()`` or
process state.  These tests pin the exact canonical document, the included
field set and a frozen digest, so a change to fingerprint semantics can never
land silently.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCommand,
    ApplicationMessage,
    ApplicationOperation,
    ApplicationResponse,
    ApplicationStatus,
)
from cmm.application.errors import IdempotencyConflictError
from cmm.application.idempotency import (
    IdempotencyRecord,
    InMemoryIdempotencyRepository,
    fingerprint_command,
)

SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

#: The default bound of the one in-memory idempotency repository.
DEFAULT_CAPACITY = 1024

#: Frozen digest of the canonical document for :func:`_command`, computed from
#: the documented semantics independently of this implementation.  A change
#: here means an uploaded fingerprint no longer matches a stored one.
GOLDEN_FINGERPRINT = "01642c97ab27ce4aac2418cad11cb1752572892b873816b0725be2fbd685c208"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _command(**overrides: object) -> ApplicationCommand:
    fields: dict[str, object] = {
        "request_id": "req-1",
        "api_version": APPLICATION_API_VERSION,
        "operation": ApplicationOperation.MESSAGE_SUBMIT,
        "actor_id": "actor-1",
        "session_id": "session-1",
        "payload": {"message_id": "message-1", "content": "hello"},
        "metadata": {"channel": "api"},
        "expected_session_revision": 1,
        "idempotency_key": "idem-1",
    }
    fields.update(overrides)
    return ApplicationCommand(**fields)  # type: ignore[arg-type]


def _canonical_document(command: ApplicationCommand) -> str:
    """Return the documented canonical document, built without this module."""

    public_fields = command.to_dict()
    return json.dumps(
        {
            "api_version": public_fields["api_version"],
            "operation": public_fields["operation"],
            "actor_id": public_fields["actor_id"],
            "session_id": public_fields["session_id"],
            "expected_session_revision": public_fields["expected_session_revision"],
            "payload": public_fields["payload"],
            "metadata": public_fields["metadata"],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _response(**overrides: object) -> ApplicationResponse:
    fields: dict[str, object] = {
        "request_id": "req-1",
        "api_version": APPLICATION_API_VERSION,
        "status": ApplicationStatus.ROUTED,
        "data": {"decision_id": "orchestration-decision:req-1"},
    }
    fields.update(overrides)
    return ApplicationResponse(**fields)  # type: ignore[arg-type]


def _record(**overrides: object) -> IdempotencyRecord:
    command = overrides.pop("command", None)
    if command is None:
        command = _command()
    fields: dict[str, object] = {
        "key": "idem-1",
        "fingerprint": fingerprint_command(command),  # type: ignore[arg-type]
        "response": _response(),
    }
    fields.update(overrides)
    return IdempotencyRecord(**fields)  # type: ignore[arg-type]


def _repository(capacity: int = DEFAULT_CAPACITY) -> InMemoryIdempotencyRepository:
    return InMemoryIdempotencyRepository(capacity=capacity)


#: Commands that differ from the baseline only in a fingerprinted public field.
DIFFERING_COMMANDS: tuple[tuple[str, Callable[[], ApplicationCommand]], ...] = (
    (
        "operation",
        lambda: _command(operation=ApplicationOperation.SESSION_CREATE),
    ),
    ("actor_id", lambda: _command(actor_id="actor-2")),
    ("session_id", lambda: _command(session_id="session-2")),
    ("expected_session_revision", lambda: _command(expected_session_revision=2)),
    (
        "expected_session_revision absence",
        lambda: _command(expected_session_revision=None),
    ),
    (
        "payload",
        lambda: _command(payload={"message_id": "message-1", "content": "goodbye"}),
    ),
    (
        "payload shape",
        lambda: _command(
            payload={"message_id": "message-1", "content": "hello", "extra": 1}
        ),
    ),
    ("metadata", lambda: _command(metadata={"channel": "cli"})),
    ("metadata absence", lambda: _command(metadata={})),
)


# ── Canonical fingerprint ────────────────────────────────────────────────────


def test_fingerprint_is_a_sha256_hex_digest() -> None:
    fingerprint = fingerprint_command(_command())

    assert isinstance(fingerprint, str)
    assert SHA256_HEX.match(fingerprint)


def test_fingerprint_is_deterministic_for_an_equivalent_command() -> None:
    assert fingerprint_command(_command()) == fingerprint_command(_command())


def test_fingerprint_matches_the_canonical_sha256_document() -> None:
    """The digest is SHA-256 over the canonical JSON document, UTF-8 encoded."""

    command = _command()
    expected = hashlib.sha256(_canonical_document(command).encode("utf-8")).hexdigest()

    assert fingerprint_command(command) == expected


def test_fingerprint_is_frozen_against_semantic_drift() -> None:
    """A frozen digest, so fingerprint changes are always explicit."""

    assert fingerprint_command(_command()) == GOLDEN_FINGERPRINT


def test_canonical_document_covers_exactly_the_fingerprinted_fields() -> None:
    document = json.loads(_canonical_document(_command()))

    assert set(document) == {
        "api_version",
        "operation",
        "actor_id",
        "session_id",
        "expected_session_revision",
        "payload",
        "metadata",
    }


def test_fingerprint_ignores_request_id() -> None:
    assert fingerprint_command(_command(request_id="req-1")) == fingerprint_command(
        _command(request_id="req-2")
    )


def test_fingerprint_ignores_idempotency_key() -> None:
    assert fingerprint_command(_command(idempotency_key="idem-1")) == (
        fingerprint_command(_command(idempotency_key="idem-2"))
    )
    assert fingerprint_command(_command(idempotency_key="idem-1")) == (
        fingerprint_command(_command(idempotency_key=None))
    )


def test_fingerprint_ignores_payload_key_order() -> None:
    assert fingerprint_command(
        _command(payload={"a": 1, "b": "two", "c": {"x": 1, "y": 2}})
    ) == fingerprint_command(
        _command(payload={"c": {"y": 2, "x": 1}, "b": "two", "a": 1})
    )


@pytest.mark.parametrize(("label", "factory"), DIFFERING_COMMANDS)
def test_fingerprint_changes_with_fingerprinted_fields(
    label: str, factory: Callable[[], ApplicationCommand]
) -> None:
    assert fingerprint_command(factory()) != fingerprint_command(_command()), label


def test_fingerprint_changes_with_sequence_order() -> None:
    assert fingerprint_command(
        _command(payload={"message_id": "m-1", "content": "hello", "parts": [1, 2]})
    ) != fingerprint_command(
        _command(payload={"message_id": "m-1", "content": "hello", "parts": [2, 1]})
    )


def test_fingerprint_changes_with_nested_metadata() -> None:
    nested = _command(metadata={"context": {"domain": "finance"}})
    other = _command(metadata={"context": {"domain": "operations"}})

    assert fingerprint_command(nested) != fingerprint_command(other)


def test_fingerprint_requires_an_application_command() -> None:
    with pytest.raises(TypeError):
        fingerprint_command({"request_id": "req-1"})  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        fingerprint_command(  # type: ignore[arg-type]
            ApplicationMessage(
                message_id="message-1",
                session_id="session-1",
                actor_id="actor-1",
                content="hello",
            )
        )


# ── Idempotency record ───────────────────────────────────────────────────────


def test_record_keeps_key_fingerprint_and_response() -> None:
    response = _response()
    record = IdempotencyRecord(
        key="idem-1", fingerprint=fingerprint_command(_command()), response=response
    )

    assert record.key == "idem-1"
    assert record.fingerprint == fingerprint_command(_command())
    assert record.response is response


def test_record_normalizes_the_key() -> None:
    record = _record(key="  idem-1  ")

    assert record.key == "idem-1"


def test_record_rejects_an_empty_key() -> None:
    with pytest.raises(ValueError):
        _record(key="   ")


def test_record_rejects_a_non_string_key() -> None:
    with pytest.raises(TypeError):
        _record(key=1)


def test_record_rejects_an_empty_fingerprint() -> None:
    with pytest.raises(ValueError):
        _record(fingerprint="   ")


def test_record_rejects_a_non_string_fingerprint() -> None:
    with pytest.raises(TypeError):
        _record(fingerprint=1)


def test_record_rejects_a_non_response_payload() -> None:
    with pytest.raises(TypeError):
        _record(response={"status": "routed"})


def test_record_is_frozen() -> None:
    record = _record()

    with pytest.raises(FrozenInstanceError):
        record.key = "other"  # type: ignore[misc]


def test_records_compare_by_value() -> None:
    assert _record() == _record()

    other = _record(command=_command(session_id="session-2"))

    assert other != _record()
    assert other.response == _record().response


# ── In-memory bounded repository ─────────────────────────────────────────────


def test_get_returns_none_for_an_unknown_key() -> None:
    assert _repository().get("idem-unknown") is None


def test_put_then_get_returns_the_record() -> None:
    repository = _repository()
    record = _record()

    repository.put(record)

    assert repository.get("idem-1") is record


def test_equivalent_replay_is_an_idempotent_no_op() -> None:
    repository = _repository()
    first = _record()
    equivalent = _record()

    repository.put(first)
    repository.put(equivalent)
    repository.put(first)

    assert repository.get("idem-1") is first


def test_repeated_key_with_a_different_fingerprint_conflicts() -> None:
    repository = _repository()
    repository.put(_record())

    with pytest.raises(IdempotencyConflictError) as raised:
        repository.put(_record(command=_command(session_id="session-2")))

    assert dict(raised.value.details) == {"reason_code": "IDEMPOTENCY_KEY_REUSED"}


def test_repeated_key_with_a_different_response_conflicts() -> None:
    repository = _repository()
    repository.put(_record())

    with pytest.raises(IdempotencyConflictError):
        repository.put(_record(response=_response(request_id="req-2")))


def test_a_conflict_never_overwrites_the_stored_record() -> None:
    repository = _repository()
    stored = _record()
    repository.put(stored)

    with pytest.raises(IdempotencyConflictError):
        repository.put(_record(response=_response(request_id="req-2")))

    assert repository.get("idem-1") is stored


def test_put_rejects_a_foreign_record_type() -> None:
    with pytest.raises(TypeError):
        _repository().put({"key": "idem-1"})  # type: ignore[arg-type]


def test_get_rejects_a_foreign_key_type() -> None:
    with pytest.raises(TypeError):
        _repository().get(1)  # type: ignore[arg-type]


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5, "8", None])
def test_capacity_must_be_a_positive_int(capacity: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        InMemoryIdempotencyRepository(capacity=capacity)  # type: ignore[arg-type]


def test_capacity_of_one_is_accepted() -> None:
    repository = InMemoryIdempotencyRepository(capacity=1)

    repository.put(_record(key="idem-1"))
    repository.put(_record(key="idem-2"))

    assert repository.get("idem-1") is None
    assert repository.get("idem-2") is not None


def test_full_repository_evicts_the_oldest_inserted_record() -> None:
    repository = _repository(capacity=2)
    oldest = _record(key="idem-1")
    middle = _record(key="idem-2")
    newest = _record(key="idem-3")

    repository.put(oldest)
    repository.put(middle)
    repository.put(newest)

    assert repository.get("idem-1") is None
    assert repository.get("idem-2") is middle
    assert repository.get("idem-3") is newest


def test_a_replayed_key_keeps_its_original_insertion_position() -> None:
    """Eviction order stays deterministic; a replay never refreshes a key."""

    repository = _repository(capacity=2)
    repository.put(_record(key="idem-1"))
    repository.put(_record(key="idem-2"))

    repository.put(_record(key="idem-1"))
    repository.put(_record(key="idem-3"))

    assert repository.get("idem-1") is None
    assert repository.get("idem-2") is not None
    assert repository.get("idem-3") is not None


def test_repository_is_bounded_by_the_default_capacity() -> None:
    repository = InMemoryIdempotencyRepository()

    repository.put(_record(key="idem-0"))
    for index in range(1, DEFAULT_CAPACITY + 1):
        repository.put(_record(key=f"idem-{index}"))

    assert repository.get("idem-0") is None
    assert repository.get(f"idem-{DEFAULT_CAPACITY}") is not None


def test_repository_replays_the_stored_safe_response() -> None:
    repository = _repository()
    response = _response()
    repository.put(_record(response=response))

    replayed = repository.get("idem-1")

    assert replayed is not None
    assert replayed.response.to_dict() == response.to_dict()
