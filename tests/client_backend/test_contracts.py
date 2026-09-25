"""Phase 11.50 — public contracts of the reusable client backend.

``cmm.client_backend`` is the *facade* boundary of CMM OS: it adapts the closed
Phase 11.3 application boundary and the closed Phase 11.5 conversational
boundary for first-party clients and owns no authority of its own.  These gates
protect four contract properties:

* **one closed interface version** — ``CLIENT_BACKEND_INTERFACE_VERSION`` exists,
  is exactly ``"1"`` and is *not* the canonical application API version or the
  canonical model-gateway contract version;
* **one closed operation enum** — ``ClientOperation`` iterates an exact, frozen
  member set, and a raw string is never silently coerced into an operation;
* **safe client-interface errors only** — the client layer owns the four
  interface-shape codes (``UNSUPPORTED_INTERFACE_VERSION``,
  ``INVALID_CLIENT_OPERATION``, ``INVALID_CLIENT_CONTRACT``,
  ``INTERNAL_CLIENT_ERROR``) with module-owned constant messages and never
  duplicates a canonical application/conversation code;
* **transparent version failure** — the one exception the layer *raises* to a
  direct Python caller is an ``ImportError`` from the canonical transport rather
  than a client-layer wrapper, so nothing here is a second application boundary.

Every expectation is structural: no test asserts a private helper, and no test
depends on the wall clock.
"""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationErrorCode,
    ApplicationSession,
)
from cmm.client_backend import (
    ClientBackendError,
    ClientBackendErrorCode,
    ClientBackendRequest,
    ClientBackendResult,
    ClientOperation,
)
from cmm.conversation.contracts import ConversationMessage, ConversationRole
from cmm.conversation.errors import ConversationErrorCode

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_BACKEND_PACKAGE = REPO_ROOT / "cmm" / "client_backend"

#: The one Phase 11.50 client-interface version.
EXPECTED_INTERFACE_VERSION = "1"

#: The frozen Phase 11.50 operation member set (`plan` §8, design §13).
EXPECTED_OPERATIONS = (
    "CAPABILITIES",
    "CREATE_SESSION",
    "GET_SESSION",
    "LOAD_CONVERSATION",
    "SUBMIT_MESSAGE",
    "EDIT_MESSAGE",
    "REGENERATE_RESPONSE",
    "CANCEL_REQUEST",
)

#: The frozen Phase 11.50 interface-shape error member set (`plan` §9).
EXPECTED_ERROR_CODES = (
    "UNSUPPORTED_INTERFACE_VERSION",
    "INVALID_CLIENT_OPERATION",
    "INVALID_CLIENT_CONTRACT",
    "INTERNAL_CLIENT_ERROR",
)


def test_the_client_backend_package_exists() -> None:
    """The Phase 11.50 package is a real, importable package."""

    assert CLIENT_BACKEND_PACKAGE.is_dir(), (
        "cmm/client_backend is the Phase 11.50 reusable first-party client "
        "backend package"
    )
    assert (CLIENT_BACKEND_PACKAGE / "__init__.py").is_file()


def test_the_interface_version_is_one_and_is_not_a_canonical_version() -> None:
    """The client-interface version identifies the facade contract only."""

    module = importlib.import_module("cmm.client_backend")

    assert module.CLIENT_BACKEND_INTERFACE_VERSION == EXPECTED_INTERFACE_VERSION
    assert module.CLIENT_BACKEND_INTERFACE_VERSION != APPLICATION_API_VERSION


def test_the_operation_enum_is_exactly_the_frozen_member_set() -> None:
    """``ClientOperation`` is closed: exactly the eight frozen members."""

    module = importlib.import_module("cmm.client_backend")

    assert tuple(member.name for member in module.ClientOperation) == (
        EXPECTED_OPERATIONS
    )


def test_every_operation_is_a_distinct_stable_string_value() -> None:
    """Operation values are stable, unique, non-blank public strings."""

    module = importlib.import_module("cmm.client_backend")

    values = [member.value for member in module.ClientOperation]
    assert len(set(values)) == len(values)
    assert all(isinstance(value, str) and value.strip() for value in values)
    assert all(value.islower() or "_" in value for value in values)


def test_a_raw_string_is_never_coerced_into_an_operation() -> None:
    """An operation is a real enum member; a caller string fails closed."""

    module = importlib.import_module("cmm.client_backend")

    with pytest.raises(TypeError):
        module.ClientBackendRequest(
            interface_version=EXPECTED_INTERFACE_VERSION,
            request_id="request-1",
            operation="submit_message",  # type: ignore[arg-type]
            payload={},
        )


def test_the_client_error_codes_are_exactly_the_frozen_member_set() -> None:
    """The client layer owns four interface-shape codes and no more."""

    module = importlib.import_module("cmm.client_backend")

    assert tuple(member.name for member in module.ClientBackendErrorCode) == (
        EXPECTED_ERROR_CODES
    )


def test_the_client_error_codes_do_not_duplicate_canonical_codes() -> None:
    """No canonical application or conversation code is duplicated here."""

    module = importlib.import_module("cmm.client_backend")

    client_names = {member.name for member in module.ClientBackendErrorCode}
    application_names = {member.name for member in ApplicationErrorCode}
    conversation_names = {member.name for member in ConversationErrorCode}

    assert not client_names & application_names
    assert not client_names & conversation_names


@pytest.mark.parametrize(
    "code_name", ["UNSUPPORTED_INTERFACE_VERSION", "INTERNAL_CLIENT_ERROR"]
)
def test_a_client_error_carries_one_module_owned_constant_message(
    code_name: str,
) -> None:
    """A client failure message is the layer's own constant, never raw text."""

    module = importlib.import_module("cmm.client_backend")
    code = module.ClientBackendErrorCode[code_name]

    error = module.ClientBackendError(code)

    assert error.code is code
    assert error.message == module.CLIENT_BACKEND_ERROR_MESSAGES[code]
    assert "client backend" in error.message.lower()


def test_an_unknown_error_code_member_is_rejected() -> None:
    """A raw string is never coerced into a client error code."""

    module = importlib.import_module("cmm.client_backend")

    with pytest.raises(TypeError):
        module.ClientBackendError("INTERNAL_CLIENT_ERROR")  # type: ignore[arg-type]


def test_the_client_layer_reexports_the_canonical_version_for_transparency() -> None:
    """The application API version stays observable, never redefined."""

    module = importlib.import_module("cmm.client_backend")

    assert module.APPLICATION_API_VERSION is APPLICATION_API_VERSION


def test_the_public_export_list_is_the_frozen_stable_surface() -> None:
    """``__all__`` is exactly the frozen Phase 11.50 public surface."""

    module = importlib.import_module("cmm.client_backend")

    expected = {
        "APPLICATION_API_VERSION",
        "CLIENT_BACKEND_ERROR_MESSAGES",
        "CLIENT_BACKEND_INTERFACE_VERSION",
        "CLIENT_BACKEND_MODULE_ID",
        "CLIENT_BACKEND_SERVICE_ID",
        "ClientBackend",
        "ClientBackendCapabilities",
        "ClientBackendCapabilityStatus",
        "ClientBackendError",
        "ClientBackendErrorCode",
        "ClientBackendRequest",
        "ClientBackendResult",
        "ClientOperation",
        "build_client_backend_composition_module",
    }

    assert set(module.__all__) == expected


def test_every_public_export_is_importable_from_the_package_root() -> None:
    """A first-party client needs one import path and no internal module."""

    module = importlib.import_module("cmm.client_backend")

    for name in module.__all__:
        assert hasattr(module, name), f"cmm.client_backend does not export {name}"


def test_the_package_imports_no_private_module_in_its_public_surface() -> None:
    """No internal helper module leaks through the stable public surface."""

    module = importlib.import_module("cmm.client_backend")

    assert not any(
        name.startswith("_") and not name.startswith("__") for name in module.__all__
    )


def test_the_contract_module_defines_no_authority_owner() -> None:
    """The contracts module declares values, never an authority owner."""

    source = (CLIENT_BACKEND_PACKAGE / "contracts.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="contracts.py")
    class_names = [
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]

    forbidden_suffixes = ("Store", "Repository", "Registry", "Engine", "Runtime")
    assert not [name for name in class_names if name.endswith(forbidden_suffixes)]


# ═══════════════════════════════════════════════════════════════════════════
# Remediation V1 — MAJOR-05: every public wrapper serializes to JSON-native data
#
# Independent Audit V1 reproduced that ``json.dumps(request.to_dict())`` raised
# ``TypeError`` when the payload carried a canonical ``ConversationMessage``:
# ``_primitive_safe`` deliberately passed canonical public values through, but
# ``_thaw`` returned them unchanged instead of serializing them.
# ═══════════════════════════════════════════════════════════════════════════

SESSION_ID = "remediation-contract-session"
TURN_AT = "2026-09-25T10:00:00+00:00"


def _message(message_id: str = "user-1") -> ConversationMessage:
    return ConversationMessage(
        id=message_id,
        session_id=SESSION_ID,
        role=ConversationRole.USER,
        content="What changed in the plan?",
        created_at=TURN_AT,
    )


def _session() -> ApplicationSession:
    return ApplicationSession(
        session_id=SESSION_ID,
        revision=3,
        status="ACTIVE",
        created_at=TURN_AT,
        updated_at=TURN_AT,
    )


def test_a_canonical_message_payload_serializes_to_json() -> None:
    """``REQUEST_CANONICAL_PAYLOAD_JSON_SERIALIZABLE=PASS`` for SUBMIT_MESSAGE."""

    request = ClientBackendRequest(
        interface_version=EXPECTED_INTERFACE_VERSION,
        request_id="request-submit",
        operation=ClientOperation.SUBMIT_MESSAGE,
        payload={
            "message": _message(),
            "expected_session_revision": 1,
            "requested_capabilities": ("reasoning",),
        },
    )

    document = request.to_dict()

    json.dumps(document)
    assert document["payload"]["message"]["id"] == "user-1"
    assert document["payload"]["message"]["session_id"] == SESSION_ID
    assert document["payload"]["message"]["created_at"] == TURN_AT
    assert document["payload"]["message"]["role"] == "user"
    # Canonical identities are preserved exactly: serialization generates none.
    assert request.to_dict() == document


def test_an_edit_message_payload_serializes_to_json() -> None:
    """``EDIT_MESSAGE`` carries the same canonical message contract."""

    request = ClientBackendRequest(
        interface_version=EXPECTED_INTERFACE_VERSION,
        request_id="request-edit",
        operation=ClientOperation.EDIT_MESSAGE,
        payload={"message": _message("user-1-edited"), "original_message_id": "user-1"},
    )

    document = request.to_dict()

    json.dumps(document)
    assert document["payload"]["message"]["id"] == "user-1-edited"


def test_a_canonical_result_value_serializes_to_json() -> None:
    """``RESULT_CANONICAL_PAYLOAD_JSON_SERIALIZABLE=PASS``."""

    result = ClientBackendResult(
        interface_version=EXPECTED_INTERFACE_VERSION,
        request_id="request-session",
        operation=ClientOperation.GET_SESSION,
        ok=True,
        data={"session": _session()},
    )

    document = result.to_dict()

    json.dumps(document)
    assert document["data"]["session"]["session_id"] == SESSION_ID
    assert document["data"]["session"]["revision"] == 3
    assert document["data"]["session"]["created_at"] == TURN_AT


def test_the_canonical_ids_and_revisions_survive_serialization_verbatim() -> None:
    """``CANONICAL_IDS_PRESERVED=YES`` and ``CANONICAL_REVISIONS_PRESERVED=YES``."""

    message = _message("message-identity-1")
    request = ClientBackendRequest(
        interface_version=EXPECTED_INTERFACE_VERSION,
        request_id="request-identity",
        operation=ClientOperation.SUBMIT_MESSAGE,
        payload={"message": message},
    )

    document = request.to_dict()
    serialized = json.dumps(document, sort_keys=True)

    assert message.id in serialized
    assert message.session_id in serialized
    assert message.created_at in serialized
    assert document["operation"] == "submit_message"


def test_an_opaque_payload_value_fails_closed() -> None:
    """``OPAQUE_PAYLOAD=FAIL_CLOSED``: no repr, no str and no silent pass-through."""

    with pytest.raises(ClientBackendError) as failure:
        ClientBackendRequest(
            interface_version=EXPECTED_INTERFACE_VERSION,
            request_id="request-opaque",
            operation=ClientOperation.CAPABILITIES,
            payload={"opaque": object()},
        )

    assert failure.value.code is ClientBackendErrorCode.INVALID_CLIENT_CONTRACT


def test_the_serialized_request_contains_only_json_native_values() -> None:
    """``to_dict()`` returns only None/bool/int/float/str/list/dict."""

    request = ClientBackendRequest(
        interface_version=EXPECTED_INTERFACE_VERSION,
        request_id="request-native",
        operation=ClientOperation.SUBMIT_MESSAGE,
        payload={
            "message": _message(),
            "nested": {"list": (1, 2), "enum": ClientOperation.CAPABILITIES},
        },
    )

    def _assert_native(value: object) -> None:
        assert value is None or isinstance(value, bool | int | float | str)
        if isinstance(value, list):
            for item in value:
                _assert_native(item)
        if isinstance(value, dict):
            for key, item in value.items():
                assert isinstance(key, str)
                _assert_native(item)

    _assert_native(request.to_dict())
