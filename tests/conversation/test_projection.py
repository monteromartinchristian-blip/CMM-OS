"""Phase 11.5 — projection of application + authorized domain state.

Task 5 locks the pure conversational output projection: one
``ConversationResponseProjector`` maps one ``ApplicationResponse`` and, when
supplied, one already authorized ``ConversationalDomainView`` into one frozen
``AssistantResponse``.  The projector consumes an authorized view, never creates
one, never calls Domain resolution and never fabricates a missing reference.

Proven here:

- application-only projection: every structured surface stays empty
  (``sources``, ``pending_questions``, ``approval_requests``,
  ``workflow_updates``, ``memory_updates``, ``warnings``), ``reasoning_summary``
  and ``domain_state`` are empty and ``proposed_actions`` stays empty because no
  public-safe application field carries actions;
- the deterministic public response-text ladder over application status/error
  semantics (no model call, no domain pretence);
- genuine ``ConversationalDomainView`` projection: the full mapping table,
  including ``reasoning_summary["result_refs"]`` /
  ``reasoning_summary["contradiction_refs"]`` and the ``domain_state`` shape;
- the pinned assistant ``ConversationMessage`` construction, including the
  opaque ``bot_id`` echo and the empty ``references``/``attachments``;
- capability state passes through unchanged;
- fail-closed type safety: a raw ``Exception``, a fabricated raw Domain
  dictionary and a malformed capability state all raise ``TypeError``;
- references absent from the canonical view are never recreated from
  ``application_response.data``/``metadata``;
- no ``chain_of_thought``/``scratchpad``/prompt-like key anywhere in the
  serialized response, and the structured surfaces expose exactly the frozen
  keys;
- the projection is deterministic and never mutates its inputs.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 7.2, 7.3, 10, 22 and 23).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest

from cmm.application.contracts import (
    ApplicationError,
    ApplicationErrorCode,
    ApplicationResponse,
    ApplicationStatus,
)
from cmm.conversation import (
    AssistantResponse,
    ConversationCapabilityState,
    ConversationCapabilityStatus,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.projection import ConversationResponseProjector
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    DomainInterfaceStatus,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTION_MODULE = REPO_ROOT / "cmm" / "conversation" / "projection.py"

#: The exact frozen field set of one serialized ``AssistantResponse``.
ASSISTANT_RESPONSE_FIELDS = frozenset(
    {
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
    }
)

#: The exact ``reasoning_summary`` keys of a projected response.
REASONING_SUMMARY_KEYS = frozenset({"result_refs", "contradiction_refs"})

#: The exact ``domain_state`` keys of a projected response.
DOMAIN_STATE_KEYS = frozenset(
    {"primary_domain", "supporting_domains", "confidence", "status"}
)

#: Separator-free denied key fragments: hidden reasoning, prompts and internal
#: failure detail must never surface as a key anywhere in a projected response.
DENIED_KEY_FRAGMENTS = (
    "chainofthought",
    "scratchpad",
    "hiddenreasoning",
    "internalreasoning",
    "reasoningtrace",
    "prompt",
    "traceback",
    "stacktrace",
    "rawexception",
)

#: The fabricated raw Domain payload a caller might try to smuggle in instead
#: of the canonical authorization projection.
FABRICATED_RAW_DOMAIN_PAYLOAD = {
    "resolution_id": "resolution:forged",
    "primary_domain": "domain:forged",
    "domain_objects": {"internal": "state"},
    "confidence": 0.99,
    "status": "ready",
}

#: The sanctioned ``cmm`` imports of the projection module.
ALLOWED_CMM_IMPORTS = (
    "cmm.application.contracts",
    "cmm.conversation",
    "cmm.domains.interface_integration_contracts",
)

#: Canonical owners and adapters the projection module must never name.
FORBIDDEN_CMM_MODULES = (
    "cmm.agent_runtime",
    "cmm.api",
    "cmm.cognitive",
    "cmm.domains.composer",
    "cmm.domains.resolver",
    "cmm.memory",
)

#: Transport and serialization stacks the projection module must never name.
FORBIDDEN_EXTERNAL_ROOTS = (
    "aiohttp",
    "fastapi",
    "flask",
    "httpx",
    "pydantic",
    "starlette",
    "uvicorn",
)


# ── Fixture families ─────────────────────────────────────────────────────────


def _request_message(**overrides: Any) -> ConversationMessage:
    values: dict[str, Any] = {
        "id": "message-1",
        "session_id": "session-1",
        "role": ConversationRole.USER,
        "content": "What should I do next?",
        "created_at": "2026-09-17T10:00:00+00:00",
        "bot_id": "bot:1",
    }
    values.update(overrides)
    return ConversationMessage(**values)


def _application_response(**overrides: Any) -> ApplicationResponse:
    values: dict[str, Any] = {
        "request_id": "request-1",
        "api_version": "v1",
        "status": ApplicationStatus.SUCCESS,
        "data": {"echo": "ok"},
        "metadata": {"channel": "conversation"},
    }
    values.update(overrides)
    return ApplicationResponse(**values)


def _conversational_view(**overrides: Any) -> ConversationalDomainView:
    """Construct the frozen canonical contract directly with valid values.

    The integrator-driven end-to-end construction belongs to Task 10; Task 5
    consumes an already authorized view, so the test constructs the same frozen
    contract the canonical integrator emits.
    """

    values: dict[str, Any] = {
        "primary_domain": "domain:health",
        "supporting_domains": ("domain:general",),
        "workflow_refs": ("workflow:1",),
        "question_refs": ("question:1",),
        "approval_refs": ("approval:1",),
        "source_refs": ("knowledge:item:1",),
        "contradiction_refs": ("contradiction:1",),
        "result_refs": ("result:1",),
        "memory_proposal_refs": ("proposal:1",),
        "confidence": 0.72,
        "warning_refs": ("warning:1",),
        "status": DomainInterfaceStatus.READY,
    }
    values.update(overrides)
    return ConversationalDomainView(**values)


def _capability_state() -> tuple[ConversationCapabilityState, ...]:
    return (
        ConversationCapabilityState(
            capability="continuous_conversation",
            requested=True,
            effective="session",
            status=ConversationCapabilityStatus.AVAILABLE,
        ),
        ConversationCapabilityState(
            capability="request_cancellation",
            requested=False,
            effective=None,
            status=ConversationCapabilityStatus.UNAVAILABLE,
            reason="no_cancellable_owner",
        ),
    )


def _projection_kwargs(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "request_message": _request_message(),
        "assistant_message_id": "assistant-message-1",
        "created_at": "2026-09-17T10:00:01+00:00",
        "application_response": _application_response(),
        "domain_view": None,
        "capability_state": _capability_state(),
    }
    values.update(overrides)
    return values


def _project(**overrides: Any) -> AssistantResponse:
    return ConversationResponseProjector().project(**_projection_kwargs(**overrides))


def _key_fragment(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _serialized_key_fragments(value: object) -> list[str]:
    if isinstance(value, dict):
        fragments: list[str] = []
        for key, item in value.items():
            assert isinstance(key, str)
            fragments.append(_key_fragment(key))
            fragments.extend(_serialized_key_fragments(item))
        return fragments
    if isinstance(value, list | tuple):
        fragments = []
        for item in value:
            fragments.extend(_serialized_key_fragments(item))
        return fragments
    return []


# ── Family (a): application-only projection ──────────────────────────────────


def test_application_only_projection_leaves_every_structured_surface_empty() -> None:
    capability_state = _capability_state()

    response = _project(capability_state=capability_state)

    assert response.sources == ()
    assert response.pending_questions == ()
    assert response.approval_requests == ()
    assert response.workflow_updates == ()
    assert response.memory_updates == ()
    assert response.warnings == ()
    assert response.proposed_actions == ()
    assert dict(response.reasoning_summary) == {}
    assert dict(response.domain_state) == {}


def test_application_only_projection_passes_capability_state_through_unchanged() -> (
    None
):
    capability_state = _capability_state()

    response = _project(capability_state=capability_state)

    assert response.capability_state == capability_state
    assert [id(state) for state in response.capability_state] == [
        id(state) for state in capability_state
    ]


def test_application_only_projection_builds_the_pinned_assistant_message() -> None:
    request_message = _request_message()

    response = _project(
        request_message=request_message,
        assistant_message_id="assistant-message-1",
        created_at="2026-09-17T10:00:01+00:00",
    )

    message = response.message
    assert isinstance(message, ConversationMessage)
    assert message.id == "assistant-message-1"
    assert message.session_id == request_message.session_id
    assert message.role is ConversationRole.ASSISTANT
    assert message.created_at == "2026-09-17T10:00:01+00:00"
    assert message.bot_id == "bot:1"
    assert message.references == ()
    assert message.attachments == ()
    assert message.lineage == ConversationLineage()


def test_assistant_message_echoes_a_missing_bot_id_as_none() -> None:
    response = _project(request_message=_request_message(bot_id=None))

    assert response.message.bot_id is None


def test_assistant_message_carries_the_supplied_lineage() -> None:
    lineage = ConversationLineage(supersedes_message_id="message-0")

    response = _project(lineage=lineage)

    assert response.message.lineage is lineage


@pytest.mark.parametrize(
    ("status", "error", "expected"),
    [
        (ApplicationStatus.SUCCESS, None, "Application status: success."),
        (ApplicationStatus.CANCELLED, None, "Application status: cancelled."),
        (ApplicationStatus.ESCALATED, None, "Application status: escalated."),
        (
            ApplicationStatus.ROUTED,
            None,
            "The request was routed through the canonical application boundary.",
        ),
        (
            ApplicationStatus.NEEDS_CLARIFICATION,
            None,
            "Additional information is required.",
        ),
    ],
)
def test_public_response_text_follows_the_pinned_ladder(
    status: ApplicationStatus,
    error: ApplicationError | None,
    expected: str,
) -> None:
    response = _project(
        application_response=_application_response(status=status, error=error)
    )

    assert response.message.content == expected


@pytest.mark.parametrize(
    ("status", "code", "message"),
    [
        (
            ApplicationStatus.FAILED,
            ApplicationErrorCode.INTERNAL_FAILURE,
            "Application request failed closed",
        ),
        (
            ApplicationStatus.BLOCKED,
            ApplicationErrorCode.POLICY_DENIED,
            "Application request was denied by policy",
        ),
    ],
)
def test_application_error_message_is_the_public_failure_text(
    status: ApplicationStatus,
    code: ApplicationErrorCode,
    message: str,
) -> None:
    error = ApplicationError(code=code, message=message, details={"correlation": "c-1"})

    response = _project(
        application_response=_application_response(status=status, error=error)
    )

    assert response.message.content == message
    assert "c-1" not in json.dumps(response.to_dict())


def test_error_semantics_take_precedence_over_the_status_text() -> None:
    error = ApplicationError(
        code=ApplicationErrorCode.INVALID_REQUEST,
        message="Application request is not valid",
    )

    response = _project(
        application_response=_application_response(
            status=ApplicationStatus.NEEDS_CLARIFICATION, error=error
        )
    )

    assert response.message.content == "Application request is not valid"


# ── Family (b): genuine ConversationalDomainView projection ──────────────────


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("sources", ("knowledge:item:1",)),
        ("pending_questions", ("question:1",)),
        ("approval_requests", ("approval:1",)),
        ("workflow_updates", ("workflow:1",)),
        ("memory_updates", ("proposal:1",)),
        ("warnings", ("warning:1",)),
    ],
)
def test_every_view_reference_family_maps_to_its_response_field(
    field: str, expected: tuple[str, ...]
) -> None:
    response = _project(domain_view=_conversational_view())

    assert getattr(response, field) == expected
    assert isinstance(getattr(response, field), tuple)


def test_view_result_and_contradiction_refs_map_into_reasoning_summary() -> None:
    response = _project(domain_view=_conversational_view())

    assert dict(response.reasoning_summary) == {
        "result_refs": ("result:1",),
        "contradiction_refs": ("contradiction:1",),
    }
    assert response.to_dict()["reasoning_summary"] == {
        "result_refs": ["result:1"],
        "contradiction_refs": ["contradiction:1"],
    }


def test_view_domain_state_carries_primary_supporting_confidence_and_status() -> None:
    response = _project(domain_view=_conversational_view())

    assert dict(response.domain_state) == {
        "primary_domain": "domain:health",
        "supporting_domains": ("domain:general",),
        "confidence": 0.72,
        "status": "ready",
    }
    assert response.to_dict()["domain_state"] == {
        "primary_domain": "domain:health",
        "supporting_domains": ["domain:general"],
        "confidence": 0.72,
        "status": "ready",
    }


def test_reasoning_summary_keeps_both_keys_when_the_view_refs_are_empty() -> None:
    view = _conversational_view(result_refs=(), contradiction_refs=())

    response = _project(domain_view=view)

    assert set(response.reasoning_summary) == REASONING_SUMMARY_KEYS
    assert dict(response.reasoning_summary) == {
        "result_refs": (),
        "contradiction_refs": (),
    }


def test_domain_state_keeps_a_missing_confidence_and_projects_the_status_value() -> (
    None
):
    view = _conversational_view(
        confidence=None,
        supporting_domains=(),
        status=DomainInterfaceStatus.DEGRADED,
    )

    response = _project(domain_view=view)

    assert dict(response.domain_state) == {
        "primary_domain": "domain:health",
        "supporting_domains": (),
        "confidence": None,
        "status": "degraded",
    }


def test_proposed_actions_stay_empty_even_with_a_view() -> None:
    """No public-safe application field carries actions, so none are invented."""

    response = _project(domain_view=_conversational_view())

    assert response.proposed_actions == ()


# ── Security invariants ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "slot",
    [
        "request_message",
        "application_response",
        "domain_view",
        "capability_state",
        "lineage",
    ],
)
def test_raw_exception_objects_cannot_enter_output(slot: str) -> None:
    kwargs = _projection_kwargs()
    kwargs[slot] = RuntimeError("hidden internal failure")

    with pytest.raises(TypeError):
        ConversationResponseProjector().project(**kwargs)


def test_fabricated_raw_domain_mapping_is_rejected() -> None:
    with pytest.raises(
        TypeError, match="domain_view must be a ConversationalDomainView or None"
    ):
        _project(domain_view=FABRICATED_RAW_DOMAIN_PAYLOAD)


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        ("continuous_conversation",),
        ({"capability": "continuous_conversation"},),
        (RuntimeError("hidden internal failure"),),
    ],
    ids=["none", "list", "raw-strings", "raw-dicts", "raw-exceptions"],
)
def test_malformed_capability_state_fails_closed(value: object) -> None:
    with pytest.raises(TypeError):
        _project(capability_state=value)


def test_lineage_must_be_a_conversation_lineage() -> None:
    with pytest.raises(TypeError, match="lineage must be a ConversationLineage"):
        _project(lineage="message-0")


def test_references_absent_from_the_view_are_never_recreated_from_metadata() -> None:
    forged: dict[str, Any] = {
        name: [f"forged:{name}"]
        for name in (
            "sources",
            "source_refs",
            "pending_questions",
            "question_refs",
            "approval_requests",
            "approval_refs",
            "workflow_updates",
            "workflow_refs",
            "memory_updates",
            "memory_proposal_refs",
            "warnings",
            "warning_refs",
            "result_refs",
            "contradiction_refs",
            "proposed_actions",
        )
    }
    forged["domain_state"] = {"primary_domain": "forged:domain", "status": "ready"}
    application_response = _application_response(data=forged, metadata=forged)

    without_view = _project(application_response=application_response)

    assert without_view.sources == ()
    assert without_view.pending_questions == ()
    assert without_view.approval_requests == ()
    assert without_view.workflow_updates == ()
    assert without_view.memory_updates == ()
    assert without_view.warnings == ()
    assert without_view.proposed_actions == ()
    assert dict(without_view.reasoning_summary) == {}
    assert dict(without_view.domain_state) == {}
    assert "forged" not in json.dumps(without_view.to_dict())

    with_view = _project(
        application_response=application_response,
        domain_view=_conversational_view(
            source_refs=("knowledge:item:1",),
            question_refs=(),
            approval_refs=(),
            workflow_refs=(),
            memory_proposal_refs=(),
            warning_refs=(),
            result_refs=(),
            contradiction_refs=(),
        ),
    )

    assert with_view.sources == ("knowledge:item:1",)
    assert with_view.pending_questions == ()
    assert with_view.approval_requests == ()
    assert with_view.workflow_updates == ()
    assert with_view.memory_updates == ()
    assert with_view.warnings == ()
    assert "forged" not in json.dumps(with_view.to_dict())


@pytest.mark.parametrize("with_view", [False, True], ids=["no-view", "with-view"])
def test_no_hidden_reasoning_or_prompt_like_key_appears_anywhere(
    with_view: bool,
) -> None:
    response = _project(
        domain_view=_conversational_view() if with_view else None,
        application_response=_application_response(
            data={"echo": "ok", "reasoning": "public status only"}
        ),
    )

    fragments = _serialized_key_fragments(response.to_dict())
    offenders = [
        fragment
        for fragment in fragments
        if any(denied in fragment for denied in DENIED_KEY_FRAGMENTS)
    ]

    assert not offenders, f"hidden-reasoning-shaped keys surfaced: {offenders}"
    assert set(response.reasoning_summary) == (
        REASONING_SUMMARY_KEYS if with_view else frozenset()
    )
    assert set(response.domain_state) == (
        DOMAIN_STATE_KEYS if with_view else frozenset()
    )


@pytest.mark.parametrize("with_view", [False, True], ids=["no-view", "with-view"])
def test_serialized_response_exposes_only_the_frozen_fields(with_view: bool) -> None:
    response = _project(
        domain_view=_conversational_view() if with_view else None,
    )

    assert set(response.to_dict()) == ASSISTANT_RESPONSE_FIELDS


def test_no_hidden_reasoning_key_survives_the_response_text_or_names() -> None:
    response = _project(
        domain_view=_conversational_view(),
        application_response=_application_response(error=None),
    )

    document = json.dumps(response.to_dict())
    for denied in ("chain_of_thought", "chainOfThought", "scratchpad", "raw prompt"):
        assert denied not in document


# ── Purity: determinism and immutability ─────────────────────────────────────


@pytest.mark.parametrize("with_view", [False, True], ids=["no-view", "with-view"])
def test_projection_is_deterministic(with_view: bool) -> None:
    projector = ConversationResponseProjector()
    kwargs = _projection_kwargs(
        domain_view=_conversational_view() if with_view else None
    )

    first = projector.project(**kwargs)
    second = projector.project(**kwargs)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first is not second


def test_projector_is_stateless() -> None:
    projector = ConversationResponseProjector()

    projector.project(**_projection_kwargs())

    assert vars(projector) == {}


def test_projector_never_mutates_its_inputs() -> None:
    request_message = _request_message()
    application_response = _application_response(
        data={"sources": ["forged:source"]}, metadata={"note": "keep"}
    )
    domain_view = _conversational_view()
    capability_state = _capability_state()
    lineage = ConversationLineage(supersedes_message_id="message-0")
    snapshots = (
        request_message.to_dict(),
        application_response.to_dict(),
        domain_view.to_dict(),
        capability_state,
        lineage.to_dict(),
    )

    response = ConversationResponseProjector().project(
        request_message=request_message,
        assistant_message_id="assistant-message-1",
        created_at="2026-09-17T10:00:01+00:00",
        application_response=application_response,
        domain_view=domain_view,
        capability_state=capability_state,
        lineage=lineage,
    )

    assert request_message.to_dict() == snapshots[0]
    assert application_response.to_dict() == snapshots[1]
    assert domain_view.to_dict() == snapshots[2]
    assert capability_state is snapshots[3]
    assert capability_state == snapshots[3]
    assert lineage.to_dict() == snapshots[4]
    assert response.sources == domain_view.source_refs


# ── Module boundary ──────────────────────────────────────────────────────────


def test_projection_module_imports_stay_inside_the_sanctioned_boundary() -> None:
    tree = ast.parse(PROJECTION_MODULE.read_text())

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    for module in sorted(imported):
        for forbidden in FORBIDDEN_CMM_MODULES:
            assert module != forbidden and not module.startswith(f"{forbidden}."), (
                f"projection.py must not import {module}"
            )
        root = module.split(".")[0]
        if root == "cmm":
            assert any(
                module == allowed or module.startswith(f"{allowed}.")
                for allowed in ALLOWED_CMM_IMPORTS
            ), f"unsanctioned cmm import in projection.py: {module}"
        else:
            assert root not in FORBIDDEN_EXTERNAL_ROOTS, (
                f"projection.py must not import {module}"
            )


def test_projection_module_never_constructs_a_conversational_domain_view() -> None:
    tree = ast.parse(PROJECTION_MODULE.read_text())

    constructions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ConversationalDomainView"
    ]

    assert not constructions, (
        "the projector consumes an authorized view and never creates one"
    )
