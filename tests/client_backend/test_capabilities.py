"""Phase 11.50 — capability truth of the reusable client backend.

The manifest is the load-bearing honesty surface of Phase 11.50.  These gates
pin four properties:

* **the frozen field inventory** — exactly the fields the implementation plan
  requires, no more and no fewer;
* **canonical evidence only** — every row comes from the Phase 11.3 application
  declarations or the Phase 11.5 conversational resolver.  No provider name, no
  model name and no vendor capability list is consulted;
* **no optimistic upgrade** — a Phase 11.21 fact is reported ``boundary_only``
  and never as end-to-end availability, the response-event stream is never
  relabelled as token streaming, attachments stay ``reference_only`` and
  document upload stays ``unavailable``;
* **closed values** — every row is a member of the closed status vocabulary, and
  the manifest serializes deterministically.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.application.capabilities import build_default_capabilities
from cmm.application.contracts import ApplicationCapability, CapabilityStatus
from cmm.client_backend import (
    ClientBackendCapabilities,
    ClientBackendCapabilityStatus,
)
from cmm.client_backend.capabilities import (
    CLIENT_BACKEND_MODEL_BOUNDARY_CAPABILITY_IDS,
    MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID,
    MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
    MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID,
    REASON_MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED,
    REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END,
    ClientBackendCapabilityEvidence,
    build_client_backend_capabilities,
)
from tests.client_backend._canonical_graph import build_client_backend_graph

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES_MODULE = REPO_ROOT / "cmm" / "client_backend" / "capabilities.py"

#: The exact field inventory the implementation plan requires (`plan` §26).
EXPECTED_STATUS_FIELDS = (
    "session_create",
    "session_get",
    "conversation_load",
    "conversation_submit",
    "conversation_edit",
    "conversation_regenerate",
    "response_event_stream",
    "request_cancellation",
    "attachments",
    "document_upload",
    "model_boundary_reasoning",
    "model_boundary_multimodal",
    "model_boundary_token_stream",
    "end_to_end_reasoning",
    "end_to_end_multimodal",
    "end_to_end_token_stream",
)


def _boundary(capability_id: str) -> ApplicationCapability:
    return ApplicationCapability(
        capability_id=capability_id,
        status=CapabilityStatus.AVAILABLE,
        version="1",
    )


# ── Field inventory ──────────────────────────────────────────────────────────


def test_the_manifest_carries_exactly_the_required_fields() -> None:
    """The frozen inventory is exact: no missing row and no invented row."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert isinstance(manifest, ClientBackendCapabilities)
    assert set(manifest._status_fields()) == set(EXPECTED_STATUS_FIELDS)
    for field_name in EXPECTED_STATUS_FIELDS:
        assert isinstance(manifest.status(field_name), ClientBackendCapabilityStatus), (
            field_name
        )


def test_the_manifest_reports_the_two_interface_versions() -> None:
    """The client version identifies the facade; the canonical one stays visible."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert manifest.interface_version == "1"
    assert manifest.application_api_version == "v1"


def test_an_unknown_capability_field_name_fails_closed() -> None:
    """An invented field name is never silently answered."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    with pytest.raises(ValueError):
        manifest.status("provider_ranking")


def test_the_status_vocabulary_is_closed_and_has_four_states() -> None:
    """Three-state truth is expressed by four closed members, not booleans."""

    assert {member.value for member in ClientBackendCapabilityStatus} == {
        "available",
        "degraded",
        "unavailable",
        "boundary_only",
    }


# ── Canonical truth ──────────────────────────────────────────────────────────


def test_the_conversational_rows_follow_the_canonical_resolver() -> None:
    """Session and conversation rows mirror canonical resolver truth exactly."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert manifest.session_create is ClientBackendCapabilityStatus.AVAILABLE
    assert manifest.session_get is ClientBackendCapabilityStatus.AVAILABLE
    assert manifest.conversation_load is ClientBackendCapabilityStatus.AVAILABLE
    assert manifest.conversation_submit is ClientBackendCapabilityStatus.AVAILABLE
    assert manifest.conversation_edit is ClientBackendCapabilityStatus.AVAILABLE
    assert manifest.conversation_regenerate is ClientBackendCapabilityStatus.AVAILABLE


def test_the_response_event_stream_is_degraded_and_reports_its_canonical_reason() -> (
    None
):
    """Streaming is the canonical degraded response-event stream."""

    from cmm.conversation.capabilities import (
        REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE,
    )

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert manifest.response_event_stream is ClientBackendCapabilityStatus.DEGRADED
    assert (
        manifest.reasons["response_event_stream"]
        == REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE
    )


def test_the_response_event_stream_is_not_relabelled_as_token_streaming() -> None:
    """The end-to-end token stream keeps its own honest degraded row."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    # The two rows are distinct fields with distinct meaning: the response-event
    # stream describes the existing public response delivery, and the end-to-end
    # token stream describes provider token streaming.  Neither is ever claimed
    # available from the other.
    assert manifest.end_to_end_token_stream is ClientBackendCapabilityStatus.DEGRADED
    assert manifest.end_to_end_token_stream.value != "available"
    assert manifest.response_event_stream.value != "available"
    assert (
        manifest.reasons["end_to_end_token_stream"]
        == (manifest.reasons["response_event_stream"])
    )
    assert "response_event_stream" in manifest._status_fields()
    assert "end_to_end_token_stream" in manifest._status_fields()
    assert "token_stream" not in manifest._status_fields()


def test_request_cancellation_reports_the_canonical_unavailability() -> None:
    """Cancellation follows the canonical resolver, never the model boundary."""

    from cmm.conversation.capabilities import REASON_NO_CANCELLABLE_OWNER

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert manifest.request_cancellation is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.reasons["request_cancellation"] == REASON_NO_CANCELLABLE_OWNER


def test_attachments_are_reference_only_and_upload_is_unavailable() -> None:
    """No file store, no upload and no path resolver is invented here."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert manifest.attachments is ClientBackendCapabilityStatus.AVAILABLE
    assert manifest.document_upload is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.reasons["document_upload"] == "NO_CANONICAL_STORAGE_OWNER"


def test_the_effective_attachment_mode_is_reference_only() -> None:
    """The canonical effective mode of attachments is preserved verbatim."""

    from cmm.conversation.capabilities import ConversationCapabilityResolver

    states = ConversationCapabilityResolver().resolve()
    attachments = next(state for state in states if state.capability == "attachments")

    assert attachments.effective == "reference_only"


# ═══════════════════════════════════════════════════════════════════════════
# Remediation V1 — MAJOR-04: capability truth against the frozen design
#
# Independent Audit V1 reproduced that the manifest reported
# ``attachments=available`` while dropping the canonical ``reference_only``
# qualifier, and that ``response_event_stream`` was reported ``degraded`` purely
# because provider token streaming is unavailable.
# ═══════════════════════════════════════════════════════════════════════════

#: The frozen Phase 11.50 effective mode of the attachment references.
FROZEN_ATTACHMENT_EFFECTIVE_MODE = "reference_only"


def test_attachments_are_degraded_with_the_frozen_reference_only_mode() -> None:
    """``ATTACHMENTS_STATUS=DEGRADED`` and ``ATTACHMENTS_MODE=reference_only``.

    A client must be able to distinguish "conversational reference metadata only"
    from real attachment reachability, so the canonical ``reference_only``
    qualifier is preserved as immutable client-visible evidence.
    """

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert manifest.attachments is ClientBackendCapabilityStatus.DEGRADED
    assert manifest.attachment_effective_mode == FROZEN_ATTACHMENT_EFFECTIVE_MODE
    assert manifest.document_upload is ClientBackendCapabilityStatus.UNAVAILABLE
    assert (
        manifest.to_dict()["attachment_effective_mode"]
        == FROZEN_ATTACHMENT_EFFECTIVE_MODE
    )


def test_the_response_event_stream_is_available_independently_of_token_streaming() -> (
    None
):
    """``RESPONSE_EVENT_STREAM=AVAILABLE`` while ``TOKEN_STREAM_FACTS_SEPARATE=YES``.

    The public response-event delivery exists in its own right (the Phase 11.3
    application boundary declares ``streaming`` available); provider token
    streaming is a different, still degraded fact.
    """

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    assert manifest.response_event_stream is ClientBackendCapabilityStatus.AVAILABLE
    assert manifest.end_to_end_token_stream is ClientBackendCapabilityStatus.DEGRADED
    assert manifest.end_to_end_token_stream is not manifest.response_event_stream
    assert manifest.response_event_stream is not manifest.model_boundary_token_stream


def test_an_unknown_internal_failure_never_claims_the_response_event_stream() -> None:
    """No declaration supplied means no claim: the row stays unavailable."""

    from cmm.client_backend.capabilities import (
        ClientBackendCapabilityEvidence,
        build_client_backend_capabilities,
    )

    manifest = build_client_backend_capabilities(
        evidence=ClientBackendCapabilityEvidence(),
        conversation_resolver=None,
    )

    assert manifest.response_event_stream is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.attachment_effective_mode is None


# ── Model-boundary vs end-to-end ─────────────────────────────────────────────


def test_no_model_boundary_row_is_claimed_without_a_canonical_declaration() -> None:
    """An undeclared boundary fact is unavailable, never guessed."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    for field_name in (
        "model_boundary_reasoning",
        "model_boundary_multimodal",
        "model_boundary_token_stream",
    ):
        assert manifest.status(field_name) is ClientBackendCapabilityStatus.UNAVAILABLE
        assert manifest.reasons[field_name] == (
            REASON_MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED
        )


def test_no_end_to_end_row_is_available_at_this_baseline() -> None:
    """Phase 11.50 claims no end-to-end reasoning, multimodal or token stream."""

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    for field_name in (
        "end_to_end_reasoning",
        "end_to_end_multimodal",
        "end_to_end_token_stream",
    ):
        assert (
            manifest.status(field_name) is not ClientBackendCapabilityStatus.AVAILABLE
        ), field_name


def test_a_declared_boundary_fact_is_boundary_only_and_never_end_to_end() -> None:
    """The exact Phase 11.50 ruling: boundary availability is not E2E availability."""

    graph = build_client_backend_graph(
        model_boundary_capabilities=(
            _boundary(MODEL_BOUNDARY_REASONING_CAPABILITY_ID),
            _boundary(MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID),
            _boundary(MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID),
        )
    )
    manifest = graph.client.capabilities()

    assert (
        manifest.model_boundary_reasoning is ClientBackendCapabilityStatus.BOUNDARY_ONLY
    )
    assert (
        manifest.model_boundary_multimodal
        is ClientBackendCapabilityStatus.BOUNDARY_ONLY
    )
    assert (
        manifest.model_boundary_token_stream
        is ClientBackendCapabilityStatus.BOUNDARY_ONLY
    )

    # ... and the matching end-to-end rows stay honest.
    assert manifest.end_to_end_reasoning is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.end_to_end_multimodal is ClientBackendCapabilityStatus.UNAVAILABLE
    assert (
        manifest.end_to_end_reasoning.value
        != ClientBackendCapabilityStatus.AVAILABLE.value
    )
    assert (
        manifest.reasons["end_to_end_reasoning"]
        == REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END
    )
    assert (
        manifest.reasons["end_to_end_multimodal"]
        == REASON_MODEL_BOUNDARY_ONLY_NOT_END_TO_END
    )


def test_an_unavailable_boundary_declaration_is_not_upgraded() -> None:
    """A declaration that is not AVAILABLE proves nothing at the boundary."""

    graph = build_client_backend_graph(
        model_boundary_capabilities=(
            ApplicationCapability(
                capability_id=MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
                status=CapabilityStatus.UNAVAILABLE,
                version="1",
                reason_code="PROVIDER_LACKS_REASONING",
            ),
        )
    )
    manifest = graph.client.capabilities()

    assert (
        manifest.model_boundary_reasoning is ClientBackendCapabilityStatus.UNAVAILABLE
    )
    assert manifest.end_to_end_reasoning is ClientBackendCapabilityStatus.UNAVAILABLE


def test_a_deferred_boundary_declaration_is_not_upgraded() -> None:
    """A DEFERRED declaration is not boundary availability."""

    graph = build_client_backend_graph(
        model_boundary_capabilities=(
            ApplicationCapability(
                capability_id=MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID,
                status=CapabilityStatus.DEFERRED,
                version="1",
            ),
        )
    )
    manifest = graph.client.capabilities()

    assert (
        manifest.model_boundary_multimodal is ClientBackendCapabilityStatus.UNAVAILABLE
    )


def test_the_frozen_model_boundary_capability_ids_are_exactly_three() -> None:
    """The injected boundary vocabulary is closed."""

    assert CLIENT_BACKEND_MODEL_BOUNDARY_CAPABILITY_IDS == (
        MODEL_BOUNDARY_REASONING_CAPABILITY_ID,
        MODEL_BOUNDARY_MULTIMODAL_CAPABILITY_ID,
        MODEL_BOUNDARY_TOKEN_STREAM_CAPABILITY_ID,
    )


def test_a_foreign_model_boundary_capability_id_is_rejected() -> None:
    """Only a frozen Phase 11.50 boundary ID may be injected as boundary truth."""

    with pytest.raises(ValueError):
        ClientBackendCapabilityEvidence(
            model_boundary_capabilities=(
                ApplicationCapability(
                    capability_id="provider-supports-everything",
                    status=CapabilityStatus.AVAILABLE,
                    version="1",
                ),
            )
        )


def test_no_conversational_owner_reports_unavailable_not_optimistic() -> None:
    """Without a composed conversational owner, no row is claimed."""

    manifest = build_client_backend_capabilities(
        evidence=ClientBackendCapabilityEvidence(
            application_capabilities=build_default_capabilities(),
        ),
        conversation_resolver=None,
    )

    assert manifest.session_create is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.conversation_submit is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.conversation_regenerate is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.attachments is ClientBackendCapabilityStatus.UNAVAILABLE
    assert manifest.request_cancellation is ClientBackendCapabilityStatus.UNAVAILABLE
    # The application-level response-event stream is still the canonical one.
    assert manifest.response_event_stream is ClientBackendCapabilityStatus.AVAILABLE


# ── Determinism and safety ───────────────────────────────────────────────────


def test_the_manifest_serializes_deterministically() -> None:
    """Two builds of the same graph produce the same public document."""

    first = build_client_backend_graph().client.capabilities().to_dict()
    second = build_client_backend_graph().client.capabilities().to_dict()

    assert first == second
    assert set(first) == {
        "interface_version",
        "application_api_version",
        *EXPECTED_STATUS_FIELDS,
        "reasons",
    }
    assert first["reasons"] == dict(sorted(first["reasons"].items()))


def test_the_manifest_is_immutable() -> None:
    """The projection is frozen and its reason mapping is a proxy."""

    from dataclasses import FrozenInstanceError

    graph = build_client_backend_graph()
    manifest = graph.client.capabilities()

    with pytest.raises(FrozenInstanceError):
        manifest.session_create = ClientBackendCapabilityStatus.UNAVAILABLE  # type: ignore[misc]
    with pytest.raises(TypeError):
        manifest.reasons["request_cancellation"] = "AVAILABLE"  # type: ignore[index]


def test_the_manifest_carries_no_hidden_reasoning_or_secret_surface() -> None:
    """No manifest key or string names hidden reasoning or a credential."""

    graph = build_client_backend_graph()
    serialized = str(graph.client.capabilities().to_dict()).lower()

    for forbidden in (
        "chain_of_thought",
        "chainofthought",
        "hidden_reasoning",
        "hiddenreasoning",
        "scratchpad",
        "api_key",
        "apikey",
        "credential",
        "password",
        "private_key",
    ):
        assert forbidden not in serialized


# ── Capability evidence is not an authority ──────────────────────────────────


def test_building_capabilities_does_not_touch_the_canonical_gateway() -> None:
    """Reading capability truth executes nothing and enters no pipeline."""

    graph = build_client_backend_graph()

    graph.client.capabilities()
    graph.client.capabilities()

    assert graph.canonical_gateway_calls() == 0


def test_the_capabilities_module_imports_neither_provider_nor_model_names() -> None:
    """Capability truth is never derived from provider/model/vendor inspection."""

    tree = ast.parse(
        CAPABILITIES_MODULE.read_text(encoding="utf-8"), filename="capabilities.py"
    )
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for module in imported:
        assert not module.startswith("cmm.agent_runtime")
        assert module not in {
            "kernel.llm.model_gateway",
            "kernel.llm.provider_registry",
            "kernel.llm.model_catalog",
            "cmm.orchestration.orchestrator",
        }


def test_the_capabilities_module_defines_no_authority_owner() -> None:
    """The projection module declares values, never an owner."""

    tree = ast.parse(
        CAPABILITIES_MODULE.read_text(encoding="utf-8"), filename="capabilities.py"
    )
    class_names = [
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]

    forbidden_suffixes = (
        "Store",
        "Repository",
        "Registry",
        "Engine",
        "Runtime",
        "Resolver",
        "Router",
        "Manager",
    )
    assert not [name for name in class_names if name.endswith(forbidden_suffixes)]
