"""Phase 11.5 — requested versus effective conversational capability state.

These tests pin the Task 3 seam of the committed Phase 11.5 plan: the
conversational boundary reports the *effective* state of its sixteen fixed
capabilities, and requesting a capability never creates execution authority.

Proven here:

- the resolver returns all sixteen fixed capability IDs in the fixed plan order;
- the frozen baseline truth table: streaming is truthfully degraded to
  ``response_event_stream`` (no provider token-streaming runtime exists),
  document upload is unavailable (no canonical storage owner) and attachments
  are available only as references;
- cancellation stays ``UNAVAILABLE`` at the real ``build_default_capabilities``
  baseline and becomes available only when an injected canonical application
  declaration reports ``request-cancellation`` as available;
- requesting a capability marks ``requested=True`` and changes nothing else;
- unknown, blank and non-string requested IDs fail closed as ``INVALID_REQUEST``
  boundary errors instead of silently becoming available;
- injected declarations are validated at construction: a non-declaration entry
  raises ``TypeError`` and a duplicate capability ID raises ``ValueError``
  (mirroring ``cmm.application.capabilities``), so duplicate-declaration
  precedence can never resolve ambiguously;
- a cancellation declaration that supplies no reason code still reports the
  canonical ``NO_CANCELLABLE_OWNER`` reason (``UNAVAILABLE`` never carries
  ``reason=None``);
- the frozen baseline truth table is frozen at runtime as well: rewriting it
  raises ``TypeError``;
- the ``resolve`` boundary split: a ``None`` iterable raises the natural
  ``TypeError`` (call-site type defect) while a bad ID inside the iterable
  raises the conversational ``INVALID_REQUEST`` error;
- the resolver copies its inputs, never mutates them and never fabricates
  authority.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 16-20 record the effective semantics; section 25 authorizes the
dependency direction ``cmm.conversation -> cmm.application``).
"""

from __future__ import annotations

import pytest

from cmm.application.capabilities import build_default_capabilities
from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationCapability,
    CapabilityStatus,
)
from cmm.conversation import (
    ConversationBoundaryError,
    ConversationCapabilityState,
    ConversationCapabilityStatus,
    ConversationErrorCode,
)
from cmm.conversation.capabilities import (
    _BASELINE_STATES,
    ConversationCapabilityResolver,
)

#: The fixed Phase 11.5 capability IDs, in the fixed plan order.
FIXED_CAPABILITY_IDS = (
    "continuous_conversation",
    "message_editing",
    "controlled_regeneration",
    "attachments",
    "response_streaming",
    "request_cancellation",
    "document_upload",
    "bot_association",
    "domain_projection",
    "approval_response",
    "workflow_pause",
    "workflow_resume",
    "workflow_cancel",
    "workflow_retry",
    "workflow_replan",
    "action_execution",
)

#: The frozen Phase 11.5 baseline truth table (cancellation included: the real
#: baseline declares ``request-cancellation`` unavailable with the canonical
#: ``NO_CANCELLABLE_OWNER`` reason code).
BASELINE_TRUTH_TABLE = (
    (
        "continuous_conversation",
        ConversationCapabilityStatus.AVAILABLE,
        "session_backed_multi_turn",
        None,
    ),
    (
        "message_editing",
        ConversationCapabilityStatus.AVAILABLE,
        "append_only_lineage",
        None,
    ),
    (
        "controlled_regeneration",
        ConversationCapabilityStatus.AVAILABLE,
        "canonical_reexecution",
        None,
    ),
    (
        "attachments",
        ConversationCapabilityStatus.AVAILABLE,
        "reference_only",
        None,
    ),
    (
        "response_streaming",
        ConversationCapabilityStatus.DEGRADED,
        "response_event_stream",
        "PROVIDER_TOKEN_STREAMING_UNAVAILABLE",
    ),
    (
        "request_cancellation",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANCELLABLE_OWNER",
    ),
    (
        "document_upload",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_STORAGE_OWNER",
    ),
    (
        "bot_association",
        ConversationCapabilityStatus.AVAILABLE,
        "opaque_non_authoritative",
        None,
    ),
    (
        "domain_projection",
        ConversationCapabilityStatus.AVAILABLE,
        "authorized_projection_when_supplied_by_canonical_integrator",
        None,
    ),
    (
        "approval_response",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_APPROVAL_COMMAND",
    ),
    (
        "workflow_pause",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_WORKFLOW_CONTROL",
    ),
    (
        "workflow_resume",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_WORKFLOW_CONTROL",
    ),
    (
        "workflow_cancel",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_WORKFLOW_CONTROL",
    ),
    (
        "workflow_retry",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_WORKFLOW_CONTROL",
    ),
    (
        "workflow_replan",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_WORKFLOW_CONTROL",
    ),
    (
        "action_execution",
        ConversationCapabilityStatus.UNAVAILABLE,
        None,
        "NO_CANONICAL_ACTION_EXECUTOR",
    ),
)

#: Remediation MAJOR-04 — the control capabilities that have no canonical
#: application command at this baseline, with their frozen public reason code.
CONTROL_CAPABILITY_REASONS = {
    "approval_response": "NO_CANONICAL_APPROVAL_COMMAND",
    "workflow_pause": "NO_CANONICAL_WORKFLOW_CONTROL",
    "workflow_resume": "NO_CANONICAL_WORKFLOW_CONTROL",
    "workflow_cancel": "NO_CANONICAL_WORKFLOW_CONTROL",
    "workflow_retry": "NO_CANONICAL_WORKFLOW_CONTROL",
    "workflow_replan": "NO_CANONICAL_WORKFLOW_CONTROL",
    "action_execution": "NO_CANONICAL_ACTION_EXECUTOR",
}


def _baseline_resolver() -> ConversationCapabilityResolver:
    """The resolver wired exactly like the canonical application baseline."""

    return ConversationCapabilityResolver(build_default_capabilities())


def _by_id(
    states: tuple[ConversationCapabilityState, ...],
) -> dict[str, ConversationCapabilityState]:
    return {state.capability: state for state in states}


def _available_cancellation() -> ApplicationCapability:
    """The canonical ``request-cancellation`` declaration in its available form."""

    return ApplicationCapability(
        capability_id="request-cancellation",
        status=CapabilityStatus.AVAILABLE,
        version=APPLICATION_API_VERSION,
    )


def _unavailable_cancellation_without_a_reason_code() -> ApplicationCapability:
    """The canonical ``request-cancellation`` declaration with no reason code."""

    return ApplicationCapability(
        capability_id="request-cancellation",
        status=CapabilityStatus.UNAVAILABLE,
        version=APPLICATION_API_VERSION,
    )


# ── Shape and fixed order ────────────────────────────────────────────────────


def test_resolve_returns_all_nine_fixed_capabilities_in_the_fixed_order() -> None:
    states = _baseline_resolver().resolve()

    assert isinstance(states, tuple)
    assert all(isinstance(state, ConversationCapabilityState) for state in states)
    assert tuple(state.capability for state in states) == FIXED_CAPABILITY_IDS


@pytest.mark.parametrize(
    ("capability", "status", "effective", "reason"),
    BASELINE_TRUTH_TABLE,
    ids=[row[0] for row in BASELINE_TRUTH_TABLE],
)
def test_the_frozen_baseline_truth_table_is_exactly_the_effective_state(
    capability: str,
    status: ConversationCapabilityStatus,
    effective: str | None,
    reason: str | None,
) -> None:
    entry = _by_id(_baseline_resolver().resolve())[capability]

    assert entry.requested is False
    assert entry.status is status
    assert entry.effective == effective
    assert entry.reason == reason


# ── Streaming truth (plan step 1, section 17) ────────────────────────────────


def test_streaming_is_truthfully_degraded_to_response_event_stream() -> None:
    state = _baseline_resolver().resolve(("response_streaming",))
    stream = next(x for x in state if x.capability == "response_streaming")

    assert stream.requested is True
    assert stream.effective == "response_event_stream"
    assert stream.status is ConversationCapabilityStatus.DEGRADED
    assert stream.reason == "PROVIDER_TOKEN_STREAMING_UNAVAILABLE"


# ── Cancellation truth (section 18) ──────────────────────────────────────────


def test_cancellation_stays_unavailable_at_the_application_baseline() -> None:
    declaration = next(
        item
        for item in build_default_capabilities()
        if item.capability_id == "request-cancellation"
    )

    assert declaration.status is CapabilityStatus.UNAVAILABLE

    entry = _by_id(_baseline_resolver().resolve())["request_cancellation"]

    assert entry.status is ConversationCapabilityStatus.UNAVAILABLE
    assert entry.effective is None
    assert entry.reason == declaration.reason_code
    assert entry.reason == "NO_CANCELLABLE_OWNER"


def test_cancellation_is_unavailable_without_any_application_capabilities() -> None:
    entry = _by_id(ConversationCapabilityResolver().resolve())["request_cancellation"]

    assert entry.status is ConversationCapabilityStatus.UNAVAILABLE
    assert entry.effective is None
    assert entry.reason == "NO_CANCELLABLE_OWNER"


def test_requesting_cancellation_does_not_create_authority() -> None:
    entry = _by_id(_baseline_resolver().resolve(("request_cancellation",)))[
        "request_cancellation"
    ]

    assert entry.requested is True
    assert entry.status is ConversationCapabilityStatus.UNAVAILABLE
    assert entry.effective is None


def test_injected_available_cancellation_unlocks_canonical_cancellable_requests() -> (
    None
):
    injected = (
        *(
            item
            for item in build_default_capabilities()
            if item.capability_id != "request-cancellation"
        ),
        _available_cancellation(),
    )
    resolver = ConversationCapabilityResolver(injected)

    entry = _by_id(resolver.resolve(("request_cancellation",)))["request_cancellation"]

    assert entry.requested is True
    assert entry.status is ConversationCapabilityStatus.AVAILABLE
    assert entry.effective == "canonical_cancellable_requests"
    assert entry.reason is None

    # The injection unlocks cancellation only; every other row is unchanged.
    other = _by_id(resolver.resolve())["document_upload"]
    assert other.status is ConversationCapabilityStatus.UNAVAILABLE
    assert other.reason == "NO_CANONICAL_STORAGE_OWNER"


def test_injected_non_available_cancellation_keeps_the_canonical_reason_code() -> None:
    injected = (
        ApplicationCapability(
            capability_id="request-cancellation",
            status=CapabilityStatus.DEFERRED,
            version=APPLICATION_API_VERSION,
            reason_code="OWNER_NOT_IMPLEMENTED",
        ),
    )

    entry = _by_id(ConversationCapabilityResolver(injected).resolve())[
        "request_cancellation"
    ]

    assert entry.status is ConversationCapabilityStatus.UNAVAILABLE
    assert entry.effective is None
    assert entry.reason == "OWNER_NOT_IMPLEMENTED"


def test_injected_unavailable_cancellation_without_a_reason_code_uses_the_canonical_reason() -> (
    None
):
    """``UNAVAILABLE`` never resolves without a reason code.

    An ``UNAVAILABLE`` declaration that supplies no ``reason_code`` must still
    report the canonical ``NO_CANCELLABLE_OWNER``: the fallback is the reason
    code whenever the declaration does not carry one (Task 3 fix round 1 pins
    this half of the guard so it can never silently resolve as ``reason=None``).
    """

    injected = (_unavailable_cancellation_without_a_reason_code(),)

    entry = _by_id(
        ConversationCapabilityResolver(injected).resolve(("request_cancellation",))
    )["request_cancellation"]

    assert entry.requested is True
    assert entry.status is ConversationCapabilityStatus.UNAVAILABLE
    assert entry.effective is None
    assert entry.reason == "NO_CANCELLABLE_OWNER"


# ── Duplicate declarations fail closed (Task 3 fix round 1) ──────────────────


#: The ambiguous duplicate pair in both injection orders: last-match precedence
#: would resolve the (UNAVAILABLE, AVAILABLE) row as unlocked cancellation.
DUPLICATE_CANCELLATION_PAIRS = (
    pytest.param(
        (
            _unavailable_cancellation_without_a_reason_code(),
            _available_cancellation(),
        ),
        id="unavailable-then-available",
    ),
    pytest.param(
        (
            _available_cancellation(),
            _unavailable_cancellation_without_a_reason_code(),
        ),
        id="available-then-unavailable",
    ),
)


@pytest.mark.parametrize("injected", DUPLICATE_CANCELLATION_PAIRS)
def test_duplicate_injected_capability_ids_fail_closed_at_construction(
    injected: tuple[ApplicationCapability, ...],
) -> None:
    """Duplicates are rejected, so cancellation precedence is never ambiguous.

    ``cmm.application.capabilities.CapabilityApplicationService`` rejects a
    duplicate capability ID, and the conversational resolver mirrors it: an
    ``(UNAVAILABLE, AVAILABLE)`` pair can never be constructed, so no
    declaration order can silently unlock cancellation.
    """

    with pytest.raises(ValueError, match="duplicate capability ID"):
        ConversationCapabilityResolver(injected)


def test_any_duplicate_injected_capability_id_is_rejected_not_only_cancellation() -> (
    None
):
    """The duplicate rule is general, not a cancellation special case."""

    declaration = ApplicationCapability(
        capability_id="messages",
        status=CapabilityStatus.AVAILABLE,
        version=APPLICATION_API_VERSION,
    )

    with pytest.raises(ValueError, match="duplicate capability ID"):
        ConversationCapabilityResolver((declaration, declaration))


# ── Document upload and attachments (section 19) ─────────────────────────────


def test_document_upload_is_unavailable_without_a_canonical_storage_owner() -> None:
    entry = _by_id(_baseline_resolver().resolve())["document_upload"]

    assert entry.status is ConversationCapabilityStatus.UNAVAILABLE
    assert entry.effective is None
    assert entry.reason == "NO_CANONICAL_STORAGE_OWNER"


def test_attachments_are_available_only_as_reference_only() -> None:
    entry = _by_id(_baseline_resolver().resolve(("attachments",)))["attachments"]

    assert entry.requested is True
    assert entry.status is ConversationCapabilityStatus.AVAILABLE
    assert entry.effective == "reference_only"
    assert entry.reason is None


# ── Bot association (section 20) ─────────────────────────────────────────────


def test_bot_association_is_available_and_explicitly_non_authoritative() -> None:
    entry = _by_id(_baseline_resolver().resolve(("bot_association",)))[
        "bot_association"
    ]

    assert entry.status is ConversationCapabilityStatus.AVAILABLE
    assert entry.effective == "opaque_non_authoritative"
    assert entry.reason is None


# ── Requested flags (section 16) ─────────────────────────────────────────────


def test_unrequested_capabilities_are_still_present_with_requested_false() -> None:
    states = _baseline_resolver().resolve()

    assert len(states) == len(FIXED_CAPABILITY_IDS)
    assert all(state.requested is False for state in states)
    assert tuple(state.capability for state in states) == FIXED_CAPABILITY_IDS


def test_requested_flags_reflect_membership_and_every_row_appears_exactly_once() -> (
    None
):
    states = _baseline_resolver().resolve(
        ("attachments", "attachments", "bot_association")
    )

    # Every fixed capability row appears exactly once, in the fixed plan order.
    assert len(states) == len(FIXED_CAPABILITY_IDS)
    assert tuple(state.capability for state in states) == FIXED_CAPABILITY_IDS

    flags = {state.capability: state.requested for state in states}
    expected = {
        capability: capability in {"attachments", "bot_association"}
        for capability in FIXED_CAPABILITY_IDS
    }
    assert flags == expected


def test_the_truth_table_is_identical_whether_requested_or_not() -> None:
    plain = _by_id(_baseline_resolver().resolve())
    requested = _by_id(
        _baseline_resolver().resolve(("response_streaming", "request_cancellation"))
    )

    for capability in FIXED_CAPABILITY_IDS:
        assert requested[capability].status is plain[capability].status
        assert requested[capability].effective == plain[capability].effective
        assert requested[capability].reason == plain[capability].reason


# ── Fail closed on invalid input ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "capability",
    ["teleportation", "streaming", "provider_token_streaming"],
    ids=["unknown", "spec-example-name", "provider-name"],
)
def test_unknown_requested_capabilities_fail_closed_as_invalid_input(
    capability: str,
) -> None:
    with pytest.raises(ConversationBoundaryError) as excinfo:
        _baseline_resolver().resolve((capability,))

    assert excinfo.value.code is ConversationErrorCode.INVALID_REQUEST


@pytest.mark.parametrize("capability", ["", "   "], ids=["empty", "whitespace"])
def test_blank_requested_capabilities_fail_closed_as_invalid_input(
    capability: str,
) -> None:
    with pytest.raises(ConversationBoundaryError) as excinfo:
        _baseline_resolver().resolve((capability,))

    assert excinfo.value.code is ConversationErrorCode.INVALID_REQUEST


@pytest.mark.parametrize(
    "capability",
    [1, None, b"attachments", object()],
    ids=["int", "none", "bytes", "object"],
)
def test_non_string_requested_capabilities_fail_closed_as_invalid_input(
    capability: object,
) -> None:
    with pytest.raises(ConversationBoundaryError) as excinfo:
        _baseline_resolver().resolve((capability,))  # type: ignore[arg-type]

    assert excinfo.value.code is ConversationErrorCode.INVALID_REQUEST


# ── Fail-closed construction and the frozen table (Task 3 fix round 1) ───────


@pytest.mark.parametrize(
    "injected",
    [
        {"request-cancellation": True},
        ("request-cancellation",),
        (None,),
    ],
    ids=["mapping-container", "raw-id-string", "none-entry"],
)
def test_non_declaration_injected_entries_fail_closed_at_construction(
    injected: object,
) -> None:
    """Only concrete ``ApplicationCapability`` declarations may be injected.

    A non-declaration entry (for example a raw mapping of request flags) is a
    call-site type defect and raises ``TypeError`` at construction instead of
    failing later with a raw ``AttributeError``.
    """

    with pytest.raises(TypeError):
        ConversationCapabilityResolver(injected)  # type: ignore[arg-type]


def test_a_none_requested_iterable_raises_the_python_boundary_type_error() -> None:
    """A ``None`` iterable is a Python type defect, not a boundary error.

    ``resolve`` documents the split: a bad capability ID *inside* the iterable
    fails closed with the conversational ``INVALID_REQUEST`` error, while a
    ``None`` (or otherwise non-iterable) argument raises the natural
    ``TypeError`` of the call site.
    """

    with pytest.raises(TypeError):
        _baseline_resolver().resolve(None)  # type: ignore[arg-type]


def test_the_baseline_truth_table_cannot_be_rewritten_at_runtime() -> None:
    """The frozen baseline table is frozen at runtime, not only by convention."""

    before = _baseline_resolver().resolve()

    with pytest.raises(TypeError):
        _BASELINE_STATES["document_upload"] = (
            ConversationCapabilityStatus.AVAILABLE,
            "reference_only",
            None,
        )  # type: ignore[index]

    assert _baseline_resolver().resolve() == before


# ── Inputs are copied and never mutated ──────────────────────────────────────


def test_the_resolver_copies_and_never_mutates_its_inputs() -> None:
    injected = [_available_cancellation()]
    injected_snapshot = list(injected)
    requested = ["request_cancellation"]

    resolver = ConversationCapabilityResolver(injected)

    first = _by_id(resolver.resolve(requested))["request_cancellation"]
    assert first.status is ConversationCapabilityStatus.AVAILABLE

    assert injected == injected_snapshot
    assert requested == ["request_cancellation"]

    injected.clear()
    requested.clear()

    second = _by_id(resolver.resolve())["request_cancellation"]
    assert second.status is ConversationCapabilityStatus.AVAILABLE
    assert second.effective == "canonical_cancellable_requests"


# ── Control capabilities without a canonical command (remediation MAJOR-04) ──


def test_every_control_capability_is_explicitly_unavailable() -> None:
    """No canonical application command exists: each control is unavailable."""

    states = _by_id(_baseline_resolver().resolve(tuple(CONTROL_CAPABILITY_REASONS)))

    for capability, reason in CONTROL_CAPABILITY_REASONS.items():
        entry = states[capability]
        assert entry.requested is True
        assert entry.status is ConversationCapabilityStatus.UNAVAILABLE
        assert entry.effective is None
        assert entry.reason == reason


def test_requesting_a_control_capability_creates_no_authority() -> None:
    resolver = ConversationCapabilityResolver(build_default_capabilities())

    request = resolver.resolve(("action_execution", "workflow_pause"))

    for state in request:
        if state.capability in CONTROL_CAPABILITY_REASONS:
            assert state.status is ConversationCapabilityStatus.UNAVAILABLE
            assert state.effective is None


def test_no_injected_application_capability_unlocks_a_control_state_by_itself() -> None:
    """Availability is never inferred from a ref, a route or a domain package."""

    injected = tuple(
        item
        for item in build_default_capabilities()
        if item.capability_id != "request-cancellation"
    )
    states = _by_id(ConversationCapabilityResolver(injected).resolve())

    for capability, reason in CONTROL_CAPABILITY_REASONS.items():
        assert states[capability].status is ConversationCapabilityStatus.UNAVAILABLE
        assert states[capability].effective is None
        assert states[capability].reason == reason


def test_request_cancellation_stays_separate_from_workflow_cancel() -> None:
    states = _by_id(_baseline_resolver().resolve())

    assert states["request_cancellation"].capability == "request_cancellation"
    assert states["workflow_cancel"].capability == "workflow_cancel"
    assert states["request_cancellation"].reason == "NO_CANCELLABLE_OWNER"
    assert states["workflow_cancel"].reason == "NO_CANONICAL_WORKFLOW_CONTROL"
